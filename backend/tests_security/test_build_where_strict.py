"""_build_where doit REFUSER une colonne inconnue, pas l'ignorer.

Contexte (audit du 12/09/2026)
-----------------------------
`pg_adapter._build_where` retirait silencieusement toute condition portant
sur une colonne inconnue (`logger.warning` puis `continue`). Une faute de
frappe sur `tenant_id` suffisait donc a supprimer le cloisonnement : la
requete renvoyait les lignes de TOUS les tenants, avec un HTTP 200 et sans
la moindre trace d'erreur.

Ces tests verrouillent le comportement strict. Ils ne necessitent ni base
de donnees, ni reseau, ni identifiants.
"""
import pytest
from sqlalchemy.sql.elements import True_

import models_sql as M
from pg_adapter import MODELS, _build_where, _cols


# Toutes les tables portant un tenant_id : ce sont celles ou une condition
# perdue en silence provoque une fuite inter-tenants.
TENANT_SCOPED = [
    (name, model) for name, model in MODELS.items()
    if "tenant_id" in _cols(model)
]


def test_toutes_les_tables_metier_sont_cloisonnees():
    """Seules `users` et `tenants` peuvent legitimement ignorer tenant_id.

    `users` est globale (rattachement via tenant_users) et `tenants` EST la
    table des tenants. Toute NOUVELLE table sans tenant_id doit etre un choix
    explicite et documente, pas un oubli : ce test force a venir ici le
    justifier.
    """
    sans_tenant = {n for n, m in MODELS.items() if "tenant_id" not in _cols(m)}
    assert sans_tenant == {"users", "tenants"}, (
        f"Tables sans tenant_id inattendues : {sans_tenant - {'users', 'tenants'}}. "
        "Si c'est voulu, ajouter la justification dans ce test."
    )


@pytest.mark.parametrize("name,model", TENANT_SCOPED, ids=[n for n, _ in TENANT_SCOPED])
def test_colonne_inconnue_leve_une_erreur(name, model):
    with pytest.raises(ValueError) as exc:
        _build_where(model, {"colonne_qui_nexiste_pas": "x"})
    msg = str(exc.value)
    assert "colonne_qui_nexiste_pas" in msg
    assert name in msg, "le message doit nommer la table pour etre diagnosticable"


@pytest.mark.parametrize(
    "faute",
    ["tenantId", "tenant", "tenant_ID", "tenantid", "Tenant_Id", "tenant-id"],
)
def test_fautes_de_frappe_sur_tenant_id_sont_refusees(faute):
    """Le scenario exact qui provoquait la fuite.

    Avant le correctif, chacune de ces fautes produisait un filtre VIDE et
    `_build_where` renvoyait `true()` -- soit la table entiere, tous tenants
    confondus.
    """
    with pytest.raises(ValueError):
        _build_where(M.Quote, {faute: "tenant-a"})


def test_filtre_partiel_refuse_meme_si_une_cle_est_valide():
    """Le danger principal : une cle valide masque la cle perdue.

    `{"id": ..., "tenantId": ...}` produisait avant un filtre sur le seul
    `id` -- donc l'acces au devis d'un AUTRE tenant en connaissant son
    identifiant. C'est le scenario d'IDOR complet.
    """
    with pytest.raises(ValueError):
        _build_where(M.Quote, {"id": "q-1", "tenantId": "tenant-a"})


def test_filtre_valide_fonctionne_toujours():
    """Le durcissement ne doit rien changer pour le code correct."""
    where = _build_where(M.Quote, {"id": "q-1", "tenant_id": "t-1"})
    assert where is not None
    assert not isinstance(where, True_), "un filtre reel ne doit jamais valoir true()"
    compiled = str(where.compile(compile_kwargs={"literal_binds": True}))
    assert "tenant_id" in compiled
    assert "id" in compiled


@pytest.mark.parametrize("op,val", [
    ("$in", {"$in": ["a", "b"]}),
    ("$nin", {"$nin": ["a"]}),
    ("$ne", {"$ne": "a"}),
])
def test_operateurs_supportes_preserves(op, val):
    where = _build_where(M.Quote, {"tenant_id": "t-1", "status": val})
    assert where is not None
    assert not isinstance(where, True_)


def test_operateur_non_supporte_leve_toujours():
    with pytest.raises(ValueError) as exc:
        _build_where(M.Quote, {"tenant_id": "t-1", "total_ht": {"$gt": 100}})
    assert "$gt" in str(exc.value)


def test_filtre_vide_vaut_true_comportement_documente():
    """`{}` renvoie `true()`, c'est-a-dire TOUTES les lignes.

    Comportement volontaire (compatibilite motor : `find({})` liste tout),
    mais c'est une arme chargee. Ce test existe pour le rendre VISIBLE et
    pour qu'une modification future soit un choix conscient.

    La protection contre l'usage accidentel est ailleurs :
    test_tenant_isolation_static.py verifie qu'aucun appel de server.py
    n'interroge une table cloisonnee sans tenant_id ni garde d'appartenance.
    """
    assert isinstance(_build_where(M.Quote, {}), True_)
    assert isinstance(_build_where(M.Quote, None), True_)
