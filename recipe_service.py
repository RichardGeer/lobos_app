from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import time
from typing import Any, Dict, List, Optional, Tuple

import requests
from sqlalchemy import select

from models import AllergyOption
from models import ExternalIdentity
from models import RecipeResult
from models import UserAllergy
from models import UserPreference


logger = logging.getLogger("lobos")

OLLAMA_BASE_URL = os.getenv("LOBOS_OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/")
FAST_MODEL = os.getenv("LOBOS_OLLAMA_MODEL_FAST", "mistral:latest")
QUALITY_MODEL = os.getenv("LOBOS_OLLAMA_MODEL_QUALITY", "llama3.1:8b-instruct-q8_0")
RECIPE_MAX_CACHE_AGE_DAYS = int(
    os.getenv("LOBOS_RECIPE_MAX_CACHE_AGE_DAYS", os.getenv("RECIPE_MAX_CACHE_AGE_IN_DAYS", "7"))
)
LOBOS_JWT_ISSUER = os.getenv("LOBOS_JWT_ISSUER", "wp-sim").strip()


def now_ts() -> int:
    return int(time.time())


def clean_title(value: str) -> str:
    if not value:
        return ""

    text = value.strip()

    if text.startswith("#"):
        text = text.lstrip("#").strip()

    if text.startswith("**") and text.endswith("**") and len(text) >= 4:
        text = text[2:-2].strip()

    text = re.sub(r"\s+", " ", text).strip()
    return text


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
    rows = (
        db.execute(
            select(AllergyOption.code)
            .join(UserAllergy, UserAllergy.allergy_option_id == AllergyOption.id)
            .where(UserAllergy.lobos_user_id == lobos_user_id)
            .order_by(AllergyOption.sort_order.asc(), AllergyOption.id.asc())
        )
        .scalars()
        .all()
    )
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

    return payload


def build_prompt_from_recipe_payload(recipe_payload: Dict[str, Any]) -> str:
    allergy_text = ", ".join(recipe_payload.get("allergy_codes") or [])
    if not allergy_text:
        allergy_text = "None listed"

    other_allergy = recipe_payload.get("other_allergy") or "None"

    return f"""Create one healthy GLP-1-friendly recipe in clean markdown.

User context:
- Eating style: {recipe_payload.get("eating_style") or "No Preference"}
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
- Keep the recipe practical and realistic.
- Prefer high-protein, moderate-portion, easy-to-tolerate meal ideas suitable for GLP-1 users.

Include:
1. Title
2. Short description
3. Ingredients
4. Steps
5. Estimated nutrition
6. Why it fits this user

Output clean markdown only.
"""


def request_payload_from_profile(profile_view: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "eating_style": profile_view.get("eating_style"),
        "meal_type": profile_view.get("meal_type"),
        "macro_preset": profile_view.get("macro_preset"),
        "prep": profile_view.get("prep"),
    }


def hash_request(request_payload: Dict[str, Any]) -> str:
    normalized = json.dumps(request_payload, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def extract_title_and_preview(response_text: str) -> Tuple[str, str]:
    title = ""
    preview = ""

    lines = [line.strip() for line in (response_text or "").splitlines() if line.strip()]
    if lines:
        title = clean_title(lines[0])

    if len(lines) > 1:
        preview = lines[1]

    if not title:
        title = "Recipe"

    return title[:256], preview[:1000]


def call_ollama(model: str, prompt: str) -> str:
    url = f"{OLLAMA_BASE_URL}/api/generate"

    response = requests.post(
        url,
        json={"model": model, "prompt": prompt, "stream": False},
        timeout=480 if model == QUALITY_MODEL else 300,
    )
    response.raise_for_status()

    data = response.json()
    return (data.get("response") or "").strip()


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


def get_recipe_by_id(db, user_id: str, recipe_id: int) -> Optional[RecipeResult]:
    return (
        db.query(RecipeResult)
        .filter(RecipeResult.user_id == user_id)
        .filter(RecipeResult.id == recipe_id)
        .first()
    )


def build_prompt(profile_view: Dict[str, Any], db=None, user_id: Optional[str] = None) -> str:
    if db is not None and user_id:
        payload = build_recipe_request_payload_for_user(db, user_id, profile_view)
        return build_prompt_from_recipe_payload(payload)

    payload = request_payload_from_profile(profile_view)
    return f"""Create one healthy recipe in clean markdown.

User context:
- Eating style: {payload.get("eating_style") or "No Preference"}
- Meal type: {payload.get("meal_type") or "Dinner"}
- Macro preset: {payload.get("macro_preset") or "Balanced"}
- Prep preference: {payload.get("prep") or "Standard"}

Include:
1. Title
2. Short description
3. Ingredients
4. Steps
5. Estimated nutrition
6. Why it fits this user

Output clean markdown only.
"""


def generate_and_save_recipe(db, user_id: str, profile_view: Dict[str, Any], want_quality: bool) -> RecipeResult:
    model = QUALITY_MODEL if want_quality else FAST_MODEL
    logger.info("recipe_generate user=%s model=%s", user_id, model)

    prompt = build_prompt(profile_view=profile_view, db=db, user_id=user_id)
    request_payload = build_recipe_request_payload_for_user(db, user_id, profile_view)
    request_hash = hash_request(request_payload)
    prompt_hash = hashlib.sha256(prompt.encode("utf-8")).hexdigest()

    response_text = call_ollama(model, prompt)
    title, preview = extract_title_and_preview(response_text)

    row = RecipeResult(
        user_id=user_id,
        created_at=now_ts(),
        request_hash=request_hash,
        request_json=json.dumps(request_payload),
        response_text=response_text,
        model=model,
        prompt_hash=prompt_hash,
        title=title,
        preview=preview,
    )

    db.add(row)
    db.commit()
    db.refresh(row)
    return row
