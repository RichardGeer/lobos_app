import os
import json
import time
import hashlib
import re
from typing import Optional, Dict, List, Any

import jwt
import requests
from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import create_engine, Column, Integer, String, Text, BigInteger, Boolean
from sqlalchemy.orm import sessionmaker, declarative_base

# ============================================================
# CONFIG
# ============================================================

DATABASE_URL = os.getenv(
    "LOBOS_DATABASE_URL",
    "postgresql+psycopg2://lobos_user:lobos_pass@127.0.0.1:5432/lobos_db",
)

OLLAMA_BASE_URL = os.getenv("LOBOS_OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/")
FAST_MODEL = os.getenv("LOBOS_OLLAMA_MODEL_FAST", "mistral:latest")
QUALITY_MODEL = os.getenv("LOBOS_OLLAMA_MODEL_QUALITY", "llama3.1:8b-instruct-q8_0")

RECIPE_MAX_CACHE_AGE_IN_DAYS = int(os.getenv("RECIPE_MAX_CACHE_AGE_IN_DAYS", "7"))

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
Base = declarative_base()

app = FastAPI()
templates = Jinja2Templates(directory="templates")

# ============================================================
# MODELS
# ============================================================

class UserProfile(Base):
    __tablename__ = "user_profiles"

    id = Column(Integer, primary_key=True)
    user_id = Column(String(128), unique=True, nullable=False)
    created_at = Column(BigInteger, nullable=False)
    updated_at = Column(BigInteger, nullable=False)

    eating_style = Column(String(128), nullable=False)
    meal_type = Column(String(64), nullable=False)
    macro_preset = Column(String(128), nullable=False)
    prep = Column(String(128), nullable=False)

    email = Column(String(256), nullable=True)
    first_name = Column(String(128), nullable=True)
    last_name = Column(String(128), nullable=True)
    roles = Column(Text, nullable=True)


class RecipeResult(Base):
    __tablename__ = "recipe_results"

    id = Column(Integer, primary_key=True)
    user_id = Column(String(128), nullable=False)
    created_at = Column(BigInteger, nullable=False)

    request_hash = Column(String(64), nullable=False)
    request_json = Column(Text, nullable=False)

    response_text = Column(Text, nullable=False)
    model = Column(String(128), nullable=True)
    prompt_hash = Column(String(64), nullable=True)

    # these exist in your DB (you showed them)
    title = Column(String(256), nullable=True)
    preview = Column(Text, nullable=True)


class PreferenceOption(Base):
    __tablename__ = "preference_options"

    id = Column(Integer, primary_key=True)
    category = Column(String(64), nullable=False)  # eating_style | meal_type | macro_preset | prep
    value = Column(String(256), nullable=False)
    sort_order = Column(Integer, nullable=False, default=0)
    is_active = Column(Boolean, nullable=False, default=True)


Base.metadata.create_all(bind=engine)

# ============================================================
# HELPERS
# ============================================================

def now_ts() -> int:
    return int(time.time())

def clean_title(t: str) -> str:
    if not t:
        return ""
    t = t.strip()
    # remove leading markdown header
    if t.startswith("#"):
        t = t.lstrip("#").strip()
    # remove surrounding bold markers
    if t.startswith("**") and t.endswith("**") and len(t) >= 4:
        t = t[2:-2].strip()
    return t

def get_user_id_from_token(token: str) -> Optional[str]:
    """Decode without verifying signature; we just need stable 'sub'."""
    try:
        payload = jwt.decode(token, options={"verify_signature": False})
        sub = payload.get("sub", None)
        return str(sub) if sub is not None else None
    except Exception:
        return None


def token_identity_from_jwt(token: str) -> Dict[str, Any]:
    try:
        payload = jwt.decode(token, options={"verify_signature": False})
        return {
            "email": payload.get("email"),
            "first_name": payload.get("first_name"),
            "last_name": payload.get("last_name"),
            "roles": payload.get("roles") or [],
        }
    except Exception:
        return {"email": None, "first_name": None, "last_name": None, "roles": []}


def roles_to_human(roles: Any) -> str:
    if not roles:
        return ""
    if isinstance(roles, list):
        return ", ".join([str(r) for r in roles])
    # if stored JSON string, try parse
    if isinstance(roles, str):
        try:
            x = json.loads(roles)
            if isinstance(x, list):
                return ", ".join([str(r) for r in x])
        except Exception:
            pass
    return str(roles)


def load_options(db) -> Dict[str, List[str]]:
    wanted = ["eating_style", "meal_type", "macro_preset", "prep"]
    opts: Dict[str, List[str]] = {k: [] for k in wanted}

    rows = (
        db.query(PreferenceOption)
        .filter(PreferenceOption.is_active.is_(True))
        .order_by(
            PreferenceOption.category.asc(),
            PreferenceOption.sort_order.asc(),
            PreferenceOption.value.asc(),
        )
        .all()
    )

    for r in rows:
        if r.category in opts:
            opts[r.category].append(r.value)

    # fallback so UI doesn't break
    if not opts["eating_style"]:
        opts["eating_style"] = ["No Preference"]
    if not opts["meal_type"]:
        opts["meal_type"] = ["Dinner"]
    if not opts["macro_preset"]:
        opts["macro_preset"] = ["40/40/20 (Protein-Enhanced Lean)"]
    if not opts["prep"]:
        opts["prep"] = ["Standard"]

    return opts


def profile_to_view(p: UserProfile) -> Dict[str, Any]:
    return {
        "user_id": p.user_id,
        "created_at": p.created_at,
        "updated_at": p.updated_at,
        "eating_style": p.eating_style,
        "meal_type": p.meal_type,
        "macro_preset": p.macro_preset,
        "prep": p.prep,
        "email": p.email,
        "first_name": p.first_name,
        "last_name": p.last_name,
        "roles": p.roles,
    }


def build_prompt(profile_view: Dict[str, Any]) -> str:
    return f"""Create a healthy recipe.

Eating Style: {profile_view.get("eating_style")}
Meal Type: {profile_view.get("meal_type")}
Macro Preset: {profile_view.get("macro_preset")}
Preparation: {profile_view.get("prep")}

Output clean markdown format.
"""


def call_ollama(model: str, prompt: str) -> str:
    url = f"{OLLAMA_BASE_URL}/api/generate"
    resp = requests.post(
        url,
        json={"model": model, "prompt": prompt, "stream": False},
        timeout=480 if model == QUALITY_MODEL else 300,
    )
    resp.raise_for_status()
    data = resp.json()
    return (data.get("response") or "").strip()


def request_payload_from_profile(profile_view: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "eating_style": profile_view.get("eating_style"),
        "meal_type": profile_view.get("meal_type"),
        "macro_preset": profile_view.get("macro_preset"),
        "prep": profile_view.get("prep"),
    }


def hash_request(payload: Dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()


def extract_title_and_preview(text: str) -> (str, str):
    t = (text or "").strip()

    # Prefer first markdown H1: "# Title"
    m = re.search(r"^\s*#\s+(.+)\s*$", t, flags=re.MULTILINE)
 
    if m:
       
        title = m.group(1).strip()
    else:
        # Fallback: "Title: something"
        m2 = re.search(r"^\s*Title:\s*(.+)\s*$", t, flags=re.MULTILINE | re.IGNORECASE)
        title = m2.group(1).strip() if m2 else ""

    if not title:
        # last fallback: first non-empty line, clipped
        for line in t.splitlines():
            line = line.strip()
            if line:
                title = line[:120]
                break

    preview = t.replace("\r", "")
    preview = re.sub(r"\s+", " ", preview).strip()
    preview = preview[:140]

    # keep title short for UI cards
    title = (title or "").strip()
    if len(title) > 72:
        title = title[:69].rstrip() + "..."

    return title, preview


def cache_cutoff_ts() -> int:
    return now_ts() - (RECIPE_MAX_CACHE_AGE_IN_DAYS * 86400)


def get_cached_recipe(db, user_id: str, request_hash: str) -> Optional[RecipeResult]:
    cutoff = cache_cutoff_ts()
    return (
        db.query(RecipeResult)
        .filter(RecipeResult.user_id == user_id)
        .filter(RecipeResult.request_hash == request_hash)
        .filter(RecipeResult.created_at >= cutoff)
        .order_by(RecipeResult.created_at.desc())
        .first()
    )


def list_recipes_for_request(db, user_id: str, request_hash: str, limit: int = 50) -> List[RecipeResult]:
    return (
        db.query(RecipeResult)
        .filter(RecipeResult.user_id == user_id)
        .filter(RecipeResult.request_hash == request_hash)
        .order_by(RecipeResult.created_at.desc())
        .limit(limit)
        .all()
    )


def get_recipe_by_id(db, user_id: str, rid: int) -> Optional[RecipeResult]:
    return (
        db.query(RecipeResult)
        .filter(RecipeResult.user_id == user_id)
        .filter(RecipeResult.id == rid)
        .first()
    )


def generate_and_save_recipe(db, user_id: str, profile_view: Dict[str, Any], want_quality: bool) -> RecipeResult:
    model = QUALITY_MODEL if want_quality else FAST_MODEL
    prompt = build_prompt(profile_view)

    req_payload = request_payload_from_profile(profile_view)
    req_hash = hash_request(req_payload)
    prompt_hash = hashlib.sha256(prompt.encode("utf-8")).hexdigest()

    response_text = call_ollama(model, prompt)
    title, preview = extract_title_and_preview(response_text)

    r = RecipeResult(
        user_id=user_id,
        created_at=now_ts(),
        request_hash=req_hash,
        request_json=json.dumps(req_payload),
        response_text=response_text,
        model=model,
        prompt_hash=prompt_hash,
        title=title,
        preview=preview,
    )

    db.add(r)
    db.commit()
    return r

# ============================================================
# ROUTES
# ============================================================

@app.get("/landing", response_class=HTMLResponse)
def landing(request: Request, token: str):
    user_id = get_user_id_from_token(token)
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token (missing sub)")

    ident = token_identity_from_jwt(token)

    with SessionLocal() as db:
        opts = load_options(db)

        profile = db.query(UserProfile).filter(UserProfile.user_id == user_id).first()
        if not profile:
            profile = UserProfile(
                user_id=user_id,
                created_at=now_ts(),
                updated_at=now_ts(),
                eating_style=opts["eating_style"][0],
                meal_type=opts["meal_type"][0],
                macro_preset=opts["macro_preset"][0],
                prep=opts["prep"][0],
            )
            db.add(profile)
            db.commit()

        # sync identity for display
        profile.email = ident.get("email")
        profile.first_name = ident.get("first_name")
        profile.last_name = ident.get("last_name")
        if ident.get("roles") is not None:
            profile.roles = json.dumps(ident.get("roles"))
        profile.updated_at = now_ts()
        db.commit()

        profile_view = profile_to_view(profile)
        roles_human = roles_to_human(profile_view.get("roles"))

    return templates.TemplateResponse(
        "landing.html",
        {
            "request": request,
            "token": token,
            "profile": profile_view,
            "roles_human": roles_human,
            "eating_style_options": opts["eating_style"],
            "meal_type_options": opts["meal_type"],
            "macro_preset_options": opts["macro_preset"],
            "prep_options": opts["prep"],
        },
    )


@app.post("/prefs/save")
def prefs_save(
    token: str = Form(...),
    eating_style: str = Form(...),
    meal_type: str = Form(...),
    macro_preset: str = Form(...),
    prep: str = Form(...),
):
    user_id = get_user_id_from_token(token)
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token")

    with SessionLocal() as db:
        profile = db.query(UserProfile).filter(UserProfile.user_id == user_id).first()
        if not profile:
            # create if missing
            profile = UserProfile(
                user_id=user_id,
                created_at=now_ts(),
                updated_at=now_ts(),
                eating_style=eating_style,
                meal_type=meal_type,
                macro_preset=macro_preset,
                prep=prep,
            )
            db.add(profile)
            db.commit()
        else:
            profile.eating_style = eating_style
            profile.meal_type = meal_type
            profile.macro_preset = macro_preset
            profile.prep = prep
            profile.updated_at = now_ts()
            db.commit()

    return RedirectResponse(url=f"/landing?token={token}", status_code=302)


@app.get("/my-recipe", response_class=HTMLResponse)
def my_recipe(request: Request, token: str, qm: str = "0", rid: Optional[int] = None):
    user_id = get_user_id_from_token(token)
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token")

    quality_mode = (qm == "1")

    with SessionLocal() as db:
        profile = db.query(UserProfile).filter(UserProfile.user_id == user_id).first()
        if not profile:
            return RedirectResponse(url=f"/landing?token={token}", status_code=302)

        profile_view = profile_to_view(profile)
        req_hash = hash_request(request_payload_from_profile(profile_view))

        history = list_recipes_for_request(db, user_id, req_hash, limit=50)

        selected: Optional[RecipeResult] = None
        if rid is not None:
            selected = get_recipe_by_id(db, user_id, int(rid))
        if selected is None:
            selected = history[0] if history else None

        selected_title = (selected.title if selected else "") or ""
        selected_text = (selected.response_text if selected else "") or ""
        selected_model = (selected.model if selected else "") or ""

        history_view = []
        for r in history:
            history_view.append(
                {
                    "id": r.id,
                    "created_at": r.created_at,
                    "model": r.model or "",
                    "title": (r.title or "").strip(),
                    "preview": (r.preview or "").strip(),
                }
            )

    return templates.TemplateResponse(
        "my_recipe.html",
        {
            "request": request,
            "token": token,
            "quality_mode": quality_mode,
            "selected_recipe_id": selected.id if selected else None,
            "selected_title": selected_title,
            "recipe_text": selected_text,
            "recipe_model_used": selected_model,
            "recipe_error": "",
            "history": history_view,
            "cache_age_days": RECIPE_MAX_CACHE_AGE_IN_DAYS,
        },
    )


@app.post("/recipe/generate")
def recipe_generate(
    token: str = Form(...),
    quality_mode: Optional[str] = Form(None),
    force_new: Optional[str] = Form(None),
):
    user_id = get_user_id_from_token(token)
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token")

    want_quality = str(quality_mode or "").lower() in ("1", "true", "on", "yes")
    force = str(force_new or "").lower() in ("1", "true", "on", "yes")

    with SessionLocal() as db:
        profile = db.query(UserProfile).filter(UserProfile.user_id == user_id).first()
        if not profile:
            return RedirectResponse(url=f"/landing?token={token}", status_code=302)

        profile_view = profile_to_view(profile)
        req_hash = hash_request(request_payload_from_profile(profile_view))

        if not force:
            cached = get_cached_recipe(db, user_id, req_hash)
            if cached:
                qm = "1" if want_quality else "0"
                return RedirectResponse(url=f"/my-recipe?token={token}&qm={qm}&rid={cached.id}", status_code=302)

        r = generate_and_save_recipe(db, user_id, profile_view, want_quality)

    qm = "1" if want_quality else "0"
    return RedirectResponse(url=f"/my-recipe?token={token}&qm={qm}&rid={r.id}", status_code=302)


@app.get("/ai-prompt", response_class=HTMLResponse)
def ai_prompt(token: str):
    user_id = get_user_id_from_token(token)
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token")

    with SessionLocal() as db:
        profile = db.query(UserProfile).filter(UserProfile.user_id == user_id).first()
        if not profile:
            raise HTTPException(status_code=404, detail="Profile not found")

        prompt = build_prompt(profile_to_view(profile))

    return HTMLResponse(f"<pre>{prompt}</pre>")


@app.get("/me", response_class=HTMLResponse)
def me(token: str):
    user_id = get_user_id_from_token(token)
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token")

    ident = token_identity_from_jwt(token)
    return HTMLResponse(
        "<pre>"
        + json.dumps({"user_id": user_id, "identity": ident}, indent=2)
        + "</pre>"
    )