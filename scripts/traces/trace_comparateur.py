# -*- coding: utf-8 -*-
"""Comparateur : vraies offres du catalogue commun (Rexel, YESSS) scorées par
le VRAI moteur de pertinence pour la requête « chauffe eau electrique 100 l »."""
import sys
sys.path.insert(0, str(__import__('pathlib').Path(__file__).resolve().parents[2] / 'backend'))
import pertinence, comparateur_produits as cp

REQUETE = "chauffe eau electrique 100 l"

offres = [
    # (fournisseur, designation réelle, prix net HT) — lignes réelles de
    # supplier_offeres le 04/10/2026 (catalogue commun)
    ("Rexel", "Chauffe-eau électrique vertical mural INITIO XPERT 100l - D=513 mm", 162.8188),
    ("La Plateforme du Bâtiment", "Chauffe-eau vertical blindé 100 L diamètre 56 cm", 171.7),
    ("Rexel", "Accessoire Chauffe-eau électrique et PECS Plaque de fixation Rapide", 6.271),
    ("YESSS", "Accessoire Chauffe-eau électrique et PECS Plaque de fixation Rapide", 9.28),
    ("Rexel", "Accessoire Chauffe-eau électrique et PECS - raccord Dielectrique tournant 3/4'", 10.4539),
    ("Rexel", "Console d'Accrochage Plafond Chauffe-eau et PECS vertical mural de 50 à 100L", 56.5014),
]
lignes = []
for f, d, p in offres:
    norm = pertinence.normalise(d)
    lignes.append({
        "fournisseur": f, "designation": d, "prix_net_ht": p,
        "unite_base": "u", "qte_par_conditionnement": 1,
        "id": f"{f}-{p}", "_pertinence": pertinence.score(norm, REQUETE),
    })

print("Requête du comparateur :", REQUETE)
print("=" * 88)
print(f"{'Offre':<58}{'Fourn.':<8}{'Prix':<10}{'Pertin.'}")
print("-" * 88)
for l in sorted(lignes, key=cp.cle_recherche):
    print(f"{l['designation'][:56]:<58}{l['fournisseur']:<8}{l['prix_net_ht']:<10.2f}{l['_pertinence']:.3f}")
print()
print("→ meilleurs_par_fournisseur() : LA ligne retenue par fournisseur")
print("-" * 88)
for m in cp.meilleurs_par_fournisseur(lignes):
    print(f"  {m['fournisseur']:<8} retient « {m['designation'][:52]} » "
          f"{m['prix_net_ht']} € (pertinence {m['pertinence']})")
print()
print("→ CE QUE VOIT L'UTILISATEUR : le classement cle_recherche (pertinence ↓, prix ↑)")
print("   Le ballon 100 L est en TÊTE, devant les accessoires 15x moins chers :")
for i, l in enumerate(sorted(lignes, key=cp.cle_recherche)[:3], 1):
    print(f"   {i}. {l['designation'][:60]} — {l['fournisseur']} — {l['prix_net_ht']} €")
print()
print("→ Un fournisseur qui ne vend QUE l'accessoire (YESSS ici) garde sa meilleure")
print("   offre pertinente — jamais présenté comme LE produit à acheter.")
