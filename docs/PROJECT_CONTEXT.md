# Lobos Project Context


# Recipe Engine - Next Design Layer

We are adding a reusable recipe variant and async queue layer so recipe generation can be cached globally, not only per user.

## New DB Objects

### recipe_variants
Stores normalized preference variants that define a reusable recipe lane.

Key fields:
- `variant_key`
- `preference_json`
- `canonical_json`
- `recipe_count`
- `status`

### recipe_variant_queue
DB-backed worker queue for async recipe backfill.

Key behavior:
- one active queue job per variant/job type
- supports retry, locking, and target recipe count

### recipe_results additions
We are extending `recipe_results` with:
- `variant_id`
- `recipe_key`
- `title_norm`
- `body_norm`
- `ingredient_signature`
- `distance_score`
- `source_hash`

## Dedup Strategy

We will dedup before insert.

Flow:
1. generate recipe candidate
2. normalize title, ingredients, and body
3. compute `ingredient_signature`
4. compute `source_hash`
5. compare to existing accepted recipes for the same variant
6. if too similar:
   - log duplicate details for debugging
   - discard candidate
7. if unique:
   - insert into `recipe_results`

Important:
- duplicate candidates are not stored in the DB
- duplicate candidates may be logged to file/app logs for debugging
- embeddings can be added later if needed

## Background Worker Direction

We will start with a Postgres-backed queue worker.

Worker flow:
1. poll `recipe_variant_queue`
2. lock next queued job using `FOR UPDATE SKIP LOCKED`
3. load variant
4. count accepted recipes for that variant
5. generate missing recipes
6. run quality check + dedup before insert
7. insert accepted recipes
8. update variant counts and queue status


This file provides the current development context for the Lobos GLP-1 nutrition system.

Last updated: 2026-03-11

---

# Project Goal

Lobos is a GLP-1 nutrition personalization system that:

• integrates with WordPress membership  
• authenticates via JWT SSO  
• stores preferences and health context  
• generates GLP-1 aware recipes  
• adapts meals based on symptoms and progress  

---

# Current Architecture

WordPress
↓
JWT SSO
↓
FastAPI
↓
Preferences API
↓
Postgres
↓
Recipe Generation Engine

---

# Current Progress

Working:

• WordPress JWT SSO  
• FastAPI `/login` endpoint  
• FastAPI `/landing` endpoint  
• identity display  
• preferences API  
• allergies checkbox system  
• onboarding completion flag  
• save preferences  
• admin + debug routes  

---

# Database

Schema snapshots:

docs/currentDBschema.sql  
docs/currentDBtables.txt  

Generated with:
sudo -u postgres pg_dump -d lobos_db --schema-only > docs/currentDBschema.sql
./scripts/export_db_schema.sh


---

# Major Tables

Core identity:

• lobos_users  
• external_identities  

User data:

• user_preferences  
• user_allergies  

Recipe system:

• recipe_generations  
• recipe_results  

---

# Upcoming Features

Short term:

• height UI (feet + inches)
• eating style dropdown fix
• GLP-1 dosage tracking design
• minor UI improvements

Next major milestone:

Recipe generation system.

---

# Long Term Vision

Future Lobos capabilities:

• symptom-aware recipe generation  
• GLP-1 stage aware nutrition  
• weight trend tracking  
• adaptive meal recommendations  
• AI-driven personalization  

---

# Design References

docs/Lobos Recommended API shape.pdf


Next time you start a new thread

Just send:

Project context:
https://github.com/RichardGeer/lobos_app/blob/main/docs/PROJECT_CONTEXT.md

and we will immediately resume.

Next session we will likely do

1️⃣ DB migration for recipe variants
2️⃣ DB migration for variant queue
3️⃣ recipe dedup structure
4️⃣ background worker design

This will basically build the core of the Lobos recipe engine.

