"""Enveloppes de réponse pour les schémas "inline" du contrat.

Les modèles du contrat sont dans models.py (générés par datamodel-code-generator, NE PAS éditer).
Le contrat décrit certaines réponses directement dans les routes (sans nom) ; le générateur ne
leur donne donc pas de classe. Ce fichier les reprend à l'identique, en réutilisant les classes
générées.
"""
from typing import Literal

from pydantic import BaseModel

from .models import (Answer, AnswerGenerator, ComparisonResponse, ComparisonRow, CountryCoverage, MatchedVia, Product,
                     Registration, SourceInfo)


class HealthResponse(BaseModel):
    status: Literal["ok"]


class ProductOut(Product):
    """Product du contrat + `matchedVia` (AJOUT optionnel demandé pour la recherche : par quel nom,
    alias ou substance active le produit a été trouvé). Propose d'ajouter ce champ au contrat."""
    matchedVia: MatchedVia | None = None


class ComparisonRowOut(ComparisonRow):
    """ComparisonRow du contrat + `cropGroup` / `targetGroup` (AJOUT optionnel : catégorie large suggérée par l'IA,
    ex. "Powdery mildews", "Cereals", à vérifier) + `alignedBy` (clé d'alignement). Propose d'ajouter ces champs au contrat."""
    cropGroup: str | None = None
    targetGroup: str | None = None
    alignedBy: Literal["eppo", "normalized_name", "original"] | None = None   # clé d'alignement de la ligne (hors contrat)


class ComparisonResponseOut(ComparisonResponse):
    """ComparisonResponse du contrat, avec des lignes enrichies de cropGroup / targetGroup."""
    rows: list[ComparisonRowOut] | None = None


class ProductsResponse(BaseModel):
    items: list[ProductOut]


class RegistrationsResponse(BaseModel):
    items: list[Registration]
    coverage: list[CountryCoverage] | None = None
    warnings: list[str] | None = None
    disclaimer: str


class SourcesResponse(BaseModel):
    items: list[SourceInfo]


class AnswerGeneratorOut(AnswerGenerator):
    """AnswerGenerator du contrat + `mode` (AJOUT optionnel : « llm » si l'IA a servi, « keyword » en mode sans clé).
    Propose d'ajouter ce champ au contrat."""
    mode: Literal["llm", "keyword"] | None = None


class AnswerOut(Answer):
    """Answer du contrat, avec le `generator` enrichi du champ `mode`."""
    generator: AnswerGeneratorOut | None = None
