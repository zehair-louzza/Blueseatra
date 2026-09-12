"""Garde anti-regression : aucun acces a une table cloisonnee sans tenant.

Pourquoi un test STATIQUE et non un test d'integration
-----------------------------------------------------
L'isolation entre tenants de server.py repose sur 23 gardes ecrites a la
main, endpoint par endpoint :

    q = await db.quotes.find_one({"id": quote_id, "tenant_id": cu.tenant_id})
    if not q:
        raise HTTPException(404, "Quote not found")
    await db.quotes.update_one({"id": quote_id}, {"$set": {...}})

Ce motif est correct. Le probleme n'est pas le code actuel -- l'audit du
12/09/2026 n'a releve aucune fuite sur 114 appels -- mais le fait que rien
n'empeche une future contribution d'ajouter un endpoint SANS garde. La
faille serait alors totalement silencieuse : pas d'exception, pas de log,
juste les donnees d'un autre tenant dans une reponse HTTP 200.

Un test d'integration ne couvrirait que les endpoints auxquels on a pense.
Ce test-ci analyse l'ARBRE SYNTAXIQUE de server.py et couvre donc tout
appel present, y compris ceux ajoutes demain. Il tourne sans base de
donnees, sans reseau et sans identifiants, donc il peut reellement bloquer
une fusion en integration continue.

Un test d'integration complementaire (sondage croise A/B avec deux vrais
jetons) reste utile pour valider le comportement a l'execution : voir
test_tenant_isolation_live.py.
"""
import ast
import re
from pathlib import Path

import pytest

from pg_adapter import MODELS, _cols

SERVER_PY = Path(__file__).resolve().parent.parent / "server.py"

OPS_LECTURE_ECRITURE = {
    "find", "find_one", "count_documents",
    "update_one", "update_many", "delete_one", "delete_many",
}

# Tables portant un tenant_id : un acces sans cloisonnement y fuit.
TABLES_CLOISONNEES = {
    name for name, model in MODELS.items() if "tenant_id" in _cols(model)
}


# ---------------------------------------------------------------------------
# Liste d'exceptions EXPLICITE.
#
# Chaque entree est un appel verifie MANUELLEMENT comme sur. Ajouter une
# entree ici doit etre un acte delibere, justifie et relu -- c'est tout
# l'interet du mecanisme. Cle = (nom de fonction, table, operation), jamais
# un numero de ligne : les lignes bougent, les justifications non.
# ---------------------------------------------------------------------------
EXCEPTIONS_VERIFIEES = {
    # --- Operations SYSTEME (aucune entree utilisateur) ---
    # Ces appels balaient volontairement TOUS les tenants. Ce ne sont pas des
    # endpoints : aucun tenant appelant n'existe, donc aucun cloisonnement
    # n'a de sens. Ils doivent en revanche propager le tenant_id de CHAQUE
    # ligne lue, ce qui est verifie a la lecture de leur code.
    ("_requeue_stuck_on_startup", "requests", "update_one"):
        "Filet de securite execute au DEMARRAGE de l'application (appele "
        "depuis l'evenement de startup, pas depuis une requete HTTP). "
        "Remet en file les demandes restees 'queued'/'processing' apres un "
        "redeploy, tous tenants confondus, et propage correctement "
        "r['tenant_id'] dans la file. Aucune entree utilisateur, aucun "
        "tenant appelant : le cloisonnement serait ici un contresens.",

    # --- Appels surs par construction ou garde en amont ---
    ("create_request", "requests", "update_one"):
        "req_id vient d'etre genere dans cette meme fonction : l'objet "
        "appartient au tenant appelant par construction.",

    ("_run_deep_vision", "requests", "update_one"):
        "Tache de fond, pas un endpoint. Son unique appelant "
        "(deep_vision endpoint) execute d'abord "
        "find_one({'id': request_id, 'tenant_id': cu.tenant_id}) et renvoie "
        "404 sinon. Garde en amont, verifiee le 12/09/2026.",

    ("login", "tenant_users", "find_one"):
        "Resolution du tenant PENDANT l'authentification : le tenant n'est "
        "pas encore connu, c'est precisement ce que la requete determine. "
        "Filtre sur user_id, qui provient du mot de passe verifie.",

    ("me", "tenant_users", "find"):
        "Liste les tenants de l'utilisateur authentifie. Filtre sur "
        "cu.user_id, issu du jeton verifie.",
}


def _charge_arbre():
    src = SERVER_PY.read_text(encoding="utf-8")
    return src, ast.parse(src)


def _fonction_englobante(fonctions, lineno):
    """Fonction la plus imbriquee contenant cette ligne."""
    meilleure = None
    for f in fonctions:
        if f.lineno <= lineno <= (f.end_lineno or f.lineno):
            if meilleure is None or f.lineno > meilleure.lineno:
                meilleure = f
    return meilleure


def _collecte_appels():
    """Tout appel db.<table>.<op>() sur une table cloisonnee, non filtre."""
    src, tree = _charge_arbre()
    fonctions = [
        n for n in ast.walk(tree)
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
    ]

    suspects = []
    total = 0

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        f = node.func
        if not isinstance(f, ast.Attribute) or f.attr not in OPS_LECTURE_ECRITURE:
            continue
        if not isinstance(f.value, ast.Attribute):
            continue

        table = f.value.attr
        if table not in TABLES_CLOISONNEES:
            continue

        total += 1
        segment = ast.get_source_segment(src, node) or ""
        if "tenant_id" in segment:
            continue  # cloisonne directement dans l'appel

        fn = _fonction_englobante(fonctions, node.lineno)
        nom_fn = fn.name if fn else "<module>"

        # --- Cloisonnement INDIRECT : le filtre est une variable ---
        # Cas reel : `flt = {"tenant_id": ..., "catalog_id": ...}` reutilise
        # sur plusieurs tables. On resout l'affectation dans la fonction.
        filtre_indirect = False
        if node.args and isinstance(node.args[0], ast.Name) and fn is not None:
            nom_var = node.args[0].id
            for sous in ast.walk(fn):
                if not isinstance(sous, ast.Assign):
                    continue
                if sous.lineno > node.lineno:
                    continue
                cibles = {t.id for t in sous.targets if isinstance(t, ast.Name)}
                if nom_var not in cibles:
                    continue
                aff = ast.get_source_segment(src, sous.value) or ""
                if "tenant_id" in aff:
                    filtre_indirect = True

        # --- GARDE d'appartenance ---
        # Une garde est une LECTURE en base, dans la meme fonction, dont le
        # filtre porte tenant_id. On inspecte l'AST des appels, et non le
        # texte de la fonction : une recherche textuelle de `tenant_id`
        # accepterait n'importe quel dictionnaire de la fonction -- une
        # charge de jeton JWT `{"tenant_id": ...}`, un corps de reponse, un
        # insert -- et declarerait "protege" un appel qui ne l'est pas.
        # Ce faux positif rendrait tout ce test inutile.
        garde = False
        if fn is not None:
            for sous in ast.walk(fn):
                if not isinstance(sous, ast.Call):
                    continue
                sf = sous.func
                if not isinstance(sf, ast.Attribute):
                    continue
                if sf.attr not in {"find_one", "find", "count_documents"}:
                    continue
                if not isinstance(sf.value, ast.Attribute):
                    continue
                if sf.value.attr not in TABLES_CLOISONNEES:
                    continue
                if not sous.args:
                    continue
                arg = ast.get_source_segment(src, sous.args[0]) or ""
                if "tenant_id" in arg:
                    garde = True
                    break

        suspects.append({
            "ligne": node.lineno,
            "table": table,
            "op": f.attr,
            "fonction": nom_fn,
            "garde": garde,
            "filtre_indirect": filtre_indirect,
            "extrait": " ".join(segment.split())[:120],
        })

    return total, suspects


def test_aucun_acces_cloisonne_sans_tenant_ni_garde():
    """LE test. Tout appel non cloisonne doit avoir une garde ou une exception."""
    total, suspects = _collecte_appels()

    assert total > 50, (
        f"Seulement {total} appels detectes sur les tables cloisonnees : "
        "l'analyse est probablement cassee (refactorisation de server.py ?). "
        "Corriger ce test AVANT de le considerer comme vert."
    )

    violations = []
    for s in suspects:
        if s["garde"] or s["filtre_indirect"]:
            continue
        cle = (s["fonction"], s["table"], s["op"])
        if cle in EXCEPTIONS_VERIFIEES:
            continue
        violations.append(s)

    if violations:
        lignes = "\n".join(
            f"  - server.py:{v['ligne']}  {v['table']}.{v['op']}()  "
            f"dans {v['fonction']}()\n      {v['extrait']}"
            for v in sorted(violations, key=lambda x: x["ligne"])
        )
        pytest.fail(
            f"\n{len(violations)} acces a une table cloisonnee SANS filtre "
            f"tenant_id ni garde d'appartenance :\n\n{lignes}\n\n"
            "Corriger de l'une de ces trois facons :\n"
            "  1. ajouter 'tenant_id': cu.tenant_id au filtre (a privilegier) ;\n"
            "  2. faire preceder d'une garde "
            "find_one({'id': ..., 'tenant_id': cu.tenant_id}) + HTTPException(404) ;\n"
            "  3. si l'appel est reellement sur, l'ajouter a "
            "EXCEPTIONS_VERIFIEES avec sa justification.\n"
            "Ne JAMAIS choisir (3) sans avoir relu le chemin d'appel complet."
        )


def test_les_exceptions_declarees_existent_encore():
    """Empeche la liste d'exceptions de pourrir en silence.

    Une justification qui ne correspond plus a aucun appel est un piege :
    elle laisse croire que le cas a ete examine alors que le code a change.
    """
    _, suspects = _collecte_appels()
    cles_reelles = {(s["fonction"], s["table"], s["op"]) for s in suspects}
    obsoletes = set(EXCEPTIONS_VERIFIEES) - cles_reelles
    assert not obsoletes, (
        f"Exceptions devenues obsoletes dans EXCEPTIONS_VERIFIEES : {obsoletes}. "
        "Les retirer : une justification perimee masque un cas non examine."
    )


def test_chaque_exception_est_justifiee():
    """Une exception sans justification serieuse n'est pas une exception."""
    for cle, raison in EXCEPTIONS_VERIFIEES.items():
        assert raison and len(raison) > 40, (
            f"Justification absente ou trop vague pour {cle}. "
            "Expliquer POURQUOI l'appel est sur, pas qu'il l'est."
        )


def test_rapport_lisible(capsys):
    """Emet le decompte, utile en sortie d'integration continue."""
    total, suspects = _collecte_appels()
    avec_garde = sum(1 for s in suspects if s["garde"])
    indirects = sum(1 for s in suspects if s["filtre_indirect"] and not s["garde"])
    exceptes = sum(
        1 for s in suspects
        if not s["garde"] and not s["filtre_indirect"]
        and (s["fonction"], s["table"], s["op"]) in EXCEPTIONS_VERIFIEES
    )
    with capsys.disabled():
        print(
            f"\n[isolation] {total} appels sur tables cloisonnees | "
            f"{total - len(suspects)} filtres directement | "
            f"{avec_garde} proteges par une garde | "
            f"{indirects} filtres via variable | "
            f"{exceptes} exceptions verifiees"
        )
