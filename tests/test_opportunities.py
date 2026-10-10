"""Tests de « Opportunité marché » (espaces libres pour le biocontrôle) : GET /opportunities et l'intention /ask.

Les tests de règle (classification, substances) n'ont pas besoin de la base ; les autres utilisent la base partagée
en lecture seule, comme tests/test_api.py.
"""
import os

import pytest
from fastapi.testclient import TestClient

from backend.app import llm
from backend.app import opportunities as opp
from backend.app.main import app

REMINDER = "Aide à l'analyse, pas une décision réglementaire"


@pytest.fixture(scope="module")
def client():
    os.environ["API_KEY"] = ""   # accès libre pour ces tests
    return TestClient(app)


# ---------------------------------------------------------------------------
# Règles sans base
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("text, expected", [
    ("Bacillus amyloliquefaciens strain D747", "biological"),
    ("Trichoderma asperellum", "biological"),
    ("Lactobacillus rhamnosus", "biological"),                          # contient « bacillus »
    ("Cydia pomonella granulovirus", "biological"),                      # virus d'insecte
    ("CLONOSTACHYS ROSEA STRAIN J1446", "biological"),                   # majuscules
    ("Metarhizium anisopliae (spores et propagules)", "biological"),     # ancien nom d'espèce
    ("anthraquinone (Anthraquinone) 151.0 g/L | cuivre (Cuivre) 60.7 g/L", "chemical"),
    ("Pyrimethanil", "chemical"),
    ("Pyrethrine", "chemical"),                                          # substance naturelle : « chemical » = pas un micro-organisme
    (None, "unknown"),
    ("", "unknown"),
    ("   ", "unknown"),
])
def test_classify_category(text, expected):
    assert opp.classify_category(text) == expected


def test_lpc_product_is_biological_even_without_active_entity():
    assert opp.classify_category(None, is_lpc=True) == "biological"
    assert opp.classify_category("", is_lpc=True) == "biological"


def test_substances_of_handles_each_source_format():
    assert opp.substances_of("anthraquinone (Anthraquinone) 151.0 g/L | Oxyquinoleate de cuivre (Oxyquinoleate de cuivre) 60.7 g/L") \
        == {"anthraquinone", "oxyquinoleate de cuivre"}
    assert opp.substances_of("Dicamba; Prosulfuron") == {"dicamba", "prosulfuron"}
    assert opp.substances_of("CLOPYRALID (PRESENT AS ACID, OR AS SALTS);MCPA (PRESENT AS ESTERS)") == {"clopyralid"}   # « mcpa » < 5 lettres
    assert opp.substances_of(None) == set()


# ---------------------------------------------------------------------------
# GET /opportunities
# ---------------------------------------------------------------------------
def test_opportunities_fr_top5_has_counts_products_and_evidence(client):
    response = client.get("/api/opportunities", params={"country": "FR", "limit": 5})
    assert response.status_code == 200
    data = response.json()
    items = data["items"]
    assert 1 <= len(items) <= 5
    scores = [i["biocontrolSpaceScore"] for i in items]
    assert scores == sorted(scores, reverse=True)                      # tri décroissant par score
    evidence_ids = {e["evidenceId"] for e in data["evidence"]}
    for item in items:
        assert item["countryCode"] == "FR"
        assert item["chemicalUses"] >= data["minChemicalUses"]
        assert item["biocontrolSpaceScore"] == pytest.approx(item["chemicalUses"] / (1 + item["biologicalUses"]), abs=0.01)
        assert item["productCategoryMethod"] == "rule_based"
        assert REMINDER in item["disclaimer"] and "par règle" in item["disclaimer"]      # rappel sur CHAQUE ligne
        assert item["chemicalEvidenceIds"], "un compte de chimiques sans preuve citable"
        assert set(item["evidenceIds"]) <= evidence_ids                                 # toute preuve citée est fournie
        if item["biologicalUses"] == 0:
            assert item["chemicalToBiologicalRatio"] is None                           # pas de division par zéro
    for ev in data["evidence"]:
        assert ev["sourceId"] and ev["collectedAt"] and ev["validationStatus"]         # règle LPC n°1
        assert ev["isSynthetic"] is False
    assert data["categoryMethod"] == "rule_based"
    assert any("Aucun usage retiré" in w for w in data["warnings"])                    # la limite des données est dite


def test_withdrawn_indicator_is_never_presented_as_withdrawn_uses(client):
    items = client.get("/api/opportunities", params={"country": "FR", "limit": 3}).json()["items"]
    for item in items:
        wd = item["withdrawnSameSubstance"]
        assert wd is not None and wd["countryCode"] == "FR"
        assert "SANS lien culture × cible" in wd["note"] and "pas des usages retirés" in wd["note"]
        assert "withdrawnUses" not in item and "withdrawnUses" not in wd


def test_opportunities_country_without_withdrawn_status_has_no_indicator(client):
    items = client.get("/api/opportunities", params={"country": "DE", "limit": 2}).json()["items"]
    assert items and all(i["withdrawnSameSubstance"] is None for i in items)           # DE : aucun statut « retiré » en source


def test_opportunities_crop_filter_and_lpc_products_are_flagged_as_hypotheses(client):
    data = client.get("/api/opportunities", params={"crop": "Grapevine", "limit": 20, "minChemicalUses": 1}).json()
    assert data["items"] and all(i["cropNormalized"] == "Grapevine" for i in data["items"])
    for item in data["items"]:
        for product in item["lpcProducts"]:
            assert product["categoryMethod"] == "rule_based"
            if product["relation"] != "lpc_product":
                assert product["reviewStatus"] != "validated" or product["relation"] == "sister_candidate"


def test_lpc_only_keeps_pairs_with_an_lpc_or_sister_product(client):
    items = client.get("/api/opportunities", params={"country": "FR", "lpcOnly": "true", "limit": 5}).json()["items"]
    assert items
    for item in items:
        assert item["lpcProducts"], "lpcOnly doit garder seulement les couples avec un produit LPC / sœur / même substance"
        for product in item["lpcProducts"]:
            assert product["evidenceIds"]
            if product["relation"] != "lpc_product":
                assert product["reviewStatus"] != "rejected"        # une sœur reste une hypothèse (to_verify), jamais présentée comme un fait
        assert item["biologicalUses"] >= 1                          # le produit LPC / sœur est lui-même compté comme biologique


def test_opportunities_rejects_bad_country(client):
    assert client.get("/api/opportunities", params={"country": "france"}).status_code == 422


def test_opportunities_unknown_product_is_404(client):
    assert client.get("/api/opportunities", params={"productId": "P-DOES-NOT-EXIST"}).status_code == 404


def test_opportunities_is_exposed_at_root_too(client):
    assert client.get("/opportunities", params={"country": "FR", "limit": 1}).status_code == 200


# ---------------------------------------------------------------------------
# /ask : intention market_opportunity (mode sans clé IA)
# ---------------------------------------------------------------------------
@pytest.fixture
def keyword_mode(monkeypatch):
    monkeypatch.setattr(llm, "is_configured", lambda: False)


@pytest.mark.parametrize("question", [
    "Où les usages chimiques reculent-ils sur la vigne ?",
    "Quels espaces libres pour le biocontrôle en France ?",
    "Quelles opportunités pour LALGUARD M52 ?",
])
def test_ask_market_opportunity(client, keyword_mode, question):
    data = client.post("/api/ask", json={"question": question}).json()
    assert data["intent"] == "market_opportunity"
    assert data["generator"]["mode"] == "keyword"
    assert REMINDER in data["answer"] and "à vérifier" in data["answer"]               # rappel obligatoire
    assert data["answerStatus"] in ("answered", "partial", "no_data")
    if data["facts"]:
        known = {e["evidenceId"] for e in data["evidence"]}
        assert all(set(f["evidenceIds"]) <= known for f in data["facts"])               # chaque fait est sourcé
        assert data["opportunities"]
        # les chiffres du texte viennent des faits : on les retrouve dans les compteurs de l'API
        assert str(data["opportunities"][0]["chemicalUses"]) in data["answer"]


def test_ask_other_intents_are_unchanged(client, keyword_mode):
    data = client.post("/api/ask", json={"question": "Dans quels pays LALSTOP G46 WG est-il homologué ?"}).json()
    assert data["intent"] == "registration_lookup"
    assert "opportunities" not in data or data["opportunities"] is None
