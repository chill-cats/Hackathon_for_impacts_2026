#!/usr/bin/env python3
"""Load the starter reference data into an EXISTING database, safely.

- Never drops, deletes or overwrites anything: rows that already exist are skipped.
- Safe on a shared server and safe to run many times.
- Loads what the adapters need: sources, pilot products, LPC mappings, EPPO mappings.

  python scripts/seed_reference.py
"""
import csv, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from adapters.loader import connect   # same DATABASE_URL handling as the adapters

# Parents first, so foreign keys are satisfied.
TABLES = [
    ("source_registry", "source_id"),
    ("products", "product_id"),
    ("product_name_mapping", "mapping_id"),
    ("active_entity_mapping", "mapping_id"),
    ("eppo_crop_mapping", "concept_id"),
    ("eppo_pest_mapping", "concept_id"),
]


def main():
    with connect() as conn:
        for table, pk in TABLES:
            path = ROOT / "data" / f"{table}.csv"
            with path.open(encoding="utf-8-sig", newline="") as f:
                rows = list(csv.DictReader(f))
            if table == "products":
                # Only the starter products; adapter-created ones (P-CA-..., P-FR-...) come from the adapters.
                rows = [r for r in rows if r["product_id"].startswith(("P-LPC-", "P-DEMO-"))]
            if not rows:
                continue
            cols = list(rows[0].keys())
            sql = (f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({', '.join(['%s'] * len(cols))}) "
                   f"ON CONFLICT ({pk}) DO NOTHING")
            before = conn.execute(f"SELECT count(*) AS n FROM {table}").fetchone()["n"]
            with conn.cursor() as cur:
                cur.executemany(sql, [tuple(r[c] if r[c] != "" else None for c in cols) for r in rows])
            after = conn.execute(f"SELECT count(*) AS n FROM {table}").fetchone()["n"]
            print(f"{table}: {after - before} added, {len(rows) - (after - before)} already there")
        conn.commit()
    print("Reference data ready.")


if __name__ == "__main__":
    main()
