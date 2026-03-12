# Lobos Project Context
## Important Variant Design Rule

To prevent variant explosion, Lobos should separate recipe preferences into:

- core cacheable variant fields
- user-specific overlay fields

The `variant_key` should be generated only from the normalized core variant fields.

Examples of core fields:
- eating style
- meal type
- major allergies
- GLP-1 phase
- macro/calorie bands

Examples of overlay fields:
- dislikes
- cuisine preference
- texture preference
- appliance preference
- free-form request text

This allows many users to share the same cached recipe pool while still supporting personalization at request time.

# Recipe Engine Progress Update

Last Updated: 2026-03-12 14:08 PST

## Completed

Recipe engine database migration has been successfully applied.

### New Tables

recipe_variants  
Stores reusable normalized preference variants so recipes can be cached globally across users.

recipe_variant_queue  
Database-backed queue used for asynchronous recipe generation and cache backfill.

### recipe_results Extensions

The following columns were added to support dedup and variant mapping:

- variant_id
- recipe_key
- title_norm
- body_norm
- ingredient_signature
- distance_score
- source_hash

Indexes were also added to support fast lookup during dedup checks.

## Dedup Strategy

Recipe deduplication happens **before database insert**.

Workflow:

1. AI generates recipe candidate
2. title / ingredients / body are normalized
3. ingredient_signature is computed
4. source_hash is computed
5. existing recipes for the same variant are checked
6. if similarity is too high:
   - duplicate candidate is logged
   - candidate is discarded
7. otherwise recipe is inserted

Duplicate candidates are **not stored in the database** to avoid table bloat.

## Recipe Variant Architecture

recipe_variants defines reusable preference variants so multiple users with similar preferences can share a cached recipe pool.

recipe_variant_queue provides a Postgres-backed job queue so variants can be asynchronously filled with recipes by a background worker.

This architecture allows:

- global recipe caching
- async recipe generation
- dedup before insert
- future support for vector similarity if needed

## Next Development Steps

1. Implement variant canonicalization helpers
2. Generate variant_key hash from canonical JSON
3. Add enqueue logic when variant recipe count is low
4. Implement background worker
5. Implement dedup helpers before insert

# Recipe Engine Progress Update

Last updated: 2026-03-12

## Completed
Recipe engine DB migration has been applied successfully.

### New tables added
- `recipe_variants`
- `recipe_variant_queue`

### `recipe_results` columns added
- `variant_id`
- `recipe_key`
- `title_norm`
- `body_norm`
- `ingredient_signature`
- `distance_score`
- `source_hash`

## Current design direction

### recipe_variants
Stores reusable normalized preference variants so recipes can be cached globally across users, not only per user.

### recipe_variant_queue
Acts as a Postgres-backed async queue for recipe backfill jobs.  
Goal: avoid duplicate active jobs for the same variant and support background cache generation.

### recipe dedup
Dedup will happen before insert.

Planned flow:
1. generate candidate recipe
2. normalize title, ingredients, and body
3. compute `ingredient_signature`
4. compute `source_hash`
5. compare against accepted recipes for the same variant
6. if too similar, log duplicate details and discard
7. if unique, insert into `recipe_results`

Important:
- duplicate candidates are not stored in DB
- duplicate candidates may be logged for debugging
- this avoids DB bloat while still allowing dedup tuning later

## Next likely work
1. Python helper functions for variant normalization and hashing
2. enqueue logic from app request flow
3. background worker design and implementation
4. recipe dedup helper logic before insert
5. decide direct-request behavior when cache is low

## New thread starter
Project context:
https://github.com/RichardGeer/lobos_app/blob/main/docs/PROJECT_CONTEXT.md

We already completed the DB migration for:
- recipe variants
- variant queue
- recipe_results dedup-related columns

Next, continue with:
1. variant key / canonical JSON helpers
2. queue enqueue logic
3. worker skeleton
4. dedup helper functions

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

