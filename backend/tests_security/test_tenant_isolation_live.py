"""Sondage croise A/B : deux vrais tenants, deux vrais jetons.

Complement de test_tenant_isolation_static.py, qui couvre tout appel
present dans server.py mais ne prouve rien du comportement a l'execution.
Celui-ci fait l'inverse : il couvre peu d'endpoints, mais il les exerce
reellement contre l'API.

Les deux sont necessaires :
  - le statique empeche une REGRESSION (un endpoint ajoute sans garde) ;
  - le live valide que les gardes existantes REPONDENT correctement
    (404/403 et non 200) et que le middleware d'authentification resout
    bien le tenant depuis le jeton et non depuis un parametre client.

IGNORE AUTOMATIQUEMENT sans identifiants pour deux tenants distincts,
afin de ne jamais bloquer l'integration continue. Renseigner :

    BLUESEATRA_API_URL      (defaut https://blueseatra-api.onrender.com)
    BLUESEATRA_A_EMAIL / BLUESEATRA_A_PASSWORD
    BLUESEATRA_B_EMAIL / BLUESEATRA_B_PASSWORD

Utiliser DEUX TENANTS DE TEST, jamais un tenant de production : le test
cree des objets et un echec pourrait en laisser.
"""
import os

import pytest

requests = pytest.importorskip("requests")

API = os.environ.get("BLUESEATRA_API_URL", "https://blueseatra-api.onrender.com").rstrip("/") + "/api"
TIMEOUT = 90  # le plan Render free dort : le premier appel peut prendre ~32 s

A_EMAIL = os.environ.get("BLUESEATRA_A_EMAIL")
A_PWD = os.environ.get("BLUESEATRA_A_PASSWORD")
B_EMAIL = os.environ.get("BLUESEATRA_B_EMAIL")
B_PWD = os.environ.get("BLUESEATRA_B_PASSWORD")

pytestmark = pytest.mark.skipif(
    not all([A_EMAIL, A_PWD, B_EMAIL, B_PWD]),
    reason="Identifiants de deux tenants de test absents (BLUESEATRA_A_* / BLUESEATRA_B_*)",
)

# Codes acceptables pour un acces refuse. 404 est preferable a 403 : il ne
# revele pas l'existence de l'objet chez l'autre tenant.
REFUS = {401, 403, 404}


def _session(email, pwd):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": pwd}, timeout=TIMEOUT)
    assert r.status_code == 200, f"login {email} a echoue : {r.status_code} {r.text[:300]}"
    token = r.json().get("token")
    assert token, f"pas de jeton dans la reponse de login pour {email}"
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {token}"})
    return s


@pytest.fixture(scope="module")
def tenant_a():
    return _session(A_EMAIL, A_PWD)


@pytest.fixture(scope="module")
def tenant_b():
    return _session(B_EMAIL, B_PWD)


def _ids(session, chemin, cle="id"):
    r = session.get(f"{API}/{chemin}", timeout=TIMEOUT)
    if r.status_code != 200:
        return []
    data = r.json()
    items = data if isinstance(data, list) else (data.get("items") or data.get("results") or [])
    return [i[cle] for i in items if isinstance(i, dict) and cle in i]


@pytest.mark.parametrize("collection", ["quotes", "requests", "catalogs"])
def test_les_listes_ne_melangent_jamais_deux_tenants(tenant_a, tenant_b, collection):
    """Aucun identifiant ne doit apparaitre dans les deux listes."""
    a = set(_ids(tenant_a, collection))
    b = set(_ids(tenant_b, collection))
    commun = a & b
    assert not commun, (
        f"FUITE : {len(commun)} objet(s) de /{collection} visibles par les DEUX "
        f"tenants : {sorted(commun)[:5]}"
    )


@pytest.mark.parametrize("collection", ["quotes", "requests", "catalogs"])
def test_lecture_croisee_refusee(tenant_a, tenant_b, collection):
    """A ne doit pas pouvoir LIRE un objet de B en connaissant son id."""
    cibles = _ids(tenant_b, collection)
    if not cibles:
        pytest.skip(f"Le tenant B n'a aucun objet dans /{collection}")
    for oid in cibles[:3]:
        r = tenant_a.get(f"{API}/{collection}/{oid}", timeout=TIMEOUT)
        assert r.status_code in REFUS, (
            f"FUITE EN LECTURE : GET /{collection}/{oid} avec le jeton de A "
            f"renvoie {r.status_code}. Attendu 404. Corps : {r.text[:200]}"
        )


@pytest.mark.parametrize("action", ["validate", "send", "reopen"])
def test_mutation_croisee_refusee(tenant_a, tenant_b, action):
    """A ne doit pas pouvoir MUTER un devis de B (scenario d'IDOR).

    C'est le test le plus important du fichier : ces endpoints filtrent la
    mutation sur le seul `id` et dependent entierement d'une garde
    d'appartenance prealable. Si la garde disparait, ce test le voit.
    """
    cibles = _ids(tenant_b, "quotes")
    if not cibles:
        pytest.skip("Le tenant B n'a aucun devis")
    oid = cibles[0]
    r = tenant_a.post(f"{API}/quotes/{oid}/{action}", timeout=TIMEOUT)
    assert r.status_code in REFUS, (
        f"FUITE EN ECRITURE : POST /quotes/{oid}/{action} avec le jeton de A "
        f"renvoie {r.status_code}. Le devis d'un AUTRE tenant a peut-etre ete "
        f"modifie. Corps : {r.text[:200]}"
    )


def test_le_tenant_vient_du_jeton_pas_du_client(tenant_a, tenant_b):
    """Un tenant_id fourni par le client doit etre ignore.

    Verifie qu'aucun parametre de requete ni en-tete ne permet de changer de
    tenant : la seule source de verite est le jeton.
    """
    b_ids = set(_ids(tenant_b, "quotes"))
    if not b_ids:
        pytest.skip("Le tenant B n'a aucun devis")

    tentatives = [
        {"params": {"tenant_id": "__B__"}},
        {"headers": {"X-Tenant-Id": "__B__"}},
        {"headers": {"X-Tenant": "__B__"}},
    ]
    for kwargs in tentatives:
        r = tenant_a.get(f"{API}/quotes", timeout=TIMEOUT, **kwargs)
        if r.status_code != 200:
            continue
        data = r.json()
        items = data if isinstance(data, list) else (data.get("items") or [])
        vus = {i["id"] for i in items if isinstance(i, dict) and "id" in i}
        fuite = vus & b_ids
        assert not fuite, (
            f"FUITE PAR PARAMETRE CLIENT : {kwargs} a expose "
            f"{len(fuite)} devis du tenant B."
        )
