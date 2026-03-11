from __future__ import annotations

import os

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.orm import sessionmaker


LOBOS_DATABASE_URL = os.getenv(
    "LOBOS_DATABASE_URL",
    "postgresql+psycopg2://lobos_user:lobos_pass@127.0.0.1:5432/lobos_db",
)


class Base(DeclarativeBase):
    pass


engine = create_engine(
    LOBOS_DATABASE_URL,
    pool_pre_ping=True,
    future=True,
)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
    future=True,
)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()