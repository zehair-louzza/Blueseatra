# Skill — Profil Organisation wWthone (complément)

> Ce fichier est un **complément** au skill principal `docs/Skill_MASTER_agent_wWthone.md`.
> Il doit être **injecté en plus** du skill principal uniquement pour les devis liés à l'organisation de l'utilisateur.
> Il **ne remplace pas** le skill principal et ne peut pas être utilisé seul.

---

## CONTEXTE D'ACTIVATION

Ce profil s'active pour tout devis impliquant :
- Des **chantiers boutiques** (enseignes, magasins, locaux commerciaux du réseau).
- Des données **OneNote** du chantier.
- Une mise en page **PDF 5 colonnes** avec bandeaux LOT.
- Une structure **en-tête 3 colonnes** Prestataire / Donneur d'ordre / Site.

---

## A. RÈGLES ONENOTE RENFORCÉES

- **Toujours** relire le OneNote du chantier avant chaque version de devis.
- Intégrer systématiquement :
  - Dimensions des locaux (hauteur, surface, linéaires).
  - Photos et croquis joints.
  - Remarques de la direction de boutique.
  - Contraintes d'accès, horaires d'intervention, réserves.
- Si **OneNote contredit une version précédente du devis**, le contenu OneNote est **prioritaire**.
- Si le OneNote est absent ou incomplet, indiquer le statut `À confirmer` dans la feuille `Hypothèses & exclusions`.

---

## B. STRUCTURE DU DEVIS ORGANISATION

### En-tête
L'en-tête du devis (XLSX et PDF) doit comporter **3 blocs distincts** :

| Prestataire | Donneur d'ordre | Site d'intervention |
|-------------|-----------------|---------------------|
| Nom, adresse, SIRET, contact | Raison sociale, adresse, contact | Enseigne, adresse exacte, code site |

### Titre
```
DEVIS N° XXXXXXXX — [ENSEIGNE] / [VILLE / SITE]
```

### Section « Objet »
Rédigée à partir des informations OneNote + demande utilisateur. Décrire :
- Nature des travaux.
- Localisation précise dans le magasin (rayon, allée, réserve, vitrine…).
- Contraintes spécifiques (horaires, accès, matières sensibles).

### Lots numérotés
Structurer le devis en lots numérotés selon la nature des travaux :

| Numéro | Intitulé typique |
|--------|------------------|
| 1.1 | Préparation des supports |
| 1.2 | Revêtements / peinture |
| 1.3 | Finitions |
| 2 | Électricité (si applicable) |
| 3 | Plomberie (si applicable) |
| 4 | Menuiseries / agencement |
| 5 | Nettoyage / évacuation |
| 6 | Main-d'œuvre et déplacement |

> Adapter les lots à la réalité du chantier. Ne pas créer de lot vide.

### Récapitulatif par lot
Avant les totaux généraux, insérer un tableau récapitulatif :

| Lot | Désignation | Total HT |
|-----|-------------|----------|
| 1.1 | Préparation | X € |
| 1.2 | Peinture | X € |
| … | … | … |
| **Total** | | **X €** |

---

## C. MISE EN PAGE PDF 5 COLONNES

### Structure des colonnes

| Colonne | Largeur |
|---------|---------|
| Désignation / Matériaux | 10,8 cm |
| Qté | 1,2 cm |
| Unité | 1,8 cm |
| PV HT unit. | 2,5 cm |
| Total HT | 3,2 cm |
| **Total** | **19,5 cm** |

### Marges de page
```
L_MARGIN = R_MARGIN = (210 mm − 195 mm) / 2 = 7,5 mm
```

### Bandeaux LOT
- Largeur = `TABLE_W` (19,5 cm), `leftPadding = rightPadding = 0`.
- Texte centré, blanc, **9 pt**, fond bleu `#2E75B6`.
- Parfaitement alignés avec les colonnes du tableau (même indentation que la première colonne).
- Format : `LOT 1 — PEINTURE INTÉRIEURE`.

### En-têtes colonnes
- Fond bleu nuit `#1A3E5C`, texte blanc, **8 pt gras**.

### Lignes
- Alternées blanc / gris clair (`#F2F2F2`).
- Police corps : 8 pt.
- Hauteur de ligne : automatique (contenu).

### Groupement
- Chaque bloc lot (bandeau + tableau + sous-total) est regroupé dans un `KeepTogether` pour éviter les coupures de page au milieu d'un lot.

### Sous-total par lot
- Ligne de sous-total après chaque lot : fond `#D9E1F2`, texte aligné à droite, libellé `Sous-total LOT X`.

### Page de signature
- Après les totaux : zone de signature client (date, nom, mention « Bon pour accord »).
- Zone de cachet prestataire.

---

## D. RÈGLES DE MISE EN PRODUCTION PDF

- Ne jamais générer le PDF organisation sans avoir vérifié que le **profil prestataire** (nom, adresse, SIRET, logo si fourni) est renseigné.
- Si le logo prestataire est fourni (fichier image) : l'insérer en haut à gauche de la première page, largeur max 4 cm.
- Numérotation des pages : `Page X / Y` en pied de page, centré.
- Référence du devis en pied de page sur chaque page.

---

*Dernière mise à jour : 20 juillet 2026 — v1.0 (extraction depuis Skill_MASTER v2.0)*
