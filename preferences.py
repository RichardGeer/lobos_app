from __future__ import annotations

import os
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

import jwt
from fastapi import APIRouter
from fastapi import Cookie
from fastapi import Depends
from fastapi import Header
from fastapi import HTTPException
from fastapi import Query
from pydantic import BaseModel
from pydantic import Field
from sqlalchemy import delete
from sqlalchemy import select
from sqlalchemy.orm import Session

from db import get_db
from models import AllergyOption
from models import ExternalIdentity
from models import UserAllergy
from models import UserPreference
from models import UserWeightLog


router = APIRouter(prefix="/api/preferences", tags=["preferences"])

LOBOS_JWT_SECRET = os.getenv("LOBOS_JWT_SECRET", "").strip()
LOBOS_JWT_ISSUER = os.getenv("LOBOS_JWT_ISSUER", "wp-sim").strip()


class PreferenceOptionOut(BaseModel):
    id: int
    code: str
    label: str
    sort_order: int


class PreferencesOptionsResponse(BaseModel):
    allergies: list[PreferenceOptionOut]
    eating_style_options: list[str]
    glp1_status_options: list[str]


class PreferencesMeResponse(BaseModel):
    onboarding_completed: bool

    birth_year: Optional[int] = None
    current_weight_lb: Optional[float] = None
    goal_weight_lb: Optional[float] = None
    height_in: Optional[int] = None
    height_ft: Optional[int] = None
    height_in_remainder: Optional[int] = None

    allergy_codes: list[str] = []
    other_allergy: Optional[str] = None

    eating_style: Optional[str] = None
    glp1_status: Optional[str] = None
    glp1_dosage: Optional[str] = None


class PreferencesSaveRequest(BaseModel):
    birth_year: Optional[int] = Field(default=None, ge=1900, le=2100)
    current_weight_lb: Optional[float] = Field(default=None, gt=0, le=2000)
    goal_weight_lb: Optional[float] = Field(default=None, gt=0, le=2000)

    height_in: Optional[int] = Field(default=None, ge=24, le=96)
    height_ft: Optional[int] = Field(default=None, ge=0, le=8)
    height_in_remainder: Optional[int] = Field(default=None, ge=0, le=11)

    allergy_codes: list[str] = Field(default_factory=list)
    other_allergy: Optional[str] = Field(default=None, max_length=1000)

    eating_style: Optional[str] = Field(default=None, max_length=200)
    glp1_status: Optional[str] = Field(default=None, max_length=200)
    glp1_dosage: Optional[str] = Field(default=None, max_length=200)


class CompleteResponse(BaseModel):
    ok: bool
    onboarding_completed: bool


def decimal_to_float(value):
    if value is None:
        return None
    if isinstance(value, Decimal):
        return float(value)
    return float(value)


def resolve_height_in(payload: PreferencesSaveRequest) -> Optional[int]:
    if payload.height_in is not None:
        return payload.height_in

    if payload.height_ft is None and payload.height_in_remainder is None:
        return None

    ft = payload.height_ft or 0
    rem = payload.height_in_remainder or 0
    return (ft * 12) + rem


def height_parts_from_total(height_in: Optional[int]) -> tuple[Optional[int], Optional[int]]:
    if height_in is None:
        return None, None
    return height_in // 12, height_in % 12


def get_token_from_request(
    token_query: Optional[str],
    authorization: Optional[str],
    token_cookie: Optional[str],
) -> str:
    if token_query:
        return token_query

    if authorization and authorization.lower().startswith("bearer "):
        return authorization[7:].strip()

    if token_cookie:
        return token_cookie

    raise HTTPException(status_code=401, detail="Missing token")


def decode_lobos_token(token: str) -> dict:
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

    return payload


def get_current_lobos_user_id(
    db: Session = Depends(get_db),
    token_query: Optional[str] = Query(default=None, alias="token"),
    authorization: Optional[str] = Header(default=None),
    token_cookie: Optional[str] = Cookie(default=None, alias="token"),
) -> int:
    token = get_token_from_request(token_query, authorization, token_cookie)
    payload = decode_lobos_token(token)

    provider = "wordpress"
    issuer = str(payload.get("iss") or "").strip()
    external_user_id = str(payload.get("sub") or "").strip()

    if not issuer or not external_user_id:
        raise HTTPException(status_code=401, detail="Token missing issuer or sub")

    stmt = (
        select(ExternalIdentity)
        .where(ExternalIdentity.provider == provider)
        .where(ExternalIdentity.issuer == issuer)
        .where(ExternalIdentity.external_user_id == external_user_id)
    )
    identity = db.execute(stmt).scalar_one_or_none()

    if identity is None:
        raise HTTPException(status_code=404, detail="User identity not found")

    return int(identity.lobos_user_id)


def ensure_user_preferences_row(db: Session, lobos_user_id: int) -> UserPreference:
    prefs = db.get(UserPreference, lobos_user_id)

    if prefs is None:
        prefs = UserPreference(
            lobos_user_id=lobos_user_id,
            onboarding_completed=False,
            onboarding_completed_at=None,
            updated_at=datetime.now(timezone.utc),
        )
        db.add(prefs)
        db.commit()
        db.refresh(prefs)

    return prefs


def serialize_preferences(db: Session, prefs: UserPreference, lobos_user_id: int) -> PreferencesMeResponse:
    allergy_stmt = (
        select(AllergyOption.code)
        .join(UserAllergy, UserAllergy.allergy_option_id == AllergyOption.id)
        .where(UserAllergy.lobos_user_id == lobos_user_id)
        .order_by(AllergyOption.sort_order.asc(), AllergyOption.id.asc())
    )
    allergy_codes = list(db.execute(allergy_stmt).scalars().all())

    height_ft, height_in_remainder = height_parts_from_total(prefs.height_in)

    return PreferencesMeResponse(
        onboarding_completed=bool(prefs.onboarding_completed),
        birth_year=prefs.birth_year,
        current_weight_lb=decimal_to_float(prefs.current_weight_lb),
        goal_weight_lb=decimal_to_float(prefs.goal_weight_lb),
        height_in=prefs.height_in,
        height_ft=height_ft,
        height_in_remainder=height_in_remainder,
        allergy_codes=allergy_codes,
        other_allergy=prefs.other_allergy,
        eating_style=prefs.eating_style,
        glp1_status=prefs.glp1_status,
        glp1_dosage=prefs.glp1_dosage,
    )


@router.get("/options", response_model=PreferencesOptionsResponse)
def get_preferences_options(
    db: Session = Depends(get_db),
    lobos_user_id: int = Depends(get_current_lobos_user_id),
):
    _ = lobos_user_id

    stmt = (
        select(AllergyOption)
        .where(AllergyOption.is_active.is_(True))
        .order_by(AllergyOption.sort_order.asc(), AllergyOption.id.asc())
    )
    rows = db.execute(stmt).scalars().all()

    allergies = [
        PreferenceOptionOut(
            id=int(row.id),
            code=row.code,
            label=row.label,
            sort_order=row.sort_order,
        )
        for row in rows
    ]

    return PreferencesOptionsResponse(
        allergies=allergies,
        eating_style_options=[
            "High Protein",
            "Low Carb",
            "No Preference",
            "Vegetarian",
            "Vegan",
            "Pescatarian",
        ],
        glp1_status_options=[
            "not_taking",
            "thinking_about_it",
            "starting_soon",
            "currently_taking",
            "paused",
            "stopped",
        ],
    )


@router.get("/me", response_model=PreferencesMeResponse)
def get_my_preferences(
    db: Session = Depends(get_db),
    lobos_user_id: int = Depends(get_current_lobos_user_id),
):
    prefs = ensure_user_preferences_row(db, lobos_user_id)
    return serialize_preferences(db, prefs, lobos_user_id)


@router.post("/me", response_model=PreferencesMeResponse)
def save_my_preferences(
    payload: PreferencesSaveRequest,
    db: Session = Depends(get_db),
    lobos_user_id: int = Depends(get_current_lobos_user_id),
):
    prefs = ensure_user_preferences_row(db, lobos_user_id)

    resolved_height_in = resolve_height_in(payload)
    if resolved_height_in is not None and not (24 <= resolved_height_in <= 96):
        raise HTTPException(status_code=400, detail="Invalid height")

    valid_code_stmt = select(AllergyOption.code).where(AllergyOption.is_active.is_(True))
    valid_codes = set(db.execute(valid_code_stmt).scalars().all())

    invalid_codes = sorted(set(payload.allergy_codes) - valid_codes)
    if invalid_codes:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid allergy_codes: {', '.join(invalid_codes)}",
        )

    prefs.birth_year = payload.birth_year
    prefs.current_weight_lb = Decimal(str(payload.current_weight_lb)) if payload.current_weight_lb is not None else None
    prefs.goal_weight_lb = Decimal(str(payload.goal_weight_lb)) if payload.goal_weight_lb is not None else None
    prefs.height_in = resolved_height_in
    prefs.other_allergy = payload.other_allergy.strip() if payload.other_allergy else None
    prefs.eating_style = payload.eating_style
    prefs.glp1_status = payload.glp1_status
    prefs.glp1_dosage = payload.glp1_dosage
    prefs.updated_at = datetime.now(timezone.utc)

    db.execute(
        delete(UserAllergy).where(UserAllergy.lobos_user_id == lobos_user_id)
    )

    if payload.allergy_codes:
        option_stmt = (
            select(AllergyOption)
            .where(AllergyOption.code.in_(payload.allergy_codes))
            .where(AllergyOption.is_active.is_(True))
        )
        option_rows = db.execute(option_stmt).scalars().all()
        code_to_id = {row.code: row.id for row in option_rows}

        for code in payload.allergy_codes:
            allergy_option_id = code_to_id.get(code)
            if allergy_option_id is None:
                continue

            db.add(
                UserAllergy(
                    lobos_user_id=lobos_user_id,
                    allergy_option_id=allergy_option_id,
                )
            )

    if payload.current_weight_lb is not None:
        latest_stmt = (
            select(UserWeightLog)
            .where(UserWeightLog.lobos_user_id == lobos_user_id)
            .order_by(UserWeightLog.recorded_at.desc(), UserWeightLog.id.desc())
            .limit(1)
        )
        latest = db.execute(latest_stmt).scalar_one_or_none()

        current_weight_decimal = Decimal(str(payload.current_weight_lb))

        should_insert_weight_log = (
            latest is None
            or latest.weight_lb is None
            or Decimal(str(latest.weight_lb)) != current_weight_decimal
        )

        if should_insert_weight_log:
            db.add(
                UserWeightLog(
                    lobos_user_id=lobos_user_id,
                    weight_lb=current_weight_decimal,
                    source="preferences_save",
                )
            )

    db.commit()
    db.refresh(prefs)

    return serialize_preferences(db, prefs, lobos_user_id)


@router.post("/me/complete", response_model=CompleteResponse)
def complete_onboarding(
    db: Session = Depends(get_db),
    lobos_user_id: int = Depends(get_current_lobos_user_id),
):
    prefs = ensure_user_preferences_row(db, lobos_user_id)

    prefs.onboarding_completed = True
    if prefs.onboarding_completed_at is None:
        prefs.onboarding_completed_at = datetime.now(timezone.utc)
    prefs.updated_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(prefs)

    return CompleteResponse(
        ok=True,
        onboarding_completed=bool(prefs.onboarding_completed),
    )