# Documentation Blueseatra

Toute la documentation du projet, classée par usage.


## Schémas

<table>
<tr>
<td width="50%" valign="top"><a href="../docs/architecture.md"><img src="../docs/assets/schema-architecture.png" alt="Architecture"></a><br><sub><b>Architecture</b> : Vercel, Render, Supabase, passerelle Hermès, VPS OVH</sub></td>
<td width="50%" valign="top"><a href="../docs/infrastructure.md"><img src="../docs/assets/schema-parcours-complet.png" alt="Parcours complet d'un devis"></a><br><sub><b>Parcours complet d'un devis</b> : dix phases, qui agit et qui réagit</sub></td>
</tr>
<tr>
<td width="50%" valign="top"><a href="../docs/manuel-utilisateur.md"><img src="../docs/assets/schema-parcours.png" alt="Parcours d'une demande"></a><br><sub><b>Parcours d'une demande</b> : de l'e-mail au devis validé</sub></td>
<td width="50%" valign="top"><a href="../docs/architecture.md"><img src="../docs/assets/schema-routage.png" alt="Routage IA"></a><br><sub><b>Routage IA</b> : passerelle Hermès, Ollama, Mistral, OpenCode Free</sub></td>
</tr>
<tr>
<td width="50%" valign="top"><a href="../docs/rgpd-masquage-ia-externe.md"><img src="../docs/assets/schema-masquage-rgpd.png" alt="Masquage RGPD"></a><br><sub><b>Masquage RGPD</b> : marqueurs avant chaque appel IA, restauration côté serveur</sub></td>
<td width="50%" valign="top"><a href="../docs/rgpd-masquage-ia-externe.md"><img src="../docs/assets/schema-g3.png" alt="Suggestions d'articles G3"></a><br><sub><b>Suggestions d'articles G3</b> : candidats réels, choix de l'IA, validation humaine</sub></td>
</tr>
<tr>
<td width="50%" valign="top"><a href="../docs/manuel-utilisateur.md"><img src="../docs/assets/schema-chiffrage.png" alt="Chiffrage sur sources activables"></a><br><sub><b>Chiffrage sur sources activables</b> : catalogue interne et catalogues fournisseurs</sub></td>
<td width="50%" valign="top"><a href="../docs/architecture.md"><img src="../docs/assets/schema-recherche-rls.png" alt="Recherche fournisseurs sous RLS"></a><br><sub><b>Recherche fournisseurs sous RLS</b> : fonctions sécurisées, mesures avant et après</sub></td>
</tr>
<tr>
<td width="50%" valign="top"><a href="../docs/manuel-utilisateur.md"><img src="../docs/assets/schema-import-catalogue.png" alt="Import de catalogue"></a><br><sub><b>Import de catalogue</b> : cinq étapes et verdict du contrôle</sub></td>
<td width="50%" valign="top"><a href="../docs/manuel-utilisateur.md"><img src="../docs/assets/schema-cycle-devis.png" alt="Cycle de vie d'un devis"></a><br><sub><b>Cycle de vie d'un devis</b> : statuts, relances, arrêt</sub></td>
</tr>
<tr>
<td width="50%" valign="top"><a href="../docs/specs/module-clients.md"><img src="../docs/assets/schema-relances-email.png" alt="Relances par e-mail"></a><br><sub><b>Relances par e-mail</b> : clic ou automatique, boîte de l'entreprise</sub></td>
<td width="50%" valign="top"><a href="../docs/tarification-2026-09.md"><img src="../docs/assets/schema-quotas.png" alt="Quotas"></a><br><sub><b>Quotas</b> : réservation, remboursement, ce qui n'est jamais compté</sub></td>
</tr>
<tr>
<td width="50%" valign="top"><a href="../docs/audit-isolation-tenants-2026-09-12.md"><img src="../docs/assets/schema-isolation.png" alt="Isolation des entreprises"></a><br><sub><b>Isolation des entreprises</b> : filtre du code et RLS PostgreSQL</sub></td>
<td width="50%" valign="top"><a href="../docs/conformite-rgpd.md"><img src="../docs/assets/schema-rgpd.png" alt="Droits RGPD"></a><br><sub><b>Droits RGPD</b> : export, anonymisation, opposition</sub></td>
</tr>
<tr>
<td width="50%" valign="top"><a href="../docs/exploitation.md"><img src="../docs/assets/schema-livraison.png" alt="Chaîne de livraison"></a><br><sub><b>Chaîne de livraison</b> : PR, contrôles, déploiement, retour arrière</sub></td>
<td width="50%" valign="top"><a href="../docs/runbook-incident.md"><img src="../docs/assets/schema-incident.png" alt="Déroulé d'un incident"></a><br><sub><b>Déroulé d'un incident</b> : détecter, contenir, corriger, vérifier</sub></td>
</tr>
<tr>
<td width="50%" valign="top"><a href="../docs/infrastructure.md"><img src="../docs/assets/vue-supabase.png" alt="Vue Supabase"></a><br><sub><b>Vue Supabase</b> : schéma blueseatra, rôles et RLS</sub></td>
<td width="50%" valign="top"><a href="../docs/infrastructure.md"><img src="../docs/assets/vue-render.png" alt="Vue Render"></a><br><sub><b>Vue Render</b> : services, variables, déploiement</sub></td>
</tr>
</table>

Les schémas sont générés par [`scripts/docs/generer_schemas.py`](../scripts/docs/generer_schemas.py) et la bannière par [`scripts/docs/generer_banniere.py`](../scripts/docs/generer_banniere.py). Les schémas des dépôts Fournisseur-Blueseatra et ovh-ai-stack sont générés par [`scripts/docs/generer_schemas_ecosysteme.py`](../scripts/docs/generer_schemas_ecosysteme.py).

## Captures d'écran

<details>
<summary><b>Les 31 écrans de l'application</b> (cliquer pour afficher)</summary>

<table>
<tr>
<td width="33%" valign="top"><img src="../docs/assets/manuel/01-tableau-de-bord.jpg" alt="Tableau de bord"><br><sub><b>Tableau de bord</b></sub></td>
<td width="33%" valign="top"><img src="../docs/assets/manuel/02-demandes.jpg" alt="Demandes"><br><sub><b>Demandes</b></sub></td>
<td width="33%" valign="top"><img src="../docs/assets/manuel/02b-boite-reception.jpg" alt="Boîte de réception triée"><br><sub><b>Boîte de réception triée</b></sub></td>
</tr>
<tr>
<td width="33%" valign="top"><img src="../docs/assets/manuel/03-demande-detail.jpg" alt="Demande lue par l'IA"><br><sub><b>Demande lue par l'IA</b></sub></td>
<td width="33%" valign="top"><img src="../docs/assets/manuel/03b-demande-lignes.jpg" alt="Lignes de travaux extraites"><br><sub><b>Lignes de travaux extraites</b></sub></td>
<td width="33%" valign="top"><img src="../docs/assets/manuel/04-devis-liste.jpg" alt="Liste des devis"><br><sub><b>Liste des devis</b></sub></td>
</tr>
<tr>
<td width="33%" valign="top"><img src="../docs/assets/manuel/05-editeur-devis.jpg" alt="Éditeur de devis"><br><sub><b>Éditeur de devis</b></sub></td>
<td width="33%" valign="top"><img src="../docs/assets/manuel/05b-versions-devis.jpg" alt="Versions d'un devis"><br><sub><b>Versions d'un devis</b></sub></td>
<td width="33%" valign="top"><img src="../docs/assets/manuel/16-pdf-devis.jpg" alt="PDF Pro Forma"><br><sub><b>PDF Pro Forma</b></sub></td>
</tr>
<tr>
<td width="33%" valign="top"><img src="../docs/assets/manuel/06-catalogues.jpg" alt="Catalogues"><br><sub><b>Catalogues</b></sub></td>
<td width="33%" valign="top"><img src="../docs/assets/manuel/06b-controle-import.jpg" alt="Contrôle avant activation"><br><sub><b>Contrôle avant activation</b></sub></td>
<td width="33%" valign="top"><img src="../docs/assets/manuel/06c-afficher-catalogue-fournisseur.jpg" alt="Catalogue d'un fournisseur"><br><sub><b>Catalogue d'un fournisseur</b></sub></td>
</tr>
<tr>
<td width="33%" valign="top"><img src="../docs/assets/manuel/06d-sources-chiffrage.jpg" alt="Sources du chiffrage"><br><sub><b>Sources du chiffrage</b></sub></td>
<td width="33%" valign="top"><img src="../docs/assets/screens/catalogue-fournisseurs.jpg" alt="Catalogue fournisseurs"><br><sub><b>Catalogue fournisseurs</b></sub></td>
<td width="33%" valign="top"><img src="../docs/assets/manuel/15-comparateur-prix.jpg" alt="Comparateur de prix"><br><sub><b>Comparateur de prix</b></sub></td>
</tr>
<tr>
<td width="33%" valign="top"><img src="../docs/assets/manuel/15b-comparateur-resultats.jpg" alt="Le moins cher par fournisseur"><br><sub><b>Le moins cher par fournisseur</b></sub></td>
<td width="33%" valign="top"><img src="../docs/assets/manuel/15c-comparateur-produits-identiques.jpg" alt="Produits identiques"><br><sub><b>Produits identiques</b></sub></td>
<td width="33%" valign="top"><img src="../docs/assets/manuel/07-clients.jpg" alt="Clients"><br><sub><b>Clients</b></sub></td>
</tr>
<tr>
<td width="33%" valign="top"><img src="../docs/assets/manuel/08-fiche-client.jpg" alt="Fiche client"><br><sub><b>Fiche client</b></sub></td>
<td width="33%" valign="top"><img src="../docs/assets/manuel/09-relances.jpg" alt="À relancer"><br><sub><b>À relancer</b></sub></td>
<td width="33%" valign="top"><img src="../docs/assets/manuel/10-offre-consommation.jpg" alt="Offre et consommation"><br><sub><b>Offre et consommation</b></sub></td>
</tr>
<tr>
<td width="33%" valign="top"><img src="../docs/assets/manuel/11-membres.jpg" alt="Membres et rôles"><br><sub><b>Membres et rôles</b></sub></td>
<td width="33%" valign="top"><img src="../docs/assets/manuel/12-parametres.jpg" alt="Paramètres"><br><sub><b>Paramètres</b></sub></td>
<td width="33%" valign="top"><img src="../docs/assets/manuel/12b-societe-pdf.jpg" alt="Société et PDF"><br><sub><b>Société et PDF</b></sub></td>
</tr>
<tr>
<td width="33%" valign="top"><img src="../docs/assets/manuel/13-donnees-personnelles.jpg" alt="Données personnelles"><br><sub><b>Données personnelles</b></sub></td>
<td width="33%" valign="top"><img src="../docs/assets/manuel/14-journal-audit.jpg" alt="Journal d'audit"><br><sub><b>Journal d'audit</b></sub></td>
<td width="33%" valign="top"><img src="../docs/assets/screens/accueil.jpg" alt="Page d'accueil"><br><sub><b>Page d'accueil</b></sub></td>
</tr>
<tr>
<td width="33%" valign="top"><img src="../docs/assets/screens/tarifs.jpg" alt="Offres"><br><sub><b>Offres</b></sub></td>
<td width="33%" valign="top"><img src="../docs/assets/screens/valeurs.jpg" alt="Valeurs"><br><sub><b>Valeurs</b></sub></td>
<td width="33%" valign="top"><img src="../docs/assets/screens/connexion.jpg" alt="Connexion"><br><sub><b>Connexion</b></sub></td>
</tr>
<tr>
<td width="33%" valign="top"><img src="../docs/assets/screens/ollama-config.jpg" alt="Configuration du moteur IA"><br><sub><b>Configuration du moteur IA</b></sub></td>
</tr>
</table>

</details>

## Utiliser

| Document | Contenu |
|---|---|
| [Manuel d'utilisation](./manuel-utilisateur.md) | Chaque écran, pas à pas, avec captures : demandes, devis, catalogues, clients, relances, membres, paramètres, offre |
| [Tarification](./tarification-2026-09.md) | Offres, quotas, règles multi-entreprises |
| [Contact et messagerie](./contact-blueseatra.md) | Adresse publique `contact@blueseatra.com`, motifs, boîtes Hostinger, DNS (SPF, DKIM, DMARC) |
| [Blueseatra_Documentation_FR.pdf](./Blueseatra_Documentation_FR.pdf) · [EN](./Blueseatra_Documentation_EN.pdf) | Présentation générale (PDF) |

## Comprendre

| Document | Contenu |
|---|---|
| [Architecture](./architecture.md) | Vue générale, parcours d'une demande, modules, modèle de données |
| [Infrastructure et parcours complet](./infrastructure.md) · [EN](./infrastructure.en.md) | Les dix phases d'un devis (qui agit, qui réagit), vues Supabase et Render, points d'attention |
| [Schéma de base de données](./schema-base-donnees.md) | Tables et colonnes du chiffrage et des devis, état au 01/10/2026 |
| [ADR : moteur IA sur OVH](./decisions/ADR-OVH-AI-STACK.md) | Pourquoi un moteur IA auto-hébergé |
| [ADR : cascade OCR](./decisions/ADR-OCR-CASCADE.md) | Choix et ordre des modèles de lecture |
| [ADR : file d'extraction séquentielle](./decisions/ADR-FILE-EXTRACTION-SEQUENTIELLE.md) | Une lecture à la fois, positions en file |
| [Spécification du module Clients](./specs/module-clients.md) | Tables, écrans, règles de relance, critères d'acceptation |
| [Cartographie](./Cartographie-Blueseatra-v2.pdf) · [Rapport d'architecture](./Blueseatra_Rapport_Jury_Architecture.pdf) | Documents de synthèse (PDF) |

## Développer

| Document | Contenu |
|---|---|
| [Guide développeur](./guide-developpeur.md) | Installation locale, variables, migrations, tests, dépannage |
| [Référence API](./reference-api.md) | Les 110 routes, générées depuis le code |
| [Contrat d'API fournisseurs](./contrat-api-fournisseurs.md) | Recherche et comparaison fournisseurs |
| [Intégration du module Fournisseur](./integration-module-fournisseur.md) | Lien avec le dépôt Fournisseur-Blueseatra |
| [Connecteur MCP](./MCP-PERPLEXITY.md) | Pont MCP vers Perplexity Computer |
| [Contribuer](../CONTRIBUTING.md) | Branches, commits, relecture |

## Exploiter

| Document | Contenu |
|---|---|
| [Exploitation](./exploitation.md) | Mise en production, supervision, quotas, retour arrière, sécurité |
| [DEPLOIEMENT.md](../DEPLOIEMENT.md) | Guide complet Vercel, Render, Supabase et VPS OVH |
| [Runbook DATABASE_URL_APP](./runbook-render-database-url-app.md) | Passage au rôle non propriétaire sur Render |
| [Checklist des secrets Render](../render-secrets-checklist.md) | Variables à renseigner à la main |
| [Audit d'isolation](./audit-isolation-tenants-2026-09-12.md) | Audit RLS du 12/09/2026 |
| [Runbook incident](./runbook-incident.md) | SLO, corrélation par `request_id`, déroulé, RACI, post-mortem |
| [Vocabulaire Rexel — passe de nuit](./vocabulaire-rexel-passe-nuit.md) | Remplissage par tranches des gros catalogues (747 771 offres) : procédure, seuils, constats `pg_stat_activity` |
| [Conformité RGPD](./conformite-rgpd.md) | Registre des traitements, droits des personnes, sous-traitants |
| [Masquage RGPD, OpenCode Free et G3](./rgpd-masquage-ia-externe.md) | Ce qui est masqué avant chaque appel IA, mesures sur données réelles, limites, OpenCode Free, chaîne G3, état en production |
| [SECURITY.md](../SECURITY.md) | Politique de sécurité et signalement |

## Historique

| Document | Contenu |
|---|---|
| [CHANGELOG](../CHANGELOG.md) | Changements PR par PR |
| [Mesures du rapprochement fournisseurs](./lot0-mesures-rapprochement-fournisseurs.md) | Mesures sur données réelles |
| [HANDOFF](../HANDOFF.md) · [Journal des actions](../JOURNAL-ACTIONS.md) | Optimisation de l'IA locale |
| [Guide d'import n8n](./Guide-import-n8n-P1.pdf) | Automatisations n8n (PDF) |
| [Skills de devis](./skills/devis-options-master/SKILL.md) · [Master prompt](./Skill_MASTER_agent_wWthone.md) · [Profil organisation](./Skill_PROFIL_organisation_wWthone.md) | Consignes des agents de chiffrage |

## Licence

Toute cette documentation, ses schémas et ses captures sont couverts par la licence propriétaire du dépôt : [LICENSE](../LICENSE). Titulaire : Zehair Louzza, exploitant le nom commercial « Blueseatra ».
