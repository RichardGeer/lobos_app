from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import jwt
from fastapi import HTTPException

from models import ExternalIdentity
from models import LobosUser
from models import UserProfile
from models import UserPreference


LOBOS_JWT_SECRET = os.getenv("LOBOS_JWT_SECRET", "").strip()
LOBOS_JWT_ISSUER = os.getenv("LOBOS_JWT_ISSUER", "wp-sim").strip()
LOBOS_REQUIRED_MEMBERSHIP_ID = int(os.getenv("LOBOS_REQUIRED_MEMBERSHIP_ID", "27"))
LOBOS_REQUIRED_MEMBERSHIP_TITLE = os.getenv(
    "LOBOS_REQUIRED_MEMBERSHIP_TITLE",
    "GLP-1 Action Plan Hub",
).strip()


def now_ts() -> int:
    return int(time.time())


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def normalize_text(value: Any) -> Optional[str]:
    if value is None:
        return None

    text = str(value).strip()
    return text if text else None


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
        sub = payload.get("sub")
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
        return ", ".join(str(r) for r in roles)

    if isinstance(roles, str):
        try:
            parsed = json.loads(roles)
            if isinstance(parsed, list):
                return ", ".join(str(r) for r in parsed)
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


def ensure_lobos_user_and_identity(
    db,
    issuer: str,
    external_user_id: str,
) -> LobosUser:
    identity = (
        db.query(ExternalIdentity)
        .filter(ExternalIdentity.provider == "wordpress")
        .filter(ExternalIdentity.issuer == issuer)
        .filter(ExternalIdentity.external_user_id == external_user_id)
        .first()
    )

    if identity is not None:
        lobos_user = db.query(LobosUser).filter(LobosUser.id == identity.lobos_user_id).first()
        if lobos_user is None:
            raise HTTPException(status_code=500, detail="External identity points to missing user")
        return lobos_user

    lobos_user = LobosUser(created_at=now_utc(), updated_at=now_utc())
    db.add(lobos_user)
    db.flush()

    identity = ExternalIdentity(
        lobos_user_id=lobos_user.id,
        provider="wordpress",
        issuer=issuer,
        external_user_id=external_user_id,
        created_at=now_utc(),
    )
    db.add(identity)
    db.flush()

    return lobos_user


def upsert_user_profile_from_identity(
    db,
    user_id: str,
    ident: Dict[str, Any],
    defaults: Optional[Dict[str, Any]] = None,
) -> UserProfile:
    profile = db.query(UserProfile).filter(UserProfile.user_id == user_id).first()

    if profile is None:
        defaults = defaults or {}
        profile = UserProfile(
            user_id=user_id,
            created_at=now_ts(),
            updated_at=now_ts(),
            eating_style=defaults.get("eating_style"),
            meal_type=defaults.get("meal_type"),
            macro_preset=defaults.get("macro_preset"),
            prep=defaults.get("prep"),
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


def ensure_user_preferences_row(db, lobos_user_id: int) -> UserPreference:
    prefs = db.get(UserPreference, lobos_user_id)

    if prefs is None:
        prefs = UserPreference(
            lobos_user_id=lobos_user_id,
            onboarding_completed=False,
            onboarding_completed_at=None,
            updated_at=now_utc(),
        )
        db.add(prefs)
        db.flush()

    return prefs


def is_onboarding_complete(prefs: Optional[UserPreference]) -> bool:
    return bool(prefs and prefs.onboarding_completed)


def profile_to_view(profile: UserProfile) -> Dict[str, Any]:
    membership_obj = None

    if getattr(profile, "membership", None):
        try:
            membership_obj = json.loads(profile.membership)
        except Exception:
            membership_obj = profile.membership

    return {
        "user_id": profile.user_id,
        "created_at": profile.created_at,
        "updated_at": profile.updated_at,
        "eating_style": profile.eating_style,
        "meal_type": profile.meal_type,
        "macro_preset": profile.macro_preset,
        "prep": profile.prep,
        "email": profile.email,
        "first_name": profile.first_name,
        "last_name": profile.last_name,
        "roles": profile.roles,
        "membership": membership_obj,
    }
