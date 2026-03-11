from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import BigInteger
from sqlalchemy import Boolean
from sqlalchemy import DateTime
from sqlalchemy import ForeignKey
from sqlalchemy import Integer
from sqlalchemy import Numeric
from sqlalchemy import SmallInteger
from sqlalchemy import String
from sqlalchemy import Text
from sqlalchemy import UniqueConstraint
from sqlalchemy import text
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column

from db import Base


class LobosUser(Base):
    __tablename__ = "lobos_users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    email: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    first_name: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    last_name: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class ExternalIdentity(Base):
    __tablename__ = "external_identities"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    lobos_user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("lobos_users.id"),
        nullable=False,
    )

    provider: Mapped[str] = mapped_column(Text, nullable=False)
    issuer: Mapped[str] = mapped_column(Text, nullable=False)
    external_user_id: Mapped[str] = mapped_column(Text, nullable=False)

    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        server_default=text("now()"),
    )
    last_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        UniqueConstraint(
            "provider",
            "issuer",
            "external_user_id",
            name="external_identities_provider_issuer_external_user_id_key",
        ),
    )


class UserPreference(Base):
    __tablename__ = "user_preferences"

    lobos_user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("lobos_users.id"),
        primary_key=True,
    )

    # existing / old columns still present in your DB
    current_weight: Mapped[Optional[Decimal]] = mapped_column(Numeric(6, 2), nullable=True)
    goal_weight: Mapped[Optional[Decimal]] = mapped_column(Numeric(6, 2), nullable=True)
    height: Mapped[Optional[Decimal]] = mapped_column(Numeric(6, 2), nullable=True)
    age: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    eating_style: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    glp1_status: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    glp1_dosage: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    onboarding_completed: Mapped[Optional[bool]] = mapped_column(
        Boolean,
        nullable=True,
        server_default=text("false"),
    )
    onboarding_completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        server_default=text("now()"),
    )

    meal_type: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    macro_preset: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    prep: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)

    # new migrated columns
    birth_year: Mapped[Optional[int]] = mapped_column(SmallInteger, nullable=True)
    current_weight_lb: Mapped[Optional[Decimal]] = mapped_column(Numeric(6, 2), nullable=True)
    goal_weight_lb: Mapped[Optional[Decimal]] = mapped_column(Numeric(6, 2), nullable=True)
    height_in: Mapped[Optional[int]] = mapped_column(SmallInteger, nullable=True)
    other_allergy: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class UserProfile(Base):
    __tablename__ = "user_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    created_at: Mapped[int] = mapped_column(BigInteger, nullable=False)
    updated_at: Mapped[int] = mapped_column(BigInteger, nullable=False)

    eating_style: Mapped[str] = mapped_column(String(128), nullable=False)
    meal_type: Mapped[str] = mapped_column(String(64), nullable=False)
    macro_preset: Mapped[str] = mapped_column(String(128), nullable=False)
    prep: Mapped[str] = mapped_column(String(128), nullable=False)

    email: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    first_name: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    last_name: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    roles: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    membership: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class RecipeResult(Base):
    __tablename__ = "recipe_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[int] = mapped_column(BigInteger, nullable=False)

    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    request_json: Mapped[str] = mapped_column(Text, nullable=False)

    response_text: Mapped[str] = mapped_column(Text, nullable=False)
    model: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    prompt_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    title: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    preview: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class PreferenceOption(Base):
    __tablename__ = "preference_options"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    category: Mapped[str] = mapped_column(String(64), nullable=False)
    value: Mapped[str] = mapped_column(String(256), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class AllergyOption(Base):
    __tablename__ = "allergy_options"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    code: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    label: Mapped[str] = mapped_column(Text, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )


class UserAllergy(Base):
    __tablename__ = "user_allergies"

    lobos_user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("lobos_users.id", ondelete="CASCADE", name="fk_user_allergies_lobos_user"),
        primary_key=True,
    )
    allergy_option_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("allergy_options.id", ondelete="CASCADE", name="fk_user_allergies_allergy_option"),
        primary_key=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )


class UserWeightLog(Base):
    __tablename__ = "user_weight_log"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    lobos_user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("lobos_users.id", ondelete="CASCADE", name="fk_user_weight_log_lobos_user"),
        nullable=False,
        index=True,
    )
    weight_lb: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
        index=True,
    )
    source: Mapped[Optional[str]] = mapped_column(Text, nullable=True)