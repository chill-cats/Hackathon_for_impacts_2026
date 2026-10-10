"""Writes any adapter's canonical records into PostgreSQL (shared by all sources)."""
import csv, os, re
from dataclasses import asdict, fields
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

from .base import ReferenceData, SourceAdapter, Product, Alias, Registration, Use

ROOT = Path(__file__).resolve().parents[1]
EXPORT_TABLES = ["source_registry", "products", "product_aliases", "registrations", "uses"]


def database_url() -> str:
    """DATABASE_URL from the environment, or from the repo's .env file.

    Accepts the SQLAlchemy form too (postgresql+psycopg://...), so the backend and the
    adapters can share the same .env.
    """
    url = os.getenv("DATABASE_URL", "")
    env = ROOT / ".env"
    if not url and env.exists():
        for line in env.read_text().splitlines():
            if line.startswith("DATABASE_URL="):
                url = line.split("=", 1)[1].strip().strip('"').strip("'")
    if not url:
        raise SystemExit("DATABASE_URL is not set (export it or put it in .env)")
    return re.sub(r"^postgres(ql)?\+\w+://", "postgresql://", url)


def connect():
    return psycopg.connect(database_url(), row_factory=dict_row)


def load_references(conn) -> ReferenceData:
    q = lambda sql: conn.execute(sql).fetchall()
    return ReferenceData(
        entities=q("SELECT * FROM active_entity_mapping ORDER BY mapping_id"),
        names=q("SELECT * FROM product_name_mapping"),
        crops=q("SELECT * FROM eppo_crop_mapping"),
        pests=q("SELECT * FROM eppo_pest_mapping"))


def _upsert(conn, table, pk, records, cls):
    if not records:
        return
    cols = [f.name for f in fields(cls)]
    updates = ", ".join(f"{c} = EXCLUDED.{c}" for c in cols if c != pk)
    sql = (f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({', '.join(['%s'] * len(cols))}) "
           f"ON CONFLICT ({pk}) DO UPDATE SET {updates}")
    with conn.cursor() as cur:
        cur.executemany(sql, [tuple(asdict(r)[c] for c in cols) for r in records])


def _detect_changes(conn, adapter, new_regs):
    """Compare with what is already in the DB for this source (bonus: change detection)."""
    old = {r["registration_id"]: r for r in conn.execute(
        "SELECT registration_id, status_normalized, expiration_date::text AS exp "
        "FROM registrations WHERE source_id = %s", (adapter.source_id,)).fetchall()}
    changes = []
    for r in new_regs:
        prev = old.pop(r.registration_id, None)
        if prev is None:
            changes.append(f"NEW {r.registration_id}")
        elif prev["status_normalized"] != r.status_normalized or (prev["exp"] or None) != r.expiration_date:
            changes.append(f"CHANGED {r.registration_id}: {prev['status_normalized']}/{prev['exp']} "
                           f"-> {r.status_normalized}/{r.expiration_date}")
    gone = list(old)   # in the DB but no longer in the source
    changes += [f"NO LONGER IN SOURCE {rid} (marked obsolete, not deleted)" for rid in gone]
    return changes, gone


def run(adapter: SourceAdapter, input_path: Path = None) -> dict:
    with connect() as conn:
        run_id = conn.execute(
            "INSERT INTO collection_runs (source_id, input_file) VALUES (%s, %s) RETURNING run_id",
            (adapter.source_id, str(input_path) if input_path else None)).fetchone()["run_id"]
        conn.commit()
        try:
            refs = load_references(conn)
            raw = adapter.fetch(input_path)
            res = adapter.transform(raw, refs)
            changes, gone = _detect_changes(conn, adapter, res.registrations)

            with conn.transaction():                       # all or nothing
                _upsert(conn, "products", "product_id", res.products, Product)
                _upsert(conn, "product_aliases", "alias_id", res.aliases, Alias)
                _upsert(conn, "registrations", "registration_id", res.registrations, Registration)
                reg_ids = [r.registration_id for r in res.registrations]
                conn.execute("DELETE FROM uses WHERE registration_id = ANY(%s)", (reg_ids,))
                _upsert(conn, "uses", "use_id", res.uses, Use)
                if gone:
                    conn.execute("UPDATE registrations SET validation_status = 'obsolete' "
                                 "WHERE registration_id = ANY(%s)", (gone,))
                conn.execute(
                    "UPDATE collection_runs SET finished_at = now(), status = 'success', input_file = %s, "
                    "rows_read = %s, rows_written = %s, notes = %s WHERE run_id = %s",
                    (raw.raw_file, res.rows_read, len(res.registrations),
                     "\n".join(changes + res.warnings) or None, run_id))
        except Exception as exc:
            conn.rollback()
            conn.execute("UPDATE collection_runs SET finished_at = now(), status = 'failed', notes = %s "
                         "WHERE run_id = %s", (repr(exc), run_id))
            conn.commit()
            raise
    return {"run_id": run_id, "rows_read": res.rows_read, "products": len(res.products),
            "registrations": len(res.registrations), "uses": len(res.uses),
            "aliases": len(res.aliases), "changes": changes, "warnings": res.warnings}


def export_csv():
    """Write the DB back to data/*.csv so scripts/validate_data.py and the CSV export stay in sync."""
    with connect() as conn:
        for table in EXPORT_TABLES:
            with conn.cursor() as cur:
                cur.execute(f"SELECT * FROM {table} ORDER BY 1")
                cols = [d.name for d in cur.description]
                rows = cur.fetchall()
            with (ROOT / "data" / f"{table}.csv").open("w", encoding="utf-8", newline="") as f:
                w = csv.writer(f)
                w.writerow(cols)
                for r in rows:
                    w.writerow([_fmt(r[c]) for c in cols])


def _fmt(v):
    if v is None:
        return ""
    if isinstance(v, bool):
        return "true" if v else "false"
    if hasattr(v, "isoformat") and hasattr(v, "tzinfo") and v.tzinfo is not None:
        return v.strftime("%Y-%m-%dT%H:%M:%SZ")
    return v.isoformat() if hasattr(v, "isoformat") else v