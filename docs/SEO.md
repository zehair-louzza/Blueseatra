# Stratégie SEO et GEO de Blueseatra

Dernière mise à jour : octobre 2026. Contact public affiché : **contact@blueseatra.com** (adresses, motifs et DNS : [contact-blueseatra.md](./contact-blueseatra.md)).
Fondateur (identité commune avec journeyinto-ai.com) : **Zehair Louzza**, Paris.

## 1. Ce qui a été mis en place dans le dépôt

| Élément | Fichier | Rôle |
|---|---|---|
| Balises SEO de l'accueil (title, description, canonical, Open Graph, Twitter) | `frontend/public/index.html` | Ce que Google et les réseaux affichent |
| Données structurées JSON-LD (Organization, Person fondateur, WebSite, SoftwareApplication, FAQPage) | `frontend/public/index.html` + chaque page | Résultats enrichis, Knowledge Graph, moteurs IA |
| Contenu HTML de secours dans `#root` | `frontend/public/index.html` | Lisible sans JavaScript (robots, IA) |
| 6 pages statiques ciblées | `frontend/public/*.html` (générées) | Une page par intention de recherche |
| Générateur des pages + sitemap + image OG | `scripts/seo/generer_pages_seo.py` | Régénérer après toute modification de texte |
| `robots.txt`, `sitemap.xml`, `site.webmanifest`, `llms.txt` | `frontend/public/` | Exploration, indexation, moteurs de réponse IA |
| URLs propres, `noindex` sur `/app` et `/login`, cache des assets | `frontend/vercel.json` | Pas d'indexation de l'espace privé, vitesse |
| Footer : liens Solutions, À propos, Contact, email | `frontend/src/pages/Landing.js` | Maillage interne + contact visible |
| Titre de page dynamique FR/EN | `Landing.js`, `i18n_lp.js` | Fin du titre générique « Blueseatra » |

Pour modifier un texte : éditer `PAGES` dans `scripts/seo/generer_pages_seo.py`, puis
`python3 scripts/seo/generer_pages_seo.py` et committer les fichiers générés.

## 2. Carte des mots-clés (une page = une intention)

| Page | Mot-clé principal | Variantes secondaires |
|---|---|---|
| `/` | logiciel devis IA bâtiment | devis BTP IA, Blueseatra |
| `/logiciel-devis-ia` | logiciel devis IA | générateur de devis IA, devis intelligence artificielle, faire un devis avec l'IA, IA devis artisan |
| `/automatisation-devis` | automatisation devis | automatiser ses devis, devis automatique, devis BTP automatique, relance devis |
| `/logiciel-devis-batiment` | logiciel devis bâtiment | logiciel devis BTP, logiciel devis artisan, devis travaux, devis TCE, chiffrage travaux, TVA travaux |
| `/facturation-ia` | facturation IA | logiciel devis facture, solution facturation IA, facture pro forma, facturation électronique 2026, facturation électronique artisan |
| `/a-propos` | Blueseatra fondateur | Zehair Louzza |
| `/contact` | contact Blueseatra | démo logiciel devis |

Règle : un mot-clé principal n'est travaillé que sur **une seule page** (pas de cannibalisation).
La balise `meta keywords` n'est pas utilisée : Google l'ignore depuis 2009. Les mots-clés
vivent dans le title, le H1, les H2, le texte et les ancres de liens.

## 3. Actions à faire hors du dépôt (indispensables)

1. **Google Search Console** : ajouter la propriété de domaine `blueseatra.com` (vérification
   par enregistrement TXT chez Hostinger), puis soumettre `https://www.blueseatra.com/sitemap.xml`
   et demander l'indexation des 6 pages via « Inspection de l'URL ».
2. **Bing Webmaster Tools** : importer depuis Search Console (Bing alimente aussi ChatGPT et Copilot).
3. **Google Business Profile** : fiche « Éditeur de logiciels » à Paris avec l'email de contact.
4. **Email** : boîte `contact@blueseatra.com` créée chez Hostinger (vérifié le 10/10/2026) ; MX, SPF et DKIM en place, DMARC à renforcer (voir [contact-blueseatra.md](./contact-blueseatra.md)).
5. **Liens externes** : depuis journeyinto-ai.com (page À propos et footer : « Autre projet du fondateur : Blueseatra »),
   le profil LinkedIn, le profil GitHub, et la page LinkedIn entreprise Blueseatra.
6. **Mentions légales** : page `/mentions-legales` en place (éditeur, hébergeurs, RGPD) ; ajouter forme juridique, SIREN/SIRET et adresse du siège
   dès que la structure juridique est fixée (obligation légale et signal de confiance E-E-A-T).

## 4. Brainstorming : perspectives pour gagner les premières positions

Soyons honnêtes : personne ne peut garantir la première place sur Google. Les requêtes « logiciel devis »
sont tenues par des acteurs installés (Obat, Tolteck, Batappli, Axonaut, Henrri...) avec des milliers de
backlinks. La stratégie gagnante est d'attaquer **là où ils sont faibles** puis d'élargir.

### Axe A. Niche d'abord, volume ensuite
- Viser des requêtes longue traîne que les gros n'ont pas : « devis TCE IA », « devis maintenance bureaux »,
  « transformer un email en devis », « devis à partir d'une photo », « devis depuis un PDF client »,
  « comparer prix Rexel Prolians ». Peu de concurrence = positions rapides.
- Une fois ces pages en top 3, monter vers « logiciel devis IA » puis « logiciel devis bâtiment ».

### Axe B. Pages métier (programmatique mais utile)
- Une page par métier : électricien, plombier, peintre, plaquiste, menuisier, chauffagiste, maintenance multitechnique.
  Chaque page avec un exemple réel de devis (lots, heures, TVA), pas un simple copier-coller.
- Une page par cas tertiaire : aménagement de bureaux, boutique, restaurant, cabinet médical.

### Axe C. Contenu d'expertise (E-E-A-T)
- Guides signés par le fondateur : « Taux de TVA travaux 2026 expliqué », « Mentions obligatoires d'un devis BTP »,
  « Facturation électronique 2027 : ce que doit faire un artisan », « Comment chiffrer la main-d'oeuvre ».
- Outils gratuits : calculateur TVA travaux, générateur de mentions légales de devis, modèle de devis Excel.
  Les outils gratuits attirent naturellement des liens (backlinks) et des recherches.

### Axe D. GEO : être cité par les moteurs IA
- `llms.txt`, FAQ structurées et phrases factuelles courtes (déjà en place) aident Perplexity, ChatGPT et Gemini
  à citer Blueseatra dans « quel logiciel de devis IA pour le BTP ».
- Être présent dans les comparatifs : contacter les blogs qui publient « meilleurs logiciels IA BTP 2026 ».

### Axe E. Signaux de marque
- Annuaires logiciels : Capterra, GetApp, Appvizer, LesFlashs ; avis clients réels.
- Partenariats : fédérations (CAPEB, FFB), écoles BTP, comptables (lien naturel avec la facturation électronique).
- Journey into AI peut publier une étude de cas « comment l'IA lit un devis » renvoyant vers Blueseatra.

### Axe F. Technique (prochaines étapes)
- Pré-rendu complet de la landing React (react-snap ou migration Next.js/Vite SSG) pour un HTML identique au rendu.
- Version anglaise des pages statiques (`/en/...`) avec hreflang si le marché international est visé.
- Suivre Core Web Vitals via Vercel Speed Insights (déjà installé) : LCP < 2,5 s, CLS < 0,1.
- Images en WebP/AVIF pour `/landing/*.jpg`.

### Indicateurs à suivre (Search Console)
- Impressions et clics par page, position moyenne par mot-clé principal.
- Objectif réaliste : indexation en 1 à 2 semaines, premières positions longue traîne en 1 à 3 mois,
  requêtes concurrentielles en 6 à 12 mois avec contenu régulier et backlinks.

## 5. Sources réglementaires citées
- Calendrier facturation électronique : https://entreprendre.service-public.gouv.fr/actualites/A15683
- Définition d'une facture électronique (PDF non conforme) : https://www.francenum.gouv.fr/ma-priorite/passer-la-facturation-electronique-guide-pour-tpe-pme
- Consignes Google sur le contenu utile : https://developers.google.com/search/docs/fundamentals/creating-helpful-content
