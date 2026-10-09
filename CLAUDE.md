# Contexte projet — Hackathon IA for Impact 2026, défi Lallemand Plant Care

## Le sujet
Lallemand Plant Care (LPC) fabrique des microorganismes (champignons, bactéries) qui protègent les plantes.
Chaque pays publie ses homologations de produits de protection des plantes (PPP) dans sa propre base,
avec sa langue et son format. LPC veut un prototype d'agent IA qui collecte, normalise, compare et restitue
ces homologations (produit × pays × usage), interrogeable en langage naturel, avec la source de chaque donnée.
C'est une preuve de concept, pas un système réglementaire officiel.

## Périmètre MVP
- Sources : Canada (Santé Canada PPID, CSV, source_id CA-PPID), France (ANSES E-Phy open data, CSV/XML, FR-EPHY),
  Allemagne (BVL PSM API, JSON, DE-BVL). Plan B si l'Allemagne bloque : US EPA PPLS API.
- Produits pilotes (chercher par ingrédient, pas seulement par marque) :
  - LALSTOP CONTANS WG → Coniothyrium minitans (souche CON/M/91-08)
  - LALSTOP G46 WG → Clonostachys rosea J1446 (ancien nom : Gliocladium catenulatum J1446)
  - LALGUARD M52 OD → Metarhizium brunneum F52 / Ma 43 (anciens noms : Metarhizium anisopliae, M. anisopliae var. anisopliae)

## Règles non négociables (exigences LPC)
1. Chaque donnée réglementaire a : source_id, source_record_url, collected_at (UTC ISO 8601), validation_status.
2. Aucune donnée inventée. Absent = vide / "unknown" / "not_found".
3. Une absence de résultat n'est JAMAIS une preuve d'absence d'homologation.
4. Ne jamais modifier les colonnes *_original ; les transformations vont dans *_normalized.
5. Produits sœurs = hypothèses (review_status "to_verify") tant que non validées.
6. Données fictives : is_synthetic=true, toujours visibles.
7. Aucune clé d'API personnelle requise : le prototype doit tourner sans clé IA (mode dégradé).
8. Fournisseur d'IA interchangeable via .env (AI_BASE_URL, AI_API_KEY, AI_MODEL).
9. Le dépôt doit se relancer depuis le seul README.
10. Ne pas contourner authentification, quotas ou restrictions des sources ; ne pas scraper si une API/un téléchargement officiel existe.

## Architecture
sources officielles → scripts/ingest_xx.py (coéquipiers) → data/incoming/xx_*.csv (format du starter kit)
→ backend/etl/normalize.py (normalisation EPPO / ingrédients / produits sœurs, sans base)
→ backend/etl/load_db.py (charge les CSV dans PostgreSQL)
→ PostgreSQL (serveur d'équipe, URL dans DATABASE_URL du .env ; jamais d'identifiants dans le code).
  Tables = celles du starter kit : products, product_aliases, registrations, uses, source_registry,
  eppo_crop_mapping, eppo_pest_mapping, active_entity_mapping, product_name_mapping
  + collection_runs (journal des collectes) + field_evidence (preuve champ par champ, confiance, méthode, modèle)
  + vue v_comparison (tableau produit × pays × usage). Schéma exporté dans db/schema.sql.
→ backend/app/ (FastAPI) : contrat EXACT de schema/openapi.yaml + /products/{id}/sisters + /export.
  Routes exposées à la fois à la racine (/products…) et sous /api (/api/products…) car le nginx du frontend transmet /api/ sans retirer le préfixe.
  Port = variable BACK_PORT (défaut 3000). backend/Dockerfile pour docker compose (profil "backend").
→ /ask : agent LLM à outils + garde-fous (citations d'ID vérifiées, chiffres vérifiés, résultat vide = message fixe)
→ frontend/ (Angular, Damien) : appelle /api/... ; développe d'abord sur un mock Prism de schema/openapi.yaml.
→ intégration Microsoft 365 (connecteur Power Automate / Copilot Studio, export Excel).
Ne pas toucher frontend/ (sauf demande explicite). Ne pas modifier les fichiers du starter kit.

## Contrats à respecter
- Colonnes : data/field_dictionary.csv, data/products.csv, data/registrations.csv, data/uses.csv
- API : schema/openapi.yaml (ne pas le modifier)
- Évaluation : evaluation/gold_questions.csv, scripts/evaluate_submission.py

## Environnement
Windows / PowerShell, Python 3.11+, venv .venv. Équipe débutante : code simple, commenté, expliqué.