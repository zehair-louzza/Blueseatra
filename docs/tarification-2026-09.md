# Blueseatra : nouvelle tarification et règles multi-entreprises

Brainstorming du 24/09/2026. Il s'appuie sur nos échanges et documents précédents, sur l'état réel du code et de la base de production, et sur une comparaison des prix du marché.

## 1. Ce que nous avions déjà décidé

| Sujet | Décision déjà prise | Où |
|---|---|---|
| Noms des offres | Découverte, Initial, Pilotage, Performance, Signature (positionnement premium) | Dossier maître de déploiement, tickets #89 et #90 |
| Unités facturées | Jamais de tokens. Des unités métier : **devis assistés**, **pages lues (OCR)** et **crédits** | Échange « coût IA par devis » |
| Coût IA réel | Environ **0,05 € par devis** (hypothèse réaliste, à mesurer en pilote) | Même échange |
| IA non illimitée | Quotas par offre, packs prépayés, dépassement seulement avec accord et plafond | Dossier maître, §11 |
| Stockage et import | Quotas séparés des crédits IA (Découverte 25 Mo par import, jusqu'à 1 Go pour Performance) | Dossier maître, §10.2, et ticket #87 |
| Registre des consommations | Écritures ajoutées uniquement, jamais modifiées, corrections par écriture inverse | Ticket #89 |
| Impayé | Suspension, **jamais de suppression** de données | Ticket #90 |
| Partenaires | Modèle B : Blueseatra facture chaque entreprise, le partenaire touche environ 15 % de commission | Échange « partenaires » |

## 2. Ce que fait le marché

| Logiciel | Prix mensuel HT | Ce qui est inclus |
|---|---|---|
| Tolteck | 19 € (annuel) à 25 € | Devis et factures |
| Obat | 25 € à 95 € selon le profil et l'offre | Devis et factures **illimités**, assistant vocal limité à 2 devis |
| Batappli | 39 € à 79 € | Devis et factures illimités, 1 utilisateur |

Sources : [Obat, tarifs](https://www.obat.fr/tarifs/), [Tolteck, tarifs](https://www.tolteck.com/tarifs), [Batappli, tarifs](https://www.batappli.fr/tarifs).

**Leçon principale :** les concurrents vendent tous des devis et factures illimités. Si Blueseatra limite le nombre de devis, il paraîtra plus cher et plus restrictif, alors que son coût réel ne vient que de l'IA et de la lecture des documents.

## 3. Proposition : ce qui change

1. **Tout ce qui est manuel devient illimité dans toutes les offres** : devis, PDF, catalogues, catalogue commun, comparateur de prix. C'est aligné sur le marché et ne coûte presque rien.
2. **Seul l'automatique est compté**, avec deux compteurs lisibles :
   - **Devis assistés par l'IA** : une demande lue et transformée en devis structuré.
   - **Pages lues** : uniquement pour les photos et les PDF scannés. Un PDF qui contient déjà du texte ne consomme aucune page.
3. **Les crédits restent en coulisse**, dans le registre, pour les actions plus lourdes (analyse approfondie, régénération). L'écran montre les deux compteurs, pas une monnaie abstraite.
4. **Le prix est par entreprise**, avec des sièges inclus. On paie un siège supplémentaire, jamais un utilisateur qui passe d'une entreprise à l'autre.

## 4. Grille validée le 24/09/2026

| Offre | Prix HT / mois | Sièges | Devis assistés IA / mois | Pages lues / mois | Import catalogue | Pour qui |
|---|---:|---:|---:|---:|---|---|
| **Découverte** | Essai gratuit de 14 jours | 1 | 10 (sur l'essai) | 30 (sur l'essai) | 25 Mo | Tester sans carte, puis choisir une offre |
| **Initial** | 59 € | 1 | 60 | 150 | 100 Mo, 5 par mois | Artisan ou indépendant |
| **Pilotage** | 149 € | 3 | 250 | 750 | 300 Mo, 15 par mois | PME TCE ou maintenance |
| **Performance** | 399 € | 10 | 1 000 | 3 000 | 1 Go, 100 par mois | Plusieurs chiffreurs |
| **Signature** | Sur devis | Contrat | Contrat | Contrat | Contrat | Groupe, réseau, franchise |

- **Siège supplémentaire :** 15 € HT par mois.
- **Recharges :** 25 devis assistés pour 19 € HT, 100 pour 59 € HT ; 500 pages lues pour 39 € HT.
- **Annuel :** 2 mois offerts.

Contrôle de marge : avec environ 0,05 € de coût IA par devis, Initial représente environ 3 € d'IA pour 59 € encaissés, et Performance environ 50 € pour 399 €. Les chiffres sont à recalibrer après un mois de pilote réel.

## 5. Règles multi-entreprises à appliquer

Ces règles viennent de ce qui est déjà construit et vérifié (catalogue commun, isolation RLS, rôle `blueseatra_app`, sélecteur d'entreprise).

| # | Règle | Conséquence pour la facturation |
|---|---|---|
| R1 | **Une entreprise = un abonnement.** Un utilisateur peut appartenir à plusieurs entreprises (sélecteur d'espace) ; chacune a son offre, ses compteurs et sa facture | Jamais de compteur partagé entre deux entreprises |
| R2 | **Le catalogue commun est inclus pour tous**, visible par toutes les entreprises, masquable, **jamais supprimé** | Il ne compte **jamais** dans le stockage d'une entreprise ; le tenant système n'est pas facturé |
| R3 | **Les catalogues importés appartiennent à l'entreprise qui les importe** et ne sont visibles que par elle | Ils comptent dans le quota de stockage et d'import de cette entreprise uniquement |
| R4 | **Portefeuille de consommation par entreprise**, avec réservation avant chaque appel IA et plafond dur | Une boucle, un import raté ou une attaque ne peut pas vider le budget d'un autre |
| R5 | **Registre en ajout seul**, lisible seulement par l'entreprise concernée (RLS) | Le solde affiché est toujours reproductible |
| R6 | **Quotas vérifiés par le serveur**, jamais par le navigateur | L'interface affiche les jauges, sans jamais décider |
| R7 | **Impayé = lecture seule**, puis suspension, sans purge | Les devis restent consultables et exportables |
| R8 | **Espaces de test** (ex. « ANELEC Test ») : marqués « test », non facturés, plafonds IA bas, non visibles des clients | Pas de fausse facture interne |
| R9 | **Même propriétaire, plusieurs entreprises** : −20 % à partir de la deuxième entreprise payante | Encourage les groupes sans mélanger les données |
| R10 | **Partenaire** : il voit le nombre d'entreprises, leurs offres, le statut de paiement et sa commission, **jamais leurs devis ni leurs prix** | Les données restent isolées par entreprise |

## 6. Ordre de mise en œuvre

1. **Site :** mettre à jour la section Tarifs de la page d'accueil avec la grille validée. C'est faisable immédiatement, sans paiement.
2. **Base :** tables `plans`, `tenant_entitlements`, `usage_ledger` et `usage_reservations` avec RLS (ticket #89). La colonne `tenants.plan` existe déjà, avec `starter` par défaut, et sera reliée aux nouvelles offres.
3. **Serveur :** vérification du quota avant chaque extraction et OCR, et une page Facturation avec les deux jauges.
4. **Stripe en mode test** (ticket #90), puis passage en réel après la facturation électronique (ticket #91).

## 7. Décisions prises

- **Entrée de gamme :** essai gratuit de 14 jours (1 siège, 10 devis assistés, 30 pages lues), puis choix d'une offre payante.
- **Prix :** grille haute, soit Initial 59 €, Pilotage 149 €, Performance 399 € et Signature sur devis.
- **Affichage :** la grille est visible sur la page d'accueil, avec la mention « Paiement en ligne bientôt disponible ».

## 8. Politique de dépassement (ticket #89)

Décision : **refus explicite, jamais de surfacturation silencieuse ni de mode dégradé caché.**

| Situation | Comportement |
|---|---|
| Forfait du mois épuisé, recharge disponible | La recharge est consommée ; le forfait l'est toujours en premier |
| Forfait et recharges épuisés | Nouvelle lecture IA refusée : erreur **402** avec un message clair et un lien vers l'offre, jamais une 500 |
| Travail manuel (devis, PDF, catalogues, comparateur) | Toujours possible, jamais compté |
| Essai terminé ou impayé | Lecture seule : les données restent consultables et exportables |
| Offre `interne` ou Signature | Illimité, mais tout reste compté dans le registre |
| Extraction en échec | Remboursée par une écriture d'annulation |

**Garde-fous**
- **Projection :** la page Offre et consommation affiche le rythme actuel et, s'il y a lieu, la date d'épuisement prévue avant la fin de la période.
- **Rapprochement :** `GET /api/abonnement/rapprochement` (owner, admin, billing_admin) vérifie que chaque demande lue a consommé exactement un devis assisté et que chaque demande en échec a été remboursée. Il sert de contrôle avant l'activation du blocage (`BLUESEATRA_QUOTAS_APPLIQUES=1`).
- **Registre :** les soldes affichés sont toujours la somme du registre, en ajout seul, et restent donc reproductibles.

## 9. Mise en service du paiement Stripe (ticket #90)

1. **Mode test :**
   - lancer `STRIPE_SECRET_KEY=sk_test_… python scripts/stripe/creer_catalogue.py` ;
   - dans Stripe, **Développeurs → Webhooks**, ajouter `https://blueseatra-api.onrender.com/api/stripe/webhook` avec les événements `checkout.session.completed`, `customer.subscription.created`, `customer.subscription.updated`, `customer.subscription.deleted`, `invoice.paid` et `invoice.payment_failed` ;
   - activer le portail client (**Paramètres → Portail client**).
2. **Render :** définir `STRIPE_SECRET_KEY` (clé test) et `STRIPE_WEBHOOK_SECRET`, puis appliquer la migration `20260927090000_facturation_stripe.sql` sur Supabase.
3. **Recette en mode test :**
   - paiement réussi avec la carte `4242 4242 4242 4242` ;
   - paiement refusé avec `4000 0000 0000 0341` ;
   - webhook rejoué depuis le tableau de bord Stripe : un seul effet ;
   - changement d'offre en cours de mois, avec prorata calculé par Stripe ;
   - recharge ;
   - annulation.
4. **Bascule live :** seulement après la validation de la facturation électronique (#91). Clé live et `BLUESEATRA_STRIPE_LIVE=1` sur Render, nouveau secret webhook live.
