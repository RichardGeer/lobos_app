BEGIN;

-- ============================================================
-- 1) recipe_variants
-- Reusable normalized preference variants for global recipe cache
-- ============================================================

CREATE TABLE IF NOT EXISTS recipe_variants
(
    id BIGSERIAL PRIMARY KEY,
    variant_key TEXT NOT NULL UNIQUE,
    variant_version INTEGER NOT NULL DEFAULT 1,
    name TEXT NULL,
    source_type TEXT NOT NULL DEFAULT 'system',
    preference_json JSONB NOT NULL,
    canonical_json JSONB NOT NULL,
    recipe_count INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'active',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_generated_at TIMESTAMPTZ NULL
);

CREATE INDEX IF NOT EXISTS idx_recipe_variants_status
    ON recipe_variants(status);

CREATE INDEX IF NOT EXISTS idx_recipe_variants_updated_at
    ON recipe_variants(updated_at);

CREATE INDEX IF NOT EXISTS idx_recipe_variants_canonical_json_gin
    ON recipe_variants
    USING GIN(canonical_json);

-- ============================================================
-- 2) recipe_variant_queue
-- DB-backed async queue for filling a variant with recipes
-- ============================================================

CREATE TABLE IF NOT EXISTS recipe_variant_queue
(
    id BIGSERIAL PRIMARY KEY,
    variant_id BIGINT NOT NULL REFERENCES recipe_variants(id) ON DELETE CASCADE,
    job_type TEXT NOT NULL DEFAULT 'backfill_recipes',
    priority INTEGER NOT NULL DEFAULT 100,
    status TEXT NOT NULL DEFAULT 'queued',
    target_recipe_count INTEGER NOT NULL DEFAULT 20,
    attempt_count INTEGER NOT NULL DEFAULT 0,
    max_attempts INTEGER NOT NULL DEFAULT 5,
    locked_by TEXT NULL,
    locked_at TIMESTAMPTZ NULL,
    available_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    started_at TIMESTAMPTZ NULL,
    finished_at TIMESTAMPTZ NULL,
    last_error TEXT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_recipe_variant_queue_status_priority
    ON recipe_variant_queue(status, priority, available_at, created_at);

CREATE INDEX IF NOT EXISTS idx_recipe_variant_queue_variant_id
    ON recipe_variant_queue(variant_id);

CREATE UNIQUE INDEX IF NOT EXISTS uq_recipe_variant_queue_active_job
    ON recipe_variant_queue(variant_id, job_type)
    WHERE status IN ('queued', 'running');

-- ============================================================
-- 3) Extend recipe_results
-- Keep only accepted recipes in DB; duplicate candidates are logged
-- and discarded before insert
-- ============================================================

ALTER TABLE recipe_results
    ADD COLUMN IF NOT EXISTS variant_id BIGINT NULL REFERENCES recipe_variants(id);

ALTER TABLE recipe_results
    ADD COLUMN IF NOT EXISTS recipe_key TEXT NULL;

ALTER TABLE recipe_results
    ADD COLUMN IF NOT EXISTS title_norm TEXT NULL;

ALTER TABLE recipe_results
    ADD COLUMN IF NOT EXISTS body_norm TEXT NULL;

ALTER TABLE recipe_results
    ADD COLUMN IF NOT EXISTS ingredient_signature TEXT NULL;

ALTER TABLE recipe_results
    ADD COLUMN IF NOT EXISTS distance_score NUMERIC(8,6) NULL;

ALTER TABLE recipe_results
    ADD COLUMN IF NOT EXISTS source_hash TEXT NULL;

CREATE INDEX IF NOT EXISTS idx_recipe_results_variant_id
    ON recipe_results(variant_id);

CREATE INDEX IF NOT EXISTS idx_recipe_results_source_hash
    ON recipe_results(source_hash);

CREATE INDEX IF NOT EXISTS idx_recipe_results_ingredient_signature
    ON recipe_results(ingredient_signature);

COMMIT;
