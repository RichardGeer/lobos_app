
---

# 2️⃣ Paste into `docs/ARCHITECTURE.md`

This file explains **how the system is supposed to work**, not the current state.

```markdown
# Lobos Architecture

This document describes the system architecture and major design decisions.

---

# High Level System

WordPress
↓
JWT SSO Authentication
↓
FastAPI Backend
↓
Postgres Database
↓
Recipe Generation Engine
↓
Recipe Cache

---

# Identity Model

Users authenticate through WordPress.

WordPress sends a JWT token containing:

• user id  
• email  
• name  
• membership information

FastAPI validates the token and maps it to a Lobos user.

Primary tables:

• lobos_users  
• external_identities

---

# User Preferences Model

User preferences are stored in:

user_preferences

Examples:

• weight  
• goal weight  
• height  
• allergies  
• eating style  
• GLP-1 stage  
• dosage information  

Preferences can be updated after onboarding.

---

# Recipe Variant System

Recipe generation uses **variant caching**.

A variant represents a normalized combination of inputs:

Examples:

• meal type  
• eating style  
• dietary preference  
• activity level  
• macro target  
• GLP-1 stage  
• symptoms  
• preparation style

Each unique combination maps to a single variant.

Multiple users may reuse the same variant.

---

# Recipe Variant Cache

Recipes are cached globally per variant.

Variant table concept:

recipe_variants

Stores:

• normalized variant definition  
• request count  
• cached recipe count  
• last generation time

---

# Recipe Generation Queue

Background workers generate recipes when needed.

Queue table concept:

recipe_variant_queue

Reasons for queueing:

• new variant created  
• cache below threshold  
• recipes marked stale

Workers:

1. pull queue job
2. generate recipes
3. run deduplication checks
4. store results
5. update variant cache status

---

# Recipe Storage

Recipes are stored in:

recipe_results

Recipes are associated with:

• a variant  
• generation request metadata

---

# Recipe Deduplication

When generating recipes:

1. create normalized recipe signature
2. compare with existing recipes in the same variant
3. reject duplicates
4. accept only distinct recipes

Future improvement:

semantic similarity detection using embeddings.

---

# Embedding Support (Future)

Possible future table:

recipe_embeddings

Used for:

• semantic search
• duplicate detection
• recommendation systems

Embeddings may be generated from:

• recipe title
• ingredient list
• instructions
• normalized recipe description

---

# Long Term System Vision

Future capabilities:

• symptom-aware recipe generation  
• GLP-1 stage aware nutrition  
• adaptive recipe recommendations  
• weight trend tracking  
• meal history tracking  
• AI-driven nutrition personalization

---

# Development Philosophy

Priorities:

1. minimize AI API cost  
2. maximize recipe reuse  
3. keep schema extensible  
4. support future AI personalization
