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

## État actuel (mis à jour 03:00)
- Contrat API de référence : openapi.proposed.yaml (v0.2.1, Damien), expliqué dans docs/openapi-changes.md. schema/openapi.yaml = contrat d'origine, compatible, ne pas modifier.
- API faite : backend/app/ (main.py, services.py, db.py lecture seule, models.py GÉNÉRÉ par datamodel-codegen, schemas.py). Lancement : uvicorn backend.app.main:app --port 3000. Tests : tests/test_api.py.
- ETL fait : backend/etl/normalize.py et load_db.py (--normalize-db pour normaliser les lignes déjà en base). Schéma réel : docs/db_schema.md.
- Base partagée : données réelles FR-EPHY (~13 500 produits), CA-PPID, DE-BVL. Données de test = is_synthetic=true (P-TEST-*), masquées par défaut.
- Adaptateurs des coéquipiers : backend/etl/adapters/ (base.py commun, fr_ephy.py, ca_ppid.py, de_bvl.py), écrivent directement en base.
- product_aliases.related_product_id (migration db/migrations/001_…) : lien EXACT vers le produit sœur ; ne JAMAIS joindre produits et sœurs par le nom.
- Pas de date d'expiration côté FR : utiliser status_normalized = withdrawn.
- Pas encore de clé IA : tout doit marcher en mode sans clé (mots-clés).

## État actuel (mis à jour 04:15)
- Contrat API de référence : openapi.proposed.yaml (v0.2.1, Damien), expliqué dans docs/openapi-changes.md. schema/openapi.yaml = contrat d'origine, ne pas modifier. Champs ajoutés hors contrat (à reporter par Damien) : matchedVia sur /products, generator.mode sur /ask.
- API : backend/app/ (main.py, services.py, db.py lecture seule, models.py GÉNÉRÉ par datamodel-codegen, schemas.py). Lancement : uvicorn backend.app.main:app --port 3000. Routes à la racine ET sous /api.
- Agent /ask : backend/app/agent.py + llm.py (pipeline 6 étapes, garde-fous dans le code). Sans clé IA → mode "keyword". scripts/run_gold.py donne 70/70 sur les vraies données.
- Tests : `python -m pytest -q` depuis la racine (pytest.ini limite la collecte à tests/).
- ETL : backend/etl/normalize.py et load_db.py. Ordre de rechargement : `python backend/etl/load_db.py --no-test` (références : sources, produits pilotes LPC, dictionnaires) → adaptateurs des pays → `python backend/etl/load_db.py --normalize-db`.
- Adaptateurs : backend/etl/adapters/france/ (Nhan), germany/ (Hanane), canada/ (Dyland) ; chacun a son propre base.py ; ils écrivent directement en base.
- Base partagée réinitialisée à 03:14 puis rechargée : FR-EPHY (~13 500 homologations), DE-BVL (~2 100), CA-PPID (5, uniquement produits contenant nos ingrédients). AUCUNE donnée de test en base (rechargé avec --no-test).
- product_aliases.related_product_id existe : lien EXACT vers le produit sœur ; ne JAMAIS joindre produits et sœurs par le nom.
- Normalisation : mappings LPC trop petits (33/608 cultures, 10/896 cibles reconnues) → dictionnaire IA data/ai_term_mapping.csv en cours (method "ai_suggested", review_status "to_verify").
- Pas de date d'expiration côté FR : utiliser status_normalized = withdrawn.
- ⚠️ Ne JAMAIS exécuter db/schema.sql ni db/reset_DANGER.sql sur la base partagée. Aucun DELETE/DROP/TRUNCATE.
- Frontend : Damien travaille sur une branche séparée, fusion dans main prévue avant 11:00.