"""Generation des pages SEO statiques de blueseatra.com.

Pourquoi des pages statiques ?
  Le site public est une application React (CRA). Google sait executer le
  JavaScript, mais une page HTML deja remplie est indexee plus vite, plus
  surement, et lue aussi par les moteurs IA (Perplexity, ChatGPT, Gemini) qui
  n'executent pas toujours le JS. Chaque page cible une intention de recherche
  precise (un mot-cle principal + ses variantes), conformement aux consignes
  Google "contenu utile, fiable et cree pour les utilisateurs".

Usage :
  python3 scripts/seo/generer_pages_seo.py
  -> ecrit frontend/public/<slug>.html, sitemap.xml, og/blueseatra-og.png

Regles editoriales (a respecter si vous modifiez les textes) :
  - un seul H1 par page, contenant le mot-cle principal ;
  - title <= 60 caracteres, meta description <= 155 caracteres ;
  - aucune promesse fausse : Blueseatra prepare devis et factures pro forma ;
    il n'est pas (encore) plateforme agreee de facturation electronique ;
  - pas de bourrage de mots-cles : on ecrit pour un artisan, pas pour un robot.
"""
from __future__ import annotations

import html
import json
from datetime import date
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
PUBLIC = RACINE / "frontend" / "public"
SITE = "https://www.blueseatra.com"
EMAIL = "contact@blueseatra.com"
AUJOURD_HUI = date.today().isoformat()

FONDATEUR = {
    "@type": "Person",
    "@id": f"{SITE}/a-propos#fondateur",
    "name": "Zehair Louzza",
    "jobTitle": "Fondateur de Blueseatra",
    "worksFor": {"@id": f"{SITE}/#organisation"},
    "url": f"{SITE}/a-propos",
    "sameAs": [
        "https://github.com/zehair-louzza",
        "https://www.linkedin.com/in/zehair-louzza-873367109",
        "https://journeyinto-ai.com",
    ],
}

ORGANISATION = {
    "@type": "Organization",
    "@id": f"{SITE}/#organisation",
    "name": "Blueseatra",
    "url": f"{SITE}/",
    "logo": f"{SITE}/brand/blueseatra-mark.png",
    "email": EMAIL,
    "address": {"@type": "PostalAddress", "addressLocality": "Paris", "addressRegion": "Île-de-France", "addressCountry": "FR"},
    "contactPoint": {"@type": "ContactPoint", "email": EMAIL, "contactType": "customer support", "availableLanguage": ["French", "English"]},
    "founder": {"@id": f"{SITE}/a-propos#fondateur"},
    "sameAs": ["https://github.com/zehair-louzza"],
}

# --------------------------------------------------------------------------
# Contenu des pages. Chaque section : (titre H2, [paragraphes ou listes]).
# Une liste Python dans les paragraphes devient une liste <ul>.
# --------------------------------------------------------------------------
PAGES = [
    {
        "slug": "logiciel-devis-ia",
        "title": "Logiciel de devis IA pour le bâtiment | Blueseatra",
        "description": "Créez vos devis avec l'IA : Blueseatra lit emails, PDF et photos, chiffre sur vos prix et prépare un devis BTP prêt à valider. Essai gratuit 14 jours.",
        "h1": "Logiciel de devis IA : vos devis prêts en quelques minutes, sur vos prix",
        "chapo": "Blueseatra est un logiciel de devis avec intelligence artificielle conçu pour les artisans, les PME du bâtiment et les entreprises de maintenance TCE. L'IA lit la demande du client, vous gardez la main sur chaque prix.",
        "sections": [
            ("Comment l'IA crée un devis avec Blueseatra", [
                "Vous recevez une demande par email, en PDF, en Excel ou en photo d'une note de chantier. Blueseatra en extrait le client, l'adresse du chantier, les lots, les quantités et les matériaux. Chaque ligne est ensuite rapprochée de votre catalogue de prix actif.",
                ["Lecture automatique des emails, PDF, DOCX, XLSX, CSV et photos (OCR)",
                 "Structuration en lots et sous-lots TCE : électricité, plomberie, peinture, cloisons, menuiserie",
                 "Main-d'oeuvre en heures, taille d'équipe et déplacements proposés",
                 "TVA bâtiment 20 %, 10 %, 5,5 % ou 0 % et mentions légales sur le PDF"],
            ]),
            ("Une IA qui n'invente jamais vos prix", [
                "C'est la différence avec un générateur de devis IA généraliste : chez Blueseatra, l'IA lit et structure, mais les prix, remises, marges et TVA sont calculés par des règles métier fixes. Un article inconnu est signalé, jamais inventé. La version du catalogue est figée sur chaque devis pour garder une trace exacte.",
            ]),
            ("Pour qui ?", [
                ["Artisans et indépendants du bâtiment qui veulent faire leurs devis plus vite",
                 "PME tous corps d'état (TCE) qui chiffrent beaucoup de demandes",
                 "Entreprises de maintenance et de second oeuvre en tertiaire : bureaux, boutiques, commerces",
                 "Groupes et réseaux qui gèrent plusieurs entreprises, avec des données isolées"],
            ]),
        ],
        "faq": [
            ("Qu'est-ce qu'un logiciel de devis IA ?", "C'est un logiciel qui utilise l'intelligence artificielle pour lire une demande client et préparer automatiquement les lignes d'un devis. Avec Blueseatra, l'IA prépare le brouillon et vous validez chaque ligne avant l'envoi."),
            ("L'IA peut-elle modifier mes prix ?", "Non. Les montants viennent uniquement de votre catalogue et sont calculés par des règles fixes. L'IA ne fixe jamais un prix."),
            ("Combien coûte Blueseatra ?", "Un essai gratuit de 14 jours sans carte bancaire est proposé, puis des offres par entreprise à partir de l'offre Initial pour un artisan. Les devis et PDF sont illimités dans toutes les offres."),
        ],
        "liens": ["automatisation-devis", "logiciel-devis-batiment", "facturation-ia"],
    },
    {
        "slug": "automatisation-devis",
        "title": "Automatisation des devis BTP avec l'IA | Blueseatra",
        "description": "Automatisez vos devis : de la demande client au PDF signé en 5 étapes. Lecture IA, catalogue fournisseurs, TVA et mentions légales. Gagnez des heures.",
        "h1": "Automatisation des devis : de la demande brute au devis validé",
        "chapo": "Chiffrer une demande à la main prend souvent une demi-journée : relire l'email, chercher les références, retaper les lignes, appliquer la TVA, mettre en page le PDF. Blueseatra automatise ces tâches répétitives pour que votre temps reparte sur le chantier.",
        "sections": [
            ("Les 5 étapes d'un devis automatisé", [
                ["Collecter : collez un email, importez un PDF, un bordereau Excel ou une photo",
                 "Lire : client, chantier, lots et quantités sont extraits par l'IA",
                 "Rapprocher : chaque ligne est comparée à votre catalogue et aux catalogues fournisseurs",
                 "Contrôler : heures, déplacements et TVA sont proposés, vous corrigez",
                 "Éditer : le PDF reprend votre logo et vos mentions légales, vous validez et envoyez"],
            ]),
            ("Automatiser sans perdre le contrôle", [
                "L'automatisation des devis ne doit pas vous faire perdre la maîtrise de vos marges. Blueseatra affiche la source tarifaire de chaque ligne, garde la marge interne hors du PDF client et enregistre chaque action dans un journal d'audit.",
            ]),
            ("Relances et suivi des devis", [
                "Une fois envoyés, les devis sont suivis. Blueseatra propose des relances au bon moment pour augmenter votre taux de signature, sans tableau Excel à tenir à jour.",
            ]),
        ],
        "faq": [
            ("Comment automatiser ses devis dans le BTP ?", "Centralisez les demandes, utilisez un catalogue de prix à jour et laissez un outil comme Blueseatra lire la demande et préparer les lignes. Vous gardez la validation finale."),
            ("Combien de temps peut-on gagner ?", "Le gain dépend de la taille du devis. L'essentiel du temps économisé vient de la lecture de la demande, de la recherche des références et de la mise en page, qui sont automatisées."),
            ("Puis-je importer mon propre catalogue ?", "Oui, en CSV ou Excel. Les colonnes sont reconnues automatiquement et chaque import crée une version que vous activez quand vous le souhaitez."),
        ],
        "liens": ["logiciel-devis-ia", "logiciel-devis-batiment", "facturation-ia"],
    },
    {
        "slug": "logiciel-devis-batiment",
        "title": "Logiciel de devis bâtiment et TCE | Blueseatra",
        "description": "Logiciel de devis bâtiment pour artisans et PME TCE : lots, main-d'oeuvre, déplacements, TVA 20/10/5,5 %, catalogues Rexel, Prolians, SFIC. Essai gratuit.",
        "h1": "Logiciel de devis bâtiment pour artisans et entreprises TCE",
        "chapo": "Un devis de travaux n'est pas une simple liste de prix. Il faut des lots, de la main-d'oeuvre, des déplacements, la bonne TVA et des mentions légales conformes. Blueseatra reprend la logique d'un vrai chiffreur du bâtiment.",
        "sections": [
            ("Un devis travaux structuré comme sur le terrain", [
                ["Lots et sous-lots tous corps d'état (TCE)",
                 "Fournitures et pose séparées, heures-homme et taille d'équipe",
                 "Frais de déplacement et d'installation de chantier",
                 "Descriptif de travaux compréhensible par le client final"],
            ]),
            ("Catalogues fournisseurs et comparaison de prix", [
                "Les catalogues de distributeurs du bâtiment comme Rexel, Point.P, Prolians ou SFIC sont consultables dans chaque espace, à côté de votre propre catalogue de prix négociés. Le moins cher par fournisseur apparaît en un coup d'oeil.",
            ]),
            ("TVA bâtiment et mentions obligatoires", [
                "Blueseatra gère les taux de TVA travaux en France : 20 %, 10 % pour la rénovation de logements de plus de deux ans, 5,5 % pour certains travaux de rénovation énergétique, et 0 % en franchise en base. Le PDF intègre SIRET, assurance, durée de validité et bon pour accord.",
            ]),
        ],
        "faq": [
            ("Quel logiciel de devis pour un artisan du bâtiment ?", "Choisissez un logiciel qui gère les lots, la main-d'oeuvre, les taux de TVA du bâtiment et vos propres prix. Blueseatra ajoute la lecture IA des demandes pour aller plus vite."),
            ("Blueseatra convient-il aux devis tertiaires ?", "Oui. Il est pensé pour l'aménagement, la rénovation et la maintenance de bureaux, boutiques et commerces, ainsi que pour le logement individuel."),
            ("Mes données sont-elles séparées des autres entreprises ?", "Oui. Chaque espace est isolé au niveau de la base de données et chaque action est tracée."),
        ],
        "liens": ["logiciel-devis-ia", "automatisation-devis", "facturation-ia"],
    },
    {
        "slug": "facturation-ia",
        "title": "Facturation IA : du devis à la facture | Blueseatra",
        "description": "Facturation et IA pour le BTP : transformez un devis validé en facture pro forma en un clic et préparez la facturation électronique 2026-2027.",
        "h1": "Facturation IA : du devis validé à la facture, sans ressaisie",
        "chapo": "La facture commence au devis. Si le devis est juste, structuré et tracé, la facturation devient une formalité. Blueseatra utilise l'IA en amont, là où se perd le plus de temps, pour que vos factures reprennent des données propres.",
        "sections": [
            ("Du devis à la facture pro forma", [
                "Un devis validé dans Blueseatra peut être édité en devis-facture pro forma, avec les mêmes lignes, la même TVA et les mêmes mentions. Aucune ressaisie, aucune erreur de recopie.",
            ]),
            ("Se préparer à la facturation électronique 2026-2027", [
                "Depuis le 1er septembre 2026, toutes les entreprises assujetties à la TVA doivent pouvoir recevoir des factures électroniques. L'obligation d'émettre arrive le 1er septembre 2027 pour les PME, TPE et micro-entreprises, via une plateforme agréée (source : entreprendre.service-public.gouv.fr).",
                "Une facture électronique conforme repose sur des données structurées. En structurant vos devis dès la demande (client, lots, quantités, TVA), Blueseatra vous aide à disposer de données prêtes à être transmises à la plateforme agréée de votre choix.",
            ]),
            ("Ce que fait Blueseatra aujourd'hui", [
                ["Devis et devis-facture pro forma en PDF avec vos mentions légales",
                 "Calcul fiable de la TVA bâtiment, sans intervention de l'IA sur les montants",
                 "Historique et versions des devis",
                 "Suivi et relances des devis envoyés"],
                "Blueseatra n'est pas une plateforme agréée de facturation électronique. Pour l'émission et la réception des factures électroniques, vous restez libre de choisir votre plateforme agréée.",
            ]),
        ],
        "faq": [
            ("Qu'est-ce que la facturation IA ?", "C'est l'utilisation de l'intelligence artificielle pour réduire la saisie dans la chaîne devis-facture : lecture des demandes, structuration des lignes, contrôle des incohérences. Les montants restent calculés par des règles fixes."),
            ("Un PDF envoyé par email est-il une facture électronique ?", "Non. Selon l'administration, une facture électronique doit contenir des données structurées et transiter par une plateforme agréée. Un simple PDF n'est pas suffisant."),
            ("Quand mon entreprise doit-elle émettre des factures électroniques ?", "Le 1er septembre 2027 pour les PME, TPE et micro-entreprises. La réception est obligatoire pour toutes les entreprises depuis le 1er septembre 2026."),
        ],
        "liens": ["logiciel-devis-ia", "automatisation-devis", "logiciel-devis-batiment"],
    },
    {
        "slug": "a-propos",
        "title": "À propos de Blueseatra et de son fondateur",
        "description": "Blueseatra a été fondé à Paris par Zehair Louzza, fondateur de Journey into AI, pour ramener le calme dans la paperasse du BTP grâce à une IA fiable.",
        "h1": "À propos de Blueseatra",
        "chapo": "Blueseatra est un logiciel français de devis assisté par l'IA, créé à Paris pour les artisans, les PME du bâtiment et les entreprises de maintenance.",
        "sections": [
            ("Le fondateur", [
                "Je m'appelle Zehair Louzza. J'ai travaillé sur la préparation de devis, le chiffrage de travaux et la gestion de catalogues fournisseurs, puis je me suis spécialisé dans la data et l'intelligence artificielle. Je suis aussi le fondateur de Journey into AI (journeyinto-ai.com), une plateforme pour comprendre l'IA de A à Z.",
                "J'ai créé Blueseatra après avoir constaté le temps perdu à recopier des demandes, chercher des références et refaire les mêmes calculs de TVA. L'objectif : que l'IA fasse la lecture et la mise en forme, et que l'humain garde la décision.",
            ]),
            ("Notre nom, notre promesse", [
                ["Blue : la confiance dans le calcul. Les prix sont calculés par des règles, jamais par un modèle.",
                 "Sea : le flot de vos demandes, réunies dans un seul flux, quel que soit le canal.",
                 "Tra : transformation et traçabilité. Chaque étape est tracée, chaque entreprise est isolée."],
            ]),
            ("Nos engagements", [
                ["Aucun prix inventé par l'IA",
                 "Données isolées par entreprise et journal d'audit",
                 "Hébergement et traitements pensés pour la confidentialité",
                 f"Un contact direct : {EMAIL}"],
            ]),
        ],
        "faq": [],
        "liens": ["logiciel-devis-ia", "contact"],
        "type_page": "AboutPage",
    },
    {
        "slug": "contact",
        "title": "Contact Blueseatra | Démo et questions",
        "description": f"Contactez Blueseatra pour une démo du logiciel de devis IA, une question sur les offres ou l'import de votre catalogue : {EMAIL}.",
        "h1": "Contacter Blueseatra",
        "chapo": "Une question sur le logiciel, une démonstration, l'import de votre catalogue ou une offre pour plusieurs entreprises ? Écrivez-nous, nous répondons personnellement.",
        "sections": [
            ("Email", [f"EMAIL_BLOCK"]),
            ("Localisation", ["Blueseatra est basé à Paris, Île-de-France, et accompagne les entreprises du bâtiment partout en France."]),
            ("Essayer sans attendre", ["Vous pouvez aussi créer votre espace et tester Blueseatra gratuitement pendant 14 jours, sans carte bancaire."]),
        ],
        "faq": [],
        "liens": ["logiciel-devis-ia", "a-propos"],
        "type_page": "ContactPage",
    },
    {
        "slug": "mentions-legales",
        "title": "Mentions légales et confidentialité | Blueseatra",
        "description": "Mentions légales du site blueseatra.com : éditeur, hébergeurs, propriété intellectuelle, données personnelles et cookies.",
        "h1": "Mentions légales et confidentialité",
        "chapo": "Conformément à la loi n° 2004-575 du 21 juin 2004 pour la confiance dans l'économie numérique (LCEN), voici les informations relatives au site www.blueseatra.com.",
        "sections": [
            ("Éditeur du site", [
                ["Blueseatra, projet édité par Zehair Louzza",
                 "Paris, Île-de-France, France",
                 f"Email : {EMAIL}",
                 "Directeur de la publication : Zehair Louzza"],
                "Le numéro d'immatriculation (SIREN/SIRET) sera ajouté ici dès l'immatriculation de la structure.",
            ]),
            ("Hébergement", [
                ["Site web : Vercel Inc., 440 N Barranca Ave #4133, Covina, CA 91723, États-Unis (vercel.com)",
                 "Serveur d'application : Render Services, Inc., 525 Brannan Street, Suite 300, San Francisco, CA 94107, États-Unis (render.com)",
                 "Base de données : Supabase Inc. (supabase.com)"],
            ]),
            ("Propriété intellectuelle", [
                "Les textes, logos, marques, images et le logiciel Blueseatra sont protégés par le droit de la propriété intellectuelle. Toute reproduction, même partielle, est interdite sans autorisation écrite préalable.",
            ]),
            ("Données personnelles", [
                "Les données transmises (email de contact, compte utilisateur, documents importés pour un devis) servent uniquement à fournir le service et à répondre à vos demandes. Elles ne sont ni vendues ni cédées à des tiers. Les données de chaque entreprise sont isolées dans la base de données. La lecture automatique des documents peut faire appel à des sous-traitants techniques (hébergeurs, fournisseurs de modèles d'IA) qui agissent uniquement pour le compte de Blueseatra.",
                f"Conformément au RGPD et à la loi Informatique et Libertés, vous disposez d'un droit d'accès, de rectification, d'effacement, d'opposition et de portabilité. Pour l'exercer : {EMAIL}. Vous pouvez aussi saisir la CNIL (cnil.fr).",
            ]),
            ("Cookies et mesure d'audience", [
                "Le site utilise une mesure d'audience et de performance sans cookie publicitaire (Vercel Analytics et Speed Insights). Des éléments techniques nécessaires à la connexion sont stockés dans votre navigateur lorsque vous utilisez l'application.",
            ]),
            ("Droit applicable", [
                "Les présentes mentions légales sont régies par le droit français. En cas de litige, et à défaut d'accord amiable, les tribunaux français sont compétents.",
            ]),
        ],
        "faq": [],
        "liens": ["a-propos", "contact"],
    },
]

LIBELLES = {
    "logiciel-devis-ia": "Logiciel de devis IA",
    "automatisation-devis": "Automatisation des devis",
    "logiciel-devis-batiment": "Logiciel de devis bâtiment",
    "facturation-ia": "Facturation IA",
    "a-propos": "À propos",
    "contact": "Contact",
    "mentions-legales": "Mentions légales",
}


def e(texte: str) -> str:
    return html.escape(texte, quote=True)


def rendre_bloc(bloc) -> str:
    if isinstance(bloc, list):
        return "<ul>" + "".join(f"<li>{e(x)}</li>" for x in bloc) + "</ul>"
    if bloc == "EMAIL_BLOCK":
        return f'<p class="email"><a href="mailto:{EMAIL}">{EMAIL}</a></p>'
    return f"<p>{e(bloc)}</p>"


def json_ld(page: dict) -> str:
    url = f"{SITE}/{page['slug']}"
    graphe = [
        ORGANISATION,
        FONDATEUR,
        {
            "@type": page.get("type_page", "WebPage"),
            "@id": f"{url}#page",
            "url": url,
            "name": page["title"],
            "description": page["description"],
            "inLanguage": "fr-FR",
            "isPartOf": {"@id": f"{SITE}/#site"},
            "publisher": {"@id": f"{SITE}/#organisation"},
            "dateModified": AUJOURD_HUI,
        },
        {
            "@type": "BreadcrumbList",
            "itemListElement": [
                {"@type": "ListItem", "position": 1, "name": "Accueil", "item": f"{SITE}/"},
                {"@type": "ListItem", "position": 2, "name": LIBELLES[page["slug"]], "item": url},
            ],
        },
    ]
    if page["faq"]:
        graphe.append({
            "@type": "FAQPage",
            "mainEntity": [
                {"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": r}}
                for q, r in page["faq"]
            ],
        })
    return json.dumps({"@context": "https://schema.org", "@graph": graphe}, ensure_ascii=False, indent=2)


def rendre_page(page: dict) -> str:
    url = f"{SITE}/{page['slug']}"
    sections = "".join(
        f"<section><h2>{e(titre)}</h2>{''.join(rendre_bloc(b) for b in blocs)}</section>"
        for titre, blocs in page["sections"]
    )
    faq = ""
    if page["faq"]:
        faq = "<section><h2>Questions fréquentes</h2>" + "".join(
            f"<details><summary>{e(q)}</summary><p>{e(r)}</p></details>" for q, r in page["faq"]
        ) + "</section>"
    liens = "".join(f'<li><a href="/{s}">{e(LIBELLES[s])}</a></li>' for s in page["liens"])
    nav = "".join(f'<a href="/{s}">{e(l)}</a>' for s, l in LIBELLES.items() if s not in ("a-propos", "contact", "mentions-legales"))
    return f"""<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(page['title'])}</title>
<meta name="description" content="{e(page['description'])}">
<meta name="robots" content="index, follow, max-image-preview:large">
<meta name="author" content="Zehair Louzza">
<link rel="canonical" href="{url}">
<link rel="alternate" hreflang="fr" href="{url}">
<link rel="alternate" hreflang="x-default" href="{url}">
<meta name="theme-color" content="#193852">
<link rel="icon" type="image/png" sizes="32x32" href="/brand/favicon-32.png">
<link rel="apple-touch-icon" href="/brand/apple-touch.png">
<meta property="og:type" content="website">
<meta property="og:site_name" content="Blueseatra">
<meta property="og:locale" content="fr_FR">
<meta property="og:title" content="{e(page['title'])}">
<meta property="og:description" content="{e(page['description'])}">
<meta property="og:url" content="{url}">
<meta property="og:image" content="{SITE}/og/blueseatra-og.png">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{e(page['title'])}">
<meta name="twitter:description" content="{e(page['description'])}">
<meta name="twitter:image" content="{SITE}/og/blueseatra-og.png">
<link rel="stylesheet" href="/seo/seo.css">
<script type="application/ld+json">
{json_ld(page)}
</script>
</head>
<body>
<header class="bar"><div class="wrap">
<a class="logo" href="/" aria-label="Blueseatra, accueil"><img src="/brand/blueseatra-lockup.png" alt="Blueseatra" width="150" height="50"></a>
<nav aria-label="Solutions">{nav}</nav>
<a class="btn" href="/signup">Essai gratuit 14 jours</a>
</div></header>
<main class="wrap">
<nav class="ariane" aria-label="Fil d'Ariane"><a href="/">Accueil</a> › <span>{e(LIBELLES[page['slug']])}</span></nav>
<h1>{e(page['h1'])}</h1>
<p class="chapo">{e(page['chapo'])}</p>
<p><a class="btn" href="/signup">Essayer gratuitement</a> <a class="btn ghost" href="mailto:{EMAIL}">Demander une démo</a></p>
{sections}
{faq}
<section class="voir"><h2>À lire aussi</h2><ul>{liens}</ul></section>
</main>
<footer><div class="wrap">
<p><strong>Blueseatra</strong> · Logiciel de devis IA pour le bâtiment · Paris, France</p>
<p>Contact : <a href="mailto:{EMAIL}">{EMAIL}</a> · <a href="/a-propos">À propos</a> · <a href="/contact">Contact</a> · <a href="/mentions-legales">Mentions légales</a> · <a href="/login">Connexion</a></p>
<p>Fondé par <a href="/a-propos">Zehair Louzza</a>, également fondateur de <a href="https://journeyinto-ai.com" rel="noopener">Journey into AI</a>.</p>
</div></footer>
</body>
</html>
"""


def ecrire_sitemap() -> None:
    urls = [("", "1.0")] + [(p["slug"], "0.8" if p["slug"] not in ("a-propos", "contact", "mentions-legales") else ("0.3" if p["slug"] == "mentions-legales" else "0.5")) for p in PAGES] + [("signup", "0.6")]
    lignes = "".join(
        f"  <url><loc>{SITE}/{slug}</loc><lastmod>{AUJOURD_HUI}</lastmod><priority>{prio}</priority></url>\n"
        for slug, prio in urls
    )
    (PUBLIC / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + lignes + "</urlset>\n",
        encoding="utf-8",
    )


def ecrire_image_og() -> None:
    """Image de partage 1200x630 (LinkedIn, WhatsApp, X, Google Discover)."""
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        print("Pillow absent : image OG non regeneree")
        return
    fond = Image.new("RGB", (1200, 630), (25, 56, 82))
    dessin = ImageDraw.Draw(fond)
    marque = Image.open(PUBLIC / "brand" / "blueseatra-mark.png").convert("RGBA").resize((240, 240))
    dessin.rounded_rectangle((840, 165, 1120, 445), radius=36, fill=(255, 255, 255))
    fond.paste(marque, (860, 185), marque)

    def police(taille, gras=False):
        for nom in (["DejaVuSans-Bold.ttf"] if gras else ["DejaVuSans.ttf"]):
            for dossier in ("/usr/share/fonts/truetype/dejavu/", ""):
                try:
                    return ImageFont.truetype(dossier + nom, taille)
                except OSError:
                    continue
        return ImageFont.load_default()

    dessin.text((80, 150), "Blueseatra", font=police(76, True), fill=(255, 255, 255))
    dessin.text((80, 265), "Logiciel de devis IA", font=police(48, True), fill=(122, 205, 214))
    dessin.text((80, 330), "pour le bâtiment et la maintenance", font=police(40), fill=(230, 238, 245))
    dessin.text((80, 450), "Emails, PDF, photos → devis validé, sur vos prix", font=police(30), fill=(200, 215, 228))
    dessin.text((80, 520), "www.blueseatra.com", font=police(28), fill=(160, 185, 205))
    (PUBLIC / "og").mkdir(exist_ok=True)
    fond.save(PUBLIC / "og" / "blueseatra-og.png", optimize=True)


def main() -> None:
    for page in PAGES:
        assert len(page["title"]) <= 60, (page["slug"], len(page["title"]))
        assert len(page["description"]) <= 160, (page["slug"], len(page["description"]))
        (PUBLIC / f"{page['slug']}.html").write_text(rendre_page(page), encoding="utf-8")
    ecrire_sitemap()
    ecrire_image_og()
    print(f"{len(PAGES)} pages, sitemap et image OG generes dans {PUBLIC}")


if __name__ == "__main__":
    main()
