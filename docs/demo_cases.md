# Cas de démo (comparaisons réelles)

Généré par `scripts/find_demo_cases.py` le 2026-10-10 05:27 UTC, lecture seule sur la base partagée. Les chiffres sont des comptes de lignes extraites : une absence ne prouve jamais une absence d'homologation. Les sœurs sont des hypothèses (`to_verify`). Les doses gardent leur unité originale (jamais converties).

Base URL des requêtes : `http://localhost:3000/api` (lancer `uvicorn backend.app.main:app --port 3000`).

## a) Produits pilotes et sœurs : lignes comparables par paire de pays

`use` = culture × cible, `crop` = culture seule (granularity=crop). Trié par `crop` puis `use`.

| Produit | ID | Type | Paire | Lignes use | Lignes crop |
|---|---|---|---|---|---|
| LALGUARD M52 OD | P-LPC-M52 | pilote | FR,DE | 2 | 5 |
| LALGUARD M52 OD | P-LPC-M52 | pilote | CA,DE | 0 | 5 |
| LALSTOP G46 WG | P-LPC-G46 | pilote | CA,DE | 0 | 4 |
| PRESTOP | P-CA-28820 | sœur (hypothèse) | CA,DE | 0 | 4 |
| PRESTOP WG | P-CA-32404 | sœur (hypothèse) | CA,DE | 0 | 4 |
| PRESTOP | P-FR-EPHY-2120177 | PRESTOP | CA,DE | 0 | 4 |
| PRESTOP 4B | P-FR-EPHY-2150847 | PRESTOP | CA,DE | 0 | 4 |
| PRESTOP (WP) | P-DE-BVL-027495-00 | PRESTOP | CA,DE | 0 | 4 |
| LALSTOP G46 WG | P-LPC-G46 | pilote | FR,DE | 1 | 3 |
| PRESTOP | P-CA-28820 | sœur (hypothèse) | FR,DE | 1 | 3 |
| PRESTOP WG | P-CA-32404 | sœur (hypothèse) | FR,DE | 1 | 3 |
| PRESTOP | P-FR-EPHY-2120177 | PRESTOP | FR,DE | 1 | 3 |
| LALSTOP G46 WG | P-LPC-G46 | pilote | FR,CA | 0 | 1 |
| LALGUARD M52 OD | P-LPC-M52 | pilote | FR,CA | 0 | 1 |
| PRESTOP | P-CA-28820 | sœur (hypothèse) | FR,CA | 0 | 1 |
| PRESTOP WG | P-CA-32404 | sœur (hypothèse) | FR,CA | 0 | 1 |
| PRESTOP | P-FR-EPHY-2120177 | PRESTOP | FR,CA | 0 | 1 |
| PRESTOP 4B | P-FR-EPHY-2150847 | PRESTOP | FR,CA | 0 | 1 |

Requêtes à utiliser en démo :

- LALGUARD M52 OD (FR,DE, 5 lignes crop) : `GET /compare?productId=P-LPC-M52&countries=FR,DE&granularity=crop`
- LALGUARD M52 OD (CA,DE, 5 lignes crop) : `GET /compare?productId=P-LPC-M52&countries=CA,DE&granularity=crop`
- LALSTOP G46 WG (CA,DE, 4 lignes crop) : `GET /compare?productId=P-LPC-G46&countries=CA,DE&granularity=crop`
- PRESTOP (CA,DE, 4 lignes crop) : `GET /compare?productId=P-CA-28820&countries=CA,DE&granularity=crop`
- PRESTOP WG (CA,DE, 4 lignes crop) : `GET /compare?productId=P-CA-32404&countries=CA,DE&granularity=crop`
- LALSTOP G46 WG (FR,CA, 1 lignes crop) : `GET /compare?productId=P-LPC-G46&countries=FR,CA&granularity=crop`
- LALGUARD M52 OD (FR,CA, 1 lignes crop) : `GET /compare?productId=P-LPC-M52&countries=FR,CA&granularity=crop`
- PRESTOP (FR,CA, 1 lignes crop) : `GET /compare?productId=P-CA-28820&countries=FR,CA&granularity=crop`

## b) Top 10 des couples culture × cible présents en FR et en DE

Nombre de produits (non synthétiques) ayant un usage sur ce couple, par pays. Trié par le plus petit des deux comptes.

| Culture | Cible | Produits FR | Produits DE |
|---|---|---|---|
| Barley | Rhynchosporium leaf blotch (Rhynchosporium secalis) | 115 | 164 |
| Rye | Rhynchosporium leaf blotch (Rhynchosporium secalis) | 101 | 136 |
| Wheat | Fusarium diseases | 91 | 104 |
| Oats | Crown rust | 85 | 55 |
| Wheat | Eyespot | 48 | 44 |
| Grapevine | Botrytis cinerea | 50 | 37 |
| Barley | Eyespot | 34 | 34 |
| Pome fruit | Scab | 103 | 31 |
| Pome fruit | Aphids | 24 | 87 |
| Roses | Aphids | 36 | 23 |

Requêtes :

- Barley × Rhynchosporium leaf blotch (Rhynchosporium secalis) : `GET /products?crop=Barley&target=Rhynchosporium leaf blotch (Rhynchosporium secalis)` puis `GET /compare?productId=<id>&countries=FR,DE&crop=Barley&target=Rhynchosporium leaf blotch (Rhynchosporium secalis)`
- Rye × Rhynchosporium leaf blotch (Rhynchosporium secalis) : `GET /products?crop=Rye&target=Rhynchosporium leaf blotch (Rhynchosporium secalis)` puis `GET /compare?productId=<id>&countries=FR,DE&crop=Rye&target=Rhynchosporium leaf blotch (Rhynchosporium secalis)`
- Wheat × Fusarium diseases : `GET /products?crop=Wheat&target=Fusarium diseases` puis `GET /compare?productId=<id>&countries=FR,DE&crop=Wheat&target=Fusarium diseases`
- Oats × Crown rust : `GET /products?crop=Oats&target=Crown rust` puis `GET /compare?productId=<id>&countries=FR,DE&crop=Oats&target=Crown rust`
- Wheat × Eyespot : `GET /products?crop=Wheat&target=Eyespot` puis `GET /compare?productId=<id>&countries=FR,DE&crop=Wheat&target=Eyespot`

## c) Top 10 des cultures avec des produits retirés ou expirés

Produits distincts par culture et par pays (statut normalisé `withdrawn` ou `expired` vs `active`). Un produit peut compter dans les deux colonnes s'il a plusieurs homologations.

**Aucune culture n'a de produit retiré/expiré avec des usages.** Dans les données actuelles, les homologations retirées (FR : `RETIRE`) n'ont aucun usage extrait, donc aucun lien avec une culture ; DE n'a pas de statut (`unknown`). Ce n'est pas une preuve d'absence de retraits par culture.

| Pays | Statut normalisé | Homologations | Usages |
|---|---|---|---|
| CA | active | 2089 | 87816 |
| CA | unknown | 11 | 489 |
| DE | unknown | 2165 | 82239 |
| FR | active | 1687 | 18023 |
| FR | withdrawn | 11882 | 0 |

Cas de démo possible : lister les retraits sans culture avec `GET /expirations?country=FR`.

Requêtes :

- (voir ci-dessus : `GET /expirations?country=FR`)

## d) Opportunité marché : espaces libres pour le biocontrôle

**Aide à l'analyse, pas une décision réglementaire ; classification biologique/chimique par règle, à vérifier.** Par couple culture × cible normalisés : usages ACTIFS de produits chimiques vs biologiques (catégorie déduite du nom de la substance active, hypothèse). Score = usages chimiques / (1 + usages biologiques). Aucun usage retiré n'existe dans les sources : le classement montre l'état actuel, pas un recul. « Retirés, même substance » = produits retirés du même pays contenant une substance de ces chimiques, SANS lien culture × cible (ce ne sont pas des usages retirés). Un 0 biologique ne prouve pas l'absence de produit biologique homologué.

Requête exacte : `GET /opportunities?country=FR&limit=5`

| Culture × cible | Pays | Usages chimiques | Usages biologiques | Score | Produits LPC / sœurs autorisés | Retirés, même substance |
|---|---|---|---|---|---|---|
| General treatments × Slugs and snails | FR | 165 | 0 | 165.0 | aucun | 285 |
| Wheat × Rust | FR | 151 | 0 | 151.0 | aucun | 254 |
| Wheat × Septoria leaf spot | FR | 134 | 0 | 134.0 | aucun | 481 |
| Barley × Rust | FR | 128 | 0 | 128.0 | aucun | 144 |
| Barley × Rhynchosporium leaf blotch (Rhynchosporium secalis) | FR | 126 | 0 | 126.0 | aucun | 202 |

Requête exacte : `GET /opportunities?country=DE&limit=5`

| Culture × cible | Pays | Usages chimiques | Usages biologiques | Score | Produits LPC / sœurs autorisés | Retirés, même substance |
|---|---|---|---|---|---|---|
| Ornamental plants × Spider mites | DE | 1135 | 0 | 1135.0 | aucun | n/a |
| Ornamental plants × Scale insects | DE | 826 | 0 | 826.0 | aucun | n/a |
| Ornamental plants × Aphids | DE | 743 | 0 | 743.0 | aucun | n/a |
| Ornamental plants × Sucking insects | DE | 712 | 0 | 712.0 | aucun | n/a |
| Bottle gourd × Sucking insects | DE | 594 | 0 | 594.0 | aucun | n/a |

Requête exacte : `GET /opportunities?country=FR&lpcOnly=true&limit=5`

| Culture × cible | Pays | Usages chimiques | Usages biologiques | Score | Produits LPC / sœurs autorisés | Retirés, même substance |
|---|---|---|---|---|---|---|
| Tomato; Eggplant × Brown spot diseases | FR | 51 | 4 | 10.2 | PRESTOP (sister_candidate) | 161 |
| Cucurbits with edible peel × Brown spot diseases | FR | 19 | 1 | 9.5 | PRESTOP (sister_candidate) | 59 |
| Tomato; Eggplant × Mites | FR | 25 | 2 | 8.33 | LALGUARD M52 OD (lpc_product) | 78 |
| Grapevine × Thrips | FR | 18 | 2 | 6.0 | LALGUARD M52 OD (lpc_product) | 110 |
| Cut flowers and foliage plants × Botrytis cinerea | FR | 15 | 2 | 5.0 | PRESTOP (sister_candidate) | 86 |

Requête exacte : `GET /opportunities?productId=P-LPC-M52&limit=5`

| Culture × cible | Pays | Usages chimiques | Usages biologiques | Score | Produits LPC / sœurs autorisés | Retirés, même substance |
|---|---|---|---|---|---|---|
| Leek × Thrips | DE | 7 | 0 | 7.0 | aucun | n/a |
| Onion × Thrips | DE | 7 | 0 | 7.0 | aucun | n/a |
| Grapevine × Thrips | DE | 6 | 0 | 6.0 | aucun | n/a |

Avec `lpcOnly=true`, seuls les couples où un produit LPC, un candidat sœur ou un produit de même substance est déjà autorisé sont gardés (potentiel d'extension d'un produit déjà présent). Avec `productId`, la liste montre les couples où la substance du produit est autorisée dans au moins un pays mais pas dans le pays indiqué. Les produits sœurs et de même substance sont des hypothèses (`to_verify`). Question `/ask` associée : « Où les usages chimiques reculent-ils sur la vigne ? » ou « Quelles opportunités pour LALGUARD M52 ? ».
