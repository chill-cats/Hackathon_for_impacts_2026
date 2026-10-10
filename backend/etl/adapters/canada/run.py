"""Run one or more source adapters into the database.

  python -m adapters.run canada                                    # live download
  python -m adapters.run canada --input data/raw/canada/product_en.csv   # frozen extract
  python -m adapters.run canada --export-csv                       # also refresh data/*.csv
"""
import argparse
import sys
from pathlib import Path

if __package__ in (None, ""):
    # Started as a plain file (e.g. the editor's Run/Debug button): make the package imports work.
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    __package__ = "adapters"
    import adapters  # noqa: F401

from .canada import CanadaAdapter
from . import loader

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = {"canada": ROOT / "data" / "raw" / "canada" / "product_en.csv"}

# Add new sources here: "france": FranceAdapter, "germany": GermanyAdapter
ADAPTERS = {"canada": CanadaAdapter}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("source", nargs="?", default="canada", choices=sorted(ADAPTERS))
    ap.add_argument("--input", type=Path, help="Frozen extract instead of live download")
    ap.add_argument("--export-csv", action="store_true", help="Rewrite data/*.csv from the database")
    args = ap.parse_args()
    if len(sys.argv) == 1 and DEFAULT_INPUT[args.source].exists():
        # No arguments at all (editor button): use the frozen extract instead of downloading live.
        args.input = DEFAULT_INPUT[args.source]
        print(f"No arguments given: using frozen extract {args.input}")

    summary = loader.run(ADAPTERS[args.source](), args.input)
    print(f"[{args.source}] run {summary['run_id']}: read {summary['rows_read']} rows -> "
          f"{summary['registrations']} registrations, {summary['products']} new products, "
          f"{summary['uses']} uses, {summary['aliases']} aliases")
    for c in summary["changes"]:
        print("  CHANGE:", c)
    for w in summary["warnings"]:
        print("  WARNING:", w)
    if args.export_csv:
        loader.export_csv()
        print("  data/*.csv refreshed from the database")


if __name__ == "__main__":
    main()