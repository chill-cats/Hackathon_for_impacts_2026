"""Enveloppes de réponse pour les schémas "inline" du contrat.

Les modèles du contrat sont dans models.py (générés par datamodel-code-generator, NE PAS éditer).
Le contrat décrit certaines réponses directement dans les routes (sans nom) ; le générateur ne
leur donne donc pas de classe. Ce fichier les reprend à l'identique, en réutilisant les classes
générées.
"""
from typing import Literal

from pydantic import BaseModel

from .models import CountryCoverage, MatchedVia, Product, Registration, SourceInfo


class HealthResponse(BaseModel):
    status: Literal["ok"]


class ProductOut(Product):
    """Product du contrat + `matchedVia` (AJOUT optionnel demandé pour la recherche : par quel nom,
    alias ou substance active le produit a été trouvé). Propose d'ajouter ce champ au contrat."""
    matchedVia: MatchedVia | None = None


class ProductsResponse(BaseModel):
    items: list[ProductOut]


class RegistrationsResponse(BaseModel):
    items: list[Registration]
    coverage: list[CountryCoverage] | None = None
    warnings: list[str] | None = None
    disclaimer: str


class SourcesResponse(BaseModel):
    items: list[SourceInfo]
