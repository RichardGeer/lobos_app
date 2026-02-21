import os
import json
import time
import hashlib
from typing import Optional, Dict, List, Any, Tuple

import jwt
import requests
from fastapi import FastAPI, Request, Form
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
RECIPE_MAX_CACHE_AGE_DAYS = int(os.getenv("LOBOS_RECIPE_MAX_CACHE_AGE_DAYS", "7"))
JWT_SECRET = os.getenv("LOBOS_JWT_SECRET", "")
JWT_ISSUER = os.getenv("LOBOS_JWT_ISSUER", "")

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,  # prevents DetachedInstanceError after session closes
)

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
    roles = Column(Text, nullable=True)  # json string or plain string


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
    Verify when secret exists; otherwise decode without signature (dev-friendly).
    """
    if not token:
        return {}

    if JWT_SECRET:
        try:
            kwargs: Dict[str, Any] = {"algorithms": ["HS256"]}
            if JWT_ISSUER:
                kwargs["issuer"] = JWT_ISSUER
            return jwt.decode(token, JWT_SECRET, **kwargs)
        except Exception:
            # fall back to unverified decode so you can still test
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
    # roles_val may already be "administrator" or may be JSON string ["administrator"]
    try:
        parsed = json.loads(roles_val)
        if isinstance(parsed, list):
            return ", ".join(str(x) for x in parsed)
    except Exception:
        pass
    return str(roles_val)


def load_options(db) -> Dict[str, List[str]]:
    rows = (
        db.query(PreferenceOption)
        .filter(PreferenceOption.is_active == True)  # noqa: E712
        .order_by(
            PreferenceOption.category.asc(),
            PreferenceOption.sort_order.asc(),
            PreferenceOption.value.asc(),
        )
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


def prefs_payload(profile: UserProfile) -> Dict[str, str]:
    return {
        "eating_style": profile.eating_style,
        "meal_type": profile.meal_type,
        "macro_preset": profile.macro_preset,
        "prep": profile.prep,
    }


def hash_payload(payload: Dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()


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


def get_latest_recipe(db, user_id: str) -> Optional[RecipeResult]:
    return (
        db.query(RecipeResult)
        .filter(RecipeResult.user_id == user_id)
        .order_by(RecipeResult.created_at.desc())
        .first()
    )

def get_latest_cached_for_request(
    db,
    user_id: str,
    request_hash: str,
    model: str,
    max_age_days: int,
) -> Optional[RecipeResult]:
    min_created_at = now_ts() - (max_age_days * 86400)

    return (
        db.query(RecipeResult)
        .filter(
            RecipeResult.user_id == user_id,
            RecipeResult.request_hash == request_hash,
            RecipeResult.model == model,
            RecipeResult.created_at >= min_created_at,
        )
        .order_by(RecipeResult.created_at.desc())
        .first()
    )

def get_recent_history_for_request(
    db,
    user_id: str,
    request_hash: str,
    limit: int = 10,
) -> List[RecipeResult]:
    return (
        db.query(RecipeResult)
        .filter(
            RecipeResult.user_id == user_id,
            RecipeResult.request_hash == request_hash,
        )
        .order_by(RecipeResult.created_at.desc())
        .limit(limit)
        .all()
    )


def ensure_profile(db, user_id: str, token_payload: Dict[str, Any]) -> Tuple[UserProfile, Dict[str, List[str]]]:
    opts = load_options(db)

    # safe defaults even if table is empty
    default_eating = opts["eating_style"][0] if opts["eating_style"] else "No Preference"
    default_meal = opts["meal_type"][0] if opts["meal_type"] else "Dinner"
    default_macro = opts["macro_preset"][0] if opts["macro_preset"] else "40/40/20 (Protein-Enhanced Lean)"
    default_prep = opts["prep"][0] if opts["prep"] else "Standard"

    profile = db.query(UserProfile).filter(UserProfile.user_id == user_id).first()
    if not profile:
        profile = UserProfile(
            user_id=user_id,
            created_at=now_ts(),
            updated_at=now_ts(),
            eating_style=default_eating,
            meal_type=default_meal,
            macro_preset=default_macro,
            prep=default_prep,
            email=token_payload.get("email"),
            first_name=token_payload.get("first_name"),
            last_name=token_payload.get("last_name"),
            roles=json.dumps(token_payload.get("roles") or []),
        )
        db.add(profile)
        db.commit()
        return profile, opts

    # keep identity fields synced (nice UX)
    profile.email = token_payload.get("email")
    profile.first_name = token_payload.get("first_name")
    profile.last_name = token_payload.get("last_name")
    if token_payload.get("roles") is not None:
        try:
            profile.roles = json.dumps(token_payload.get("roles"))
        except Exception:
            profile.roles = str(token_payload.get("roles"))

    profile.updated_at = now_ts()
    db.commit()

    return profile, opts


def generate_or_get_cached_recipe(db, profile: UserProfile, want_quality: bool, force_new: bool) -> RecipeResult:
    model = QUALITY_MODEL if want_quality else FAST_MODEL
    timeout_s = TIMEOUT_QUALITY if want_quality else TIMEOUT_FAST

    payload = prefs_payload(profile)
    request_hash = hash_payload(payload)

    # cache hit (same prefs + same model + within age window)
    if not force_new:
        cached = get_latest_cached_for_request(
            db,
            profile.user_id,
            request_hash,
            model,
            RECIPE_MAX_CACHE_AGE_DAYS,
        )
        if cached:
            return cached

    prompt = build_prompt(profile)
    prompt_hash = hashlib.sha256(prompt.encode("utf-8")).hexdigest()

    response_text = call_ollama(model, prompt, timeout_s)

    result = RecipeResult(
        user_id=profile.user_id,
        created_at=now_ts(),
        request_hash=request_hash,
        request_json=json.dumps(payload),
        response_text=response_text,
        model=model,
        prompt_hash=prompt_hash,
    )
    db.add(result)
    db.commit()
    return result

# ============================================================
# ROUTES
# ============================================================

@app.get("/landing", response_class=HTMLResponse)
def landing(request: Request, token: str):
    user_id = get_user_id_from_token(token)
    if not user_id:
        return HTMLResponse("Invalid token (missing sub).", status_code=400)

    payload = decode_token(token)

    with SessionLocal() as db:
        profile, opts = ensure_profile(db, user_id, payload)
        roles_human = roles_to_human(profile.roles)

    return templates.TemplateResponse(
        "landing.html",
        {
            "request": request,
            "token": token,
            "profile": profile,
            "roles_human": roles_human,

            # must match your landing.html loops:
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
        return HTMLResponse("Invalid token (missing sub).", status_code=400)

    payload = decode_token(token)

    with SessionLocal() as db:
        profile, _opts = ensure_profile(db, user_id, payload)

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
        return HTMLResponse("Invalid token (missing sub).", status_code=400)

    qm = request.query_params.get("qm", "0")
    quality_mode = qm == "1"

    rid_raw = request.query_params.get("rid")
    selected_rid: Optional[int] = None
    if rid_raw:
        try:
            selected_rid = int(rid_raw)
        except Exception:
            selected_rid = None

    with SessionLocal() as db:
        profile = db.query(UserProfile).filter(UserProfile.user_id == user_id).first()
        if not profile:
            profile, _opts = ensure_profile(db, user_id, decode_token(token))

        # Compute current prefs fingerprint for "same prefs" history
        payload = prefs_payload(profile)
        request_hash = hash_payload(payload)

        # History (same prefs)
        history_same_prefs = get_recent_history_for_request(db, user_id, request_hash, limit=15)

        # Which recipe to display?
        shown: Optional[RecipeResult] = None
        if selected_rid is not None:
            shown = (
                db.query(RecipeResult)
                .filter(RecipeResult.id == selected_rid, RecipeResult.user_id == user_id)
                .first()
            )

        if not shown:
            shown = get_latest_recipe(db, user_id)

        # Build sidebar items
        def fmt_ts(ts: int) -> str:
            return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ts))

        history_items = []
        for r in history_same_prefs:
            history_items.append(
                {
                    "id": r.id,
                    "created_at": r.created_at,
                    "created_at_human": fmt_ts(r.created_at),
                    "model": r.model or "",
                    "is_selected": (shown is not None and r.id == shown.id),
                }
            )

    return templates.TemplateResponse(
        "my_recipe.html",
        {
            "request": request,
            "token": token,
            "profile": profile,
            "quality_mode": quality_mode,
            "recipe_text": shown.response_text if shown else "",
            "recipe_model_used": shown.model if shown else "",
            "recipe_error": "",
            "recipe_history": history_items,
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
        return HTMLResponse("Invalid token (missing sub).", status_code=400)

    want_quality = str(quality_mode or "").lower() in ("1", "true", "on", "yes")
    force = str(force_new or "").lower() in ("1", "true", "on", "yes")

    with SessionLocal() as db:
        profile = db.query(UserProfile).filter(UserProfile.user_id == user_id).first()
        if not profile:
            profile, _opts = ensure_profile(db, user_id, decode_token(token))

        generate_or_get_cached_recipe(db, profile, want_quality=want_quality, force_new=force)

    qm = "1" if want_quality else "0"
    return RedirectResponse(url=f"/my-recipe?token={token}&qm={qm}", status_code=302)
@app.get("/me", response_class=HTMLResponse)
def me(token: str):
    payload = decode_token(token)
    user_id = get_user_id_from_token(token)
    return HTMLResponse(f"<pre>{json.dumps({'user_id': user_id, 'payload': payload}, indent=2)}</pre>")


@app.get("/ai-prompt", response_class=HTMLResponse)
def ai_prompt(token: str):
    user_id = get_user_id_from_token(token)
    if not user_id:
        return HTMLResponse("Invalid token (missing sub).", status_code=400)

    with SessionLocal() as db:
        profile = db.query(UserProfile).filter(UserProfile.user_id == user_id).first()
        if not profile:
            profile, _opts = ensure_profile(db, user_id, decode_token(token))

        prompt = build_prompt(profile)

    return HTMLResponse(f"<pre>{prompt}</pre>")