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

import json
import re
import statistics

from sqlalchemy import text

from database import get_current_tenant, tenant_session
import catalogue_commun
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
# Plafond de lignes lues en SQL avant le traitement Python. Le catalogue
# consolide compte ~944 000 offres : un terme large ("cable") en
# ramenerait des dizaines de milliers en memoire sur un service a 512 Mo.
# Les lignes sont triees par prix croissant, les moins cheres sont donc
# toujours dans la fenetre ; `tronque` signale que la liste est partielle.
PLAFOND_LIGNES = 5000

# Seules les offres de la VERSION ACTIVE de leur catalogue sont visibles.
# Un import lourd ecrit d'abord une version non active (script
# scripts/fournisseur/import_catalogue_lourd.py) : sans ce filtre, ses
# lignes apparaitraient pendant l'import puis en double avec l'ancienne
# version. Les offres sans catalogue (historique) restent visibles.
FILTRE_VERSION_ACTIVE = """
    o.is_active
    AND (o.catalog_id IS NULL
         OR o.version_id IN (
            SELECT c.active_version_id FROM blueseatra.catalogs c
            WHERE c.tenant_id IN (:tenant_id, :commun)
              AND c.active_version_id IS NOT NULL)
         -- offres historiques dont le catalogue n'a jamais ete cree :
         -- elles restent visibles comme avant le versionnage.
         OR o.catalog_id NOT IN (
            SELECT c.id FROM blueseatra.catalogs c WHERE c.tenant_id IN (:tenant_id, :commun)))
"""

# Perimetre : les offres de l'entreprise + le catalogue commun, sauf si
# l'entreprise l'a masque. Filtre EXPLICITE (mode repli sous postgres).
FILTRE_PERIMETRE = """
    (o.tenant_id = :tenant_id
     OR (:avec_commun AND o.tenant_id = :commun))
"""
# Sous-requete NON correlee : evaluee une fois par recherche (et non par
# ligne). Mesure sur 943 681 offres : surcout ~150 ms contre ~300 ms en
# EXISTS correle. version_id est une cle primaire de catalog_versions :
# aucun risque de collision entre tenants.

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
    (o.tenant_id = :commun) AS catalogue_commun,
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


def motif_postgres(motif: str) -> str:
    """Expression reguliere du vocabulaire (syntaxe Python) -> PostgreSQL.

    Le vocabulaire ecrit les limites de mot en \\b, comme Python. Or en
    PostgreSQL, \\b signifie RETOUR ARRIERE (caractere 0x08) : les motifs
    "courbe c", "2p", "ph+n", "alu", "diff"... ne trouvaient AUCUNE ligne
    (constate le 01/10/2026 : "disjoncteur 16a courbe c" -> 0 resultat).
    La limite de mot PostgreSQL s'ecrit \\y.
    """
    return motif.replace("\\b", "\\y")


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
                parametres[cle] = motif_postgres(nu(motif))
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


def termes_recherche(requete: str) -> list[list[dict]]:
    """Memes termes que _conditions(), au format de offres_candidates().

    ET entre les termes, OU entre les ecritures d'un meme terme. Les motifs
    sont identiques a ceux de _conditions() (meme normalisation, memes
    jokers) : la fonction SQL les injecte en litteraux echappes (%L).
    """
    termes = fusionne_composes([t for t in normalise(requete).split() if t])
    return [[{"op": "regex", "v": motif_postgres(nu(m))} if est_regex(m)
             else {"op": "like", "v": f"%{nu(m)}%"} for m in alternatives]
            for _, alternatives in termes]


# Appel de blueseatra.offres_candidates (migration 20261001180000).
# POURQUOI UNE FONCTION SQL : sous blueseatra_app, la RLS empeche
# PostgreSQL d'utiliser l'index trigramme (LIKE n'est pas LEAKPROOF) ;
# chaque recherche filtrait ligne a ligne (27 s au comparateur, > 30 s au
# selecteur du devis, constate le 01/10/2026). La fonction, SECURITY
# DEFINER, ne renvoie que des identifiants et colonnes de tri, et refuse
# tout tenant autre que l'entreprise courante ou le catalogue commun. Les
# fiches sont relues ENSUITE par id, sous RLS, avec filtre tenant explicite.
SQL_CANDIDATES = """
    SELECT c.id, c.tenant_id, c.supplier_id, c.price_ht, c.recherche_norm
      FROM blueseatra.offres_candidates(
               CAST(:tenants AS text[]), CAST(:termes AS jsonb), :limite,
               :version, :hist, :versions_actives, :tri_prix) c
"""


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
    parametres["commun"] = catalogue_commun.TENANT_COMMUN

    # RECHERCHE EN DEUX TEMPS. (1) Les 5 000 candidats les moins chers
    # viennent de blueseatra.offres_candidates (voir SQL_CANDIDATES) :
    # filtre trigramme ou index par prix selon l'estimation, versions
    # actives seulement. (2) Les fiches completes (1,1 ko chacune) ne sont
    # lues ensuite QUE pour les lignes affichees et les meilleurs prix par
    # fournisseur. Memes lignes, meme ordre, memes statistiques qu'avant.
    sql = text(SQL_CANDIDATES + """
        ORDER BY c.price_ht ASC NULLS LAST, c.id
    """)
    parametres_fonction = {
        "termes": json.dumps(termes_recherche(requete)),
        "limite": PLAFOND_LIGNES, "version": None, "hist": None,
        "versions_actives": True, "tri_prix": True,
    }
    sql_noms = text("""
        SELECT f.tenant_id, f.id, f.name FROM blueseatra.suppliers f
         WHERE f.tenant_id = :tenant_id OR f.tenant_id = :commun
    """)
    sql_fiches = text(f"""
        SELECT {CHAMPS}
        FROM blueseatra.supplier_offers o
        LEFT JOIN blueseatra.suppliers f
               ON f.id = o.supplier_id
              AND f.tenant_id = o.tenant_id
        WHERE o.id = ANY(:ids)
          AND (o.tenant_id = :tenant_id OR o.tenant_id = :commun)
    """)

    async with tenant_session() as session:
        avec_commun = not await catalogue_commun.est_masque(session, tenant)
        parametres_fonction["tenants"] = (
            [tenant, catalogue_commun.TENANT_COMMUN] if avec_commun else [tenant])
        resultat = await session.execute(sql, parametres_fonction)
        lignes = [dict(r) for r in resultat.mappings().all()]
        for l in lignes:
            l["prix_net_ht"] = l.pop("price_ht")
        noms = {(r["tenant_id"], r["id"]): r["name"] for r in (await session.execute(
            sql_noms, {"tenant_id": tenant, "commun": parametres["commun"]})).mappings()}
        for l in lignes:
            l["fournisseur"] = noms.get((l.pop("tenant_id"), l.pop("supplier_id")))

        total = len(lignes)
        tronque = total >= PLAFOND_LIGNES

        if inclure_qualifiants:
            retenus, isoles = lignes, []
        else:
            retenus, isoles = _separe_qualifiants(lignes, requete)

        # Ids a detailler : les lignes affichees + le moins cher de chaque
        # fournisseur (meme regle que plus bas).
        a_lire = [l["id"] for l in retenus[:limite]]
        vus: dict[str, tuple] = {}
        for l in retenus:
            p, nom = l.get("prix_net_ht"), l.get("fournisseur") or "inconnu"
            if p is not None and p > 0 and (nom not in vus or p < vus[nom][0]):
                vus[nom] = (p, l["id"])
        a_lire += [i for _, i in vus.values()]
        fiches = {}
        if a_lire:
            res = await session.execute(sql_fiches, {
                "ids": list(dict.fromkeys(a_lire)), "tenant_id": tenant,
                "commun": parametres["commun"]})
            fiches = {r["id"]: dict(r) for r in res.mappings()}

    # Les lignes detaillees reprennent l'ordre et le perimetre du premier
    # passage ; les autres gardent seulement prix/fournisseur/recherche.
    retenus = [fiches.get(l["id"], l) for l in retenus]

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
        "tronque": tronque,
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

    sql = text(f"""
        SELECT
            coalesce(f.name, 'inconnu')                       AS nom,
            count(*)                                          AS references_,
            max(o.source_date)                                AS derniere_maj,
            round(100.0 * count(o.ean) / nullif(count(*), 0), 1)      AS taux_ean,
            round(100.0 * count(o.price_ht) / nullif(count(*), 0), 1) AS prix_pct,
            bool_or(o.tenant_id = :commun)                    AS catalogue_commun
        FROM blueseatra.supplier_offers o
        LEFT JOIN blueseatra.suppliers f
               ON f.id = o.supplier_id
              AND f.tenant_id = o.tenant_id
        WHERE {FILTRE_PERIMETRE}
          AND (o.tenant_id = :tenant_id OR o.tenant_id = :commun)
          AND {FILTRE_VERSION_ACTIVE}
        GROUP BY coalesce(f.name, 'inconnu'), (o.tenant_id = :commun)
        ORDER BY count(*) DESC
    """)
    async with tenant_session() as session:
        avec_commun = not await catalogue_commun.est_masque(session, tenant)
        resultat = await session.execute(sql, {"tenant_id": tenant, "avec_commun": avec_commun,
                                               "commun": catalogue_commun.TENANT_COMMUN})
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
                "catalogue_commun": bool(l["catalogue_commun"]),
            }
            for l in lignes
        ],
        "total_references": sum(l["references_"] for l in lignes),
    }
