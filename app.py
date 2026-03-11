import os
import json
import time
import hashlib
import re

from typing import Optional, Dict, List, Any, Tuple
from datetime import datetime, timezone

import jwt
import requests
from fastapi import FastAPI, Request, Form, HTTPException, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import (
    create_engine,
    Column,
    Integer,
    String,
    Text,
    BigInteger,
    Boolean,
    ForeignKey,
    UniqueConstraint,
    DateTime,
)
from sqlalchemy.orm import sessionmaker, declarative_base


import logging

# ============================================================
# LOGGING
# ============================================================

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("lobos")

# ============================================================
# CONFIG
# ============================================================

DATABASE_URL = os.getenv(
    "LOBOS_DATABASE_URL",
    "postgresql+psycopg2://lobos_user:lobos_pass@127.0.0.1:5432/lobos_db",
)

LOBOS_JWT_SECRET = os.getenv("LOBOS_JWT_SECRET", "").strip()
LOBOS_JWT_ISSUER = os.getenv("LOBOS_JWT_ISSUER", "wp-sim").strip()

OLLAMA_BASE_URL = os.getenv("LOBOS_OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/")
FAST_MODEL = os.getenv("LOBOS_OLLAMA_MODEL_FAST", "mistral:latest")
QUALITY_MODEL = os.getenv("LOBOS_OLLAMA_MODEL_QUALITY", "llama3.1:8b-instruct-q8_0")

RECIPE_MAX_CACHE_AGE_DAYS = int(
    os.getenv("LOBOS_RECIPE_MAX_CACHE_AGE_DAYS", os.getenv("RECIPE_MAX_CACHE_AGE_IN_DAYS", "7"))
)

# Membership gate
LOBOS_REQUIRED_MEMBERSHIP_ID = int(os.getenv("LOBOS_REQUIRED_MEMBERSHIP_ID", "27"))
LOBOS_REQUIRED_MEMBERSHIP_TITLE = os.getenv(
    "LOBOS_REQUIRED_MEMBERSHIP_TITLE",
    "GLP-1 Action Plan Hub"
).strip()
LOBOS_REQUIRE_MEMBERSHIP = os.getenv("LOBOS_REQUIRE_MEMBERSHIP", "1").strip().lower() in (
    "1", "true", "yes", "on"
)

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
Base = declarative_base()

app = FastAPI()
templates = Jinja2Templates(directory="templates")

# ============================================================
# MODELS
# ============================================================

class LobosUser(Base):
    __tablename__ = "lobos_users"

    id = Column(BigInteger, primary_key=True)
    email = Column(Text, nullable=True)
    first_name = Column(Text, nullable=True)
    last_name = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False)
    updated_at = Column(DateTime(timezone=True), nullable=False)


class ExternalIdentity(Base):
    __tablename__ = "external_identities"

    id = Column(BigInteger, primary_key=True)
    lobos_user_id = Column(BigInteger, ForeignKey("lobos_users.id"), nullable=False)

    provider = Column(Text, nullable=False)
    issuer = Column(Text, nullable=False)
    external_user_id = Column(Text, nullable=False)

    created_at = Column(DateTime(timezone=True), nullable=False)
    last_login_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        UniqueConstraint("provider", "issuer", "external_user_id", name="uq_external_identity"),
    )


class UserPreference(Base):
    __tablename__ = "user_preferences"

    lobos_user_id = Column(BigInteger, ForeignKey("lobos_users.id"), primary_key=True)

    current_weight = Column(Text, nullable=True)
    goal_weight = Column(Text, nullable=True)
    height = Column(Text, nullable=True)
    age = Column(Integer, nullable=True)

    eating_style = Column(String(128), nullable=True)
    meal_type = Column(String(64), nullable=True)
    macro_preset = Column(String(128), nullable=True)
    prep = Column(String(128), nullable=True)

    glp1_status = Column(Text, nullable=True)
    glp1_dosage = Column(Text, nullable=True)

    onboarding_completed = Column(Boolean, nullable=False, default=False)
    onboarding_completed_at = Column(DateTime(timezone=True), nullable=True)
    updated_at = Column(DateTime(timezone=True), nullable=False)


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
    membership = Column(Text, nullable=True)


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

    title = Column(String(256), nullable=True)
    preview = Column(Text, nullable=True)


class PreferenceOption(Base):
    __tablename__ = "preference_options"

    id = Column(Integer, primary_key=True)
    category = Column(String(64), nullable=False)
    value = Column(String(256), nullable=False)
    sort_order = Column(Integer, nullable=False, default=0)
    is_active = Column(Boolean, nullable=False, default=True)


Base.metadata.create_all(bind=engine)

# ============================================================
# HELPERS
# ============================================================

def now_ts() -> int:
    return int(time.time())

def now_utc() -> datetime:
    return datetime.now(timezone.utc)

def clean_title(t: str) -> str:
    if not t:
        return ""
    t = t.strip()

    if t.startswith("#"):
        t = t.lstrip("#").strip()

    if t.startswith("**") and t.endswith("**") and len(t) >= 4:
        t = t[2:-2].strip()

    t = re.sub(r"\s+", " ", t).strip()
    return t


def normalize_text(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text if text else None


def get_nested(obj: Any, *keys: str) -> Any:
    current = obj
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def verify_and_get_payload(token: str) -> Dict[str, Any]:
    if not LOBOS_JWT_SECRET:
        raise HTTPException(status_code=500, detail="LOBOS_JWT_SECRET is not configured")

    try:
        payload = jwt.decode(
            token,
            LOBOS_JWT_SECRET,
            algorithms=["HS256"],
            issuer=LOBOS_JWT_ISSUER,
            options={"require": ["iss", "sub", "iat", "nbf", "exp"]},
        )
    except jwt.ExpiredSignatureError as exc:
        raise HTTPException(status_code=401, detail="Token expired") from exc
    except jwt.ImmatureSignatureError as exc:
        raise HTTPException(status_code=401, detail="Token not yet valid") from exc
    except jwt.InvalidIssuerError as exc:
        raise HTTPException(status_code=401, detail="Invalid issuer") from exc
    except jwt.InvalidTokenError as exc:
        raise HTTPException(status_code=401, detail="Invalid token") from exc

    sub = normalize_text(payload.get("sub"))
    if not sub:
        raise HTTPException(status_code=401, detail="Invalid token (missing sub)")

    return payload


def get_raw_payload_from_token(token: str) -> Dict[str, Any]:
    try:
        return jwt.decode(token, options={"verify_signature": False})
    except Exception:
        return {}


def get_user_id_from_token(token: str) -> Optional[str]:
    try:
        payload = get_raw_payload_from_token(token)
        sub = payload.get("sub", None)
        return str(sub) if sub is not None else None
    except Exception:
        return None


def token_identity_from_jwt(token: str) -> Dict[str, Any]:
    """
    NOTE: decode-without-verify only for display/debug after /login has already verified.
    """
    try:
        payload = get_raw_payload_from_token(token)
        identity = payload.get("identity")
        if not isinstance(identity, dict):
            identity = {}

        return {
            "email": identity.get("email", payload.get("email")),
            "first_name": identity.get("first_name", payload.get("first_name")),
            "last_name": identity.get("last_name", payload.get("last_name")),
            "roles": identity.get("roles", payload.get("roles")) or [],
            "membership": identity.get("membership", payload.get("membership")),
        }
    except Exception:
        return {
            "email": None,
            "first_name": None,
            "last_name": None,
            "roles": [],
            "membership": None,
        }


def roles_to_human(roles: Any) -> str:
    if not roles:
        return ""
    if isinstance(roles, list):
        return ", ".join([str(r) for r in roles])
    if isinstance(roles, str):
        try:
            x = json.loads(roles)
            if isinstance(x, list):
                return ", ".join([str(r) for r in x])
        except Exception:
            pass
    return str(roles)


def membership_to_dict(membership: Any) -> Dict[str, Any]:
    if membership is None:
        return {}

    if isinstance(membership, dict):
        return membership

    if isinstance(membership, str):
        try:
            parsed = json.loads(membership)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            pass

    return {}


def has_required_membership(membership: Any) -> bool:
    membership_obj = membership_to_dict(membership)
    memberpress = membership_obj.get("memberpress", {})

    active = memberpress.get("active")
    if isinstance(active, bool):
        if active:
            return True

    memberships = memberpress.get("memberships", [])
    if not isinstance(memberships, list):
        memberships = []

    for item in memberships:
        if not isinstance(item, dict):
            continue

        item_id = item.get("id")
        item_title = str(item.get("title", "")).strip()
        item_status = str(item.get("status", "")).strip().lower()

        id_match = (
            LOBOS_REQUIRED_MEMBERSHIP_ID > 0 and
            item_id == LOBOS_REQUIRED_MEMBERSHIP_ID
        )

        title_match = (
            bool(LOBOS_REQUIRED_MEMBERSHIP_TITLE) and
            item_title == LOBOS_REQUIRED_MEMBERSHIP_TITLE
        )

        if (id_match or title_match) and item_status in ("complete", "active"):
            return True

    return False


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
    membership_obj = None
    if getattr(p, "membership", None):
        try:
            membership_obj = json.loads(p.membership)
        except Exception:
            membership_obj = p.membership

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
        "membership": membership_obj,
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


def extract_title_and_preview(text: str) -> Tuple[str, str]:
    t = (text or "").strip()

    m = re.search(r"^\s*#\s+(.+)\s*$", t, flags=re.MULTILINE)
    if m:
        raw_title = m.group(1).strip()
    else:
        m2 = re.search(r"^\s*Title:\s*(.+)\s*$", t, flags=re.MULTILINE | re.IGNORECASE)
        raw_title = m2.group(1).strip() if m2 else ""

    if not raw_title:
        for line in t.splitlines():
            line = line.strip()
            if line:
                raw_title = line[:120]
                break

    title = clean_title(raw_title)

    if len(title) > 72:
        title = title[:69].rstrip() + "..."

    preview = t.replace("\r", "")
    preview = re.sub(r"\s+", " ", preview).strip()
    preview = preview[:140]

    return title, preview


def cache_cutoff_ts() -> int:
    return now_ts() - (RECIPE_MAX_CACHE_AGE_DAYS * 86400)


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


def is_admin_token(token: str) -> bool:
    ident = token_identity_from_jwt(token)
    roles = ident.get("roles") or []
    if isinstance(roles, str):
        try:
            roles = json.loads(roles)
        except Exception:
            roles = [roles]

    roles_norm = {str(r).strip().lower() for r in (roles or [])}
    return ("administrator" in roles_norm) or ("admin" in roles_norm)


def seed_default_options_if_empty(db) -> None:
    if db.query(PreferenceOption).count() > 0:
        return

    defaults = [
        ("eating_style", "High Protein", 10),
        ("eating_style", "Low Carb", 20),
        ("eating_style", "No Preference", 999),

        ("meal_type", "Breakfast", 10),
        ("meal_type", "Lunch", 20),
        ("meal_type", "Dinner", 30),
        ("meal_type", "Snack", 40),
        ("meal_type", "Dessert", 50),

        ("macro_preset", "40/40/20 (Protein-Enhanced Lean)", 10),

        ("prep", "5-Ingredient", 10),
        ("prep", "Standard", 20),
    ]

    for cat, val, order in defaults:
        db.add(PreferenceOption(category=cat, value=val, sort_order=order, is_active=True))
    db.commit()


def find_external_identity(db, provider: str, issuer: str, external_user_id: str) -> Optional[ExternalIdentity]:
    return (
        db.query(ExternalIdentity)
        .filter(ExternalIdentity.provider == provider)
        .filter(ExternalIdentity.issuer == issuer)
        .filter(ExternalIdentity.external_user_id == external_user_id)
        .first()
    )

def create_lobos_user_and_identity(
    db,
    provider: str,
    issuer: str,
    external_user_id: str,
    email: Optional[str],
    first_name: Optional[str],
    last_name: Optional[str],
) -> LobosUser:
    now = now_utc()

    user = LobosUser(
        email=email,
        first_name=first_name,
        last_name=last_name,
        created_at=now,
        updated_at=now,
    )
    db.add(user)
    db.flush()

    identity = ExternalIdentity(
        lobos_user_id=user.id,
        provider=provider,
        issuer=issuer,
        external_user_id=external_user_id,
        created_at=now,
        last_login_at=now,
    )
    db.add(identity)
    db.flush()

    return user

def update_lobos_user_basics(
    user: LobosUser,
    email: Optional[str],
    first_name: Optional[str],
    last_name: Optional[str],
) -> None:
    changed = False

    if email is not None and email != user.email:
        user.email = email
        changed = True

    if first_name is not None and first_name != user.first_name:
        user.first_name = first_name
        changed = True

    if last_name is not None and last_name != user.last_name:
        user.last_name = last_name
        changed = True

    if changed:
        user.updated_at = now_utc()


def get_or_create_user_profile_from_identity(
    db,
    user_id: str,
    ident: Dict[str, Any],
) -> UserProfile:
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
        db.flush()

    profile.email = ident.get("email")
    profile.first_name = ident.get("first_name")
    profile.last_name = ident.get("last_name")

    if ident.get("roles") is not None:
        profile.roles = json.dumps(ident.get("roles"))

    if "membership" in ident:
        try:
            profile.membership = json.dumps(ident.get("membership"))
        except Exception:
            profile.membership = None

    profile.updated_at = now_ts()
    db.flush()
    return profile

def ensure_user_preferences_row(
    db,
    lobos_user_id: int,
    profile: UserProfile,
) -> UserPreference:
    prefs = db.query(UserPreference).filter(UserPreference.lobos_user_id == lobos_user_id).first()
    if not prefs:
        prefs = UserPreference(
            lobos_user_id=lobos_user_id,
            current_weight=None,
            goal_weight=None,
            height=None,
            age=None,
            eating_style=profile.eating_style,
            meal_type=profile.meal_type,
            macro_preset=profile.macro_preset,
            prep=profile.prep,
            glp1_status=None,
            glp1_dosage=None,
            onboarding_completed=False,
            onboarding_completed_at=None,
            updated_at=now_utc(),
        )
        db.add(prefs)
        db.flush()
    return prefs

def is_onboarding_complete(prefs: Optional[UserPreference]) -> bool:
    return bool(prefs and prefs.onboarding_completed)

# ============================================================
# ROUTES
# ============================================================

@app.get("/login")
def login(token: str = Query(..., min_length=1)):
    payload = verify_and_get_payload(token)

    issuer = normalize_text(payload.get("iss"))
    external_user_id = normalize_text(payload.get("sub"))
    if issuer is None or external_user_id is None:
        raise HTTPException(status_code=401, detail="Invalid token (missing issuer or sub)")

    identity = payload.get("identity")
    if not isinstance(identity, dict):
        identity = {}

    ident = {
        "email": identity.get("email", payload.get("email")),
        "first_name": identity.get("first_name", payload.get("first_name")),
        "last_name": identity.get("last_name", payload.get("last_name")),
        "roles": identity.get("roles", payload.get("roles")) or [],
        "membership": identity.get("membership", payload.get("membership")),
    }

    membership_ok = has_required_membership(ident.get("membership"))
    provider = "wordpress"

    with SessionLocal() as db:
        external_identity = find_external_identity(db, provider, issuer, external_user_id)

        if external_identity is None:
            lobos_user = create_lobos_user_and_identity(
                db=db,
                provider=provider,
                issuer=issuer,
                external_user_id=external_user_id,
                email=normalize_text(ident.get("email")),
                first_name=normalize_text(ident.get("first_name")),
                last_name=normalize_text(ident.get("last_name")),
            )
        else:
            lobos_user = db.query(LobosUser).filter(LobosUser.id == external_identity.lobos_user_id).first()
            if lobos_user is None:
                raise HTTPException(status_code=500, detail="Identity mapping exists but Lobos user not found")

            update_lobos_user_basics(
                lobos_user,
                email=normalize_text(ident.get("email")),
                first_name=normalize_text(ident.get("first_name")),
                last_name=normalize_text(ident.get("last_name")),
            )
            external_identity.last_login_at = now_utc()

        profile = get_or_create_user_profile_from_identity(
            db=db,
            user_id=external_user_id,
            ident=ident,
        )

        prefs = ensure_user_preferences_row(
            db=db,
            lobos_user_id=lobos_user.id,
            profile=profile,
        )

        db.commit()

        if LOBOS_REQUIRE_MEMBERSHIP and not membership_ok:
            return RedirectResponse(url=f"/access-denied?token={token}", status_code=302)

        if not is_onboarding_complete(prefs):
            return RedirectResponse(url=f"/landing?token={token}", status_code=302)

        return RedirectResponse(url=f"/my-recipe?token={token}", status_code=302)


@app.get("/access-denied", response_class=HTMLResponse)
def access_denied(token: Optional[str] = None):
    return HTMLResponse(
        """
        <html>
        <head><title>Lobos - Access Denied</title></head>
        <body style="font-family: sans-serif; margin: 40px;">
            <h1>Access denied</h1>
            <p>Active membership required to access Lobos.</p>
        </body>
        </html>
        """,
        status_code=403,
    )


@app.get("/admin", response_class=HTMLResponse)
def admin(request: Request, token: str):
    user_id = get_user_id_from_token(token)
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token")

    if not is_admin_token(token):
        raise HTTPException(status_code=403, detail="Admin only")

    with SessionLocal() as db:
        seed_default_options_if_empty(db)

        rows = (
            db.query(PreferenceOption)
            .order_by(
                PreferenceOption.category.asc(),
                PreferenceOption.sort_order.asc(),
                PreferenceOption.value.asc(),
            )
            .all()
        )

        grouped = {"eating_style": [], "meal_type": [], "macro_preset": [], "prep": []}
        for r in rows:
            if r.category in grouped:
                grouped[r.category].append(
                    {
                        "id": r.id,
                        "value": r.value,
                        "sort_order": r.sort_order,
                        "is_active": bool(r.is_active),
                    }
                )

    return templates.TemplateResponse(
        "admin.html",
        {
            "request": request,
            "token": token,
            "grouped": grouped,
        },
    )


@app.post("/admin/option/add")
def admin_option_add(
    token: str = Form(...),
    category: str = Form(...),
    value: str = Form(...),
    sort_order: int = Form(0),
):
    user_id = get_user_id_from_token(token)
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token")
    if not is_admin_token(token):
        raise HTTPException(status_code=403, detail="Admin only")

    category = (category or "").strip()
    value = (value or "").strip()
    if category not in ("eating_style", "meal_type", "macro_preset", "prep"):
        raise HTTPException(status_code=400, detail="Invalid category")
    if not value:
        raise HTTPException(status_code=400, detail="Value cannot be empty")

    with SessionLocal() as db:
        existing = (
            db.query(PreferenceOption)
            .filter(PreferenceOption.category == category)
            .filter(PreferenceOption.value.ilike(value))
            .first()
        )
        if existing:
            existing.value = value
            existing.sort_order = int(sort_order or 0)
            existing.is_active = True
        else:
            db.add(
                PreferenceOption(
                    category=category,
                    value=value,
                    sort_order=int(sort_order or 0),
                    is_active=True,
                )
            )
        db.commit()

    return RedirectResponse(url=f"/admin?token={token}", status_code=302)


@app.post("/admin/option/update")
def admin_option_update(
    token: str = Form(...),
    option_id: int = Form(...),
    value: str = Form(...),
    sort_order: int = Form(0),
):
    user_id = get_user_id_from_token(token)
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token")
    if not is_admin_token(token):
        raise HTTPException(status_code=403, detail="Admin only")

    value = (value or "").strip()
    if not value:
        raise HTTPException(status_code=400, detail="Value cannot be empty")

    with SessionLocal() as db:
        row = db.query(PreferenceOption).filter(PreferenceOption.id == int(option_id)).first()
        if not row:
            raise HTTPException(status_code=404, detail="Option not found")

        row.value = value
        row.sort_order = int(sort_order or 0)
        db.commit()

    return RedirectResponse(url=f"/admin?token={token}", status_code=302)


@app.post("/admin/option/toggle")
def admin_option_toggle(
    token: str = Form(...),
    option_id: int = Form(...),
):
    user_id = get_user_id_from_token(token)
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token")
    if not is_admin_token(token):
        raise HTTPException(status_code=403, detail="Admin only")

    with SessionLocal() as db:
        row = db.query(PreferenceOption).filter(PreferenceOption.id == int(option_id)).first()
        if not row:
            raise HTTPException(status_code=404, detail="Option not found")

        row.is_active = not bool(row.is_active)
        db.commit()

    return RedirectResponse(url=f"/admin?token={token}", status_code=302)


@app.get("/landing", response_class=HTMLResponse)
def landing(request: Request, token: str):
    user_id = get_user_id_from_token(token)
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token (missing sub)")

    ident = token_identity_from_jwt(token)
    is_admin = is_admin_token(token)

    logger.info(
        "landing: user_id=%s roles=%s membership_present=%s require_membership=%s",
        user_id,
        ident.get("roles"),
        ident.get("membership") is not None,
        LOBOS_REQUIRE_MEMBERSHIP,
    )

    if LOBOS_REQUIRE_MEMBERSHIP and not has_required_membership(ident.get("membership")):
        logger.warning(
            "landing denied: user_id=%s missing required membership id=%s title=%s",
            user_id,
            LOBOS_REQUIRED_MEMBERSHIP_ID,
            LOBOS_REQUIRED_MEMBERSHIP_TITLE,
        )
        return templates.TemplateResponse(
            "landing.html",
            {
                "request": request,
                "token": token,
                "profile": {
                    "user_id": user_id,
                    "created_at": None,
                    "updated_at": None,
                    "eating_style": "",
                    "meal_type": "",
                    "macro_preset": "",
                    "prep": "",
                    "email": ident.get("email"),
                    "first_name": ident.get("first_name"),
                    "last_name": ident.get("last_name"),
                    "roles": json.dumps(ident.get("roles") or []),
                    "membership": ident.get("membership"),
                },
                "roles_human": roles_to_human(ident.get("roles")),
                "eating_style_options": [],
                "meal_type_options": [],
                "macro_preset_options": [],
                "prep_options": [],
                "is_admin": is_admin,
                "membership_required_error": "Active membership required to access Lobos.",
            },
            status_code=403,
        )

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

        profile.email = ident.get("email")
        profile.first_name = ident.get("first_name")
        profile.last_name = ident.get("last_name")

        if ident.get("roles") is not None:
            profile.roles = json.dumps(ident.get("roles"))

        if "membership" in ident:
            try:
                profile.membership = json.dumps(ident.get("membership"))
            except Exception:
                profile.membership = None

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
            "is_admin": is_admin,
            "membership_required_error": "",
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
            db.flush()
        else:
            profile.eating_style = eating_style
            profile.meal_type = meal_type
            profile.macro_preset = macro_preset
            profile.prep = prep
            profile.updated_at = now_ts()

        external_identity = (
            db.query(ExternalIdentity)
            .filter(ExternalIdentity.provider == "wordpress")
            .filter(ExternalIdentity.issuer == LOBOS_JWT_ISSUER)
            .filter(ExternalIdentity.external_user_id == user_id)
            .first()
        )

        if external_identity:
            prefs = db.query(UserPreference).filter(
                UserPreference.lobos_user_id == external_identity.lobos_user_id
            ).first()

            if prefs is None:
                prefs = UserPreference(
                    lobos_user_id=external_identity.lobos_user_id,
                    current_weight=None,
                    goal_weight=None,
                    height=None,
                    age=None,
                    eating_style=eating_style,
                    meal_type=meal_type,
                    macro_preset=macro_preset,
                    prep=prep,
                    glp1_status=None,
                    glp1_dosage=None,
                    onboarding_completed=True,
                    onboarding_completed_at=now_utc(),
                    updated_at=now_utc(),
                )
                db.add(prefs)
            else:
                prefs.eating_style = eating_style
                prefs.meal_type = meal_type
                prefs.macro_preset = macro_preset
                prefs.prep = prep
                prefs.onboarding_completed = True
                if prefs.onboarding_completed_at is None:
                    prefs.onboarding_completed_at = now_utc()
                prefs.updated_at = now_utc()

        db.commit()

    return RedirectResponse(url=f"/my-recipe?token={token}", status_code=302)


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

        selected_title = clean_title((selected.title if selected else "") or "")
        selected_text = (selected.response_text if selected else "") or ""
        selected_model = (selected.model if selected else "") or ""

        history_view = []
        for r in history:
            history_view.append(
                {
                    "id": r.id,
                    "created_at": r.created_at,
                    "model": r.model or "",
                    "title": clean_title((r.title or "").strip()),
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
            "cache_age_days": RECIPE_MAX_CACHE_AGE_DAYS,
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
    return HTMLResponse("<pre>" + json.dumps({"user_id": user_id, "identity": ident}, indent=2) + "</pre>")


@app.get("/me/login-debug", response_class=HTMLResponse)
def me_login_debug(token: str):
    payload = verify_and_get_payload(token)
    return HTMLResponse("<pre>" + json.dumps(payload, indent=2) + "</pre>")