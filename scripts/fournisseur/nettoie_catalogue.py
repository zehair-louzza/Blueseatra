"""Produit un catalogue nettoye : designation canonique en tete, puis
les attributs discriminants en colonnes separees.

Le libelle d'origine est CONSERVE dans une colonne dediee. C'est une
donnee contractuelle : c'est lui qui figurera sur le devis, et lui seul
permet de retrouver l'article chez le fournisseur.
"""
import sys, time
sys.path.insert(0, '/home/user/workspace/saas/backend')
import pandas as pd
from designation_canonique import designation_canonique

SRC = '/tmp/cat.pkl'
OUT = '/home/user/workspace/catalogue_nettoye.csv'

t0 = time.time()
df = pd.read_pickle(SRC)
print(f"lu : {len(df):,} lignes en {time.time()-t0:.0f}s", flush=True)

def col(nom, defaut=''):
    """Colonne du fichier source si elle existe, sinon une colonne vide.

    Le catalogue consolide n'a pas toujours les memes colonnes selon
    l'export : 'Sous-famille' et 'Eco-contribution HT' etaient absentes
    de celui-ci alors qu'elles figurent dans d'autres. Exiger une
    colonne absente faisait echouer tout le nettoyage apres 69 s
    d'analyse.
    """
    if nom in df.columns:
        return df[nom].fillna(defaut).astype(str) if defaut == '' else df[nom]
    return pd.Series([defaut] * len(df), index=df.index)



marques = col('Marque').tolist()
libelles = df['Designation'].fillna('').astype(str).tolist()

cols = {k: [] for k in (
    'designation', 'type_produit', 'calibre', 'courbe', 'poles',
    'pouvoir_coupure', 'sensibilite', 'section', 'puissance',
    'temperature', 'tension', 'conditionnement_lot', 'est_accessoire',
    'courant_continu')}

t0 = time.time()
for i, (lib, mq) in enumerate(zip(libelles, marques)):
    r = designation_canonique(lib, mq or None)
    a, q = r['attributs'], r['qualifiants']
    cols['designation'].append(r['designation_courte'])
    cols['type_produit'].append(r['type_produit'] or '')
    cols['calibre'].append(a.get('calibre', ''))
    cols['courbe'].append(a.get('courbe', ''))
    cols['poles'].append(a.get('poles', ''))
    cols['pouvoir_coupure'].append(a.get('pdc', ''))
    cols['sensibilite'].append(a.get('sensibilite', ''))
    cols['section'].append(a.get('section', ''))
    cols['puissance'].append(a.get('puissance', ''))
    cols['temperature'].append(a.get('temperature', ''))
    cols['tension'].append(a.get('tension', ''))
    cols['conditionnement_lot'].append(q.get('lot', ''))
    cols['est_accessoire'].append('oui' if q.get('accessoire') else '')
    cols['courant_continu'].append('oui' if q.get('courant_continu') else '')
    if i and i % 200000 == 0:
        print(f"  {i:,} traitees ({time.time()-t0:.0f}s)", flush=True)

print(f"analyse terminee en {time.time()-t0:.0f}s", flush=True)

# ORDRE DES COLONNES : la designation d'abord, puis le detail le plus
# discriminant, puis l'identification, puis les prix, et le libelle
# d'origine en dernier -- consultable mais jamais devant.
out = pd.DataFrame({
    'Designation':          cols['designation'],
    'Type':                 cols['type_produit'],
    'Calibre':              cols['calibre'],
    'Courbe':               cols['courbe'],
    'Poles':                cols['poles'],
    'Pouvoir de coupure':   cols['pouvoir_coupure'],
    'Sensibilite':          cols['sensibilite'],
    'Section':              cols['section'],
    'Puissance':            cols['puissance'],
    'Temperature':          cols['temperature'],
    'Tension':              cols['tension'],
    'Lot':                  cols['conditionnement_lot'],
    'Accessoire':           cols['est_accessoire'],
    'Courant continu':      cols['courant_continu'],
    'Fournisseur':          col('Fournisseur'),
    'Marque':               col('Marque'),
    'Famille':              col('Famille'),
    'Reference fournisseur': col('Reference fournisseur'),
    'Reference fabricant':  col('Reference fabricant'),
    'Code EAN':             col('Code EAN'),
    'Prix net HT':          col('Prix net HT', None),
    'Prix public HT':       col('Prix public HT', None),
    'Unite de vente':       col('Unite de vente'),
    'Designation origine':  libelles,
})

# Tri : type, puis calibre numerique, puis designation. Un tri
# alphabetique sur "16A" placerait 16A apres 100A.
ordre_cal = out['Calibre'].str.extract(r'(\d+)')[0].astype(float)
out = out.assign(_c=ordre_cal).sort_values(
    ['Type', '_c', 'Designation'], na_position='last').drop(columns='_c')

t0 = time.time()
out.to_csv(OUT, index=False, encoding='utf-8-sig')
print(f"ecrit : {OUT} en {time.time()-t0:.0f}s", flush=True)
import os
print(f"taille : {os.path.getsize(OUT)/1024/1024:.0f} Mo")
