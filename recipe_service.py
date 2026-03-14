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

RECIPE_SHARED_POOL_SCAN_LIMIT = int(os.getenv("LOBOS_RECIPE_SHARED_POOL_SCAN_LIMIT", "40"))
RECIPE_SHARED_POOL_CLONE_LIMIT = int(os.getenv("LOBOS_RECIPE_SHARED_POOL_CLONE_LIMIT", "1"))
RECIPE_MIN_ACCEPTABLE_OVERLAY_SCORE = int(os.getenv("LOBOS_RECIPE_MIN_ACCEPTABLE_OVERLAY_SCORE", "0"))


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


def normalize_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value

    if value is None:
        return False

    text = str(value).strip().lower()
    return text in {"1", "true", "yes", "y", "on", "quality"}


def strip_markdown_fences(text: str) -> str:
    if not text:
        return ""

    cleaned = text.replace("\r\n", "\n").replace("\r", "\n").strip()

    # Remove a full fenced wrapper if the whole response is wrapped.
    fenced_match = re.match(
        r"^\s*```(?:markdown|md)?\s*\n(?P<body>.*?)(?:\n```)\s*$",
        cleaned,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if fenced_match:
        cleaned = fenced_match.group("body").strip()

    # Defensive cleanup for partial leading/trailing fences.
    lines = cleaned.splitlines()

    if lines and re.match(r"^\s*```(?:markdown|md)?\s*$", lines[0], flags=re.IGNORECASE):
        lines = lines[1:]

    while lines and re.match(r"^\s*```\s*$", lines[-1]):
        lines = lines[:-1]

    cleaned = "\n".join(lines).strip()

    # Sometimes model returns a stray first line like ```markdown without closing properly.
    cleaned = re.sub(r"^\s*```(?:markdown|md)?\s*\n?", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\n?```\s*$", "", cleaned).strip()

    return cleaned


def sanitize_recipe_response(text: str) -> str:
    cleaned = strip_markdown_fences(text)
    cleaned = cleaned.replace("\u0000", "").strip()
    return cleaned


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


def normalize_text(value: Any) -> str:
    if value is None:
        return ""

    text = str(value).strip().lower()
    text = re.sub(r"\s+", " ", text)
    return text


def normalize_text_list(values: Any) -> List[str]:
    if not values:
        return []

    if isinstance(values, str):
        values = [values]

    out: List[str] = []
    seen = set()

    for item in values:
        text = normalize_text(item)
        if not text:
            continue
        if text in seen:
            continue
        seen.add(text)
        out.append(text)

    return out


def bucket_prep(prep: Optional[str]) -> str:
    text = normalize_text(prep)

    if not text:
        return "standard"

    if "quick" in text or "under 15" in text or "15" in text:
        return "under_15"

    if "30" in text:
        return "under_30"

    if "45" in text:
        return "under_45"

    if "batch" in text:
        return "batch"

    return text.replace(" ", "_")


def bucket_macro_preset(macro_preset: Optional[str]) -> str:
    text = normalize_text(macro_preset)

    if not text:
        return "balanced"

    if "40/40/20" in text or "protein" in text:
        return "protein_enhanced"

    if "lower carb" in text or "low carb" in text:
        return "lower_carb"

    if "balanced" in text:
        return "balanced"

    return text.replace(" ", "_")


def bucket_glp1_phase(glp1_status: Optional[str], glp1_dosage: Optional[str]) -> str:
    status = normalize_text(glp1_status)
    dosage = normalize_text(glp1_dosage)

    if not status and not dosage:
        return "unspecified"

    if "not" in status and "glp" in status:
        return "not_on_glp1"

    if "starting" in status or "new" in status or "early" in status:
        return "early"

    if "maintenance" in status or "stable" in status:
        return "maintenance"

    if dosage:
        if any(token in dosage for token in ["0.25", "0.5"]):
            return "early"

        if any(token in dosage for token in ["1.0", "1 ", "1mg", "1 mg"]):
            return "active"

        if any(token in dosage for token in ["1.7", "2.0", "2.4", "2.5", "5", "7.5", "10", "12.5", "15"]):
            return "maintenance"

    return "active"


def bucket_goal(current_weight_lb: Optional[float], goal_weight_lb: Optional[float]) -> str:
    if current_weight_lb is None or goal_weight_lb is None:
        return "unspecified"

    delta = current_weight_lb - goal_weight_lb

    if delta <= 0:
        return "maintain_or_gain"

    if delta < 15:
        return "light_loss"

    if delta < 40:
        return "moderate_loss"

    return "significant_loss"


def parse_free_text_terms(other_allergy: Optional[str]) -> List[str]:
    text = normalize_text(other_allergy)

    if not text:
        return []

    parts = re.split(r"[,;/\n]| and | or ", text)

    cleaned: List[str] = []

    for part in parts:
        item = normalize_text(part)
        if not item:
            continue
        if len(item) < 3:
            continue
        cleaned.append(item)

    out: List[str] = []
    seen = set()

    for item in cleaned:
        if item in seen:
            continue
        seen.add(item)
        out.append(item)

    return out[:12]


def extract_overlay_exclusions(other_allergy: Optional[str]) -> List[str]:
    raw_terms = parse_free_text_terms(other_allergy)
    exclusions: List[str] = []

    known_food_terms = [
        "cilantro",
        "mushroom",
        "mushrooms",
        "peanut",
        "peanuts",
        "cashew",
        "cashews",
        "almond",
        "almonds",
        "walnut",
        "walnuts",
        "pistachio",
        "pistachios",
        "shrimp",
        "prawn",
        "prawns",
        "lobster",
        "crab",
        "clam",
        "clams",
        "oyster",
        "oysters",
        "scallop",
        "scallops",
        "sesame",
        "soy",
        "tofu",
        "egg",
        "eggs",
        "milk",
        "dairy",
        "cheese",
        "yogurt",
        "gluten",
        "wheat",
    ]

    text_blob = " ".join(raw_terms)

    for term in known_food_terms:
        if term in text_blob:
            exclusions.append(term)

    return normalize_text_list(exclusions)


def normalize_allergy_codes(codes: List[str]) -> List[str]:
    normalized = normalize_text_list(codes)
    normalized.sort()
    return normalized


def medical_exclusion_tags(allergy_codes: List[str], other_allergy: Optional[str]) -> List[str]:
    tags: List[str] = []
    code_set = set(normalize_allergy_codes(allergy_codes))
    free_text = normalize_text(other_allergy)

    if "shellfish" in code_set or "shellfish" in free_text:
        tags.append("shellfish")

    if "nuts" in code_set or "tree_nuts" in code_set or "peanut" in free_text or "nuts" in free_text:
        tags.append("nuts")

    if "dairy" in code_set or "dairy" in free_text or "milk" in free_text:
        tags.append("dairy")

    if "gluten" in code_set or "wheat" in code_set or "gluten" in free_text or "wheat" in free_text:
        tags.append("gluten")

    if "soy" in code_set or "soy" in free_text:
        tags.append("soy")

    if "egg" in code_set or "eggs" in free_text or "egg" in free_text:
        tags.append("egg")

    return normalize_text_list(tags)


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
        "meal_type": profile_view.get("meal_type"),
        "macro_preset": profile_view.get("macro_preset"),
        "prep": profile_view.get("prep"),
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
        payload["meal_type"] = prefs.meal_type or payload["meal_type"]
        payload["macro_preset"] = prefs.macro_preset or payload["macro_preset"]
        payload["prep"] = prefs.prep or payload["prep"]
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
        payload["macro_preset"] = profile_view.get("macro_preset") or "Balanced"

    if not payload["prep"]:
        payload["prep"] = profile_view.get("prep") or "Standard"

    return payload


def build_core_variant_json(recipe_payload: Dict[str, Any]) -> Dict[str, Any]:
    allergy_codes = normalize_allergy_codes(recipe_payload.get("allergy_codes") or [])
    medical_tags = medical_exclusion_tags(
        allergy_codes=allergy_codes,
        other_allergy=recipe_payload.get("other_allergy"),
    )

    return {
        "eating_style": normalize_text(recipe_payload.get("eating_style")) or "no_preference",
        "meal_type": normalize_text(recipe_payload.get("meal_type")) or "dinner",
        "macro_band": bucket_macro_preset(recipe_payload.get("macro_preset")),
        "prep_band": bucket_prep(recipe_payload.get("prep")),
        "glp1_phase": bucket_glp1_phase(
            recipe_payload.get("glp1_status"),
            recipe_payload.get("glp1_dosage"),
        ),
        "goal_band": bucket_goal(
            recipe_payload.get("current_weight_lb"),
            recipe_payload.get("goal_weight_lb"),
        ),
        "allergy_codes": allergy_codes,
        "medical_exclusions": medical_tags,
    }


def build_overlay_json(recipe_payload: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "user_id": recipe_payload.get("user_id"),
        "first_name": recipe_payload.get("first_name"),
        "glp1_dosage": recipe_payload.get("glp1_dosage"),
        "birth_year": recipe_payload.get("birth_year"),
        "current_weight_lb": recipe_payload.get("current_weight_lb"),
        "goal_weight_lb": recipe_payload.get("goal_weight_lb"),
        "height_in": recipe_payload.get("height_in"),
        "raw_other_allergy": recipe_payload.get("other_allergy"),
        "overlay_exclusions": extract_overlay_exclusions(recipe_payload.get("other_allergy")),
        "overlay_notes": parse_free_text_terms(recipe_payload.get("other_allergy")),
    }


def request_payload_from_profile(profile_view: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "eating_style": profile_view.get("eating_style"),
        "meal_type": profile_view.get("meal_type"),
        "macro_preset": profile_view.get("macro_preset"),
        "prep": profile_view.get("prep"),
    }


def hash_request(request_payload: Dict[str, Any]) -> str:
    core_variant_json = build_core_variant_json(request_payload)
    normalized = json.dumps(core_variant_json, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def build_prompt_from_recipe_payload(recipe_payload: Dict[str, Any]) -> str:
    core_variant_json = build_core_variant_json(recipe_payload)
    overlay_json = build_overlay_json(recipe_payload)

    allergy_text = ", ".join(core_variant_json.get("allergy_codes") or [])
    if not allergy_text:
        allergy_text = "None listed"

    medical_exclusions = ", ".join(core_variant_json.get("medical_exclusions") or [])
    if not medical_exclusions:
        medical_exclusions = "None"

    overlay_exclusions = ", ".join(overlay_json.get("overlay_exclusions") or [])
    if not overlay_exclusions:
        overlay_exclusions = "None"

    overlay_notes = ", ".join(overlay_json.get("overlay_notes") or [])
    if not overlay_notes:
        overlay_notes = "None"

    return f"""Create one healthy GLP-1-friendly recipe in clean markdown.

Use this design rule:
- Treat the CORE VARIANT as the reusable recipe pool definition.
- Treat OVERLAY preferences as personalization guidance only.
- Do not overfit the recipe to cosmetic or one-off preferences if it reduces reusability.
- Safety and medical restrictions must still be respected.

CORE VARIANT:
- Eating style: {core_variant_json.get("eating_style")}
- Meal type: {core_variant_json.get("meal_type")}
- Macro band: {core_variant_json.get("macro_band")}
- Prep band: {core_variant_json.get("prep_band")}
- GLP-1 phase: {core_variant_json.get("glp1_phase")}
- Goal band: {core_variant_json.get("goal_band")}
- Structured allergies: {allergy_text}
- Medical exclusions: {medical_exclusions}

OVERLAY:
- Overlay exclusions: {overlay_exclusions}
- Overlay notes: {overlay_notes}
- GLP-1 dosage detail: {recipe_payload.get("glp1_dosage") or "Not specified"}
- Current weight (lb): {recipe_payload.get("current_weight_lb") or "Not specified"}
- Goal weight (lb): {recipe_payload.get("goal_weight_lb") or "Not specified"}
- Height: {recipe_payload.get("height_ft") or "?"} ft {recipe_payload.get("height_in_remainder") or "?"} in

Requirements:
- Avoid all structured allergies and medical exclusions.
- Respect overlay exclusions when practical.
- Keep the recipe practical and realistic.
- Prefer high-protein, moderate-portion, easy-to-tolerate meal ideas suitable for GLP-1 users.
- Keep ingredients mainstream and repeatable.
- Avoid niche ingredients unless strongly justified by the core variant.

Include:
1. Title
2. Short description
3. Ingredients
4. Steps
5. Estimated nutrition
6. Why it fits this user

Return plain markdown only.
Do not wrap the response in triple backticks.
Do not use ```markdown.
Do not use code fences.
"""


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

    logger.info(
        "ollama_generate model=%s fast_model=%s quality_model=%s",
        model,
        FAST_MODEL,
        QUALITY_MODEL,
    )

    response = requests.post(
        url,
        json={"model": model, "prompt": prompt, "stream": False},
        timeout=480 if model == QUALITY_MODEL else 300,
    )
    response.raise_for_status()

    data = response.json()
    raw_text = (data.get("response") or "").strip()
    return sanitize_recipe_response(raw_text)


def cache_cutoff_ts() -> int:
    return now_ts() - (RECIPE_MAX_CACHE_AGE_DAYS * 86400)


def build_request_envelope(request_payload: Dict[str, Any]) -> Dict[str, Any]:
    core_variant_json = build_core_variant_json(request_payload)
    overlay_json = build_overlay_json(request_payload)

    return {
        "full_request": request_payload,
        "core_variant_json": core_variant_json,
        "overlay_json": overlay_json,
    }


def safe_parse_request_json(request_json_text: Optional[str]) -> Dict[str, Any]:
    if not request_json_text:
        return {}

    try:
        data = json.loads(request_json_text)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def recipe_text_contains_term(recipe_text: str, term: str) -> bool:
    if not recipe_text or not term:
        return False

    pattern = r"\b" + re.escape(term) + r"\b"
    return re.search(pattern, recipe_text, flags=re.IGNORECASE) is not None


def score_recipe_for_overlay(row: RecipeResult, overlay_json: Dict[str, Any]) -> int:
    score = 0
    text = (row.response_text or "").lower()

    overlay_exclusions = normalize_text_list(overlay_json.get("overlay_exclusions"))
    for term in overlay_exclusions:
        if recipe_text_contains_term(text, term):
            score -= 100

    overlay_notes = normalize_text_list(overlay_json.get("overlay_notes"))
    for note in overlay_notes:
        if note and recipe_text_contains_term(text, note):
            score += 3

    dosage_text = normalize_text(overlay_json.get("glp1_dosage"))
    if dosage_text:
        if "early" in dosage_text or "0.25" in dosage_text or "0.5" in dosage_text:
            if "gentle" in text or "easy-to-tolerate" in text or "light" in text:
                score += 5

    return score


def clone_recipe_for_user(
    db,
    source_row: RecipeResult,
    target_user_id: str,
    request_payload: Dict[str, Any],
    request_hash: str,
) -> RecipeResult:
    envelope = build_request_envelope(request_payload)

    cloned = RecipeResult(
        user_id=target_user_id,
        created_at=now_ts(),
        request_hash=request_hash,
        request_json=json.dumps(envelope, ensure_ascii=False),
        response_text=source_row.response_text,
        model=source_row.model,
        prompt_hash=source_row.prompt_hash,
        title=source_row.title,
        preview=source_row.preview,
    )

    db.add(cloned)
    db.commit()
    db.refresh(cloned)

    logger.info(
        "recipe_shared_clone target_user=%s source_recipe_id=%s cloned_recipe_id=%s",
        target_user_id,
        source_row.id,
        cloned.id,
    )

    return cloned


def get_user_cached_recipe(
    db,
    user_id: str,
    request_hash: str,
    model: Optional[str] = None,
) -> Optional[RecipeResult]:
    cutoff = cache_cutoff_ts()

    query = (
        db.query(RecipeResult)
        .filter(RecipeResult.user_id == user_id)
        .filter(RecipeResult.request_hash == request_hash)
        .filter(RecipeResult.created_at >= cutoff)
    )

    if model:
        query = query.filter(RecipeResult.model == model)

    return query.order_by(RecipeResult.created_at.desc()).first()


def find_shared_recipe_candidates(
    db,
    request_hash: str,
    exclude_user_id: Optional[str] = None,
    model: Optional[str] = None,
    limit: int = RECIPE_SHARED_POOL_SCAN_LIMIT,
) -> List[RecipeResult]:
    cutoff = cache_cutoff_ts()

    query = (
        db.query(RecipeResult)
        .filter(RecipeResult.request_hash == request_hash)
        .filter(RecipeResult.created_at >= cutoff)
        .order_by(RecipeResult.created_at.desc())
    )

    if exclude_user_id:
        query = query.filter(RecipeResult.user_id != exclude_user_id)

    if model:
        query = query.filter(RecipeResult.model == model)

    return query.limit(limit).all()


def pick_best_shared_recipe(
    candidates: List[RecipeResult],
    overlay_json: Dict[str, Any],
) -> Optional[RecipeResult]:
    scored: List[Tuple[int, RecipeResult]] = []

    for row in candidates:
        score = score_recipe_for_overlay(row, overlay_json)
        scored.append((score, row))

    scored.sort(key=lambda item: item[0], reverse=True)

    if not scored:
        return None

    best_score, best_row = scored[0]

    if best_score < RECIPE_MIN_ACCEPTABLE_OVERLAY_SCORE:
        return None

    return best_row


def get_cached_recipe(
    db,
    user_id: str,
    request_hash: str,
    model: Optional[str] = None,
) -> Optional[RecipeResult]:
    user_row = get_user_cached_recipe(db, user_id, request_hash, model=model)
    if user_row is not None:
        logger.info(
            "recipe_user_cache_hit user=%s recipe_id=%s model=%s",
            user_id,
            user_row.id,
            user_row.model,
        )
        return user_row

    return None

def get_or_clone_shared_recipe(
    db,
    user_id: str,
    request_payload: Dict[str, Any],
    want_quality: Any,
) -> Optional[RecipeResult]:
    request_hash = hash_request(request_payload)
    overlay_json = build_overlay_json(request_payload)
    target_model = QUALITY_MODEL if normalize_bool(want_quality) else FAST_MODEL

    user_row = get_user_cached_recipe(
        db,
        user_id,
        request_hash,
        model=target_model,
    )
    if user_row is not None:
        logger.info(
            "recipe_user_cache_hit user=%s recipe_id=%s model=%s",
            user_id,
            user_row.id,
            user_row.model,
        )
        return user_row

    shared_candidates = find_shared_recipe_candidates(
        db=db,
        request_hash=request_hash,
        exclude_user_id=user_id,
        model=target_model,
        limit=RECIPE_SHARED_POOL_SCAN_LIMIT,
    )

    best_shared = pick_best_shared_recipe(shared_candidates, overlay_json)
    if best_shared is None:
        return None

    return clone_recipe_for_user(
        db=db,
        source_row=best_shared,
        target_user_id=user_id,
        request_payload=request_payload,
        request_hash=request_hash,
    )



def list_recipes_for_request(
    db,
    user_id: str,
    request_hash: str,
    limit: int = 50,
) -> List[RecipeResult]:
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

Eating style: {payload.get("eating_style") or "No Preference"}
Meal type: {payload.get("meal_type") or "Dinner"}
Macro preset: {payload.get("macro_preset") or "Balanced"}
Preparation: {payload.get("prep") or "Standard"}

Return plain markdown only.
Do not wrap the response in triple backticks.
Do not use ```markdown.
Do not use code fences.
"""


def generate_and_save_recipe(
    db,
    user_id: str,
    profile_view: Dict[str, Any],
    want_quality: Any,
) -> RecipeResult:
    want_quality_bool = normalize_bool(want_quality)
    model = QUALITY_MODEL if want_quality_bool else FAST_MODEL

    logger.info(
        "recipe_generate user=%s want_quality=%s want_quality_bool=%s model=%s fast_model=%s quality_model=%s",
        user_id,
        want_quality,
        want_quality_bool,
        model,
        FAST_MODEL,
        QUALITY_MODEL,
    )

    request_payload = build_recipe_request_payload_for_user(
        db=db,
        user_id=user_id,
        profile_view=profile_view,
    )

    prompt = build_prompt_from_recipe_payload(request_payload)
    request_hash = hash_request(request_payload)
    prompt_hash = hashlib.sha256(prompt.encode("utf-8")).hexdigest()

    response_text = call_ollama(model, prompt)
    title, preview = extract_title_and_preview(response_text)

    row = RecipeResult(
        user_id=user_id,
        created_at=now_ts(),
        request_hash=request_hash,
        request_json=json.dumps(build_request_envelope(request_payload), ensure_ascii=False),
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
