# Lobos Project Context

Last Updated: 2026-03-12

This document summarizes the current development state of the Lobos system so development threads can resume quickly with full context.

---

# Project Goal

Lobos is a GLP-1 nutrition personalization platform that:

• integrates with WordPress membership  
• authenticates users via JWT SSO  
• stores user nutrition preferences  
• generates GLP-1-aware recipes  
• adapts recipes based on symptoms and preferences  
• minimizes AI cost via global recipe caching

---

# Current Architecture

WordPress
↓
JWT SSO
↓
FastAPI Backend
↓
Preferences API
↓
Postgres Database
↓
Recipe Generation Engine (planned)

---

# Current Working Features

WordPress

• JWT SSO login working

FastAPI

• `/login` endpoint working  
• `/landing` endpoint working  
• identity display working  
• preferences API working  

User Preferences

• allergies checkbox system implemented  
• onboarding completion flag implemented  
• save preferences working  

Admin

• debug endpoints implemented

---

# Database

Schema snapshots are stored here:

docs/currentDBschema.sql  
docs/currentDBtables.txt  

These files are generated using:

```bash
sudo -u postgres pg_dump -d lobos_db --schema-only > docs/currentDBschema.sql
./scripts/export_db_schema.sh

Near-Term Improvements

UI

• convert height input from inches → feet + inches
• restore eating style dropdown options
• minor UI improvements

Data Model

• design GLP-1 dosage tracking
• support future weight history tracking

Major Upcoming Feature

Recipe generation system.

Goals:

• minimize AI API usage
• cache reusable recipes globally
• reuse recipes across users with similar preferences

Key Design Direction

Recipe generation will use a variant caching system.

Instead of generating recipes per user request, Lobos will:

normalize request into a recipe variant

check if recipes already exist for that variant

reuse cached recipes if available

generate new recipes only if needed

store recipes for global reuse

Deduplication Strategy

Recipes should not be too similar.

When generating recipes:

compute a normalized recipe signature

compare with existing recipes in the same variant

reject near-duplicates

store only distinct recipes

Semantic similarity checks may use embeddings in the future.

Vector Support (Planned)

Future recipe ingestion may include:

• AI generated recipes
• imported PDF recipes
• imported text recipes

Vector embeddings may be used for:

• duplicate detection
• recipe similarity search

Schema will be designed to support vectors but vector pipelines will be implemented later.

References

API design reference:

docs/Lobos Recommended API shape.pdf
