---
name: devis-options-master
description: "Skill maître Blueseatra: une demande peut contenir une ou plusieurs options exclusives à chiffrer en devis distincts (soit A soit B, ou les pièces suivantes). Rédige un descriptif de travaux compréhensible et justifie déplacement et main-d'oeuvre. Utiliser à chaque création de devis, extraction, génération, ou quand le client demande plusieurs scénarios dans un seul PDF."
license: MIT
metadata:
  author: louzza-zehair
  version: "1.0"
  perplexity:
    connectors:
      - id: blueseatra_67549df0c3854ee8a376a1e0ef06f21d
        reason: Lit les demandes et devis du tenant pour appliquer le découpage d'options.
---

# Devis options maître

## Quand utiliser ce skill

Toujours, dès qu'une demande de devis est extraite ou qu'un brouillon est créé dans Blueseatra (SaaS, Hermes, agent devis).

## Règle d'or

Une **demande** (un PDF, un e-mail) n'est pas forcément un **devis**.

- **ET / puis / ainsi que / y compris** : une seule option, plusieurs lignes.
- **OU / soit… soit / ou bien / option 1 / option 2 / à défaut** : autant de devis distincts que d'alternatives exclusives.
- Ne jamais fusionner deux alternatives exclusives dans le même total.
- Ne jamais inventer de prix. FastAPI + catalogue seuls chiffrent.

Les noms (donneur, client, site) changent à chaque document. Ne jamais figer une société.

## 1. Découper les options

1. Lire tout le texte (et les pièces listées après « les pièces suivantes »).
2. Détecter les marqueurs exclusifs : `soit`, `ou soit`, `ou bien`, `ou les pièces suivantes`, `option N`, `à défaut`, `variante`.
3. Pour chaque option, produire un scénario :

| Champ | Contenu |
|---|---|
| `label` | Titre court (ex. Remplacement total pompe) |
| `description` | Périmètre de CETTE option seulement |
| `line_items` | Fournitures / pièces de cette option |
| `labor_hours` | Heures-homme estimées (pas un prix) |
| `travel_days` | Jours de présence chantier |
| `crew_size` | 1 si moins de 6 h, sinon 2 |
| `excludes` | Ce que cette option ne couvre pas (l'autre option) |

4. Si aucune alternative : une seule option = la demande entière.
5. En cas de doute réel (OU ambigu), créer quand même les options détectées et les marquer `Estimé` plutôt que de tout fusionner.

Exemple canonique (une demande, deux devis) : voir `references/exemples.md`.

## 2. Descriptif de travaux (obligatoire)

Chaque devis a un bloc client, rédigé en français professionnel, qui explique **la logique du travail**, pas seulement le titre.

Structure fixe :

1. **Intitulé** : `Option i/n — {label}` si plusieurs options, sinon le titre seul.
2. **Périmètre** : ce qui est fourni et posé. Site d'intervention.
3. **Déroulement** : phases numérotées (arrivée, sécurisation, dépose, pose, essais, nettoyage, repli).
4. **Déplacement** : nombre de jours = jours de présence. Expliquer : 1 jour de chantier = 1 forfait déplacement (défaut 40 € HT/j, heures 8h-18h). Pas un forfait magique.
5. **Main-d'œuvre** : heures-homme = personnes × heures/jour × jours, plafond 7 h/personne/jour. Expliquer le total (défaut 42 € HT/h). Marquer Estimé si non mesuré.
6. **Hors périmètre** : l'autre option, et tout ce qui n'est pas demandé.

Interdit : inventer un diagnostic, une cause de panne, ou des travaux non demandés.

## 3. Déplacement et main-d'œuvre

Calcul (FastAPI / matching, jamais l'IA pour le €) :

- `Heures-homme = personnes × heures/j × jours` (max 7 h/j/personne).
- `Jours déplacement = jours réels d'intervention` (sauf consigne contraire).
- Barèmes de vraisemblance (heures seulement) : spot 0,45 h, ballon ECS 4,5 h, pompe / relevage complet ~4,5 h, pièces pompe ~2,5 h + 1,25 h install/repli, minimum visite 2 h.

L'IA propose `labor_hours`, `travel_days`, `crew_size`. Elle n'écrit aucun €.

## 4. Création des devis

Pour N options : créer **N brouillons** distincts, même `request_id`, même donneur / client / site / DI.

- Objet : `Option i/N — {label}` + préfixe DI si présent.
- Chaque brouillon a son descriptif, ses lignes, son MO, son déplacement.
- Numéros `BS-AAAA-xxxx` séquentiels.

## 5. Prix

Catalogue tenant uniquement. Ligne hors catalogue : quantité et libellé, prix vide. Jamais un tarif web ou inventé.
