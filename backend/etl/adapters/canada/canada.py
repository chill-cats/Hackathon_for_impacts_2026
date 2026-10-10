"""Health Canada PPID adapter (owner: Dyland)."""
import csv, io, urllib.request
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Optional

from .base import (SourceAdapter, RawData, AdapterResult, ReferenceData,
                   Product, Alias, Registration, Use, norm)

ROOT = Path(__file__).resolve().parents[1]
API_URL = "https://pest-control.canada.ca/pesticide-registry-api/api/extract/product?lang=en"
RECORD_URL = "https://pest-control.canada.ca/pesticide-registry-api/api/extract/product/{}?lang=en"
AUTHORITY = "Health Canada - Pest Management Regulatory Agency (PMRA)"
NON_END_USE = {"TECHNICAL ACTIVE", "MANUFACTURING CONCENTRATE"}   # raw ingredients, not products farmers buy
ACTIVE_STATUSES = {"FULL REGISTRATION", "TEMPORARY PRODUCT", "EMERGENCY REGISTRATION", "LIMITED TERM PRODUCT"}
USE_NOTE = ("Product-level list from Health Canada PPID; crop-target pairing, dose and "
            "conditions must come from the official label")


def _decode(raw: bytes) -> str:
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        return raw.decode("latin-1")   # PPID extracts observed as ISO-8859-1


class CanadaAdapter(SourceAdapter):
    source_id = "CA-PPID"
    country_code = "CA"
    id_prefix = "CA"

    def __init__(self, include_technical: bool = False):
        self.include_technical = include_technical

    # ---------- fetch ----------
    def fetch(self, input_path: Optional[Path] = None) -> RawData:
        if input_path:
            return RawData(text=_decode(input_path.read_bytes()),
                           collected_at=datetime.fromtimestamp(input_path.stat().st_mtime, timezone.utc),
                           raw_file=str(input_path))
        with urllib.request.urlopen(API_URL, timeout=120) as resp:
            text = _decode(resp.read())
        now = datetime.now(timezone.utc)
        raw_dir = ROOT / "data" / "raw" / "canada"
        raw_dir.mkdir(parents=True, exist_ok=True)
        raw_file = raw_dir / f"product_en_{now:%Y%m%dT%H%M%SZ}.csv"
        raw_file.write_text(text, encoding="utf-8")          # keep the evidence of what was collected
        return RawData(text=text, collected_at=now, raw_file=str(raw_file))

    # ---------- transform ----------
    @staticmethod
    def _status(row, today):
        status = row["Registration Status"].strip().upper()
        if status == "CANCELLED" or row["Current / Historical"].strip().lower() == "historical":
            return "withdrawn"
        exp = row["Expiry date"].strip()
        if exp and exp < today.isoformat():
            return "expired"
        if status in ACTIVE_STATUSES:
            return "active"
        return "unknown"   # e.g. Phase-Out; exact wording stays in status_original

    def transform(self, raw: RawData, refs: ReferenceData) -> AdapterResult:
        rows = list(csv.DictReader(io.StringIO(raw.text)))
        res = AdapterResult(rows_read=len(rows))
        today = date.today()

        for row in rows:
            entity, strain_match = refs.match_entity(row["Active ingredients - English"])
            if not entity:
                continue
            if row["Marketing type"].strip().upper() in NON_END_USE and not self.include_technical:
                continue

            regno = row["Registration number"].strip()
            name = row["Product name - English"].strip()
            mapped = refs.names.get(norm(name))

            # Only an exact canonical-name match joins a pilot product; anything else is its own product.
            if mapped and mapped["relationship_type"] == "canonical_name":
                product_id = mapped["product_id"]
            else:
                product_id = f"P-CA-{regno}"
                res.products.append(Product(
                    product_id=product_id, commercial_name=name,
                    active_entity_original=row["Active ingredients - English"].strip(),
                    active_entity_normalized=entity["canonical_species"]))
                res.aliases.append(self._alias(regno, name, entity, strain_match, mapped))

            if not strain_match:
                res.warnings.append(f"{name} ({regno}): strain in source differs from LPC canonical strain - check equivalence")

            reg_id = f"R-CA-{regno}"
            status = self._status(row, today)
            exp = row["Expiry date"].strip() or None
            res.registrations.append(Registration(
                registration_id=reg_id, product_id=product_id, country_code="CA",
                authority_name=AUTHORITY, registration_number=regno,
                status_original=row["Registration Status"].strip(), status_normalized=status,
                approval_date=row["Date first registered"].strip() or None, expiration_date=exp,
                source_id=self.source_id, source_record_url=RECORD_URL.format(regno),
                collected_at=raw.collected_at))
            if status == "active" and exp and (date.fromisoformat(exp) - today).days <= 365:
                res.warnings.append(f"{name} ({regno}): registration expires {exp} (within 12 months)")

            # PPID lists crops and pests separately at product level: never cross-multiply them.
            for i, crop in enumerate(self._split(row["Sites of Use"]), 1):
                m = refs.crop(crop)
                res.uses.append(Use(use_id=f"U-CA-{regno}-C{i:02d}", registration_id=reg_id,
                                    crop_name_original=crop,
                                    crop_name_normalized=m["name_normalized"] if m else None,
                                    eppo_crop_code=m["eppo_code"] if m else None,
                                    restrictions_original=USE_NOTE))
            for i, pest in enumerate(self._split(row["Pests"]), 1):
                m = refs.pest(pest)
                res.uses.append(Use(use_id=f"U-CA-{regno}-T{i:02d}", registration_id=reg_id,
                                    target_name_original=pest,
                                    target_name_normalized=m["name_normalized"] if m else None,
                                    eppo_target_code=m["eppo_code"] if m else None,
                                    restrictions_original=USE_NOTE))
        return res

    @staticmethod
    def _split(s):
        return [x.strip() for x in (s or "").split(";") if x.strip()]

    @staticmethod
    def _alias(regno, name, entity, strain_match, mapped):
        if mapped and mapped["review_status"] == "validated":
            return Alias(alias_id=f"AL-CA-{regno}", product_id=entity["product_id"], alias_name=name,
                         country_code="CA", relationship_type="confirmed_sister_product",
                         confidence=float(mapped["confidence_score"]), review_status="validated",
                         evidence=f"LPC product_name_mapping {mapped['mapping_id']}: {mapped['evidence_summary']}")
        evidence = (f"Same active entity ({entity['canonical_species']}"
                    f"{', same strain' if strain_match else ', strain not confirmed'}) in Health Canada PPID reg. {regno}")
        if mapped:
            evidence += f"; also listed in LPC product_name_mapping {mapped['mapping_id']}"
        conf = float(mapped["confidence_score"]) if mapped else (0.80 if strain_match else 0.50)
        return Alias(alias_id=f"AL-CA-{regno}", product_id=entity["product_id"], alias_name=name,
                     country_code="CA", relationship_type="sister_product_candidate",
                     confidence=conf, review_status="to_verify", evidence=evidence)
