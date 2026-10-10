# Contact Blueseatra et messagerie du domaine

Dernière mise à jour : 10 octobre 2026.

Ce document recense les adresses e-mail de Blueseatra, les endroits où elles sont affichées, la configuration DNS du domaine et les points restant à traiter.

## Adresses

| Adresse | Rôle | Hébergement |
|---|---|---|
| `contact@blueseatra.com` | **Adresse publique unique** : prestations, offres et abonnements, contact entreprise, aide | Hostinger Mail |
| `relances@blueseatra.com` | Expéditeur des relances de devis de l'entreprise « ANELEC Test » (messagerie d'envoi, [spécification 4.7](./specs/module-clients.md)) | Hostinger Mail |
| `demandes@blueseatra.com` | Boîte existante, réservée à la réception de demandes (n8n) | Hostinger Mail |

Les trois boîtes existent dans hPanel (Emails → Comptes de messagerie, vérifié le 10/10/2026). Le domaine `blouseatra.com` n'existe pas (aucun enregistrement A ni MX) : toute adresse en `@blouseatra.com` est une faute de frappe.

## Une adresse, trois motifs

Les visiteurs et les clients écrivent tous à `contact@blueseatra.com`. Le motif est porté par l'objet prérempli, ce qui permet de trier la boîte (filtres Hostinger) sans multiplier les adresses :

| Motif | Objet prérempli | Exemples |
|---|---|---|
| Prestations | `[Blueseatra] Prestations` | Démonstration, import de catalogue, paramétrage, accompagnement |
| Offres et abonnement | `[Blueseatra] Offres et abonnement` (`: Signature` pour l'offre sur devis) | Choix ou changement d'offre, facturation |
| Entreprise | `[Blueseatra] Contact entreprise` | Partenariat, presse, questions administratives ou juridiques |
| Aide (depuis l'application) | `[Blueseatra] Aide` | Question d'un utilisateur connecté |

En anglais, les objets sont `Services`, `Plans and subscription`, `Company enquiry` et `Help`, selon la langue de l'interface au moment du clic.

## Où l'adresse est affichée

| Endroit | Fichier | Lien |
|---|---|---|
| Pied de page de l'accueil | `frontend/src/pages/Landing.js` | Motif « Entreprise » |
| Bouton « Nous contacter » de l'offre Signature | `frontend/src/pages/Landing.js` | Motif « Offres », précision « Signature ». Avant le 10/10/2026, ce bouton menait par erreur à la création d'un espace d'essai |
| Choix de l'offre (Facturation), tant que le paiement en ligne est fermé | `frontend/src/components/ChoixOffre.js` | Motif « Offres » |
| Barre latérale de l'application : « Contacter Blueseatra » | `frontend/src/components/AppShell.js` | Motif « Aide » |
| Page `/contact` : trois liens par motif et bouton « Demander une démo » | `frontend/public/contact.html` | Objets préremplis |
| Pages publiques (accueil, à propos, solutions, mentions légales), `llms.txt`, données structurées JSON-LD (`ContactPoint`) | `frontend/public/` | Adresse seule |
| Messages de l'API : espace suspendu (`quotas.py`), paiement en ligne non activé (`facturation_stripe.py`) | `backend/` | Adresse citée dans le texte |

**Source unique dans le code :**
- **Site :** `frontend/src/lib/contact.js`, qui fournit `CONTACT_EMAIL` et `mailtoContact(motif)`.
- **API :** `backend/contact_blueseatra.py`. La variable `BLUESEATRA_CONTACT_EMAIL` permet de changer l'adresse sans modifier le code.

Les pages statiques de `frontend/public/` reprennent l'adresse en dur (HTML sans JavaScript, lu par les robots). Il faut les modifier à la main si l'adresse change un jour.

## DNS du domaine (vérifié le 10/10/2026)

| Enregistrement | Valeur | État |
|---|---|---|
| MX | `mx1.hostinger.com` (5), `mx2.hostinger.com` (10) | Correct |
| SPF | `v=spf1 include:_spf.mail.hostinger.com ~all` | Correct |
| DKIM | `hostingermail-a/b/c._domainkey` → `hostingermail-*.dkim.mail.hostinger.com` (CNAME) | Correct |
| DMARC | `v=DMARC1; p=none` | À renforcer (ci-dessous) |

## Points restant à traiter

1. **DMARC en observation seulement.** Avec `p=none`, un e-mail usurpant `@blueseatra.com` n'est ni rejeté ni mis en spam, et aucun rapport n'est reçu.
   - **Étape 1 :** ajouter un rapport, par exemple `v=DMARC1; p=none; rua=mailto:contact@blueseatra.com`, et lire les rapports pendant deux à quatre semaines.
   - **Étape 2 :** passer à `p=quarantine` quand les rapports ne montrent que des envois légitimes (Hostinger, relances).
   - **Où :** hPanel → Domaines → DNS.
2. **Tri de la boîte `contact@`.** Créer dans Hostinger Mail un filtre par objet (`[Blueseatra] Prestations`, `Offres`, `Contact entreprise`, `Aide`) vers des dossiers dédiés.
3. **Réponse automatique facultative** sur `contact@`, avec un délai de réponse annoncé, par exemple « sous un jour ouvré ».
4. **Mentions légales.** Compléter la forme juridique, le SIREN ou SIRET et l'adresse du siège dès que la structure est fixée (voir [SEO.md](./SEO.md)).
5. **Nom affiché des relances.** L'expéditeur `relances@blueseatra.com` s'affiche « No_Replay Relance Blueseatra ». Les réponses des clients arrivent pourtant bien dans cette boîte : la consulter, ou choisir un nom qui n'annonce pas l'absence de réponse.
