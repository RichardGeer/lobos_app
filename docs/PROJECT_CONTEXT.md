# Lobos Project Context

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

