"""Tests de backend/etl/normalize.py (pas de base de données nécessaire)."""
import sys
from pathlib import Path

# Rend backend/etl importable depuis tests/
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend" / "etl"))

import normalize as nz  # noqa: E402


def test_crop_german_plural():
    result = nz.normalize_crop("Tomaten")
    assert result["eppo_code"] == "LYPES"
    assert result["normalized"] == "Tomato"
    assert result["method"] == "lpc_mapping"


def test_crop_case_accent_and_spaces():
    assert nz.normalize_crop("  weinREBE ")["eppo_code"] == "VITVI"
    assert nz.normalize_crop("Pêcher")["eppo_code"] == "PRNPS"
    assert nz.normalize_crop("PECHER")["eppo_code"] == "PRNPS"


def test_target_french_alias():
    assert nz.normalize_target("pourriture grise")["eppo_code"] == "BOTRCI"


def test_unknown_words_return_none():
    assert nz.normalize_crop("xyzzy") is None
    assert nz.normalize_target("xyzzy") is None
    assert nz.normalize_active_entity("xyzzy") is None
    assert nz.normalize_crop("") is None


def test_ambiguous_alias_returns_none():
    # "mosca blanca" désigne deux concepts (T. vaporariorum et B. tabaci) : on ne tranche pas
    assert nz.normalize_target("mosca blanca") is None


def test_active_entity_former_name():
    result = nz.normalize_active_entity("Gliocladium catenulatum J1446")
    assert result["species"] == "Clonostachys rosea"
    assert result["strain"] == "J1446"


def test_active_entity_does_not_invent_strain():
    result = nz.normalize_active_entity("Coniothyrium minitans")
    assert result["species"] == "Coniothyrium minitans"
    assert result["strain"] is None  # la souche n'est pas écrite dans le texte


def test_search_terms_include_current_name():
    terms = [t.lower() for t in nz.search_terms_for("Gliocladium")]
    assert "clonostachys rosea" in terms


def test_search_terms_unknown_term_is_kept():
    assert nz.search_terms_for("xyzzy") == ["xyzzy"]


def test_sisters_same_species_and_strain():
    products = [
        {"product_id": "A", "commercial_name": "TEST A", "active_entity_original": "Gliocladium catenulatum J1446"},
        {"product_id": "B", "commercial_name": "TEST B", "active_entity_original": "Clonostachys rosea J1446"},
        {"product_id": "C", "commercial_name": "TEST C", "active_entity_original": "Clonostachys rosea"},
    ]
    found = {(c["product_a_id"], c["product_b_id"]): c for c in nz.find_sister_candidates(products)}
    assert found[("A", "B")]["confidence"] == 0.9
    assert found[("A", "C")]["confidence"] == 0.6
    assert all(c["review_status"] == "to_verify" for c in found.values())


def test_sisters_different_strains_are_not_linked():
    products = [
        {"product_id": "A", "commercial_name": "A", "active_entity_original": "Metarhizium brunneum F52"},
        {"product_id": "B", "commercial_name": "B", "active_entity_original": "Metarhizium brunneum strain Ma 43"},
    ]
    assert nz.find_sister_candidates(products) == []


def test_sisters_from_name_mapping_keep_their_status():
    products = [{"product_id": "P-LPC-G46", "commercial_name": "LALSTOP G46 WG"}]
    names = {c["product_b"]: c for c in nz.find_sister_candidates(products)}
    assert names["PRESTOP"]["confidence"] == 0.85
    assert names["PRESTOP"]["review_status"] == "to_verify"
