# Country ingestion adapters

Each country is an independent Docker build and scheduled service targeting the
existing flat PostgreSQL schema. Run commands from the country directory.

```text
adapters/
  france/
    main.py          # Scheduled database ingestion
    exporter.py      # Standalone CSV export
    validate.py      # France CSV validation CLI
    tests/
  germany/
    main.py          # Scheduled database ingestion
    exporter.py      # Standalone CSV export
    verify.py        # BVL verification CLI
    bvl/             # BVL client, conversion and export helpers
    fixtures/de/     # Explicitly synthetic offline source data
    tests/
```

Both directories contain `Dockerfile`, `compose.yaml`, `requirements.txt`,
`.env.example`, and a README with country-specific options. Local `.env`, `.venv/`,
`state/`, and `out/` are ignored. Docker stores snapshots in persistent volumes.
The existing Compose project names and volume names are preserved.

## Run

From the repository root, choose `france` or `germany`:

```sh
cd adapters/france
cp .env.example .env  # Only for a new installation; preserve an existing .env.
# Set DATABASE_URL in .env.
docker compose up -d --build
```

See [France](france/README.md) and [Germany](germany/README.md) for export,
validation, replay and diagnostic commands. The services write to the database;
standalone exporters generate CSV bundles without running the scheduled service.

## Local tests

Create a fresh virtual environment after moving a checkout; virtual environments
contain absolute paths and are not portable. From each country directory:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m unittest discover -s tests -v
```

Run each country's suite separately because they use local module names.
Database integration tests require a disposable test database; see each README.

## Migration from the copied folders

`France/` and `Germany/` are now `france/` and `germany/`. Germany's nested
`adapters/` package is now `bvl/`; `run_de.py` is `exporter.py`, and `verify_de.py`
is `verify.py`. France's `validate_france_csv.py` is `validate.py`.
Update external scripts using the old paths. Existing local configuration is
preserved. Historical backup directories are retained locally in `_archive/`,
which is ignored and outside both Docker build contexts; Git retains their
previous tracked versions.
