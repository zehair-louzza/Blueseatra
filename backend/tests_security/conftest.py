"""Conftest minimal pour la suite de securite.

VOLONTAIREMENT SEPARE de backend/tests/conftest.py.

Ce dernier fait, AU MOMENT DE L'IMPORT :

    frontend_env = dotenv_values("/app/frontend/.env")
    base_url = os.environ.get("REACT_APP_BACKEND_URL") or frontend_env.get(...)
    if not base_url:
        raise RuntimeError("REACT_APP_BACKEND_URL missing ...")

Un `raise` au niveau module empeche pytest de COLLECTER le repertoire des
qu'il n'y a pas de backend vivant ni de fichier /app/frontend/.env. Aucun
test purement unitaire ou statique ne peut donc y vivre, et rien de tout
cela ne peut tourner en integration continue.

Les tests de cette suite doivent tourner PARTOUT, sans base de donnees,
sans reseau, sans identifiants -- c'est la condition pour qu'ils bloquent
reellement une fusion. D'ou ce repertoire distinct.

(Rendre backend/tests/conftest.py paresseux serait la vraie correction,
mais elle touche les 10 tests d'integration existants : a traiter dans une
PR dediee.)
"""
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))
