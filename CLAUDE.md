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
→ scripts/normalize.py (normalisation EPPO / ingrédients / produits sœurs, sans base)
→ scripts/load_db.py (charge les CSV dans PostgreSQL)
→ PostgreSQL : schéma dans db/schema.sql (tables ACTIVE_ENTITY, PRODUCT, PRODUCT_COMPONENT, PRODUCT_NAME,
  JURISDICTION, REGISTRATION, REGISTRATION_VERSION, AUTHORIZED_USE, APPLICATION_RULE, USE_CROP, USE_TARGET,
  SOURCE, SOURCE_SNAPSHOT, EVIDENCE). Connexion UNIQUEMENT via DATABASE_URL dans .env (jamais d'identifiants dans le code).
  docker-compose.yml permet de relancer la même base en local.
→ api/main.py (FastAPI, contrat EXACT de schema/openapi.yaml + /products/{id}/sisters + /export)
→ /ask : agent LLM à outils + garde-fous (citations d'ID vérifiées, chiffres vérifiés, résultat vide = message fixe)
→ frontend/ (Angular, coéquipier ; développe d'abord sur un mock Prism de openapi.yaml, puis l'API réelle sur :8000)
→ intégration Microsoft 365 (connecteur Power Automate / Copilot Studio, export Excel).

## Contrats à respecter
- Colonnes : data/field_dictionary.csv, data/products.csv, data/registrations.csv, data/uses.csv
- API : schema/openapi.yaml (ne pas le modifier)
- Évaluation : evaluation/gold_questions.csv, scripts/evaluate_submission.py

## Environnement
Windows / PowerShell, Python 3.11+, venv .venv. Équipe débutante : code simple, commenté, expliqué.