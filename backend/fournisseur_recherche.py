"""Recherche et comparaison de prix fournisseurs.

MODELE : LA REQUETE EST LA SPECIFICATION
----------------------------------------
Ce que le chiffreur tape definit le cahier des charges. Tout produit qui
satisfait ces termes est comparable, et le RESTE du descriptif n'entre
pas en compte.

"disjoncteur 16a courbe c ph+n" rend donc comparables un ABB a 6,83 EUR,
un Schneider a 8,51 EUR et un Legrand a 8,68 EUR, bien qu'ils n'aient ni
la meme marque, ni la meme reference, ni le meme libelle. C'est le bon
comportement : le chiffreur cherche le moins cher qui respecte la spec.

Ce modele en remplace un premier, fonde sur l'identite produit (EAN puis
reference fabricant). Mesure sur le catalogue consolide de 914 628
lignes : la reference fabricant seule produit 98,6 % de faux
rapprochements, et l'EAN n'est renseigne que chez 2 fournisseurs sur 5,
avec 0,02 % de recouvrement. L'identite produit est une voie sans issue ;
l'equivalence fonctionnelle definie par la requete fonctionne.

GARANTIE D'INCLUSION, ABSOLUE
-----------------------------
Tout produit contenant les termes demandes est renvoye, meme si son
libelle contient bien davantage. La pertinence TRIE, elle ne FILTRE
jamais. Aucun produit ne peut etre ecarte par un score trop faible.

Les produits d'une autre nature (differentiel quand on demande un
disjoncteur simple, reconditionne quand on veut du neuf) ne sont pas
supprimes mais ISOLES dans une rubrique a part, comptes et consultables.

TOUT SE PASSE EN SQL
--------------------
L'endpoint existant /catalog/search charge le catalogue en memoire puis
filtre en Python. Acceptable pour 712 pricing_items, impossible pour
914 628 offres fournisseurs. Les requetes ci-dessous s'appuient sur la
colonne generee recherche_norm et son index trigramme
(migration 20260912070000).
"""
from __future__ import annotations

import re
import statistics

from sqlalchemy import text

from database import get_current_tenant, tenant_session
from vocabulaire_btp import (
    QUALIFIANTS,
    est_regex,
    fusionne_composes,
    libelles,
    nu,
)

# Bornes de pagination. 200 est un plafond de protection : au-dela, la
# reponse depasse ce qu'un ecran peut exploiter et la serialisation coute
# plus que la requete.
LIMITE_DEFAUT = 50
LIMITE_MAX = 200

# Colonnes renvoyees. Explicites plutot que SELECT *, pour ne pas
# exposer par accident une colonne ajoutee plus tard.
CHAMPS = """
    o.id,
    f.name              AS fournisseur,
    o.raw_label         AS designation,
    o.brand             AS marque,
    o.raw_reference     AS reference_fournisseur,
    o.manufacturer_ref  AS reference_fabricant,
    o.ean               AS code_ean,
    o.price_ht          AS prix_net_ht,
    o.price_ht_per_unit AS prix_unitaire_ht,
    o.raw_unit          AS unite_vente,
    o.product_url       AS url_produit,
    o.source_date       AS date_prix,
    o.recherche_norm
"""


def normalise(texte: str) -> str:
    """Meme normalisation que blueseatra.normalise_recherche en SQL.

    Les decimales collees sont preservees : "2,5 mm2" ne doit pas
    devenir "2 5 mm2", sinon une recherche sur "2,5" ne trouve plus rien
    et la section est perdue -- ce qui faisait confondre le fil 1,5 mm2
    et le 2,5 mm2, deux articles de prix differents.
    """
    import unicodedata

    texte = re.sub(r"(\d)[.,](\d)", r"\1.\2", str(texte or ""))
    texte = unicodedata.normalize("NFKD", texte)
    texte = "".join(c for c in texte if not unicodedata.combining(c))
    texte = texte.lower()
    return " ".join(re.sub(r"[^a-z0-9.+]+", " ", texte).split())


def _conditions(requete: str) -> tuple[list[str], dict, list[dict]]:
    """Traduit la requete en conditions SQL parametrees.

    ET entre les termes, OU entre les ecritures d'un meme terme.

    SECURITE : aucune valeur issue de l'utilisateur n'est concatenee dans
    le SQL. Les motifs voyagent en parametres lies, y compris les
    expressions regulieres. C'est la meme regle que pour set_config du
    tenant : un identifiant de cloisonnement ou un motif de recherche ne
    se colle jamais dans une chaine SQL.
    """
    bruts = [t for t in normalise(requete).split() if t]
    # Fusionne les criteres ecrits en deux mots ("courbe c") et ecarte
    # les termes d'une seule lettre isoles : traites separement, le "c"
    # de "courbe c" devenait un motif LIKE '%c%' correspondant a presque
    # toutes les lignes -- pertinence perdue et index trigramme inutile.
    termes = fusionne_composes(bruts)

    conditions: list[str] = []
    parametres: dict = {}
    reconnus: list[dict] = []

    for i, (libelle_terme, alternatives) in enumerate(termes):
        morceaux = []
        for j, motif in enumerate(alternatives):
            cle = f"m{i}_{j}"
            if est_regex(motif):
                # ~ et non ~* : recherche_norm est deja en minuscules,
                # l'insensibilite a la casse serait un cout inutile.
                morceaux.append(f"o.recherche_norm ~ :{cle}")
                parametres[cle] = nu(motif)
            else:
                # LIKE '%...%' : accelere par l'index trigramme.
                morceaux.append(f"o.recherche_norm LIKE :{cle}")
                parametres[cle] = f"%{nu(motif)}%"
        conditions.append("(" + " OR ".join(morceaux) + ")")

        # On ne signale que ce qui a REELLEMENT ete elargi, et en clair :
        # afficher une expression reguliere a un chiffreur n'a aucun sens.
        clair = libelles(libelle_terme)
        if clair:
            reconnus.append({"saisi": libelle_terme, "equivalences": clair})

    return conditions, parametres, reconnus


def _separe_qualifiants(lignes: list[dict], requete: str):
    """Isole les produits porteurs d'un qualifiant non demande.

    Rien n'est supprime : la fonction rend deux ensembles. Sur
    "disjoncteur 16a courbe c ph+n", 85 des 174 resultats etaient des
    differentiels, de prix median 189,86 EUR contre 6,83 EUR pour le
    moins cher des simples -- le prix median affiche passait de 33 a
    131 EUR. La comparaison etait fausse.
    """
    q = normalise(requete)
    retenus = list(lignes)
    isoles: list[dict] = []

    for libelle, motif in QUALIFIANTS:
        if re.search(motif, q):
            # Le qualifiant fait partie de la demande : il reste dedans.
            continue
        compile_ = re.compile(motif)
        porteurs = [l for l in retenus
                    if compile_.search(l.get("recherche_norm") or "")]
        if not porteurs:
            continue
        retenus = [l for l in retenus if l not in porteurs]
        prix = [l["prix_net_ht"] for l in porteurs
                if l.get("prix_net_ht") is not None]
        isoles.append({
            "libelle": libelle,
            "nombre": len(porteurs),
            "prix_median": round(statistics.median(prix), 2) if prix else None,
        })

    return retenus, isoles


# --- criteres a affiner --------------------------------------------------

def _poles(t: str):
    for motif, val in (
        (r"\b3p\+n\b|\btetrapolaire\b|\b4p\b", "3P+N / 4P"),
        (r"(?<![2-9])1?p\+n|\bph\+n\b|\bu\+n\b|\bphase neutre\b", "1P+N"),
        (r"\b3p\b(?!\+)|\btripolaire\b", "3P"),
        (r"\b2p\b(?!\+)|\bbipolaire\b", "2P"),
        (r"(?<![0-9])\b1p\b(?!\+)|\bunipolaire\b", "1P"),
    ):
        if re.search(motif, t):
            return val
    return None


def _courbe(t: str):
    m = re.search(r"\b(?:courbe|cbe|crb) ?([bcd])\b", t)
    return f"courbe {m.group(1).upper()}" if m else None


def _section(t: str):
    m = re.search(r"\b(\d+(?:\.\d+)?) ?mm2\b", t)
    return f"{m.group(1)} mm2" if m else None


def _dimensions(t: str):
    d = re.findall(r"\b(\d+(?:\.\d+)?(?: ?x ?\d+(?:\.\d+)?){1,2})\b", t)
    if not d:
        return None
    parties = [x.strip() for x in d[0].split("x")]
    return "x".join(sorted(parties, key=float))


def _volume(t: str):
    m = re.search(r"\b(\d+(?:\.\d+)?) ?(?:l|litres?)\b", t)
    return f"{m.group(1)} L" if m else None


CRITERES = [
    ("pôles", _poles),
    ("courbe", _courbe),
    ("section", _section),
    ("dimensions", _dimensions),
    ("volume", _volume),
]


def _criteres_a_affiner(lignes: list[dict], requete: str) -> list[dict]:
    """Sur quoi les resultats sont-ils heterogenes ?

    Si la requete est imprecise, on compare des choses incomparables :
    "disjoncteur 16a" ramene du 1P et du 4P, dont les prix n'ont rien a
    voir. La responsabilite de la precision revient a la requete, mais
    l'outil doit AIDER a la preciser.

    Seuls les criteres ABSENTS de la requete sont proposes : inutile de
    suggerer d'affiner sur la courbe si "courbe c" est deja tape.
    """
    q = normalise(requete)
    sortie = []
    for nom, extrait in CRITERES:
        compte: dict[str, int] = {}
        for ligne in lignes:
            val = extrait(ligne.get("recherche_norm") or "")
            if val:
                compte[val] = compte.get(val, 0) + 1
        if len(compte) < 2:
            continue
        # Deja contraint par la requete ?
        if any(normalise(v).split()[0] in q for v in list(compte)[:3]):
            continue
        valeurs = sorted(compte.items(), key=lambda x: -x[1])
        sortie.append({
            "critere": nom,
            "valeurs": [{"valeur": v, "nombre": n} for v, n in valeurs[:6]],
        })
    return sortie


# --- point d'entree -----------------------------------------------------

async def recherche(requete: str, limite: int = LIMITE_DEFAUT,
                    inclure_qualifiants: bool = False) -> dict:
    """Recherche par inclusion, avec comparaison entre fournisseurs.

    Passe par tenant_session(), donc app.tenant_id est emis et RLS
    cloisonne les lignes. Aucun filtre tenant_id n'est ecrit a la main
    ici : le dupliquer donnerait l'illusion d'une protection et
    masquerait une eventuelle defaillance de la politique.
    """
    requete = (requete or "").strip()
    if not requete:
        raise ValueError("La requête est vide.")
    limite = max(1, min(int(limite), LIMITE_MAX))

    conditions, parametres, reconnus = _conditions(requete)
    if not conditions:
        raise ValueError("La requête ne contient aucun terme exploitable.")

    # CEINTURE ET BRETELLES -- le filtre tenant_id est EXPLICITE en plus
    # de RLS, et ce n'est pas une redondance inutile.
    #
    # RLS ne cloisonne que si le moteur metier tourne sous blueseatra_app
    # (NOBYPASSRLS). Or backend/database.py prevoit un REPLI : sans
    # DATABASE_URL_APP, le moteur metier est `postgres`, qui a
    # BYPASSRLS et possede les tables. Dans ce mode, une requete SQL
    # brute sans filtre renverrait les lignes de TOUS les tenants.
    #
    # Le repli est un etat normal et documente -- il a servi trois fois
    # le 12/09/2026 pour restaurer la production. Une requete qui fuite
    # en repli est donc une fuite reelle, pas un cas theorique.
    #
    # Tout le reste du code filtre deja tenant_id explicitement (101
    # appels verifies par l'audit d'isolation). Ce module ne fait pas
    # exception.
    tenant = get_current_tenant()
    if not tenant:
        raise RuntimeError(
            "Recherche fournisseurs appelee sans tenant courant. Sous RLS "
            "la requete renverrait zero ligne sans erreur ; en mode repli "
            "elle renverrait les lignes de TOUS les tenants. Corriger "
            "l'appelant : la dependance get_current doit avoir pose le "
            "contexte via set_current_tenant."
        )
    parametres["tenant_id"] = tenant

    sql = text(f"""
        SELECT {CHAMPS}
        FROM blueseatra.supplier_offers o
        LEFT JOIN blueseatra.suppliers f
               ON f.id = o.supplier_id
              AND f.tenant_id = o.tenant_id
        WHERE o.tenant_id = :tenant_id
          AND {' AND '.join(conditions)}
        ORDER BY o.price_ht ASC NULLS LAST
    """)

    async with tenant_session() as session:
        resultat = await session.execute(sql, parametres)
        lignes = [dict(r) for r in resultat.mappings().all()]

    total = len(lignes)

    if inclure_qualifiants:
        retenus, isoles = lignes, []
    else:
        retenus, isoles = _separe_qualifiants(lignes, requete)

    criteres = _criteres_a_affiner(retenus, requete)

    prix = [l["prix_net_ht"] for l in retenus
            if l.get("prix_net_ht") is not None and l["prix_net_ht"] > 0]
    bloc_prix = None
    if prix:
        bas, haut = min(prix), max(prix)
        bloc_prix = {
            "min": round(bas, 2),
            "max": round(haut, 2),
            "median": round(statistics.median(prix), 2),
            "ecart_pct": round(100 * (haut - bas) / bas) if bas > 0 else 0,
        }

    # Le moins cher chez chaque fournisseur : la vue de negociation.
    meilleurs: dict[str, dict] = {}
    for ligne in retenus:
        p = ligne.get("prix_net_ht")
        nom = ligne.get("fournisseur") or "inconnu"
        if p is None or p <= 0:
            continue
        if nom not in meilleurs or p < meilleurs[nom]["prix_net_ht"]:
            meilleurs[nom] = {
                "fournisseur": nom,
                "prix_net_ht": round(p, 2),
                "designation": ligne.get("designation"),
                "id": ligne.get("id"),
            }

    for ligne in retenus:
        ligne.pop("recherche_norm", None)

    return {
        "requete": requete,
        "total": total,
        "comparables": len(retenus),
        "termes_reconnus": reconnus,
        "prix": bloc_prix,
        "resultats": retenus[:limite],
        "moins_cher_par_fournisseur": sorted(
            meilleurs.values(), key=lambda x: x["prix_net_ht"]),
        "qualifiants_isoles": isoles,
        "criteres_a_affiner": criteres,
    }


async def liste_fournisseurs() -> dict:
    """Fournisseurs du tenant, avec volumetrie et qualite des donnees.

    Le taux d'EAN renseigne n'est pas decoratif : il indique au chiffreur
    a quel point les offres de ce fournisseur sont rapprochables. Mesure
    sur le catalogue consolide : Rexel 77,8 %, Point.P 93,8 %, et ZERO
    chez Prolians, La Plateforme et SFIC.
    """
    tenant = get_current_tenant()
    if not tenant:
        raise RuntimeError(
            "liste_fournisseurs() appelee sans tenant courant. Voir la "
            "note de recherche() : en mode repli, l'absence de filtre "
            "exposerait tous les tenants."
        )

    sql = text("""
        SELECT
            coalesce(f.name, 'inconnu')                       AS nom,
            count(*)                                          AS references_,
            max(o.source_date)                                AS derniere_maj,
            round(100.0 * count(o.ean) / nullif(count(*), 0), 1)      AS taux_ean,
            round(100.0 * count(o.price_ht) / nullif(count(*), 0), 1) AS prix_pct
        FROM blueseatra.supplier_offers o
        LEFT JOIN blueseatra.suppliers f
               ON f.id = o.supplier_id
              AND f.tenant_id = o.tenant_id
        WHERE o.tenant_id = :tenant_id
        GROUP BY coalesce(f.name, 'inconnu')
        ORDER BY count(*) DESC
    """)
    async with tenant_session() as session:
        resultat = await session.execute(sql, {"tenant_id": tenant})
        lignes = [dict(r) for r in resultat.mappings().all()]

    return {
        "fournisseurs": [
            {
                "nom": l["nom"],
                "references": l["references_"],
                "derniere_maj": (l["derniere_maj"].isoformat()
                                 if l["derniere_maj"] else None),
                "taux_ean": float(l["taux_ean"] or 0),
                "prix_renseignes_pct": float(l["prix_pct"] or 0),
            }
            for l in lignes
        ],
        "total_references": sum(l["references_"] for l in lignes),
    }
