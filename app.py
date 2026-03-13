from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

from fastapi import FastAPI
from fastapi import Form
from fastapi import HTTPException
from fastapi import Query
from fastapi import Request
from fastapi.responses import HTMLResponse
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from db import Base
from db import SessionLocal
from db import engine
from models import PreferenceOption
from models import RecipeResult
from models import UserPreference
from models import UserProfile
from preferences import router as preferences_router

try:
    from auth_service import ensure_lobos_user_and_identity
    from auth_service import ensure_user_preferences_row
    from auth_service import get_user_id_from_token
    from auth_service import has_required_membership
    from auth_service import is_admin_token
    from auth_service import is_onboarding_complete
    from auth_service import normalize_text
    from auth_service import profile_to_view
    from auth_service import roles_to_human
    from auth_service import token_identity_from_jwt
    from auth_service import upsert_user_profile_from_identity
    from auth_service import verify_and_get_payload
except ImportError:
    from auth_service import ensure_lobos_user_and_identity
    from auth_service import ensure_user_preferences_row
    from auth_service import get_user_id_from_token
    from auth_service import has_required_membership
    from auth_service import is_admin_token
    from auth_service import is_onboarding_complete
    from auth_service import normalize_text
    from auth_service import profile_to_view
    from auth_service import roles_to_human
    from auth_service import token_identity_from_jwt
    from auth_service import upsert_user_profile_from_identity
    from auth_service import verify_and_get_payload

from recipe_service import FAST_MODEL
from recipe_service import QUALITY_MODEL
from recipe_service import build_recipe_request_payload_for_user
from recipe_service import generate_and_save_recipe
from recipe_service import get_cached_recipe
from recipe_service import get_recipe_by_id
from recipe_service import hash_request
from recipe_service import list_recipes_for_request

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("lobos")

LOBOS_REQUIRE_MEMBERSHIP = os.getenv("LOBOS_REQUIRE_MEMBERSHIP", "1").strip().lower() in (
    "1",
    "true",
    "yes",
    "on",
)

app = FastAPI()
app.include_router(preferences_router)

templates = Jinja2Templates(directory="templates")

Base.metadata.create_all(bind=engine)


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


def seed_default_options_if_empty(db) -> None:
    if db.query(PreferenceOption).count() > 0:
        return

    defaults = [
        ("eating_style", "High Protein", 10),
        ("eating_style", "Low Carb", 20),
        ("eating_style", "Mediterranean", 30),
        ("eating_style", "Vegetarian", 40),
        ("eating_style", "No Preference", 999),
        ("meal_type", "Breakfast", 10),
        ("meal_type", "Lunch", 20),
        ("meal_type", "Dinner", 30),
        ("meal_type", "Snack", 40),
        ("macro_preset", "40/40/20 (Protein-Enhanced Lean)", 10),
        ("macro_preset", "Balanced", 20),
        ("macro_preset", "Lower Carb", 30),
        ("prep", "Quick", 10),
        ("prep", "Standard", 20),
        ("prep", "Batch Friendly", 30),
    ]

    for category, value, sort_order in defaults:
        db.add(
            PreferenceOption(
                category=category,
                value=value,
                sort_order=sort_order,
                is_active=True,
            )
        )

    db.commit()


def get_profile_for_user_or_401(db, user_id: str) -> UserProfile:
    profile = db.query(UserProfile).filter(UserProfile.user_id == user_id).first()

    if profile is None:
        raise HTTPException(status_code=404, detail="Profile not found")

    return profile


def get_preferences_for_user(db, user_id: str) -> Optional[UserPreference]:
    profile = db.query(UserProfile).filter(UserProfile.user_id == user_id).first()
    if profile is None:
        return None

    # user_id in UserProfile is external WP user id, so prefs lookup should happen
    # via auth_service/recipe_service mapping flows during login and generation.
    # For simple page gating here, generation/login already create the row.
    # We only need to verify onboarding from any matching UserPreference row.
    # This query intentionally stays simple and safe.
    return (
        db.query(UserPreference)
        .join(
            # join condition is implicit via created login flow;
            # since UserPreference is keyed by lobos_user_id, the row should exist
            # after /login has run
            # direct lookup is not available from external user_id here
            # so page routes rely on existing profile and generation flow
        )
        .first()
    )


@app.get("/healthz")
def healthz() -> Dict[str, str]:
    return {"status": "ok"}


@app.get("/", response_class=HTMLResponse)
def home() -> HTMLResponse:
    return HTMLResponse(
        """
        <html>
          <head><title>Lobos</title></head>
          <body style="font-family: sans-serif; margin: 40px;">
            <h1>Lobos</h1>
            <p>Use the WordPress SSO login link to enter the app.</p>
          </body>
        </html>
        """
    )


@app.get("/me")
def me(token: str = Query(..., min_length=1)) -> Dict[str, Any]:
    user_id = get_user_id_from_token(token)

    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token")

    ident = token_identity_from_jwt(token)

    with SessionLocal() as db:
        profile = db.query(UserProfile).filter(UserProfile.user_id == user_id).first()

        return {
            "user_id": user_id,
            "identity": ident,
            "profile": profile_to_view(profile) if profile else None,
            "roles_human": roles_to_human(ident.get("roles")),
        }


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

    with SessionLocal() as db:
        seed_default_options_if_empty(db)
        opts = load_options(db)

        lobos_user = ensure_lobos_user_and_identity(
            db=db,
            issuer=issuer,
            external_user_id=external_user_id,
        )

        profile = upsert_user_profile_from_identity(
            db=db,
            user_id=external_user_id,
            ident=ident,
            defaults={
                "eating_style": opts["eating_style"][0],
                "meal_type": opts["meal_type"][0],
                "macro_preset": opts["macro_preset"][0],
                "prep": opts["prep"][0],
            },
        )

        _ = profile

        prefs = ensure_user_preferences_row(
            db=db,
            lobos_user_id=lobos_user.id,
        )

        db.commit()

        if LOBOS_REQUIRE_MEMBERSHIP and not membership_ok:
            return RedirectResponse(url=f"/access-denied?token={token}", status_code=302)

        if not is_onboarding_complete(prefs):
            return RedirectResponse(url=f"/landing?token={token}", status_code=302)

        return RedirectResponse(url=f"/my-recipe?token={token}", status_code=302)


@app.get("/access-denied", response_class=HTMLResponse)
def access_denied(token: Optional[str] = None):
    _ = token

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


@app.get("/landing", response_class=HTMLResponse)
def landing(request: Request, token: str):
    user_id = get_user_id_from_token(token)

    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token")

    with SessionLocal() as db:
        seed_default_options_if_empty(db)

        profile = db.query(UserProfile).filter(UserProfile.user_id == user_id).first()
        if profile is None:
            return RedirectResponse(url=f"/login?token={token}", status_code=302)

        profile_view = profile_to_view(profile)

        return templates.TemplateResponse(
            "landing.html",
            {
                "request": request,
                "token": token,
                "profile": profile_view,
                "options": load_options(db),
            },
        )


@app.get("/my-recipe", response_class=HTMLResponse)
def my_recipe(request: Request, token: str):
    user_id = get_user_id_from_token(token)

    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token")

    with SessionLocal() as db:
        profile = db.query(UserProfile).filter(UserProfile.user_id == user_id).first()
        if profile is None:
            return RedirectResponse(url=f"/login?token={token}", status_code=302)

        profile_view = profile_to_view(profile)
        request_payload = build_recipe_request_payload_for_user(
            db=db,
            user_id=user_id,
            profile_view=profile_view,
        )
        request_hash = hash_request(request_payload)
        recipes = list_recipes_for_request(db, user_id, request_hash, limit=50)

        return templates.TemplateResponse(
            "my_recipe.html",
            {
                "request": request,
                "token": token,
                "profile": profile_view,
                "recipes": recipes,
                "fast_model": FAST_MODEL,
                "quality_model": QUALITY_MODEL,
            },
        )


@app.get("/recipe/{recipe_id}", response_class=HTMLResponse)
def recipe_detail(request: Request, recipe_id: int, token: str):
    user_id = get_user_id_from_token(token)

    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token")

    with SessionLocal() as db:
        row = get_recipe_by_id(db, user_id, recipe_id)
        if row is None:
            raise HTTPException(status_code=404, detail="Recipe not found")

        html = f"""
        <html>
          <head>
            <title>{row.title or "Recipe"}</title>
            <style>
              body {{
                font-family: system-ui, -apple-system, Segoe UI, Roboto, sans-serif;
                margin: 24px;
                max-width: 900px;
              }}
              pre {{
                white-space: pre-wrap;
                word-wrap: break-word;
              }}
              a {{
                text-decoration: none;
              }}
            </style>
          </head>
          <body>
            <p><a href="/my-recipe?token={token}">← Back to My Recipes</a></p>
            <h1>{row.title or "Recipe"}</h1>
            <pre>{row.response_text}</pre>
          </body>
        </html>
        """

        return HTMLResponse(html)


@app.post("/generate-recipe")
def generate_recipe(
    token: str = Form(...),
    quality: str = Form("fast"),
):
    user_id = get_user_id_from_token(token)

    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token")

    want_quality = str(quality or "").strip().lower() in ("1", "true", "yes", "on", "quality", "best")

    with SessionLocal() as db:
        profile = db.query(UserProfile).filter(UserProfile.user_id == user_id).first()
        if profile is None:
            return RedirectResponse(url=f"/login?token={token}", status_code=302)

        profile_view = profile_to_view(profile)

        request_payload = build_recipe_request_payload_for_user(
            db=db,
            user_id=user_id,
            profile_view=profile_view,
        )
        request_hash = hash_request(request_payload)

        cached = get_cached_recipe(db, user_id, request_hash)
        if cached is not None:
            logger.info("recipe_cache_hit user=%s recipe_id=%s", user_id, cached.id)
            return RedirectResponse(url=f"/recipe/{cached.id}?token={token}", status_code=302)

        row = generate_and_save_recipe(
            db=db,
            user_id=user_id,
            profile_view=profile_view,
            want_quality=want_quality,
        )

        return RedirectResponse(url=f"/recipe/{row.id}?token={token}", status_code=302)


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

        grouped = {
            "eating_style": [],
            "meal_type": [],
            "macro_preset": [],
            "prep": [],
        }

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

    if category not in {"eating_style", "meal_type", "macro_preset", "prep"}:
        raise HTTPException(status_code=400, detail="Invalid category")

    if not value:
        raise HTTPException(status_code=400, detail="Value cannot be empty")

    with SessionLocal() as db:
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
