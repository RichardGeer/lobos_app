import os
import json
import time
import hashlib
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

TIMEOUT_FAST = int(os.getenv("LOBOS_OLLAMA_TIMEOUT_FAST", "240"))
TIMEOUT_QUALITY = int(os.getenv("LOBOS_OLLAMA_TIMEOUT_QUALITY", "480"))

JWT_SECRET = os.getenv("LOBOS_JWT_SECRET", "")
JWT_ISSUER = os.getenv("LOBOS_JWT_ISSUER", "")

engine = create_engine(DATABASE_URL, pool_pre_ping=True)

# IMPORTANT: avoid DetachedInstanceError when session closes
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, expire_on_commit=False)

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
    roles = Column(Text, nullable=True)  # store JSON string (list) or plain string


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


class PreferenceOption(Base):
    __tablename__ = "preference_options"

    id = Column(Integer, primary_key=True)
    category = Column(String(64), nullable=False)   # eating_style | meal_type | macro_preset | prep
    value = Column(String(256), nullable=False)
    sort_order = Column(Integer, nullable=False, default=0)
    is_active = Column(Boolean, nullable=False, default=True)


Base.metadata.create_all(bind=engine)

# ============================================================
# HELPERS
# ============================================================

def now_ts() -> int:
    return int(time.time())


def decode_token(token: str) -> Dict[str, Any]:
    """
    Prefer verified decode if JWT_SECRET is set.
    Falls back to unverified decode if verification fails (keeps dev working).
    """
    if not token:
        return {}

    if JWT_SECRET:
        try:
            kwargs = {"algorithms": ["HS256"]}
            if JWT_ISSUER:
                kwargs["issuer"] = JWT_ISSUER
            return jwt.decode(token, JWT_SECRET, **kwargs)
        except Exception:
            # dev-friendly fallback
            pass

    try:
        return jwt.decode(token, options={"verify_signature": False})
    except Exception:
        return {}


def get_user_id_from_token(token: str) -> Optional[str]:
    payload = decode_token(token)
    sub = payload.get("sub")
    if sub is None:
        return None
    return str(sub)


def roles_to_human(roles_val: Optional[str]) -> str:
    if not roles_val:
        return ""
    try:
        parsed = json.loads(roles_val)
        if isinstance(parsed, list):
            return ", ".join(str(x) for x in parsed)
    except Exception:
        pass
    return str(roles_val)


def load_options(db) -> Dict[str, List[str]]:
    """
    Returns:
      {
        "eating_style": [...],
        "meal_type": [...],
        "macro_preset": [...],
        "prep": [...]
      }
    """
    rows = (
        db.query(PreferenceOption)
        .filter(PreferenceOption.is_active == True)  # noqa: E712
        .order_by(PreferenceOption.category.asc(), PreferenceOption.sort_order.asc(), PreferenceOption.value.asc())
        .all()
    )

    out: Dict[str, List[str]] = {"eating_style": [], "meal_type": [], "macro_preset": [], "prep": []}
    for r in rows:
        if r.category in out:
            out[r.category].append(r.value)

    return out


def build_prompt(profile: UserProfile) -> str:
    return f"""Create a healthy recipe.

Eating Style: {profile.eating_style}
Meal Type: {profile.meal_type}
Macro Preset: {profile.macro_preset}
Preparation: {profile.prep}

Output clean markdown format.
"""


def call_ollama(model: str, prompt: str, timeout_s: int) -> str:
    url = f"{OLLAMA_BASE_URL}/api/generate"
    resp = requests.post(
        url,
        json={"model": model, "prompt": prompt, "stream": False},
        timeout=timeout_s,
    )
    resp.raise_for_status()
    data = resp.json()
    return (data.get("response") or "").strip()


def generate_recipe(db, profile: UserProfile, want_quality: bool) -> RecipeResult:
    model = QUALITY_MODEL if want_quality else FAST_MODEL
    timeout_s = TIMEOUT_QUALITY if want_quality else TIMEOUT_FAST

    prompt = build_prompt(profile)

    request_payload = {
        "eating_style": profile.eating_style,
        "meal_type": profile.meal_type,
        "macro_preset": profile.macro_preset,
        "prep": profile.prep,
    }

    request_hash = hashlib.sha256(json.dumps(request_payload, sort_keys=True).encode("utf-8")).hexdigest()
    prompt_hash = hashlib.sha256(prompt.encode("utf-8")).hexdigest()

    response_text = call_ollama(model, prompt, timeout_s)

    result = RecipeResult(
        user_id=profile.user_id,
        created_at=now_ts(),
        request_hash=request_hash,
        request_json=json.dumps(request_payload),
        response_text=response_text,
        model=model,
        prompt_hash=prompt_hash,
    )

    db.add(result)
    db.commit()
    return result


def get_latest_recipe(db, user_id: str) -> Optional[RecipeResult]:
    return (
        db.query(RecipeResult)
        .filter(RecipeResult.user_id == user_id)
        .order_by(RecipeResult.created_at.desc())
        .first()
    )

# ============================================================
# ROUTES
# ============================================================

@app.get("/landing", response_class=HTMLResponse)
def landing(request: Request, token: str):
    user_id = get_user_id_from_token(token)
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token (missing sub)")

    payload = decode_token(token)

    with SessionLocal() as db:
        opts = load_options(db)

        profile = db.query(UserProfile).filter(UserProfile.user_id == user_id).first()
        if not profile:
            default_eating = opts["eating_style"][0] if opts["eating_style"] else "No Preference"
            default_meal = opts["meal_type"][0] if opts["meal_type"] else "Dinner"
            default_macro = opts["macro_preset"][0] if opts["macro_preset"] else "40/40/20 (Protein-Enhanced Lean)"
            default_prep = opts["prep"][0] if opts["prep"] else "Standard"

            profile = UserProfile(
                user_id=user_id,
                created_at=now_ts(),
                updated_at=now_ts(),
                eating_style=default_eating,
                meal_type=default_meal,
                macro_preset=default_macro,
                prep=default_prep,
            )
            db.add(profile)
            db.commit()
            db.refresh(profile)

        # sync identity fields from token
        profile.email = payload.get("email")
        profile.first_name = payload.get("first_name")
        profile.last_name = payload.get("last_name")
        if payload.get("roles") is not None:
            try:
                profile.roles = json.dumps(payload.get("roles"))
            except Exception:
                profile.roles = str(payload.get("roles"))
        profile.updated_at = now_ts()
        db.commit()

        roles_human = roles_to_human(profile.roles)

        return templates.TemplateResponse(
            "landing.html",
            {
                "request": request,
                "token": token,
                "profile": profile,
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
        raise HTTPException(status_code=401, detail="Invalid token (missing sub)")

    with SessionLocal() as db:
        profile = db.query(UserProfile).filter(UserProfile.user_id == user_id).first()
        if not profile:
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
        else:
            profile.eating_style = eating_style
            profile.meal_type = meal_type
            profile.macro_preset = macro_preset
            profile.prep = prep
            profile.updated_at = now_ts()

        db.commit()

    return RedirectResponse(url=f"/landing?token={token}", status_code=302)


@app.get("/my-recipe", response_class=HTMLResponse)
def my_recipe(request: Request, token: str):
    user_id = get_user_id_from_token(token)
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token (missing sub)")

    qm = request.query_params.get("qm", "0")
    quality_mode = qm == "1"

    with SessionLocal() as db:
        profile = db.query(UserProfile).filter(UserProfile.user_id == user_id).first()
        latest = get_latest_recipe(db, user_id)

    return templates.TemplateResponse(
        "my_recipe.html",
        {
            "request": request,
            "token": token,
            "profile": profile,
            "quality_mode": quality_mode,
            "recipe_text": latest.response_text if latest else "",
            "recipe_model_used": latest.model if latest else "",
            "recipe_error": "",
        },
    )


@app.post("/recipe/generate")
def recipe_generate(token: str = Form(...), quality_mode: Optional[str] = Form(None)):
    user_id = get_user_id_from_token(token)
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token (missing sub)")

    want_quality = str(quality_mode or "").lower() in ("1", "true", "on", "yes")

    with SessionLocal() as db:
        profile = db.query(UserProfile).filter(UserProfile.user_id == user_id).first()
        if not profile:
            raise HTTPException(status_code=400, detail="Profile not found. Visit /landing first.")
        generate_recipe(db, profile, want_quality)

    qm = "1" if want_quality else "0"
    return RedirectResponse(url=f"/my-recipe?token={token}&qm={qm}", status_code=302)


@app.get("/me", response_class=HTMLResponse)
def me(request: Request, token: str):
    payload = decode_token(token)
    user_id = get_user_id_from_token(token)
    return HTMLResponse(
        "<pre>" + json.dumps({"user_id": user_id, "payload": payload}, indent=2) + "</pre>"
    )


@app.get("/ai-prompt", response_class=HTMLResponse)
def ai_prompt(request: Request, token: str):
    user_id = get_user_id_from_token(token)
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token (missing sub)")

    with SessionLocal() as db:
        profile = db.query(UserProfile).filter(UserProfile.user_id == user_id).first()
        if not profile:
            raise HTTPException(status_code=400, detail="Profile not found. Visit /landing first.")
        prompt = build_prompt(profile)

    return HTMLResponse(f"<pre>{prompt}</pre>")