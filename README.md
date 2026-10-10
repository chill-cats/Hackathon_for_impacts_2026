# LPC Global Regulatory AI Starter Kit

Starter repository for the Lallemand Plant Care challenge at Hackathon IA for Impact 2026.

## Mission
Build a functional proof of concept that collects, structures, normalizes and compares official plant protection product registration information across markets. Any technology may be used, but the result must expose a credible Microsoft 365 integration path.

## Minimum success criteria
1. Integrate at least **3 official sources** from at least **2 regions**.
2. Produce a product x country x use comparison.
3. Preserve original values alongside normalized values.
4. Cite the official source and collection timestamp for every regulatory assertion.
5. Make uncertainty, missing fields and validation status visible.
6. Demonstrate or document Microsoft 365 interoperability.
7. Deliver a repository restartable from this README without personal API keys.

> **Regulatory disclaimer:** This repository and any prototype built from it are not official regulatory sources. Extracted information requires Regulatory Affairs validation before official, commercial or operational use. No result must not be interpreted automatically as no registration.

## Repository map
```text
.
├── README.md / QUICKSTART.md / LICENSE.md / CONTRIBUTING.md
├── data/          # CSV templates and starter records
├── schema/        # Canonical model, JSON Schema and OpenAPI
├── evaluation/    # Rubric, gold questions and output contract
├── scripts/       # Data validation and scoring
├── business/      # Questions and glossary
├── sources/       # Source-use and attribution guidance
├── examples/      # Sample API and submission payloads
└── tests/         # Smoke test
```

## Start
```bash
git clone <repository-url>
cd lpc-global-regulatory-ai-starter
python -m venv .venv
# macOS/Linux: source .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1
cp .env.example .env
python scripts/validate_data.py
python scripts/evaluate_submission.py examples/sample_submission.json
```
No third-party Python package is required for the starter scripts.

## Before development
- Select the 3 official sources and 2 regions.
- Select pilot products or active entities.
- Document the normalization and human-review workflow.
- Choose the Microsoft 365 integration mechanism.
- Test every access and prepare a frozen fallback extract.

## Data rules
- Never modify `*_original` values.
- Put transformations in `*_normalized` fields.
- Regulatory assertions require `source_id`, `source_record_url`, `collected_at` and `validation_status`.
- Use `unknown` or `not_found` rather than inventing information.
- Sister-product matches are hypotheses until reviewed.
- Synthetic data must use `is_synthetic=true`.

## Canonical contract
- Field definitions: `data/field_dictionary.csv`
- Data model: `schema/canonical_data_model.md`
- JSON Schema: `schema/canonical.schema.json`
- Minimal API: `schema/openapi.yaml`

Teams may extend the contract but must not silently remove traceability fields.

## EPPO mappings
The included mapping files are deliberately small. Candidate codes are marked `to_verify`; teams must verify them against EPPO before changing the status to `validated`.

## Microsoft 365 interoperability
Demonstrate or document at least one: REST API importable as a custom connector, Dataverse export, SharePoint/Power Automate JSON or CSV flow, Copilot Studio action, Azure/Entra ID design, or Teams/SharePoint interface.

## Final checklist
- [ ] Solution starts from a clean machine using the README.
- [ ] No personal secret is required.
- [ ] Sources, licences and limits are documented.
- [ ] Official, derived and synthetic data are distinguishable.
- [ ] API or export follows the documented contract.
- [ ] Evaluation script runs.
- [ ] Known limitations and regulatory disclaimer are visible.
- [ ] Microsoft 365 integration is demonstrated or documented.
---

## Stack Docker et front (ajout de l'équipe)

Le front Angular et le `docker-compose.yml` viennent du coéquipier front. Dossiers cibles : `frontend/` et `backend/`
(renommage de `front/` et `back/` en cours). Les commandes ci-dessous sont reprises telles quelles de son README.

# Hackathon Lallemand

```
.
├── frontend/            Angular 22 + Tailwind 4 + Spartan NG (front only, pnpm)
├── backend/             Backend (techno à définir)
├── docker-compose.yml   Lance toute la stack (commenté, à lire !)
├── .env.example         Modèle des variables d'environnement (front + back + docker)
└── .env                 Tes valeurs locales (non commité)
```

## Démarrage

```bash
cp .env.example .env          # 1 fois, puis ajuster les valeurs

# Option A - tout avec Docker (comme en production)
docker compose up -d --build  # front sur http://localhost:8080

# Option B - dev front avec rechargement à chaud
cd frontend && pnpm install && pnpm start   # http://localhost:4200
```

Quand le back existera : `docker compose --profile backend up -d --build`.

## Variables d'environnement

Un seul fichier : `.env` à la racine.
- Docker Compose et le back le lisent directement.
- Angular ne lit pas les `.env` : `frontend/scripts/generate-env.mjs` (lancé automatiquement par `pnpm start/build/test`) convertit les variables `FRONT_*` en `frontend/src/environments/environment.ts` (fichier généré, non commité).
- Tout ce qui est `FRONT_*` est public (embarqué dans le JS du navigateur) : aucun secret.

Ajouter une variable front : la déclarer `FRONT_XXX` dans `.env.example` et `.env`, l'ajouter dans `generate-env.mjs`, et dans les `args` du service `frontend` (`docker-compose.yml`) + `ARG/ENV` du `frontend/Dockerfile`.

## Déployer sur un serveur (rappel Docker)

1. Installer Docker + le plugin compose sur le serveur, cloner le repo.
2. `cp .env.example .env` et **changer les mots de passe**.
3. `docker compose --profile backend up -d --build`
4. Mise à jour : `git pull && docker compose --profile backend up -d --build`

Le front appelle `/api/...` : nginx (dans le conteneur front) redirige vers le service `backend`.

## UI : Tailwind + Spartan NG

- Styles globaux dans `frontend/src/styles.css` (Tailwind 4 + thème Spartan, via `.postcssrc.json`).
- Les composants Spartan sont **copiés dans le repo** (`frontend/src/app/ui/`, modifiables) et importés via l'alias `@spartan-ng/helm/<composant>`.
- Ajouter un composant : `cd frontend && pnpm exec ng g @spartan-ng/cli:ui <nom>` (ex : `input`, `dialog`).
