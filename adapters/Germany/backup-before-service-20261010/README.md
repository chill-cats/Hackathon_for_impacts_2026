# Germany BVL adapter

Python 3.10+ standard library. Collects official BVL JSON, joins product/use tables, and exports CSV observations plus two **explicitly separate** PostgreSQL loaders. It does not connect to your application database or publish regulatory approvals.

## Run

```sh
# A bounded live pilot (repeat --registration for more registrations).
python3 run_de.py --registration 034346-00 --out out/contans
# Omit --registration to collect all records; pagination must finish successfully.

# Fictional demonstration: manifest explicitly marks synthetic=true.
python3 run_de.py --offline fixtures/de --out out/demo

# Replay actual unchanged API pages; original collection times and hashes survive.
python3 run_de.py --offline out/contans --out out/contans-replay

python3 -m unittest discover -s tests -v
```

Output directories must be new. Export is staged and renamed only after conversion and validation succeed. Failed downloads, malformed JSON and incomplete pagination do not publish a CSV export. No private key is required. `BVL_API_BASE` may override the HTTPS API root.

`python3 verify_de.py --out out/verification` runs the same real joins for CONTANS and produces a technical verification report plus replayable export. It never marks licence terms or regulatory facts as human-validated.

## Choose the correct loader

There are two contracts in the starter repository: the flat tables used by the France importer and the versioned `regulatory` schema in `schema/postgresql.sql`. **Use exactly one loader for the schema your database actually has.**

From inside the generated export directory:

```sh
# France-compatible flat schema, already installed in your database:
psql "$DATABASE_URL" -f load-flat.sql

# OR the checked-in schema/postgresql.sql, already installed:
psql "$DATABASE_URL" -v actor_subject="$ACTOR_SUBJECT" -f load-regulatory.sql
```

Set `ACTOR_SUBJECT` to the authenticated importing user/service subject for the regulatory loader; it records audit events in the same transaction.

Both loaders are **initial imports**, not incremental synchronization. Duplicate product/registration identities fail and roll back the entire transaction. Use a separate database or an explicitly reviewed migration for a later snapshot of an already imported product. Reference source metadata can be reused without overwriting it.

Flat output columns match `scripts/ingest_france.py`: products, registrations, uses, product_aliases, source_registry, field_evidence and collection_runs. Products, registrations and uses have `validation_status=automatically_extracted`. The evidence and collection-run generated IDs are omitted from CSV so PostgreSQL assigns them. Collection-run status describes conversion coverage, not human review. No automatic product aliases are asserted.

The regulatory loader creates UUID identities, version 1 registration drafts, authorized-use drafts, application rules, original crop/target text, ingestion runs, immutable source snapshots, extractions, evidence links, coverage information and audit events for imported entities. Review status is `to_verify`, not the flat extraction-status enum. It leaves `published_at` and effective dates unset: approval date alone does not establish a version's effective interval. Unreviewed imports therefore remain absent from the published current-use view. Names and active-substance source data remain in the export/extractions; normalized concept/entity identities require review and are not guessed.

`source_snapshot.storage_uri` is the relative `raw/...` path inside the export bundle. Preserve the entire bundle; resolve these paths relative to it. For production object storage, upload the raw pages and replace storage URIs **before** executing the loader, because loaded snapshots are immutable.

## Source joins and semantics

- `mittel.kennr` identifies the market product and registration. Source-scoped IDs preserve leading zeros and punctuation. `--names` only produces candidate warnings; it never merges sister products, other-country candidates or related formulations.
- `wirkstoff_gehalt.kennr → mittel.kennr`, then `wirkstoff_gehalt.wirknr → wirkstoff.wirknr` supplies active-substance names. Exact source component rows and concentrations remain in evidence.
- `awg.kennr → mittel.kennr`; `awg_kultur`, `awg_schadorg`, `awg_aufwand`, `awg_wartezeit` and `awg_zeitpunkt` join through `awg_id`. `auflagen.ebene` links registration- or use-level conditions.
- German `kode` rows decode namespaced BVL crop, target, technique, dose-unit, timing and restriction codes. These extended BVL crop/target codes are **not automatically declared validated EPPO codes**. English translations and normalized active entities remain empty.
- Crop and target rows marked `ausgenommen=J` are exclusions, never affirmative authorizations. Exclusions, conditions, growth stages, water volumes, interval ranges, timing and waiting-period records remain in `restrictions_original` and evidence. Conditions requiring manual interpretation are not turned into guessed numbers.
- The flat schema has one scalar dose/crop/target per row. Each included crop × target × dose alternative becomes its own row with the parent BVL use ID in evidence. Count distinct `source.awg.awg_id` for BVL use counts, rather than flat output rows. Identifiers use logical source keys/content and duplicate occurrence counts, independent of response ordering or Oracle physical row locators. An edited dose alternative produces a new content identity.
- Scalars must be finite and nonnegative; application counts must be integers. A dose without a recognized unit stays in evidence instead of becoming a unitless numeric assertion. Conditional or conflicting waiting periods remain unnormalized.
- `zul_erstmalig_am`, `zul_ende` and `formulierung_art` are handled. BVL UTC date-boundary timestamps are converted to the Europe/Berlin calendar date; original timestamp strings remain in evidence. Invalid or contradictory dates are omitted with warnings.
- Status matching is exact. No recognized source status means `unknown`, even if the product appears in the API or has a future expiration. Negated wording never matches `active` by substring. No result is not proof of no registration.

## Evidence, synthetic data and replay

Every raw API page is saved unchanged with its exact requested HTTPS URL, retrieval time and SHA-256 in `manifest.json`. Field evidence identifies the source page and JSON item index. Registrations retain the actual product-response URL and collection time; use assertions cite the separate joined source responses through evidence. JSON is never truncated.

Replay requires a manifest with explicit boolean `is_synthetic`, `complete=true` for its declared scope, and `responses` entries containing `collection`, `file`, `source_url`, timezone-aware `collected_at` and `sha256`. File hashes are verified. A renamed folder cannot change real/synthetic classification, and replay never substitutes its execution time for the original retrieval time. The bundled fictional fixture timestamps are synthetic, not observed BVL collection times.

Missing collections in a deliberately limited replay are visible as incomplete coverage. Preserve and read `de_warnings.json`, `manifest.json` and `validation_report.json` alongside the CSVs. Source scope is not a claim to capture every BVL endpoint, legal decision or label condition. Review source documents before operational use. Confirm current BVL reuse/attribution terms before redistributing data; the adapter leaves `manual_validation_required=true`.

## Integration test

This opt-in test uses a locally available `postgres:17` Docker image. It creates and removes an isolated container with no network and does not access an application database:

```sh
python3 tests/db_smoke.py \
  --schema /path/to/lpc-global-regulatory-ai-starter/schema/postgresql.sql \
  --export /path/to/your/export
```

It checks SQL compatibility, use/evidence counts, draft-only visibility, snapshot immutability and transaction rollback on duplicate import. Flat CSV columns are checked against the France exchange contract; the actual externally supplied flat database DDL is not included in this adapter.

Regulatory assertions require Regulatory Affairs validation before official, commercial or operational use.
