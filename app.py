from __future__ import annotations

import os
import json
import time
import hashlib
import re
import logging

from typing import Optional, Dict, List, Any, Tuple
from datetime import datetime, timezone

import jwt
import requests
from fastapi import FastAPI
from fastapi import Request
from fastapi import Form
from fastapi import HTTPException
from fastapi import Query
from fastapi.responses import HTMLResponse
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from db import Base
from db import SessionLocal
from db import engine
from models import ExternalIdentity
from models import LobosUser
from models import PreferenceOption
from models import RecipeResult
from models import UserPreference
from models import UserProfile
from preferences import router as preferences_router


# ============================================================
# LOGGING
# ============================================================

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("lobos")

# ============================================================
# CONFIG
# ============================================================

LOBOS_JWT_SECRET = os.getenv("LOBOS_JWT_SECRET", "").strip()
LOBOS_JWT_ISSUER = os.getenv("LOBOS_JWT_ISSUER", "wp-sim").strip()

OLLAMA_BASE_URL = os.getenv("LOBOS_OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/")
FAST_MODEL = os.getenv("LOBOS_OLLAMA_MODEL_FAST", "mistral:latest")
QUALITY_MODEL = os.getenv("LOBOS_OLLAMA_MODEL_QUALITY", "llama3.1:8b-instruct-q8_0")

RECIPE_MAX_CACHE_AGE_DAYS = int(
    os.getenv("LOBOS_RECIPE_MAX_CACHE_AGE_DAYS", os.getenv("RECIPE_MAX_CACHE_AGE_IN_DAYS", "7"))
)

LOBOS_REQUIRED_MEMBERSHIP_ID = int(os.getenv("LOBOS_REQUIRED_MEMBERSHIP_ID", "27"))
LOBOS_REQUIRED_MEMBERSHIP_TITLE = os.getenv(
    "LOBOS_REQUIRED_MEMBERSHIP_TITLE",
    "GLP-1 Action Plan Hub",
).strip()
LOBOS_REQUIRE_MEMBERSHIP = os.getenv("LOBOS_REQUIRE_MEMBERSHIP", "1").strip().lower() in (
    "1", "true", "yes", "on"
)

app = FastAPI()
app.include_router(preferences_router)

templates = Jinja2Templates(directory="templates")

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
    if isinstance(active, bool) and active:
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
            LOBOS_REQUIRED_MEMBERSHIP_ID > 0
            and item_id == LOBOS_REQUIRED_MEMBERSHIP_ID
        )

        title_match = (
            bool(LOBOS_REQUIRED_MEMBERSHIP_TITLE)
            and item_title == LOBOS_REQUIRED_MEMBERSHIP_TITLE
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

    for row in rows:
        if row.category in opts:
            opts[row.category].append(row.value)

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

def decimal_to_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except Exception:
        return None


def height_parts_from_total(height_in: Optional[int]) -> Tuple[Optional[int], Optional[int]]:
    if height_in is None:
        return None, None
    return height_in // 12, height_in % 12


def get_lobos_user_id_from_external_user_id(
    db,
    external_user_id: str,
    issuer: Optional[str] = None,
) -> Optional[int]:
    issuer_to_use = issuer or LOBOS_JWT_ISSUER

    row = (
        db.query(ExternalIdentity)
        .filter(ExternalIdentity.provider == "wordpress")
        .filter(ExternalIdentity.issuer == issuer_to_use)
        .filter(ExternalIdentity.external_user_id == str(external_user_id))
        .first()
    )

    if row is None:
        return None

    return int(row.lobos_user_id)


def get_allergy_codes_for_lobos_user(db, lobos_user_id: int) -> List[str]:
    stmt = (
        select(ExternalIdentity)  # placeholder to keep SQLAlchemy import used consistently elsewhere if needed
    )
    del stmt

    rows = db.execute(
        select(
            __import__("models").AllergyOption.code
        )
        .join(
            __import__("models").UserAllergy,
            __import__("models").UserAllergy.allergy_option_id == __import__("models").AllergyOption.id,
        )
        .where(__import__("models").UserAllergy.lobos_user_id == lobos_user_id)
        .order_by(__import__("models").AllergyOption.sort_order.asc(), __import__("models").AllergyOption.id.asc())
    ).scalars().all()

    return list(rows)

def get_allergy_codes_for_lobos_user(db, lobos_user_id: int) -> List[str]:
    from models import AllergyOption, UserAllergy

    rows = db.execute(
        select(AllergyOption.code)
        .join(UserAllergy, UserAllergy.allergy_option_id == AllergyOption.id)
        .where(UserAllergy.lobos_user_id == lobos_user_id)
        .order_by(AllergyOption.sort_order.asc(), AllergyOption.id.asc())
    ).scalars().all()

    return list(rows)


def build_recipe_request_payload_for_user(
    db,
    user_id: str,
    profile_view: Dict[str, Any],
) -> Dict[str, Any]:
    lobos_user_id = get_lobos_user_id_from_external_user_id(db, user_id)
    prefs = None
    allergy_codes: List[str] = []

    if lobos_user_id is not None:
        prefs = db.query(UserPreference).filter(UserPreference.lobos_user_id == lobos_user_id).first()
        if prefs is not None:
            allergy_codes = get_allergy_codes_for_lobos_user(db, lobos_user_id)

    payload = {
        "eating_style": None,
        "meal_type": None,
        "macro_preset": None,
        "prep": None,
        "glp1_status": None,
        "glp1_dosage": None,
        "allergy_codes": allergy_codes,
        "other_allergy": None,
        "birth_year": None,
        "current_weight_lb": None,
        "goal_weight_lb": None,
        "height_in": None,
        "height_ft": None,
        "height_in_remainder": None,
        "user_id": profile_view.get("user_id"),
        "first_name": profile_view.get("first_name"),
    }

    if prefs is not None:
        payload["eating_style"] = prefs.eating_style
        payload["meal_type"] = prefs.meal_type
        payload["macro_preset"] = prefs.macro_preset
        payload["prep"] = prefs.prep
        payload["glp1_status"] = prefs.glp1_status
        payload["glp1_dosage"] = prefs.glp1_dosage
        payload["other_allergy"] = prefs.other_allergy
        payload["birth_year"] = prefs.birth_year
        payload["current_weight_lb"] = decimal_to_float(getattr(prefs, "current_weight_lb", None))
        payload["goal_weight_lb"] = decimal_to_float(getattr(prefs, "goal_weight_lb", None))
        payload["height_in"] = getattr(prefs, "height_in", None)

        height_ft, height_in_remainder = height_parts_from_total(payload["height_in"])
        payload["height_ft"] = height_ft
        payload["height_in_remainder"] = height_in_remainder

    if not payload["eating_style"]:
        payload["eating_style"] = profile_view.get("eating_style") or "No Preference"
    if not payload["meal_type"]:
        payload["meal_type"] = profile_view.get("meal_type") or "Dinner"
    if not payload["macro_preset"]:
        payload["macro_preset"] = profile_view.get("macro_preset") or "40/40/20 (Protein-Enhanced Lean)"
    if not payload["prep"]:
        payload["prep"] = profile_view.get("prep") or "Standard"

    return payload

def build_prompt_from_recipe_payload(recipe_payload: Dict[str, Any]) -> str:
    allergy_text = ", ".join(recipe_payload.get("allergy_codes") or [])
    if not allergy_text:
        allergy_text = "None listed"

    other_allergy = recipe_payload.get("other_allergy") or "None"

    return f"""Create one healthy GLP-1-friendly recipe in clean markdown.

User context:
- Eating style: {recipe_payload.get("eating_style") or "No Preference"}
- Meal type: {recipe_payload.get("meal_type") or "Not specified"}
- Macro preset: {recipe_payload.get("macro_preset") or "Not specified"}
- Preparation: {recipe_payload.get("prep") or "Not specified"}
- GLP-1 status: {recipe_payload.get("glp1_status") or "Not specified"}
- GLP-1 dosage: {recipe_payload.get("glp1_dosage") or "Not specified"}
- Allergies: {allergy_text}
- Other allergy or food issue: {other_allergy}
- Birth year: {recipe_payload.get("birth_year") or "Not specified"}
- Current weight (lb): {recipe_payload.get("current_weight_lb") or "Not specified"}
- Goal weight (lb): {recipe_payload.get("goal_weight_lb") or "Not specified"}
- Height: {recipe_payload.get("height_ft") or "?"} ft {recipe_payload.get("height_in_remainder") or "?"} in

Requirements:
- Avoid all listed allergies and food issues.
- Match the requested meal type, macro preset, and preparation style when practical.
- Keep the recipe practical and realistic.
- Prefer high-protein, moderate-portion, easy-to-tolerate meal ideas suitable for GLP-1 users.
- Include:
  1. Title
  2. Short description
  3. Ingredients
  4. Steps
  5. Estimated nutrition
  6. Why it fits this user

Output clean markdown only.
"""


def build_prompt(profile_view: Dict[str, Any]) -> str:
    return build_prompt_from_recipe_payload(
        {
            "eating_style": profile_view.get("eating_style"),
            "glp1_status": profile_view.get("glp1_status"),
            "glp1_dosage": profile_view.get("glp1_dosage"),
            "allergy_codes": profile_view.get("allergy_codes") or [],
            "other_allergy": profile_view.get("other_allergy"),
            "birth_year": profile_view.get("birth_year"),
            "current_weight_lb": profile_view.get("current_weight_lb"),
            "goal_weight_lb": profile_view.get("goal_weight_lb"),
            "height_in": profile_view.get("height_in"),
            "height_ft": profile_view.get("height_ft"),
            "height_in_remainder": profile_view.get("height_in_remainder"),
            "user_id": profile_view.get("user_id"),
            "first_name": profile_view.get("first_name"),
        }
    )

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
        "glp1_status": profile_view.get("glp1_status"),
        "glp1_dosage": profile_view.get("glp1_dosage"),
        "allergy_codes": profile_view.get("allergy_codes") or [],
        "other_allergy": profile_view.get("other_allergy"),
        "birth_year": profile_view.get("birth_year"),
        "current_weight_lb": profile_view.get("current_weight_lb"),
        "goal_weight_lb": profile_view.get("goal_weight_lb"),
        "height_in": profile_view.get("height_in"),
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

    req_payload = build_recipe_request_payload_for_user(
        db=db,
        user_id=user_id,
        profile_view=profile_view,
    )

    prompt = build_prompt_from_recipe_payload(req_payload)
    req_hash = hash_request(req_payload)
    prompt_hash = hashlib.sha256(prompt.encode("utf-8")).hexdigest()

    response_text = call_ollama(model, prompt)

    title, preview = extract_title_and_preview(response_text)
    row = RecipeResult(
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

    db.add(row)
    db.commit()

    return row

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
            birth_year=None,
            current_weight_lb=None,
            goal_weight_lb=None,
            height_in=None,
            other_allergy=None,
            eating_style=profile.eating_style,
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
        for row in rows:
            if row.category in grouped:
                grouped[row.category].append(
                    {
                        "id": row.id,
                        "value": row.value,
                        "sort_order": row.sort_order,
                        "is_active": bool(row.is_active),
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

def render_my_recipe_page(
    request: Request,
    token: str,
    quality_mode: bool,
    rid: Optional[int] = None,
    recipe_error: str = "",
):
    user_id = get_user_id_from_token(token)
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token")

    with SessionLocal() as db:
        profile = db.query(UserProfile).filter(UserProfile.user_id == user_id).first()
        if not profile:
            return RedirectResponse(url=f"/landing?token={token}", status_code=302)

        profile_view = profile_to_view(profile)
        req_payload = build_recipe_request_payload_for_user(
            db=db,
            user_id=user_id,
            profile_view=profile_view,
        )
        req_hash = hash_request(req_payload)

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
        for row in history:
            history_view.append(
                {
                    "id": row.id,
                    "created_at": row.created_at,
                    "model": row.model or "",
                    "title": clean_title((row.title or "").strip()),
                    "preview": (row.preview or "").strip(),
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
            "recipe_error": recipe_error,
            "history": history_view,
            "cache_age_days": RECIPE_MAX_CACHE_AGE_DAYS,
            "force_new": False,
        },
    )

@app.get("/my-recipe", response_class=HTMLResponse)
def my_recipe(request: Request, token: str, qm: str = "0", rid: Optional[int] = None):
    quality_mode = (qm == "1")
    return render_my_recipe_page(
        request=request,
        token=token,
        quality_mode=quality_mode,
        rid=rid,
        recipe_error="",
    )

@app.post("/recipe/generate")
def recipe_generate(
    request: Request,
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
        req_payload = build_recipe_request_payload_for_user(
            db=db,
            user_id=user_id,
            profile_view=profile_view,
        )
        req_hash = hash_request(req_payload)

        if not force:
            cached = get_cached_recipe(db, user_id, req_hash)
            if cached:
                qm = "1" if want_quality else "0"
                return RedirectResponse(
                    url=f"/my-recipe?token={token}&qm={qm}&rid={cached.id}",
                    status_code=302,
                )

        try:
            row = generate_and_save_recipe(db, user_id, profile_view, want_quality)
        except requests.RequestException as exc:
            return render_my_recipe_page(
                request=request,
                token=token,
                quality_mode=want_quality,
                rid=None,
                recipe_error=f"Recipe generation failed while calling Ollama: {exc}",
            )
        except Exception as exc:
            return render_my_recipe_page(
                request=request,
                token=token,
                quality_mode=want_quality,
                rid=None,
                recipe_error=f"Recipe generation failed: {exc}",
            )

    qm = "1" if want_quality else "0"
    return RedirectResponse(url=f"/my-recipe?token={token}&qm={qm}&rid={row.id}", status_code=302)


@app.get("/ai-prompt", response_class=HTMLResponse)
@app.get("/prompt", response_class=HTMLResponse)
def ai_prompt(token: str):
    user_id = get_user_id_from_token(token)
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token")

    with SessionLocal() as db:
        profile = db.query(UserProfile).filter(UserProfile.user_id == user_id).first()
        if not profile:
            raise HTTPException(status_code=404, detail="Profile not found")

        profile_view = profile_to_view(profile)
        req_payload = build_recipe_request_payload_for_user(
            db=db,
            user_id=user_id,
            profile_view=profile_view,
        )
        prompt = build_prompt_from_recipe_payload(req_payload)

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