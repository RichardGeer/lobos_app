#!/usr/bin/env python3
import os
import json
import time
import argparse
import hashlib
from itertools import product
from typing import Dict, List, Tuple

# usage programName --n 20
# or --max-variants 5
# Import your app models/helpers directly (no HTTP needed)
import app as lobos


def sha256_hex(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def ensure_seed_user(db, user_id: str) -> lobos.UserProfile:
    # Ensure options exist
    lobos.seed_default_options_if_empty(db)
    opts = lobos.load_options(db)

    profile = db.query(lobos.UserProfile).filter(lobos.UserProfile.user_id == user_id).first()
    if not profile:
        profile = lobos.UserProfile(
            user_id=user_id,
            created_at=lobos.now_ts(),
            updated_at=lobos.now_ts(),
            eating_style=opts["eating_style"][0],
            meal_type=opts["meal_type"][0],
            macro_preset=opts["macro_preset"][0],
            prep=opts["prep"][0],
        )
        db.add(profile)
        db.commit()
    return profile


def get_variants(db) -> List[Tuple[str, str, str, str]]:
    opts = lobos.load_options(db)
    eating_styles = opts["eating_style"]
    meal_types = opts["meal_type"]
    macro_presets = opts["macro_preset"]
    preps = opts["prep"]

    # Full cartesian product of active options
    return list(product(eating_styles, meal_types, macro_presets, preps))


def set_profile_variant(db, profile: lobos.UserProfile, variant: Tuple[str, str, str, str]) -> Dict:
    eating_style, meal_type, macro_preset, prep = variant
    profile.eating_style = eating_style
    profile.meal_type = meal_type
    profile.macro_preset = macro_preset
    profile.prep = prep
    profile.updated_at = lobos.now_ts()
    db.commit()
    return lobos.profile_to_view(profile)


def count_existing_for_variant(db, user_id: str, profile_view: Dict) -> int:
    req_payload = lobos.request_payload_from_profile(profile_view)
    req_hash = lobos.hash_request(req_payload)
    return (
        db.query(lobos.RecipeResult)
        .filter(lobos.RecipeResult.user_id == user_id)
        .filter(lobos.RecipeResult.request_hash == req_hash)
        .count()
    )


def generate_and_save_with_variation(
    db,
    user_id: str,
    profile_view: Dict,
    want_quality: bool,
    variation_id: int,
) -> lobos.RecipeResult:
    model = lobos.QUALITY_MODEL if want_quality else lobos.FAST_MODEL

    # Build your normal prompt, but add a tiny variation line to avoid duplicates
    prompt = lobos.build_prompt(profile_view).rstrip() + f"\n\nVariation ID: {variation_id}\n" \
             "Make this recipe meaningfully different from other variations."

    req_payload = lobos.request_payload_from_profile(profile_view)
    req_hash = lobos.hash_request(req_payload)
    prompt_hash = sha256_hex(prompt)

    response_text = lobos.call_ollama(model, prompt)
    title, preview = lobos.extract_title_and_preview(response_text)

    r = lobos.RecipeResult(
        user_id=user_id,
        created_at=lobos.now_ts(),
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


def main():
    ap = argparse.ArgumentParser(description="Seed Lobos recipe cache (N per variant).")
    ap.add_argument("--n", type=int, default=20, help="Recipes to generate per variant.")
    ap.add_argument("--user", type=str, default="seedbot", help="Seed user_id used for caching.")
    ap.add_argument("--quality", action="store_true", help="Use quality model instead of fast model.")
    ap.add_argument("--sleep", type=float, default=0.0, help="Sleep seconds between generations (rate limit).")
    ap.add_argument("--max-variants", type=int, default=0, help="If >0, only process first N variants.")
    args = ap.parse_args()

    with lobos.SessionLocal() as db:
        profile = ensure_seed_user(db, args.user)

        variants = get_variants(db)
        if args.max_variants and args.max_variants > 0:
            variants = variants[: args.max_variants]

        print(f"DB: {lobos.DATABASE_URL}")
        print(f"Ollama: {lobos.OLLAMA_BASE_URL}")
        print(f"Model: {lobos.QUALITY_MODEL if args.quality else lobos.FAST_MODEL}")
        print(f"Seed user: {args.user}")
        print(f"Variants: {len(variants)}")
        print(f"Target per variant: {args.n}")
        print()

        for vi, variant in enumerate(variants, start=1):
            profile_view = set_profile_variant(db, profile, variant)
            existing = count_existing_for_variant(db, args.user, profile_view)

            eating_style, meal_type, macro_preset, prep = variant
            label = f"[{vi}/{len(variants)}] {eating_style} | {meal_type} | {macro_preset} | {prep}"

            if existing >= args.n:
                print(f"{label} -> already has {existing} (skip)")
                continue

            to_make = args.n - existing
            print(f"{label} -> has {existing}, generating {to_make}...")

            for i in range(existing + 1, args.n + 1):
                r = generate_and_save_with_variation(
                    db=db,
                    user_id=args.user,
                    profile_view=profile_view,
                    want_quality=bool(args.quality),
                    variation_id=i,
                )
                print(f"  - {i}/{args.n}: id={r.id} title={r.title!r}")
                if args.sleep > 0:
                    time.sleep(args.sleep)

        print("\nDone.")


if __name__ == "__main__":
    main()