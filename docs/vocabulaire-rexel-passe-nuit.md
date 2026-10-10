# Vocabulaire Rexel — passe de nuit du 04/10/2026 (TERMINÉE)

## Résultat final en production

Source `i8d6b66ed1da1-00000000-v1` (Tarif Rexel, 747 771 offres — de loin la
plus grosse source du catalogue commun, projet Supabase `xmsxlochasjauhnxarvc`,
tenant commun `00000000-0000-4000-8000-000000000c0d`) :

| Mesure | Valeur |
|---|---|
| Mots simples (inchangés) | 99 699 |
| Paires distinctes construites | 470 048 (5 305 851 occurrences) |
| Triples distincts construits | 692 790 (3 960 595 occurrences) |
| Paires retenues (seuil ≥ 5) | 113 997 |
| Triples retenus (seuil ≥ 3) | 192 866 |
| **Total `vocabulaire_recherche` pour cette source** | **406 562 entrées** (306 863 groupes) |

Couverture : 100 % des 747 771 offres, tranches contiguës vérifiées sans trou.
`VACUUM ANALYZE` passé après le remplacement atomique. Suggestions vérifiées :
« porte c » → porte cables (414), porte conducteur (101), porte coupure (35) ;
« coupe feu » → coupe feu (606), clapet coupe feu (279), coupe feu rectangulaire (136).

Les 9 autres versions de sources avaient déjà leur vocabulaire complet (fin
2026-10-02). Le catalogue commun compte donc désormais **10 versions complètes**.

## Procédure exécutée (reproductible)

La fonction `vocabulaire_recalculer_lourd` (PR #169, migrations 20261002070000
et 20261003000000) reste la voie normale pour les sources < ~100 000 offres.
Pour le Rexel, même cette version butait sur l'I/O du petit tier de calcul
(`BuffileRead`, débordement de tri sur fichiers temporaires). La passe a donc
été menée **manuellement par tranches** :

1. Bornes toutes les 10 000 offres via
   `row_number() over (order by id) - 1` sur `supplier_offers`
   (tenant + version filtrés), positions `% 10000 = 9999`.
2. Une tranche = un seul appel SQL
   `WITH arrs AS MATERIALIZED (SELECT string_to_array(recherche_norm,' ') ...)`
   **jamais de LATERAL non matérialisé** (sinon le planificateur aplatit et
   recalcule la découpe par référence), jointure contre les mots simples
   `nb_offres >= 5` de la même source, `ON CONFLICT (mot) DO UPDATE SET nb = nb + excluded.nb`
   dans `vocab_staging_pairs` / `vocab_staging_triples`.
3. Remplacement atomique final : `DELETE ... mot ~ ' '` pour la source, puis
   `INSERT` des paires `nb >= 5` et des triples `nb >= 3`, mots simples intacts.
4. Marquage `vocabulaire_file.fait = true`, `VACUUM ANALYZE`, vérification
   `vocabulaire_suggestions(...)`, puis `DROP` des trois tables de travail.

## Constats d'exploitation nouveaux (mesurés cette nuit)

- **Le connecteur `execute_sql` explose en ~60 s côté client, mais la requête
  CONTINUE de s'exécuter côté serveur.** Un appel « timed out » n'est ni un
  échec ni un succès : avant toute relance, vérifier `pg_stat_activity` —
  relancer sans vérifier crée des backends en double qui accumulent les mêmes
  upserts (une double exécution a été observée et tuée avant commit).
- **Deux requêtes zombies de tentatives précédentes (23 h et 15 h d'exécution)
  saturaient l'I/O** et expliquaient l'échec de toutes les approches du jour.
  `pg_terminate_backend()` sur les deux → les tranches sont passées de
  « impossible » à 10-30 s chacune. Lesson : avant tout diagnostic de lenteur
  sur Supabase, regarder `pg_stat_activity` et les durées de requête.
- Tailles de tranches mesurées : 20 000 à 40 000 offres par appel passent
  dans la fenêtre de 60 s quand l'instance est saine ; les zones d'identifiants
  mélangés à d'autres tenants (fin de table) exigent 5 000-10 000.
- Un segment peut échouer deux fois sans raison visible puis passer en
  moitiés : toujours découper plus fin plutôt que ré-exécuter tel quel.

## Traces d'exécution jointes

`scripts/traces/trace_hermes_selection.py` — le vrai moteur `matching.py`
(`match_line`, `build_quote_lines`, `wrap_in_lots`, `estimate_chantier`) sur le
vrai catalogue `pricing_items` de l'entreprise : montre les scores, raisons,
décision matched/to_confirm, prix du catalogue uniquement, main-d'œuvre au
barème (42 €/h, 11 h) — Hermes ne fixe jamais un prix.

`scripts/traces/trace_comparateur.py` — le vrai `pertinence.py` +
`meilleurs_par_fournisseur` sur des offres réelles de `supplier_offers`
(Rexel, La Plateforme du Bâtiment, YESSS) : le ballon 100 L (pertinence 1,958)
passe devant les accessoires 15 fois moins chers (1,083).
