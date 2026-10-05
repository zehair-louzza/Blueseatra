# Déploiement TCE v4 : intégration au SaaS

## Périmètre

Le pack de 25 skills est présent dans `backend/skills_tce` et installé côté Hermes
par le dépôt `ovh-ai-stack`. Les fichiers identiques sont contrôlés par le même
SHA-256 de contenu, exposé dans `/api/health` et dans la vérification du VPS.
Le code s'intègre aux versions existantes de FastAPI, Pydantic et React, sans
modifier les dépendances, secrets, catalogues, marges ou tables de production.

## Adaptation au SaaS existant

- L'extraction garde son schéma historique compatible avec les écrans, enrichi
  d'action, lot, preuve et preuve de quantité. Le contrat vient du noyau TCE.
- Le modèle ne propose plus un minimum arbitraire ni des durées/effectifs.
- L'enrichissement de nomenclature est déterministe : fiches des seuls lots
  concernés, conservées en interne, sans transformer leurs contrôles en achats.
- Une quantité non établie reste null jusque dans le matching et les offres.
- Pose/raccordement/étude et fournitures client ne déclenchent pas un achat
  automatique. Une citation ambiguë exige une décision du chiffreur.
- Les variantes gardent leurs propres prestations lors de la création et du rematching.
- Pour v4, le descriptif pré-revue est déterministe et conserve les actions.
  La prose IA n'est pas injectée automatiquement comme engagement commercial.

## Validation, envoi et PDF

Le chiffreur doit confirmer la revue TCE dans l'éditeur, après vérification des
quantités, kits, accessoires et réserves. Une checklist est une aide de contrôle,
pas une liste de fournitures déjà approuvées.

L'API de validation reçoit désormais `review_tce` et `expected_digest` renvoyé par
GET/PATCH du devis. Une requête périmée est refusée. Lecture verrouillée PostgreSQL,
snapshot et statut sont atomiques ; les écritures tardives refusent un devis
qui n'est plus un brouillon de la version attendue.

Un devis incomplet ne peut être validé ou envoyé. Les anciens devis validés
sans empreinte de revue doivent être rouverts puis revalidés avant nouvel export
client ; leurs données et anciennes versions ne sont pas supprimées.

Le PDF brouillon est non contractuel, sans bon pour accord ni net à payer.
Les fournisseurs, codes catalogue et sources tarifaires internes ne sont plus
exposés ; le prix unitaire visible est le prix de vente, pas l'achat avant marge.
Les réserves et exclusions sont conservées. Le template ne déduit plus un régime
fiscal de la présence ou absence d'un numéro de TVA.

## Vérifications et limites

Exécuter la suite `Tests métier`, incluant `backend/tests/test_tce_v4.py`, le lint
frontend et son build. La préproduction GitHub utilise une base jetable ; aucun
test ne doit écrire un devis dans un tenant réel sans périmètre de test convenu.

Le modèle peut encore mal interpréter un texte tout en produisant un JSON valide.
Les heuristiques de preuve sont volontairement conservatrices ; elles ne remplacent
pas la revue professionnelle. La cascade historique de lecture des longs documents
reste bornée ; un avertissement TCE exige alors comparaison avec l'original.
Ce déploiement n'est pas une certification réglementaire, électrique ou fiscale.

## Retour arrière et exploitation

- Point de départ SaaS : `f60b48e0683501df513f70cbe0e4dc0168009299`.
- Point de départ infrastructure : `ee4a32c80c955ed64ba6e283445e3d79f0010281`.
- Retour SaaS : revert de la PR et redéploiement via le mécanisme existant ;
  aucune migration SQL à annuler, aucune donnée à restaurer/supprimer.
- Retour VPS : script de déploiement avec rollback du commit et des conteneurs
  concernés si les contrôles échouent. Les volumes et modèles restent conservés.
- Vérifier le SHA de `/api/health`, les checks GitHub, le déploiement Render et
  le déploiement frontend Vercel. Ne pas déduire le succès du seul push Git.
