"""Client IA interchangeable (SDK `openai`, compatible avec tout fournisseur qui parle le même protocole).

Configuration uniquement par le fichier .env (jamais dans le code) :
    AI_BASE_URL   adresse du fournisseur (vide = OpenAI)
    AI_API_KEY    clé (vide = PAS d'IA : l'agent passe en mode dégradé par mots-clés)
    AI_MODEL      nom du modèle
    AI_PROVIDER   nom affiché dans la réponse (facultatif)

Règle d'or : ce module ne plante JAMAIS. Clé absente, réseau coupé, quota dépassé, réponse
illisible... `complete()` renvoie alors None et l'agent continue sans IA.
"""
import logging
import os
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

log = logging.getLogger("lpc.llm")

TIMEOUT_SECONDS = 30
# Valeurs d'exemple de .env.example : elles ne comptent pas comme une vraie configuration
PLACEHOLDERS = {"", "replace_me", "changeme", "change-me", "none", "null"}


def _env(name):
    return os.environ.get(name, "").strip()


def _set(value):
    return value.lower() not in PLACEHOLDERS


def is_configured():
    """True si une clé ET un modèle sont renseignés. Sinon : mode dégradé (mots-clés + gabarits)."""
    return _set(_env("AI_API_KEY")) and _set(_env("AI_MODEL"))


def generator_info():
    """{provider, model} à renvoyer dans `generator` quand l'IA a servi."""
    provider = _env("AI_PROVIDER")
    if not _set(provider):
        host = urlparse(_env("AI_BASE_URL")).hostname
        provider = host or "openai"
    return {"provider": provider, "model": _env("AI_MODEL")}


@lru_cache(maxsize=4)
def _client(api_key, base_url):
    from openai import OpenAI   # import tardif : le prototype démarre même si le SDK manque
    # max_retries=0 : au premier échec on bascule en mode dégradé au lieu d'attendre
    return OpenAI(api_key=api_key, base_url=base_url or None, timeout=TIMEOUT_SECONDS, max_retries=0)


def complete(system, user, json_mode=False):
    """Un appel au modèle (temperature 0). Renvoie le texte, ou None si IA absente ou en échec.

    json_mode=True demande une sortie JSON (le mot « JSON » doit alors figurer dans le prompt).
    """
    if not is_configured():
        return None
    try:
        args = {
            "model": _env("AI_MODEL"),
            "temperature": 0,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        }
        if json_mode:
            args["response_format"] = {"type": "json_object"}
        response = _client(_env("AI_API_KEY"), _env("AI_BASE_URL")).chat.completions.create(**args)
        return (response.choices[0].message.content or "").strip() or None
    except Exception as error:   # noqa: BLE001 - volontairement large : jamais de plantage
        # On ne journalise que le type d'erreur (le message peut contenir des détails de requête)
        log.warning("Appel IA en échec (%s) : mode dégradé.", type(error).__name__)
        return None
