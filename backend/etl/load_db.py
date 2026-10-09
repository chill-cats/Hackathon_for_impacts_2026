"""Charge les CSV de l'équipe dans la base PostgreSQL EXISTANTE (sans toucher au schéma).

Usage (depuis la racine du dépôt) :
    python backend/etl/load_db.py               # tout charger (données de test comprises)
    python backend/etl/load_db.py --no-test     # sans data/incoming/test_*.csv
    python backend/etl/load_db.py --reset-data  # VIDE les données (jamais le schéma), après confirmation

Principes :
- La connexion vient UNIQUEMENT de DATABASE_URL dans .env (aucun identifiant dans le code).
- Aucun CREATE / ALTER / DROP / TRUNCATE : seulement des INSERT ... ON CONFLICT (upsert).
- Idempotent : relancer le script ne crée pas de doublons.
- Les colonnes *_original ne sont jamais modifiées par un upsert.
- Les colonnes *_normalized / eppo_* ne sont remplies que si elles sont vides.
- Une ligne invalide n'arrête pas le chargement : elle est listée dans data/merged/rejected_rows.csv.
"""
import argparse
import csv
import hashlib
import json
import os
import sys
from collections import Counter
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError

import normalize as nz

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
INCOMING = DATA / "incoming"
REJECTED_FILE = DATA / "merged" / "rejected_rows.csv"

# Préfixe du nom de fichier -> source_id (table source_registry), pour collection_runs
SOURCE_BY_PREFIX = {"ca": "CA-PPID", "fr": "FR-EPHY", "de": "DE-BVL", "us": "US-EPA-PPLS", "test": "FR-EPHY"}

# ---------------------------------------------------------------------------
# Description des tables : clé primaire, colonnes non texte, colonnes protégées
# ---------------------------------------------------------------------------
# types : "bool", "date", "ts" (timestamp avec fuseau), "num", "int" ; les autres colonnes sont du texte.
# originals : colonnes *_original, jamais modifiées par un upsert.
# fill_if_empty : colonnes normalisées, remplies seulement si la base est vide à cet endroit.
# keep : colonnes que l'on ne touche jamais lors d'une mise à jour
#        (une relecture humaine faite en base ne doit pas être écrasée par le fichier).
TABLES = {
    "source_registry": dict(pk=["source_id"], types={"manual_validation_required": "bool"}, on_conflict="nothing"),
    "products": dict(
        pk=["product_id"], types={"is_synthetic": "bool"},
        originals=["active_entity_original"], fill_if_empty=["active_entity_normalized"], keep=["validation_status"],
    ),
    "eppo_crop_mapping": dict(pk=["concept_id"], types={}),
    "eppo_pest_mapping": dict(pk=["concept_id"], types={}),
    "active_entity_mapping": dict(pk=["mapping_id"], types={"confidence_score": "num"}),
    "product_name_mapping": dict(pk=["mapping_id"], types={"confidence_score": "num"}),
    "registrations": dict(
        pk=["registration_id"],
        types={"approval_date": "date", "expiration_date": "date", "collected_at": "ts", "is_synthetic": "bool"},
        originals=["status_original"], keep=["validation_status"],
    ),
    "uses": dict(
        pk=["use_id"],
        types={"dose_value": "num", "max_applications": "int", "application_interval_days": "num",
               "phi_days": "num", "rei_hours": "num", "is_synthetic": "bool"},
        originals=["crop_name_original", "target_name_original", "dose_unit_original", "restrictions_original"],
        fill_if_empty=["crop_name_normalized", "eppo_crop_code", "target_name_normalized", "eppo_target_code"],
        keep=["validation_status"],
    ),
}

# Type d'entité (colonne entity_type de field_evidence) pour chaque table
ENTITY_TYPE = {"products": "product", "registrations": "registration", "uses": "use"}

# Colonnes importantes dont on compte les valeurs vides dans le résumé
IMPORTANT_COLUMNS = {
    "products": ["active_entity_original", "active_entity_normalized", "formulation_code"],
    "registrations": ["registration_number", "status_original", "approval_date", "expiration_date"],
    "uses": ["crop_name_normalized", "eppo_crop_code", "target_name_normalized", "eppo_target_code", "dose_value"],
}

# Ordre de suppression pour --reset-data (enfants avant parents, à cause des clés étrangères)
RESET_ORDER = [
    "field_evidence", "uses", "registrations", "product_aliases", "active_entity_mapping",
    "product_name_mapping", "products", "eppo_crop_mapping", "eppo_pest_mapping",
    "collection_runs", "source_registry",
]


# ---------------------------------------------------------------------------
# Lecture et conversion des CSV
# ---------------------------------------------------------------------------
def read_csv(path):
    """Renvoie (colonnes, [(numéro de ligne, {colonne: texte})])."""
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        rows = [(i, row) for i, row in enumerate(reader, start=2)]  # ligne 1 = en-tête
        return reader.fieldnames or [], rows


def convert(value, kind):
    """Convertit un texte de CSV en valeur Python. Texte vide -> None (NULL). Lève ValueError si invalide."""
    if value is None or value.strip() == "":
        return None
    value = value.strip()
    if kind == "bool":
        if value.lower() in ("true", "1"):
            return True
        if value.lower() in ("false", "0"):
            return False
        raise ValueError(f"booléen invalide : {value!r}")
    if kind == "date":
        return date.fromisoformat(value)  # attendu : AAAA-MM-JJ
    if kind == "ts":
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            raise ValueError(f"horodatage sans fuseau (UTC ISO 8601 attendu) : {value!r}")
        return parsed
    if kind == "num":
        try:
            return Decimal(value)
        except InvalidOperation:
            raise ValueError(f"nombre invalide : {value!r}")
    if kind == "int":
        return int(value)
    return value


def convert_row(table, raw):
    """Convertit toutes les colonnes d'une ligne selon TABLES[table]['types']."""
    types = TABLES[table]["types"]
    return {col: convert(val, types.get(col, "text")) for col, val in raw.items() if col is not None}


# ---------------------------------------------------------------------------
# Écriture en base
# ---------------------------------------------------------------------------
def upsert_sql(table, columns):
    """INSERT ... ON CONFLICT adapté aux règles du projet (voir en-tête du fichier)."""
    spec = TABLES[table]
    pk = spec["pk"]
    sql = (f"INSERT INTO {table} ({', '.join(columns)}) "
           f"VALUES ({', '.join(':' + c for c in columns)}) ON CONFLICT ({', '.join(pk)}) ")
    never = set(pk) | set(spec.get("originals", [])) | set(spec.get("keep", []))
    updates = []
    for c in columns:
        if c in never:
            continue
        if c in spec.get("fill_if_empty", []):
            updates.append(f"{c} = COALESCE({table}.{c}, EXCLUDED.{c})")  # garde la valeur déjà en base
        else:
            updates.append(f"{c} = EXCLUDED.{c}")
    if spec.get("on_conflict") == "nothing" or not updates:
        return sql + "DO NOTHING"
    return sql + "DO UPDATE SET " + ", ".join(updates)


def reason_of(error):
    """Première ligne du message PostgreSQL (nomme la contrainte violée)."""
    return str(getattr(error, "orig", error)).strip().splitlines()[0]


def write_rows(conn, table, columns, rows, source_label, rejected):
    """Écrit des lignes (numéro, dict). Renvoie la liste des lignes ACCEPTÉES.

    On essaie d'abord tout le lot d'un coup (rapide). Si la base refuse quelque chose,
    on rejoue ligne par ligne pour trouver les lignes fautives et les lister.
    Chaque essai est dans un SAVEPOINT : une erreur n'annule pas le reste.
    """
    if not rows:
        return []
    sql = text(upsert_sql(table, columns))
    try:
        with conn.begin_nested():
            conn.execute(sql, [r for _, r in rows])
        return list(rows)
    except DBAPIError:
        pass
    accepted = []
    for line, row in rows:
        try:
            with conn.begin_nested():
                conn.execute(sql, row)
            accepted.append((line, row))
        except DBAPIError as e:
            reject(rejected, source_label, table, line, row, reason_of(e))
    return accepted


def reject(rejected, source_label, table, line, row, reason):
    key = "|".join(str(row.get(c, "")) for c in TABLES[table]["pk"]) if row else ""
    rejected.append({"file": source_label, "table": table, "line": line, "key": key, "reason": reason})


def load_file(conn, table, path, rejected, transform=None):
    """Lit un CSV, convertit, (optionnel) normalise, écrit. Renvoie (lignes lues, lignes acceptées)."""
    label = str(path.relative_to(ROOT)).replace("\\", "/")
    columns, raw_rows = read_csv(path)
    converted = []
    for line, raw in raw_rows:
        try:
            converted.append((line, convert_row(table, raw)))
        except ValueError as e:
            reject(rejected, label, table, line, raw, f"valeur invalide : {e}")
    if transform:
        converted = transform(converted)
    accepted = write_rows(conn, table, columns, converted, label, rejected)
    return len(raw_rows), accepted


# ---------------------------------------------------------------------------
# Normalisation avant écriture (remplit seulement les colonnes vides) + preuves
# ---------------------------------------------------------------------------
def make_evidence(entity_type, entity_id, field, original, excerpt, confidence):
    return {"entity_type": entity_type, "entity_id": entity_id, "field_name": field,
            "value_original": original, "excerpt": excerpt, "confidence": confidence}


def normalize_products(evidence):
    def transform(rows):
        for _, row in rows:
            original = row.get("active_entity_original")
            if original and not row.get("active_entity_normalized"):
                found = nz.normalize_active_entity(original)
                if found:
                    value = f"{found['species']} {found['strain']}" if found["strain"] else found["species"]
                    row["active_entity_normalized"] = value
                    evidence.append(make_evidence(
                        "product", row["product_id"], "active_entity_normalized", original,
                        f"matched_variant={found['matched_variant']}; review_status={found['review_status']}",
                        found["confidence"]))
        return rows
    return transform


def normalize_uses(evidence):
    def fill(row, kind, lookup, name_col, code_col, original_col):
        original = row.get(original_col)
        if not original or (row.get(name_col) and row.get(code_col)):
            return
        found = lookup(original)
        if not found:
            return  # pas de correspondance : on laisse vide (NULL)
        note = f"mapping_status={found['mapping_status']}; eppo_code={found['eppo_code']}"
        if not row.get(name_col) and found["normalized"]:
            row[name_col] = found["normalized"]
            evidence.append(make_evidence("use", row["use_id"], name_col, original, note, None))
        if not row.get(code_col) and found["eppo_code"]:
            row[code_col] = found["eppo_code"]
            evidence.append(make_evidence("use", row["use_id"], code_col, original, note, None))

    def transform(rows):
        for _, row in rows:
            fill(row, "crop", nz.normalize_crop, "crop_name_normalized", "eppo_crop_code", "crop_name_original")
            fill(row, "target", nz.normalize_target, "target_name_normalized", "eppo_target_code", "target_name_original")
        return rows
    return transform


EVIDENCE_SQL = text("""
    INSERT INTO field_evidence
        (entity_type, entity_id, field_name, value_original, excerpt, extraction_method,
         confidence, validation_status, collected_at)
    SELECT CAST(:entity_type AS text), CAST(:entity_id AS text), CAST(:field_name AS text),
           CAST(:value_original AS text), CAST(:excerpt AS text), 'lpc_mapping',
           CAST(:confidence AS numeric), 'to_verify', CAST(:collected_at AS timestamptz)
    WHERE NOT EXISTS (
        SELECT 1 FROM field_evidence
        WHERE entity_type = :entity_type AND entity_id = :entity_id
          AND field_name = :field_name AND extraction_method = 'lpc_mapping')
""")


def write_evidence(conn, evidence, accepted_ids):
    """Une ligne de preuve par valeur normalisée (sans doublon si on relance)."""
    now = datetime.now(timezone.utc)
    rows = [dict(e, collected_at=now) for e in evidence if (e["entity_type"], e["entity_id"]) in accepted_ids]
    if rows:
        with conn.begin_nested():
            conn.execute(EVIDENCE_SQL, rows)
    return len(rows)


# ---------------------------------------------------------------------------
# Produits soeurs -> product_aliases
# ---------------------------------------------------------------------------
ALIAS_SQL = text("""
    INSERT INTO product_aliases
        (alias_id, product_id, alias_name, country_code, relationship_type, confidence, evidence, review_status, is_synthetic)
    VALUES (:alias_id, :product_id, :alias_name, :country_code, 'sister_product_candidate',
            :confidence, :evidence, :review_status, :is_synthetic)
    ON CONFLICT (alias_id) DO UPDATE SET confidence = EXCLUDED.confidence, evidence = EXCLUDED.evidence
    WHERE product_aliases.review_status = 'to_verify'   -- une relecture humaine n'est jamais écrasée
""")


def alias_id(product_id, name):
    digest = hashlib.sha1(f"{product_id}|{nz.clean(name)}".encode("utf-8")).hexdigest()[:16]
    return f"A-SIS-{digest}"


def write_sisters(conn, products):
    """Calcule les candidats soeurs et les range dans product_aliases. Renvoie le nombre de lignes."""
    synthetic = {p["product_id"]: p["is_synthetic"] for p in products}
    names = {p["product_id"]: p["commercial_name"] for p in products}
    rows = []
    for c in nz.find_sister_candidates(products):
        # Le lien est symétrique quand les deux produits sont connus : une ligne dans chaque sens
        directions = [(c["product_a_id"], c["product_b"])]
        if c["product_b_id"]:
            directions.append((c["product_b_id"], names[c["product_a_id"]]))
        for product_id, other_name in directions:
            rows.append({
                "alias_id": alias_id(product_id, other_name), "product_id": product_id, "alias_name": other_name,
                "country_code": c["country_code"], "confidence": c["confidence"],
                "evidence": f"[{c['reason']}] {c['evidence']}", "review_status": c["review_status"],
                "is_synthetic": bool(synthetic.get(c["product_a_id"]) or synthetic.get(c["product_b_id"])),
            })
    if rows:
        with conn.begin_nested():
            conn.execute(ALIAS_SQL, rows)
    return len(rows)


# ---------------------------------------------------------------------------
# collection_runs, schéma, reset
# ---------------------------------------------------------------------------
def log_run(conn, source_id, started, input_file, rows_read, rows_written, status, notes):
    conn.execute(text("""
        INSERT INTO collection_runs (source_id, started_at, finished_at, input_file, rows_read, rows_written, status, notes)
        VALUES (:s, :st, :fi, :f, :r, :w, :status, :n)"""),
        {"s": source_id, "st": started, "fi": datetime.now(timezone.utc), "f": input_file,
         "r": rows_read, "w": rows_written, "status": status, "n": notes})


def check_schema(conn):
    """Vérifie (en lecture) que les colonnes dont on a besoin existent. On n'ajoute JAMAIS de colonne."""
    needed = {t: set() for t in list(TABLES) + ["collection_runs", "field_evidence", "product_aliases"]}
    for table in TABLES:
        needed[table] |= set(read_csv(DATA / f"{table}.csv")[0])
    needed["collection_runs"] = {"source_id", "started_at", "finished_at", "input_file", "rows_read", "rows_written", "status", "notes"}
    needed["field_evidence"] = {"entity_type", "entity_id", "field_name", "value_original", "excerpt",
                                "extraction_method", "confidence", "validation_status", "collected_at"}
    needed["product_aliases"] = {"alias_id", "product_id", "alias_name", "country_code", "relationship_type",
                                 "confidence", "evidence", "review_status", "is_synthetic"}
    existing = {}
    for table, column in conn.execute(text(
            "SELECT table_name, column_name FROM information_schema.columns WHERE table_schema = 'public'")):
        existing.setdefault(table, set()).add(column)
    missing = [f"{t}.{c}" for t, cols in needed.items() for c in sorted(cols - existing.get(t, set()))]
    if missing:
        print("ERREUR : colonnes absentes de la base (je n'ajoute rien, demande à l'équipe) :")
        for m in missing:
            print("  -", m)
        sys.exit(1)


def reset_data(conn, url):
    """Vide les DONNEES de toutes les tables (jamais le schéma), après confirmation tapée."""
    print(f"\n!!! --reset-data va SUPPRIMER TOUTES LES DONNEES de la base '{url.database}' sur {url.host}.")
    print("!!! Si c'est le serveur partagé, vous effacez le travail de toute l'équipe.")
    for table in RESET_ORDER:
        print(f"    {table}: {conn.execute(text(f'SELECT count(*) FROM {table}')).scalar()} lignes")
    expected = f"EFFACER {url.database}"
    try:
        answer = input(f'Pour confirmer, tapez exactement "{expected}" : ').strip() if sys.stdin.isatty() else ""
    except EOFError:
        answer = ""
    if answer != expected:
        print("Confirmation absente ou incorrecte : rien n'a ete supprime.")
        sys.exit(1)
    for table in RESET_ORDER:
        conn.execute(text(f"DELETE FROM {table}"))
    conn.commit()
    print("Données supprimées (schéma intact).\n")


# ---------------------------------------------------------------------------
# Programme principal
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="Charge les CSV dans PostgreSQL (sans modifier le schéma).")
    parser.add_argument("--no-test", action="store_true", help="ignore data/incoming/test_*.csv")
    parser.add_argument("--reset-data", action="store_true", help="vide les données (pas le schéma), avec confirmation")
    args = parser.parse_args()

    load_dotenv(ROOT / ".env")
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        sys.exit("ERREUR : DATABASE_URL absent. Copiez .env.example en .env et renseignez-le.")
    engine = create_engine(database_url)

    rejected = []                     # lignes refusées (écrites dans rejected_rows.csv)
    written = Counter()               # table -> lignes écrites pendant ce lancement
    by_country = Counter()
    loaded = {"products": [], "registrations": [], "uses": []}   # lignes acceptées, pour le résumé
    run_notes = []

    with engine.connect() as conn:
        check_schema(conn)
        if args.reset_data:
            reset_data(conn, make_url(database_url))

        # 1) Tables de référence du kit, dans l'ordre des clés étrangères
        print("Chargement des tables de référence (data/)...")
        evidence = []
        for table in ["source_registry", "products", "eppo_crop_mapping", "eppo_pest_mapping",
                      "active_entity_mapping", "product_name_mapping"]:
            transform = normalize_products(evidence) if table == "products" else None
            _, accepted = load_file(conn, table, DATA / f"{table}.csv", rejected, transform)
            written[table] += len(accepted)
            if table == "products":
                loaded["products"] += [r for _, r in accepted]
            conn.commit()

        # 2) Fichiers data/incoming/<prefixe>_{products,registrations,uses}.csv
        prefixes = sorted({p.name.rsplit("_", 1)[0] for suffix in ("products", "registrations", "uses")
                           for p in INCOMING.glob(f"*_{suffix}.csv")})
        if args.no_test:
            prefixes = [p for p in prefixes if p != "test"]
        for prefix in prefixes:
            print(f"Chargement de data/incoming/{prefix}_*.csv ...")
            for table in ("products", "registrations", "uses"):
                path = INCOMING / f"{prefix}_{table}.csv"
                if not path.exists():
                    print(f"  (absent : {path.name})")
                    continue
                started = datetime.now(timezone.utc)
                before = len(rejected)
                transform = {"products": normalize_products, "uses": normalize_uses}.get(table)
                file_evidence = []
                try:
                    read, accepted = load_file(conn, table, path, rejected,
                                               transform(file_evidence) if transform else None)
                    ids = {(ENTITY_TYPE[table], r[TABLES[table]["pk"][0]]) for _, r in accepted}
                    written["field_evidence"] += write_evidence(conn, file_evidence, ids)
                    status, notes = "success", f"{len(rejected) - before} rejected rows" if len(rejected) > before else None
                except Exception as e:  # fichier illisible : on le note et on passe au suivant
                    conn.rollback()
                    read, accepted, status, notes = 0, [], "failed", f"{type(e).__name__}: {e}"[:500]
                    reject(rejected, path.name, table, 0, {}, notes)
                if prefix == "test":
                    notes = ((notes + "; ") if notes else "") + "SYNTHETIC TEST DATA (lpc_etl)"
                if prefix in SOURCE_BY_PREFIX:
                    log_run(conn, SOURCE_BY_PREFIX[prefix], started, f"data/incoming/{path.name}", read, len(accepted), status, notes)
                else:
                    run_notes.append(f"{path.name}: préfixe inconnu, aucune ligne collection_runs écrite")
                conn.commit()
                written[table] += len(accepted)
                loaded[table] += [r for _, r in accepted]
                if table == "registrations":
                    by_country.update(r["country_code"] for _, r in accepted)
                print(f"  {path.name}: {read} lues, {len(accepted)} écrites")

        # 3) Preuves des produits du kit + produits soeurs
        kit_ids = {("product", r["product_id"]) for r in loaded["products"]}
        written["field_evidence"] += write_evidence(conn, evidence, kit_ids)
        written["product_aliases"] += write_sisters(conn, loaded["products"])
        conn.commit()

    # 4) Fichier des lignes rejetées (réécrit à chaque lancement)
    REJECTED_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(REJECTED_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["file", "table", "line", "key", "reason"])
        writer.writeheader()
        writer.writerows(rejected)

    print_summary(written, by_country, loaded, rejected, run_notes)


def print_summary(written, by_country, loaded, rejected, notes):
    print("\n================ RESUME ================")
    print("Lignes écrites (upsert) pendant ce lancement :")
    for table, n in sorted(written.items()):
        print(f"  {table:<24}{n}")
    print("Homologations chargées par pays :", dict(sorted(by_country.items())) or "aucune")
    print("Champs vides (lignes chargées) :")
    for table, columns in IMPORTANT_COLUMNS.items():
        rows = loaded[table]
        empties = {c: sum(1 for r in rows if r.get(c) in (None, "")) for c in columns}
        print(f"  {table} ({len(rows)} lignes) : " + ", ".join(f"{c}={n}" for c, n in empties.items()))
    synthetic = {t: sum(1 for r in loaded[t] if r.get("is_synthetic")) for t in loaded}
    print("Lignes is_synthetic=true :", synthetic)
    print(f"Lignes rejetées : {len(rejected)}" + (f"  (détail : {REJECTED_FILE.relative_to(ROOT)})" if rejected else ""))
    for note in notes:
        print("Note :", note)


if __name__ == "__main__":
    main()
