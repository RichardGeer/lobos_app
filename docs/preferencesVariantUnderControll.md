The most important improvement is:

# Separate preferences into 2 layers

Do **not** let every raw user preference create a brand new cache variant.

Instead, split into:

* **cacheable core variant**
* **user-specific overlay**

That is the key to preventing variant explosion.

---

# The problem

If `variant_key` includes every preference field, you will explode the number of variants.

Example:

* high protein
* low carb
* shellfish allergy
* hates cilantro
* mild spice
* soft texture
* breakfast only
* no mushrooms
* no reheated food
* prefers Asian
* GLP-1 early phase
* 20-minute prep
* air fryer only

If all of that goes into the variant hash, then even tiny differences create a new bucket.

You end up with:

* too many variants
* too few recipes per variant
* weak cache reuse
* too many AI calls
* queue bloat

---

# Better design

## 1) Core variant

Only include fields that materially change the recipe pool.

Examples:

* goal
* eating_style
* allergies
* major diet restrictions
* meal_type
* glp1_phase
* calorie band
* protein target band

These are **cache-worthy**.

---

## 2) Overlay filters

Keep softer or highly personalized preferences out of the main variant hash.

Examples:

* dislikes cilantro
* prefers crunchy texture
* wants quick meals today
* air fryer preferred
* avoid leftovers
* cuisine preference
* ingredient mood of the day
* “something cozy”
* free-form prompt text

These should be applied as:

* post-filtering
* ranking
* prompt overlay during on-demand generation

But **not** as part of the reusable global variant identity.

---

# Rule of thumb

Ask this for every field:

**Does this meaningfully define a reusable recipe pool across many users?**

If yes, put it in `canonical_json` for `variant_key`.

If no, keep it out of the cache key and treat it as an overlay.

---

# Example

## Bad variant key input

```json
{
  "goal": "weight_loss",
  "eating_style": "high_protein",
  "allergies": ["shellfish"],
  "meal_type": "dinner",
  "glp1_phase": "early",
  "dislikes": ["cilantro"],
  "spice_level": "mild",
  "cook_time_minutes": 20,
  "cuisine": "asian",
  "texture_preference": "soft",
  "free_text": "something warm and comforting tonight"
}
```

This is too specific.

---

## Better split

### Core canonical JSON

```json
{
  "goal": "weight_loss",
  "eating_style": "high_protein",
  "allergies": ["shellfish"],
  "meal_type": "dinner",
  "glp1_phase": "early",
  "cook_time_band": "under_30"
}
```

### Overlay

```json
{
  "dislikes": ["cilantro"],
  "spice_level": "mild",
  "cuisine": "asian",
  "texture_preference": "soft",
  "free_text": "something warm and comforting tonight"
}
```

Now many users can share the same core cache, while still getting personalized results.

---

# Why this is powerful

This gives you:

* much higher cache hit rate
* fewer variant rows
* fewer queue jobs
* more recipes per useful variant
* less AI spend
* better long-term scalability

This is probably the single biggest lever in the system.

---

# Recommended schema improvement

Your current `recipe_variants` table already has:

* `preference_json`
* `canonical_json`

That is good.

I would now define them like this:

* `preference_json` = full original preference set
* `canonical_json` = **core cacheable fields only**

And optionally add:

```sql
ALTER TABLE recipe_variants
    ADD COLUMN IF NOT EXISTS overlay_json JSONB NULL;
```

Though this is optional. You may not need to store overlay at the variant level if overlay is request-specific.

---

# Even better: use bands, not exact values

Another strong protection against variant explosion:

## Bucket numeric values

Do not hash exact numbers like:

* 1370 calories
* 118g protein
* 23g fiber

Convert them to bands:

* calories: `1200_1500`
* protein: `100_130`
* fiber: `20_30`

Same for:

* prep time → `under_15`, `under_30`, `under_45`
* spice → `mild`, `medium`, `high`
* portion size → `small`, `medium`, `large`

That dramatically reduces fragmentation.

---

# Best practical model for Lobos

## Put in core variant key

Good candidates:

* meal type
* eating style
* major allergies
* major exclusions with medical importance
* GLP-1 phase / tolerance band
* macro/calorie bands
* maybe prep-time band

## Keep out of core variant key

Better as overlay:

* dislikes
* cuisine preference
* one-off free-text requests
* texture preference
* mood-based requests
* appliance preference
* “today” requests
* small cosmetic wording differences

---

# Queue strategy improvement

Queue by **core variant only**.

That means:

* fill reusable shared pools in background
* handle overlays at request time by filtering/ranking existing recipes
* only do fresh AI generation if overlay makes the cache unusable

This is much better than queueing every custom request.

---

# Dedup benefit too

This also improves dedup.

Why:

* more recipes live in the same meaningful pool
* duplicate detection becomes more effective
* you avoid duplicate recipes spread across near-identical micro-variants

---

# Concrete recommendation

I would define two functions:

## 1) `build_core_variant_json(preferences)`

Returns only cacheable fields.

## 2) `build_overlay_json(preferences)`

Returns personalization fields not used in `variant_key`.

Then:

* `variant_key = hash(core_variant_json)`
* queue and cache operate on core variant
* overlay affects ranking/filtering/prompting

---

# Simple example flow

User asks for:

* high protein dinner
* shellfish allergy
* mild spice
* hates cilantro
* wants Asian flavors
* soft texture

System does:

1. build core variant:

   * high protein
   * shellfish allergy
   * dinner

2. find cached recipes for that variant

3. overlay filter/rank:

   * remove cilantro
   * prefer mild spice
   * prefer Asian
   * prefer soft texture

4. if enough good matches exist:

   * return from cache

5. if not:

   * do targeted AI generation using core + overlay

This prevents creating a whole new permanent variant just because the user hates cilantro.

---

# My recommended wording for PROJECT_CONTEXT.md

```md
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
```

This is the right next design decision before writing the worker and hashing helpers.
