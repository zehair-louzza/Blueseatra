# Import d’un catalogue fournisseurs volumineux

Script : `scripts/fournisseur/import_catalogue_lourd.py`. Il lit sur ton PC un fichier CSV ou XLSX de plusieurs centaines de milliers de lignes et l’écrit dans Supabase par lots. Rien ne passe par Render ni par le site.

## Principe de sécurité

| Garantie | Comment |
|---|---|
| Rien n’est visible avant validation | Chaque import crée une **nouvelle version** par fournisseur. La recherche ne lit que la version active (`catalogs.active_version_id`). |
| Bascule tout ou rien | `activer` bascule tous les fournisseurs du fichier dans **une seule transaction**. |
| Retour arrière | `annuler` repointe chaque catalogue sur sa version précédente, qui est conservée. |
| Reprise après coupure | Identifiants déterministes (empreinte du fichier + numéro de ligne) : relancer `importer` reprend à la dernière ligne enregistrée, sans doublon. |
| Cloisonnement entre entreprises | Les écritures passent sous le rôle `blueseatra_app` (sans contournement RLS) avec `app.tenant_id` : une ligne destinée à une autre entreprise est refusée par la base. |
| Aucun secret dans les commandes | L’URL de connexion est lue dans `BLUESEATRA_IMPORT_DATABASE_URL`. TLS est imposé hors poste local. |
| Fichier piégé | Refus des classeurs avec macros, des faux XLSX, des archives anormalement compressées, et des fichiers de plus de 2 Go ou de plus de 3 millions de lignes. |
| Chute anormale | `activer` refuse si un fournisseur perd plus de 50 % de ses lignes, sauf `--forcer`. |

## Prérequis sur le PC (une seule fois)

```powershell
py -m pip install openpyxl psycopg2-binary
```

## 1. Valider 100 % du fichier (aucune connexion à la base)

```powershell
py scripts\fournisseur\import_catalogue_lourd.py analyser "C:\chemin\Catalogue TCE 2026.xlsx" --date-tarif 2026-09-23
```

Chaque ligne est contrôlée. Deux fichiers sont produits :

- `rapport_analyse.json` : la synthèse. Il contient le verdict (`OK`, `A_VERIFIER` ou `BLOQUANT`), les colonnes reconnues, les chiffres par fournisseur (taux de prix, taux d’EAN valides), le nombre de lignes par type d’anomalie, le bilan des EAN et l’estimation de la place en base. Ce rapport ne contient aucun secret : tu peux le partager.
- `anomalies.csv` : à ouvrir dans Excel. Il liste une ligne par anomalie détectée, avec le numéro de ligne dans le fichier source, et ne contient rien pour les lignes saines.

| Code | Signification |
|---|---|
| `SANS_PRIX` | Prix net absent ou illisible |
| `PRIX_NET_SUP_PUBLIC` | Prix net supérieur au prix public |
| `PRIX_EXTREME` | Prix net inférieur à 0,01 € ou supérieur à 50 000 € |
| `SANS_REFERENCE` / `DOUBLON_REFERENCE` | Référence fournisseur absente ou répétée chez le même fournisseur |
| `EAN_CLE` | 8 à 14 chiffres, mais clé de contrôle GS1 fausse (souvent un code interne) |
| `EAN_LONGUEUR` / `EAN_FORMAT` | Mauvais nombre de chiffres, présence de lettres ou code composé uniquement de zéros |
| `EAN_DOUBLON` | Même EAN sur deux lignes du même fournisseur |
| `DESIGNATION_COURTE` | Désignation de moins de 5 caractères |
| `REJET: …` | Ligne non importable (désignation absente) |

### Les EAN

- Lignes sans EAN : elles sont validées et importées normalement. L’EAN n’est jamais obligatoire.
- Par défaut (mode strict), seul un EAN avec une clé GS1 correcte va dans la colonne `ean`. Les autres codes sont conservés dans `raw_row.ean_invalide`, donc rien n’est perdu.
- Option `--ean-sans-controle` : si tes fournisseurs utilisent des codes internes à 8–14 chiffres, ceux-ci sont aussi placés dans la colonne `ean` et marqués `raw_row.ean_controle = "cle"`. Utilise la même option pour `analyser` et pour `importer`.
- `ean_communs_a_plusieurs_fournisseurs` compte les produits comparables directement entre fournisseurs grâce à un EAN valide.

## 2. Importer (version non visible)

Dans Supabase : Connect → Session pooler → copier l’URI (utilisateur `postgres.xmsxlochasjauhnxarvc`). Puis, dans le même terminal :

```powershell
$env:BLUESEATRA_IMPORT_DATABASE_URL = "postgresql://postgres.xmsxlochasjauhnxarvc:MOT_DE_PASSE@aws-0-eu-west-1.pooler.supabase.com:5432/postgres"
py scripts\fournisseur\import_catalogue_lourd.py importer "C:\chemin\Catalogue TCE 2026.xlsx" --tenant <TENANT_ID> --date-tarif 2026-09-23
```

Le mot de passe ne doit apparaître dans aucun fichier et ne doit être envoyé à personne. Ferme le terminal à la fin, ou lance `Remove-Item Env:BLUESEATRA_IMPORT_DATABASE_URL`.

En cas de coupure, relance exactement la même commande : l’import reprend. Le script affiche un `import_id` à conserver.

## 3. Vérifier, puis activer

```powershell
py scripts\fournisseur\import_catalogue_lourd.py statut  --import-id <ID> --tenant <TENANT_ID>
py scripts\fournisseur\import_catalogue_lourd.py activer --import-id <ID> --tenant <TENANT_ID>
```

## 4. Supprimer l’ancien tarif (ne garder que le nouveau)

Une fois le nouveau catalogue activé et contrôlé sur le site :

```powershell
py scripts\fournisseur\import_catalogue_lourd.py nettoyer --import-id <ID> --tenant <TENANT_ID> --confirmer
```

- **Ce qui est supprimé** : définitivement, uniquement les anciennes versions remplacées par cet import. Les fournisseurs absents du fichier ne sont pas touchés.
- **Condition** : la commande refuse de s’exécuter si l’import n’est pas activé.
- **Conséquence** : après le nettoyage, `annuler` devient impossible. Pour revenir en arrière, il faudrait réimporter l’ancien fichier.

## Import pour les deux entreprises ANELEC

L’analyse est faite une seule fois. Ensuite, on répète pour chaque entreprise les étapes importer → activer → contrôler → nettoyer :

```powershell
$fichier = "C:\chemin\Catalogue TCE 2026.xlsx"
foreach ($t in "f66c1482-0b9b-462a-b3ec-06847f693ec0", "9171d808-f7ee-4d51-92f6-db60d93d8ecc") {
  py scripts\fournisseur\import_catalogue_lourd.py importer $fichier --tenant $t --date-tarif 2026-09-23
}
```

Chaque import affiche son propre `import_id`, à utiliser ensuite pour `activer` puis `nettoyer`. Les anciennes offres de « ANELEC Test » pointaient vers un catalogue manquant : le script le recrée automatiquement, pour que l’ancien tarif soit bien remplacé et non doublé.

## Retour arrière

```powershell
py scripts\fournisseur\import_catalogue_lourd.py annuler --import-id <ID> --tenant <TENANT_ID>
# facultatif, suppression définitive des lignes de l'import annulé :
py scripts\fournisseur\import_catalogue_lourd.py purger  --import-id <ID> --tenant <TENANT_ID> --confirmer
```

## Prérequis côté application

La recherche fournisseurs (`backend/fournisseur_recherche.py`) doit être déployée avec le filtre `FILTRE_VERSION_ACTIVE` **avant** le premier import. Sinon, les lignes d’un import non activé apparaîtraient dans les résultats. Elle lit aussi au plus 5 000 lignes par recherche (champ `tronque`), pour protéger le service Render à 512 Mo.

## Limites connues

- Les colonnes enrichies de production (`designation_courte`, `type_produit`, `calibre`, `courbe`, `poles`, etc.) ne sont pas calculées par ce script, car elles ne sont alimentées par aucun code du dépôt. Elles restent vides pour les nouvelles lignes.
- La vue `v_best_offer_per_product` ne filtre pas encore la version active ; elle ne sert qu’après rapprochement canonique, qui n’est pas encore en place pour ces lignes.
- Les anciennes versions restent en base comme historique de prix. Pour libérer de la place, utilise `purger` sur un import annulé ; aucune purge automatique n’est faite.

## Tests

```bash
TEST_PG_DSN='postgresql://postgres@/bs?host=/tmp&port=55432' pytest scripts/fournisseur/tests -q
```

Base **jetable** initialisée avec `scripts/fournisseur/tests/schema_prod_minimal.sql`. Ne jamais pointer `TEST_PG_DSN` vers Supabase.
