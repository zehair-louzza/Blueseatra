"""Mesure le taux de réussite de l'extraction IA sur le corpus BTP (ticket #88).

Usage, depuis la racine du dépôt, avec les variables HERMES_* de l'environnement visé :
    python scripts/ia/evaluer_corpus.py                 # moteur configuré
    python scripts/ia/evaluer_corpus.py --provider openai --model gpt-4o-mini
Sort en code 1 si le taux est sous le seuil de bascule (80 %). Les documents du
corpus sont fictifs : aucun document client n'est envoyé.
"""
import argparse, asyncio, json, os, sys, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "backend"))
os.environ.setdefault("JWT_SECRET", "x" * 48)
from corpus_ia.evaluation import SEUIL_BASCULE, charger, noter  # noqa: E402
import ai_service  # noqa: E402


async def main(a):
    reglages = {k: v for k, v in (("ai_provider", a.provider), ("ai_model", a.model), ("ai_key", os.environ.get("EVAL_AI_KEY", ""))) if v}
    tot_p = tot_t = 0
    for cas in charger():
        t0 = time.perf_counter()
        try:
            sortie = await ai_service.extract_request_data(cas["texte"], reglages, from_file=a.fichier)
        except Exception as e:  # noqa: BLE001
            sortie = {"_error": f"{type(e).__name__}: {e}"}
        p, t, echecs = noter(sortie, cas["attendu"])
        tot_p, tot_t = tot_p + p, tot_t + t
        print(f"{cas['id']:<18} {p}/{t}  {round(time.perf_counter() - t0, 1)} s  {'' if not echecs else 'échecs : ' + ', '.join(echecs)}"
              f"{'  ERREUR ' + sortie['_error'][:80] if sortie.get('_error') else ''}")
    taux = tot_p / max(tot_t, 1)
    print(json.dumps({"taux_reussite": round(taux, 3), "seuil": SEUIL_BASCULE, "points": tot_p, "criteres": tot_t}))
    return 0 if taux >= SEUIL_BASCULE else 1


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--provider"); ap.add_argument("--model")
    ap.add_argument("--fichier", action="store_true", help="simuler un fichier importé (pas de secours heuristique)")
    sys.exit(asyncio.run(main(ap.parse_args())))
