"""GET /opportunities : « espaces libres pour le biocontrôle » (HORS CONTRAT, lecture seule).

Idée : pour un couple (pays, culture normalisée, cible normalisée), compter les usages ACTIFS de produits
chimiques et de produits biologiques. Beaucoup de chimiques et peu (ou pas) de biologiques = un espace où un
produit de biocontrôle pourrait trouver sa place.

Limites assumées (rappelées dans chaque réponse) :
- Aucune donnée de retrait d'USAGE n'existe dans les sources : on ne mesure donc PAS un recul, seulement l'état actuel.
- La catégorie biologique / chimique est une HYPOTHÈSE par règle (nom de micro-organisme dans la substance active),
  pas une donnée officielle. « chemical » veut dire « pas identifié comme micro-organisme » (cuivre, soufre,
  pyréthrines… y sont aussi).
- Un compte de biologiques à 0 ne prouve pas qu'aucun produit biologique n'est homologué : les cultures/cibles non
  normalisées sont exclues du calcul (voir `warnings`).
- Ce n'est pas une décision réglementaire.
"""
import re

from . import services
from .db import query, query_many
from .services import DISCLAIMER, build_evidence, cached, nz

ANALYSIS_DISCLAIMER = ("Aide à l'analyse, pas une décision réglementaire ; "
                       "classification biologique/chimique par règle, à vérifier.")
CATEGORY_METHOD = "rule_based"
SCORE_FORMULA = "chemicalUses / (1 + biologicalUses)"

# ---------------------------------------------------------------------------
# Classification biologique / chimique (règle transparente, prudente)
# ---------------------------------------------------------------------------
# Genres latins de bactéries / champignons / levures (+ virus d'insectes). Recherche par sous-chaîne, sans casse :
# « bacillus » reconnaît aussi Lactobacillus et Paenibacillus ; « virus » reconnaît granulovirus, nucléopolyhédrovirus.
BIO_GENERA = [
    "bacillus", "trichoderma", "clonostachys", "gliocladium", "coniothyrium", "metarhizium", "beauveria",
    "pseudomonas", "streptomyces", "saccharomyces", "paecilomyces", "purpureocillium", "isaria", "lecanicillium",
    "verticillium", "akanthomyces", "ampelomyces", "aureobasidium", "pythium", "candida", "metschnikowia",
    "phlebiopsis", "chondrostereum", "arthrobotrys", "virus", "bacteriophage",
]
BIO_REGEX = "(" + "|".join(BIO_GENERA) + ")"
BIO_RE = re.compile(BIO_REGEX, re.IGNORECASE)


def classify_category(active_entity_original, is_lpc=False):
    """('biological' | 'chemical' | 'unknown') d'après la substance active ORIGINALE. Hypothèse par règle.

    - produit LPC (identifiant P-LPC-* ou nom de marque LPC) -> biological ;
    - substance active vide -> unknown ;
    - un nom de micro-organisme dans la substance -> biological ; sinon -> chemical."""
    if is_lpc:
        return "biological"
    if not active_entity_original or not active_entity_original.strip():
        return "unknown"
    return "biological" if BIO_RE.search(active_entity_original) else "chemical"


# Même règle en SQL (calculée une seule fois par produit, puis jointe aux usages)
CATEGORY_SQL = """CASE
    WHEN left(p.product_id, 6) = 'P-LPC-' OR lower(p.commercial_name) = ANY(CAST(:lpc_names AS text[])) THEN 'biological'
    WHEN coalesce(btrim(p.active_entity_original), '') = '' THEN 'unknown'
    WHEN p.active_entity_original ~* :bio_re THEN 'biological'
    ELSE 'chemical' END"""

# Produit LPC, sœur (lien exact par product_aliases) ou de même substance qu'un produit LPC
RELATED_SQL = """(left(p.product_id, 6) = 'P-LPC-' OR lower(p.commercial_name) = ANY(CAST(:lpc_names AS text[]))
                  OR p.product_id = ANY(CAST(:related_ids AS text[])) OR p.active_entity_original ~* :related_re)"""

NEVER_MATCH = "a^"   # motif qui ne correspond à rien (quand aucune substance LPC n'est connue)
ACTIVE_STATUSES = "('active', 'unknown')"   # usages présents dans la source ; 'unknown' = la source ne donne pas de statut (ex. DE)
SISTER_RELATIONS = ("sister_product_candidate", "confirmed_sister_product")
MAX_EVIDENCE_SAMPLES = 2     # usages cités comme preuve, par catégorie et par couple


# ---------------------------------------------------------------------------
# Produits LPC et sœurs (contexte commun, petit, mis en cache)
# ---------------------------------------------------------------------------
@cached(60)
def lpc_context():
    """{'names': noms LPC (minuscules), 'species_re': motif des espèces LPC, 'sisters': {product_id: review_status}}."""
    _, names = services.lpc_names()
    entity_rows, alias_rows = query_many([
        ("SELECT product_id, name_variant, canonical_species FROM active_entity_mapping", None),
        ("""SELECT product_id, relationship_type, review_status, related_product_id
            FROM product_aliases WHERE NOT is_synthetic AND relationship_type IN ('sister_product_candidate', 'confirmed_sister_product')""",
         None)])
    # Espèces : « Metarhizium brunneum », « Gliocladium catenulatum »… (deux premiers mots de chaque variante)
    species = set()
    for r in entity_rows:
        for text in (r["canonical_species"], r["name_variant"]):
            words = (text or "").split()
            if len(words) >= 2:
                species.add(" ".join(words[:2]).lower())
    # Sœurs : le produit qui PORTE l'alias (lien exact) et la cible `related_product_id`. Jamais de jointure par le nom.
    sisters = {}
    for r in alias_rows:
        if not r["product_id"].startswith("P-LPC-"):
            sisters.setdefault(r["product_id"], r["review_status"])
        if r["related_product_id"]:
            sisters.setdefault(r["related_product_id"], r["review_status"])
    return {"names": names, "sisters": sisters,
            "species_re": "(" + "|".join(sorted(species)) + ")" if species else NEVER_MATCH}


def product_family(product_id):
    """Pour /ask « opportunités pour <produit> » : motif de substance + identifiant du produit (ou NotFound)."""
    ref = services.get_product(product_id)   # lève NotFound si inconnu
    rows = query("SELECT name_variant, canonical_species FROM active_entity_mapping WHERE product_id = :p", {"p": product_id})
    species = set()
    for r in rows:
        for text in (r["canonical_species"], r["name_variant"]):
            words = (text or "").split()
            if len(words) >= 2:
                species.add(" ".join(words[:2]).lower())
    return ref, ("(" + "|".join(sorted(species)) + ")" if species else NEVER_MATCH)


def relation_of(row, ctx):
    """('lpc_product' | 'sister_candidate' | 'same_active_substance', review_status) d'un produit trouvé sur un couple."""
    if row["product_id"].startswith("P-LPC-") or (row["commercial_name"] or "").lower() in ctx["names"]:
        return "lpc_product", "validated"
    if row["product_id"] in ctx["sisters"]:
        return "sister_candidate", ctx["sisters"][row["product_id"]] or "to_verify"
    return "same_active_substance", "to_verify"   # même substance qu'un produit LPC : hypothèse


# ---------------------------------------------------------------------------
# Substances actives (pour l'indicateur « retraits au niveau produit »)
# ---------------------------------------------------------------------------
DOSE_TAIL = re.compile(r"\s+\d[\d.,]*\s*(?:g/l|g/kg|kg/l|%|ml/l|g/l)?.*$", re.IGNORECASE)


def substances_of(text):
    """« anthraquinone (Anthraquinone) 151.0 g/L | cuivre … » ou « Dicamba; Prosulfuron » -> {'anthraquinone', 'cuivre'…}.

    Noms en minuscules, 5 caractères minimum (les noms trop courts donneraient trop de faux rapprochements)."""
    out = set()
    for part in re.split(r"[|;]", text or ""):
        part = re.sub(r"\([^)]*\)", " ", part)
        part = DOSE_TAIL.sub("", part).strip().lower()
        part = re.sub(r"[%_]", "", part)
        if len(part) >= 5:
            out.add(part)
    return out


# ---------------------------------------------------------------------------
# Calcul principal
# ---------------------------------------------------------------------------
def name_filters(value, resolver, column, eppo_column, params, key):
    """Filtre culture / cible : nom normalisé (via normalize.py), texte libre (sans casse) ou code EPPO."""
    value = value.strip()
    found = resolver(value)
    like = found["normalized"] if found and found.get("normalized") else value
    params[key] = f"%{like}%"
    if re.fullmatch(r"[A-Z0-9]{5,6}", value):
        params[key + "_code"] = value
        return f"({column} ILIKE :{key} OR {eppo_column} = :{key}_code)"
    return f"{column} ILIKE :{key}"


@cached(120)
def aggregate(country, crop, target, product_id, min_chemical, limit, lpc_only=False):
    """Couples (pays, culture, cible) classés par score décroissant + compteurs de qualité des données."""
    ctx = lpc_context()
    params = {"lpc_names": ctx["names"], "bio_re": BIO_REGEX, "min_chem": min_chemical, "limit": limit,
              "related_ids": list(ctx["sisters"]), "related_re": ctx["species_re"]}
    where = [f"r.status_normalized IN {ACTIVE_STATUSES}", "NOT u.is_synthetic", "NOT r.is_synthetic", "NOT p.is_synthetic"]
    if country:
        where.append("r.country_code = :cc")
        params["cc"] = country
    if crop:
        where.append(name_filters(crop, nz.normalize_crop, "u.crop_name_normalized", "u.eppo_crop_code", params, "crop_like"))
    if target:
        where.append(name_filters(target, nz.normalize_target, "u.target_name_normalized", "u.eppo_target_code", params, "target_like"))
    if product_id:
        # Couples culture × cible où la famille du produit (même substance) a déjà un usage actif, dans n'importe quel pays :
        # on cherche ensuite les pays où ces mêmes couples n'ont presque que des chimiques.
        ref, family_re = product_family(product_id)
        pairs = query(f"""SELECT DISTINCT u.crop_name_normalized AS crop, u.target_name_normalized AS target FROM uses u
                          JOIN registrations r ON r.registration_id = u.registration_id
                          JOIN products p ON p.product_id = r.product_id
                          WHERE r.status_normalized IN {ACTIVE_STATUSES} AND NOT u.is_synthetic AND NOT p.is_synthetic
                            AND u.crop_name_normalized IS NOT NULL AND u.target_name_normalized IS NOT NULL
                            AND (p.product_id = :pid OR p.active_entity_original ~* :family_re)""",
                      {"pid": product_id, "family_re": family_re})
        params["pid"], params["family_re"] = product_id, family_re
        params["family_crops"] = [x["crop"] for x in pairs] or [""]
        params["family_targets"] = [x["target"] for x in pairs] or [""]
        where.append("""EXISTS (SELECT 1 FROM unnest(CAST(:family_crops AS text[]), CAST(:family_targets AS text[])) AS f(crop, target)
                                 WHERE f.crop = u.crop_name_normalized AND f.target = u.target_name_normalized)""")
    base_where = " AND ".join(where)
    # Avec un produit : on ne garde que les couples où la substance du produit n'est PAS déjà autorisée dans ce pays
    family_count = ("count(*) FILTER (WHERE p.product_id = :pid OR p.active_entity_original ~* :family_re)"
                    if product_id else "0")
    family_where = "AND family_uses = 0" if product_id else ""
    lpc_where = "AND lpc_related_uses > 0" if lpc_only else ""

    ranked, quality = query_many([
        (f"""SELECT * FROM (
                SELECT r.country_code, u.crop_name_normalized AS crop, u.target_name_normalized AS target,
                       count(*) FILTER (WHERE cat = 'chemical') AS chemical_uses,
                       count(*) FILTER (WHERE cat = 'biological') AS biological_uses,
                       count(*) FILTER (WHERE cat = 'unknown') AS unknown_uses,
                       count(DISTINCT p.product_id) FILTER (WHERE cat = 'chemical') AS chemical_products,
                       count(DISTINCT p.product_id) FILTER (WHERE cat = 'biological') AS biological_products,
                       count(DISTINCT p.product_id) FILTER (WHERE cat = 'unknown') AS unknown_products,
                       count(*) FILTER (WHERE r.status_normalized = 'unknown') AS unknown_status_uses,
                       {family_count} AS family_uses,
                       count(*) FILTER (WHERE {RELATED_SQL}) AS lpc_related_uses
                FROM uses u
                JOIN registrations r ON r.registration_id = u.registration_id
                JOIN products p ON p.product_id = r.product_id
                CROSS JOIN LATERAL (SELECT {CATEGORY_SQL} AS cat) c
                WHERE {base_where} AND u.crop_name_normalized IS NOT NULL AND u.target_name_normalized IS NOT NULL
                GROUP BY r.country_code, u.crop_name_normalized, u.target_name_normalized) t
             WHERE chemical_uses >= :min_chem {family_where} {lpc_where}
             ORDER BY chemical_uses::float / (1 + biological_uses) DESC, chemical_uses DESC, country_code, crop, target
             LIMIT :limit""", params),
        # Qualité : part des usages actifs qui ont une culture ET une cible normalisées (les autres ne sont pas comptés)
        ("""SELECT r.country_code, count(*) AS total,
                   count(*) FILTER (WHERE u.crop_name_normalized IS NOT NULL AND u.target_name_normalized IS NOT NULL) AS usable
            FROM uses u JOIN registrations r ON r.registration_id = u.registration_id
            WHERE r.status_normalized IN ('active', 'unknown') AND NOT u.is_synthetic AND NOT r.is_synthetic
            GROUP BY r.country_code ORDER BY r.country_code""", None)])
    return ranked, quality


def couples_params(rows):
    return {"ccs": [r["country_code"] for r in rows], "crops": [r["crop"] for r in rows],
            "targets": [r["target"] for r in rows]}


KEYS = """unnest(CAST(:ccs AS text[]), CAST(:crops AS text[]), CAST(:targets AS text[])) AS k(cc, crop, target)
          JOIN uses u ON u.crop_name_normalized = k.crop AND u.target_name_normalized = k.target
          JOIN registrations r ON r.registration_id = u.registration_id AND r.country_code = k.cc
          JOIN products p ON p.product_id = r.product_id"""
BASE_WHERE = f"""r.status_normalized IN {ACTIVE_STATUSES} AND NOT u.is_synthetic AND NOT r.is_synthetic AND NOT p.is_synthetic"""
REG_COLS = "r.registration_id, r.source_id, r.source_record_url, r.collected_at, r.validation_status, r.is_synthetic, r.country_code"


def evidence_of(row, use_id):
    return build_evidence(f"use:{use_id}", row, validation_status=row.get("use_validation"))


def key_of(country, crop, target):
    return (country, crop, target)


def fetch_details(rows, ctx, product_family_re):
    """Preuves, produits LPC/sœurs et substances chimiques des couples retenus (requêtes en parallèle)."""
    base = couples_params(rows)
    related_re = product_family_re or ctx["species_re"]
    lpc_params = {**base, "lpc_names": ctx["names"], "bio_re": BIO_REGEX, "related_ids": list(ctx["sisters"]),
                  "related_re": related_re}
    return query_many([
        # a) produits LPC, sœurs et même substance autorisés sur chaque couple (un usage par produit et par couple)
        (f"""SELECT DISTINCT ON (k.cc, k.crop, k.target, p.product_id)
                    k.cc, k.crop, k.target, p.product_id, p.commercial_name, p.active_entity_original,
                    u.use_id, u.validation_status AS use_validation, {REG_COLS}
             FROM {KEYS}
             WHERE {BASE_WHERE}
               AND {RELATED_SQL}
             ORDER BY k.cc, k.crop, k.target, p.product_id, u.use_id""", lpc_params),
        # b) deux usages cités comme preuve par catégorie (chimique / biologique) et par couple
        (f"""SELECT * FROM (
                SELECT k.cc, k.crop, k.target, c.cat, u.use_id, u.validation_status AS use_validation, {REG_COLS},
                       row_number() OVER (PARTITION BY k.cc, k.crop, k.target, c.cat ORDER BY p.product_id, u.use_id) AS rn
                FROM {KEYS}
                CROSS JOIN LATERAL (SELECT {CATEGORY_SQL} AS cat) c
                WHERE {BASE_WHERE}) t
             WHERE cat IN ('chemical', 'biological') AND rn <= {MAX_EVIDENCE_SAMPLES}""",
         {**base, "lpc_names": ctx["names"], "bio_re": BIO_REGEX}),
        # c) substances des produits chimiques actifs sur chaque couple
        (f"""SELECT DISTINCT k.cc, k.crop, k.target, p.product_id, p.active_entity_original
             FROM {KEYS}
             CROSS JOIN LATERAL (SELECT {CATEGORY_SQL} AS cat) c
             WHERE {BASE_WHERE} AND cat = 'chemical'""", {**base, "lpc_names": ctx["names"], "bio_re": BIO_REGEX}),
    ])


WITHDRAWN_NOTE = ("Produits retirés de même substance, SANS lien culture × cible : ce ne sont pas des usages retirés "
                  "(les sources ne donnent aucun usage pour les produits retirés).")


@cached(600)
def withdrawn_index():
    """{pays: {substance: [homologations retirées]}} : lu une seule fois (≈12 000 lignes) puis gardé en mémoire.

    Le rapprochement est EXACT sur le nom de la substance (substances_of), jamais sur le nom du produit."""
    rows = query("""SELECT r.registration_id, r.country_code, r.source_id, r.source_record_url, r.collected_at,
                           r.validation_status, r.is_synthetic, p.product_id, p.active_entity_original
                    FROM registrations r JOIN products p ON p.product_id = r.product_id
                    WHERE r.status_normalized = 'withdrawn' AND NOT r.is_synthetic AND NOT p.is_synthetic""")
    index = {}
    for r in rows:
        for sub in substances_of(r["active_entity_original"]):
            index.setdefault(r["country_code"], {}).setdefault(sub, []).append(r)
    return index


def withdrawn_same_substance(row, substances):
    """Produits RETIRÉS (même pays) qui contiennent une substance des chimiques actifs du couple, ou None si le pays
    n'a aucun statut « retiré » dans les sources. Renvoie {'n': produits distincts, 'sample': 3 homologations}."""
    by_substance = withdrawn_index().get(row["country_code"])
    if by_substance is None:
        return None
    hits = {}
    for sub in substances:
        for r in by_substance.get(sub, ()):
            hits[r["registration_id"]] = r
    return {"n": len({r["product_id"] for r in hits.values()}), "sample": [hits[k] for k in sorted(hits)[:3]]}


@cached(120)
def opportunities(country=None, crop=None, target=None, limit=20, product_id=None, min_chemical=5, lpc_only=False):
    """GET /opportunities : voir le docstring du module. Renvoie un dict (noms de champs camelCase, hors contrat)."""
    country = country.upper() if country else None
    ranked, quality = aggregate(country, crop, target, product_id, min_chemical, limit, lpc_only)
    ctx = lpc_context()
    family_re = product_family(product_id)[1] if product_id else None

    evidence, items = {}, []
    if ranked:
        lpc_rows, sample_rows, chem_rows = fetch_details(ranked, ctx, family_re)
    else:
        lpc_rows, sample_rows, chem_rows = [], [], []

    lpc_by, sample_by, substances = {}, {}, {}
    index = {key_of(r["country_code"], r["crop"], r["target"]): i for i, r in enumerate(ranked)}
    for r in lpc_rows:
        lpc_by.setdefault(key_of(r["cc"], r["crop"], r["target"]), []).append(r)
    for r in sample_rows:
        sample_by.setdefault(key_of(r["cc"], r["crop"], r["target"]), []).append(r)
    for r in chem_rows:
        substances.setdefault(index[key_of(r["cc"], r["crop"], r["target"])], set()).update(substances_of(r["active_entity_original"]))

    for i, row in enumerate(ranked):
        key = key_of(row["country_code"], row["crop"], row["target"])
        ids = []

        def cite(ev):
            evidence.setdefault(ev["evidenceId"], ev)
            if ev["evidenceId"] not in ids:
                ids.append(ev["evidenceId"])
            return ev["evidenceId"]

        samples = {"chemical": [], "biological": []}
        for s in sample_by.get(key, []):
            samples[s["cat"]].append(cite(evidence_of(s, s["use_id"])))
        products = []
        for p in lpc_by.get(key, []):
            relation, review = relation_of(p, ctx)
            products.append({
                "productId": p["product_id"], "commercialName": p["commercial_name"], "relation": relation,
                "reviewStatus": review, "productCategory": classify_category(p["active_entity_original"], relation == "lpc_product"),
                "categoryMethod": CATEGORY_METHOD, "evidenceIds": [cite(evidence_of(p, p["use_id"]))]})
        products.sort(key=lambda x: (["lpc_product", "sister_candidate", "same_active_substance"].index(x["relation"]), x["commercialName"] or ""))

        wd = None
        found = withdrawn_same_substance(row, substances.get(i, ()))
        if found is not None:
            wd = {"countryCode": row["country_code"], "withdrawnProducts": found["n"],
                  "substancesCompared": len(substances.get(i, ())), "note": WITHDRAWN_NOTE,
                  "evidenceIds": [cite(build_evidence(f"registration:{r['registration_id']}", r)) for r in found["sample"]]}
        bio_uses = row["biological_uses"]
        items.append({
            "countryCode": row["country_code"], "cropNormalized": row["crop"], "targetNormalized": row["target"],
            "chemicalUses": row["chemical_uses"], "biologicalUses": bio_uses, "unknownCategoryUses": row["unknown_uses"],
            "chemicalProducts": row["chemical_products"], "biologicalProducts": row["biological_products"],
            "unknownCategoryProducts": row["unknown_products"],
            "chemicalToBiologicalRatio": round(row["chemical_uses"] / bio_uses, 2) if bio_uses else None,
            "biocontrolSpaceScore": round(row["chemical_uses"] / (1 + bio_uses), 2),
            "usesWithUnknownRegistrationStatus": row["unknown_status_uses"],
            "lpcProducts": products, "withdrawnSameSubstance": wd,
            "evidenceIds": ids, "chemicalEvidenceIds": samples["chemical"], "biologicalEvidenceIds": samples["biological"],
            "productCategoryMethod": CATEGORY_METHOD, "disclaimer": ANALYSIS_DISCLAIMER})

    warnings = [
        "Aucun usage retiré n'existe dans les sources : ce classement montre l'état ACTUEL des usages actifs, pas un recul dans le temps.",
        "Catégorie biologique / chimique : règle sur le nom de la substance active (hypothèse, pas une donnée officielle). "
        "« chemical » = non identifié comme micro-organisme.",
        "Un nombre d'usages biologiques égal à 0 ne prouve pas qu'aucun produit biologique n'est homologué (cultures et cibles non normalisées exclues).",
        "Pays sans statut dans la source (ex. DE) : usages comptés comme présents ; voir usesWithUnknownRegistrationStatus.",
        "Produits LPC et sœurs : les sœurs et produits de même substance sont des hypothèses (reviewStatus to_verify)."]
    for q in quality:
        if country in (None, q["country_code"]) and q["total"] and q["usable"] < q["total"]:
            warnings.append(f"{q['country_code']} : {q['usable']} usages actifs sur {q['total']} ont une culture et une cible normalisées ; "
                            "les autres ne sont pas dans ce classement.")
    if not items:
        warnings.append("Aucun couple trouvé avec ces critères. Cela ne prouve pas l'absence d'opportunité.")
    return {"items": items, "evidence": list(evidence.values()), "warnings": warnings,
            "categoryMethod": CATEGORY_METHOD, "scoreFormula": SCORE_FORMULA, "minChemicalUses": min_chemical,
            "disclaimer": f"{ANALYSIS_DISCLAIMER} {DISCLAIMER}"}
