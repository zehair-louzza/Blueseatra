import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';

const resources = {
  en: {
    translation: {
      brand_tag: 'From unstructured requests to validated quotes',
      nav: { features: 'Features', how: 'How it works', plans: 'Plans', login: 'Log in', signup: 'Get started' },
      landing: {
        hero_title: 'Turn any request into a precise quote',
        hero_sub: 'Blueseatra reads emails, PDFs, photos and forms in any language, structures the need, matches it to YOUR pricing catalog, and prepares a quote you simply validate.',
        cta_primary: 'Start free', cta_secondary: 'See how it works',
        steps_title: 'Upload \u2192 Extract \u2192 Match \u2192 Validate \u2192 Quote',
        f1_t: 'Multilingual extraction', f1_d: 'Documents in any language are read and structured automatically by AI.',
        f2_t: 'Your catalog, your prices', f2_d: 'Import pricing via CSV. AI never invents prices \u2014 every line is traceable to your catalog version.',
        f3_t: 'Explainable matching', f3_d: 'Each quote line shows a match score and reason so you stay in control.',
        f4_t: 'Multi-tenant & auditable', f4_d: 'Strict workspace isolation, roles, and a full audit trail for every action.',
        plans_title: 'Simple plans',
        plan_starter: 'Starter', plan_pro: 'Professional', plan_ent: 'Enterprise',
        plan_cta: 'Choose plan', plan_soon: 'Billing coming soon',
      },
      auth: {
        login_title: 'Welcome back', signup_title: 'Create your workspace',
        email: 'Email', password: 'Password', name: 'Full name', company: 'Company / Workspace',
        login_btn: 'Log in', signup_btn: 'Create workspace',
        no_account: "No account?", have_account: 'Already have an account?',
        login_link: 'Log in', signup_link: 'Sign up',
      },
      nav2: { dashboard: 'Dashboard', requests: 'Requests', catalogs: 'Catalogs', quotes: 'Quotes', members: 'Members', audit: 'Audit log', settings: 'Settings', billing: 'Billing', logout: 'Log out' },
      dash: { title: 'Dashboard', requests: 'Requests', drafts: 'Draft quotes', validated: 'Validated quotes', catalog_items: 'Active catalog items', recent_requests: 'Recent requests', recent_quotes: 'Recent quotes', empty: 'Nothing here yet', active_catalog: 'Active catalog' },
      req: { title: 'Requests', new: 'New request', upload_title: 'Create a request', name_field: 'Title', paste_text: 'Paste text', or_upload: 'or upload a document', file_hint: 'PDF, DOCX, PNG, JPG', submit: 'Create & process', processing: 'Processing with AI\u2026', detail: 'Request detail', extracted: 'Extracted data', raw: 'Source content', line_items: 'Line items', reprocess: 'Reprocess', make_quote: 'Generate quote', lang: 'Language', confidence: 'Confidence', client: 'Client', site: 'Site', urgency: 'Urgency', doc_type: 'Document type', request_no: 'Request N\u00b0', di: 'DI file N\u00b0', deadline: 'Reply by', donneur: 'Ordering party', client_final: 'End client', deliverables: 'Required in quote', location: 'Location', dimensions: 'Dimensions', specs: 'Specs', no_requests: 'No requests yet. Create your first one.' },
      cat: { title: 'Catalogs', import: 'Import CSV', items: 'items', version: 'Version', active: 'Active', download_tpl: 'Download template', no_catalogs: 'No catalogs yet', view_items: 'View items', activate: 'Activate', archived: 'Archived', draft: 'Draft' },
      wiz: { title: 'Import pricing catalog', step_upload: 'Upload', step_preview: 'Preview', step_validate: 'Validate', step_done: 'Done', choose_file: 'Choose CSV file', catalog_name: 'Catalog name', next: 'Next', back: 'Back', import_btn: 'Import & activate', total_rows: 'Total rows', missing: 'Missing required columns', success_rows: 'Imported', error_rows: 'Errors', view_errors: 'View errors', done_msg: 'Catalog imported and activated', go_catalogs: 'Go to catalogs' },
      quote: { title: 'Quotes', editor: 'Quote editor', number: 'Number', status: 'Status', client: 'Client', site: 'Site', object: 'Object / reference', add_line: 'Add line', add_from_catalog: 'Add from catalog', pick_item: 'Search a catalog item\u2026', remove: 'Remove', move_up: 'Move up', move_down: 'Move down', no_lines: 'No lines yet. Add a line or pick one from your catalog.', catalog_empty: 'No active catalog. Import one to pick items.', vat_rate: 'VAT rate', lines_count: 'lines', add_labor: 'Labor', add_material: 'Material', add_note: 'Note', add_page_break: 'Page break', margin: 'Margin', margin_hint: 'Visible here only \u2014 hidden on the final quote', note_ph: 'Note text\u2026', page_break_label: 'Page break', family: 'Family', article: 'Article', supplier: 'Supplier', all_families: 'All families', total_ht: 'Total excl. tax', total_vat: 'VAT', total_ttc: 'Total incl. tax', save: 'Save', validate: 'Validate', send: 'Mark as sent', pdf: 'Download PDF', desc: 'Description', qty: 'Qty', unit: 'Unit', unit_price: 'Unit price', vat: 'VAT %', line_total: 'Total', match: 'Match', source: 'Pricing source', no_quotes: 'No quotes yet. Generate one from a request.', pricing_note: 'Prices come from the catalog snapshot. AI does not set prices.' },
      members: { title: 'Members', invite: 'Add member', email: 'Email', name: 'Name', role: 'Role', password: 'Temp password', add: 'Add', no_members: 'No members' },
      audit: { title: 'Audit log', actor: 'Actor', action: 'Action', when: 'When', no_logs: 'No activity yet' },
      settings: { title: 'Integrations', tab_ai: 'AI engine', tab_company: 'Company & quote PDF', ai_provider: 'AI provider', ai_model: 'Model', ai_key: 'API key (optional)', ai_key_hint: 'Leave blank to use the built-in engine. Add your own key anytime.', key_set: 'A key is configured', n8n: 'n8n webhook URL', n8n_hint: 'Point to your n8n / ZimaBoard orchestration endpoint.', save: 'Save settings', saved: 'Settings saved', company: { intro: 'These details appear on the header and footer of generated quote / pro forma PDFs.', name: 'Company name', subtitle: 'Subtitle / slogan', address1: 'Address line', address2: 'Postal code & city', country: 'Country', phone: 'Phone', email: 'Email', siret: 'SIRET', tva: 'VAT number (TVA intra)', capital: 'Share capital', ape: 'APE / NAF code', assurance: 'Insurance', iban: 'IBAN', validity: 'Quote validity', payment_terms: 'Payment terms (one per line)', acceptance: 'Client acceptance wording', saved: 'Company profile saved' } },
      billing: { title: 'Billing', current_plan: 'Current plan', soon: 'Stripe billing will be available in a later phase.', manage: 'Manage subscription' },
      common: { loading: 'Loading\u2026', cancel: 'Cancel', close: 'Close', search: 'Search', status: 'Status', all: 'All', actions: 'Actions', open: 'Open', back: 'Back' },
      status: { received: 'Received', processing: 'Processing', needs_review: 'Needs review', done: 'Done', failed: 'Failed', draft: 'Draft', validated: 'Validated', sent: 'Sent', matched: 'Matched', proposed: 'Proposed', to_confirm: 'To confirm', confirmed: 'Confirmed' },
    },
  },
  fr: {
    translation: {
      brand_tag: 'Des demandes brutes aux devis valid\u00e9s',
      nav: { features: 'Fonctionnalit\u00e9s', how: 'Comment \u00e7a marche', plans: 'Offres', login: 'Connexion', signup: 'Commencer' },
      landing: {
        hero_title: 'Transformez chaque demande en devis pr\u00e9cis',
        hero_sub: 'Blueseatra lit les emails, PDF, photos et formulaires dans toutes les langues, structure le besoin, le rapproche de VOTRE catalogue tarifaire et pr\u00e9pare un devis que vous validez.',
        cta_primary: 'Commencer gratuitement', cta_secondary: 'Voir le fonctionnement',
        steps_title: 'Importer \u2192 Extraire \u2192 Rapprocher \u2192 Valider \u2192 Devis',
        f1_t: 'Extraction multilingue', f1_d: 'Les documents dans toutes les langues sont lus et structur\u00e9s automatiquement par l\u2019IA.',
        f2_t: 'Votre catalogue, vos prix', f2_d: 'Importez vos tarifs en CSV. L\u2019IA n\u2019invente jamais les prix \u2014 chaque ligne est tra\u00e7able \u00e0 votre version de catalogue.',
        f3_t: 'Rapprochement explicable', f3_d: 'Chaque ligne de devis affiche un score et une raison pour garder le contr\u00f4le.',
        f4_t: 'Multi-tenant & auditable', f4_d: 'Isolation stricte des espaces, r\u00f4les et journal d\u2019audit complet.',
        plans_title: 'Offres simples',
        plan_starter: 'D\u00e9marrage', plan_pro: 'Professionnel', plan_ent: 'Entreprise',
        plan_cta: 'Choisir', plan_soon: 'Facturation bient\u00f4t disponible',
      },
      auth: {
        login_title: 'Bon retour', signup_title: 'Cr\u00e9ez votre espace',
        email: 'Email', password: 'Mot de passe', name: 'Nom complet', company: 'Soci\u00e9t\u00e9 / Espace',
        login_btn: 'Connexion', signup_btn: 'Cr\u00e9er l\u2019espace',
        no_account: 'Pas de compte ?', have_account: 'D\u00e9j\u00e0 un compte ?',
        login_link: 'Connexion', signup_link: 'Inscription',
      },
      nav2: { dashboard: 'Tableau de bord', requests: 'Demandes', catalogs: 'Catalogues', quotes: 'Devis', members: 'Membres', audit: 'Journal d\u2019audit', settings: 'Param\u00e8tres', billing: 'Facturation', logout: 'D\u00e9connexion' },
      dash: { title: 'Tableau de bord', requests: 'Demandes', drafts: 'Brouillons de devis', validated: 'Devis valid\u00e9s', catalog_items: 'Articles du catalogue actif', recent_requests: 'Demandes r\u00e9centes', recent_quotes: 'Devis r\u00e9cents', empty: 'Rien pour le moment', active_catalog: 'Catalogue actif' },
      req: { title: 'Demandes', new: 'Nouvelle demande', upload_title: 'Cr\u00e9er une demande', name_field: 'Titre', paste_text: 'Coller du texte', or_upload: 'ou importer un document', file_hint: 'PDF, DOCX, PNG, JPG', submit: 'Cr\u00e9er & traiter', processing: 'Traitement par IA\u2026', detail: 'D\u00e9tail de la demande', extracted: 'Donn\u00e9es extraites', raw: 'Contenu source', line_items: 'Lignes', reprocess: 'Retraiter', make_quote: 'G\u00e9n\u00e9rer un devis', lang: 'Langue', confidence: 'Confiance', client: 'Client', site: 'Site', urgency: 'Urgence', doc_type: 'Type de document', request_no: 'N\u00b0 demande', di: 'N\u00b0 dossier DI', deadline: 'R\u00e9ponse avant', donneur: 'Donneur d\u2019ordre', client_final: 'Client final', deliverables: 'Exig\u00e9 dans le devis', location: 'Emplacement', dimensions: 'Dimensions', specs: 'Sp\u00e9cifications', no_requests: 'Aucune demande. Cr\u00e9ez la premi\u00e8re.' },
      cat: { title: 'Catalogues', import: 'Importer CSV', items: 'articles', version: 'Version', active: 'Actif', download_tpl: 'T\u00e9l\u00e9charger le mod\u00e8le', no_catalogs: 'Aucun catalogue', view_items: 'Voir les articles', activate: 'Activer', archived: 'Archiv\u00e9', draft: 'Brouillon' },
      wiz: { title: 'Importer un catalogue tarifaire', step_upload: 'Import', step_preview: 'Aper\u00e7u', step_validate: 'Validation', step_done: 'Termin\u00e9', choose_file: 'Choisir un fichier CSV', catalog_name: 'Nom du catalogue', next: 'Suivant', back: 'Retour', import_btn: 'Importer & activer', total_rows: 'Lignes totales', missing: 'Colonnes requises manquantes', success_rows: 'Import\u00e9es', error_rows: 'Erreurs', view_errors: 'Voir les erreurs', done_msg: 'Catalogue import\u00e9 et activ\u00e9', go_catalogs: 'Voir les catalogues' },
      quote: { title: 'Devis', editor: '\u00c9diteur de devis', number: 'Num\u00e9ro', status: 'Statut', client: 'Client', site: 'Site', object: 'Objet / r\u00e9f\u00e9rence', add_line: 'Ajouter une ligne', add_from_catalog: 'Ajouter depuis le catalogue', pick_item: 'Rechercher un article du catalogue\u2026', remove: 'Supprimer', move_up: 'Monter', move_down: 'Descendre', no_lines: 'Aucune ligne. Ajoutez une ligne ou choisissez-en une dans votre catalogue.', catalog_empty: 'Aucun catalogue actif. Importez-en un pour choisir des articles.', vat_rate: 'Taux de TVA', lines_count: 'lignes', add_labor: 'Main-d\u2019\u0153uvre', add_material: 'Mat\u00e9riau', add_note: 'Note', add_page_break: 'Saut de page', margin: 'Marge', margin_hint: 'Visible ici seulement \u2014 masqu\u00e9 sur le devis final', note_ph: 'Texte de la note\u2026', page_break_label: 'Saut de page', family: 'Famille', article: 'Article', supplier: 'Fournisseur', all_families: 'Toutes les familles', total_ht: 'Total HT', total_vat: 'TVA', total_ttc: 'Total TTC', save: 'Enregistrer', validate: 'Valider', send: 'Marquer envoy\u00e9', pdf: 'T\u00e9l\u00e9charger PDF', desc: 'Description', qty: 'Qt\u00e9', unit: 'Unit\u00e9', unit_price: 'Prix unitaire', vat: 'TVA %', line_total: 'Total', match: 'Rapprochement', source: 'Source tarifaire', no_quotes: 'Aucun devis. G\u00e9n\u00e9rez-en un depuis une demande.', pricing_note: 'Les prix proviennent du snapshot du catalogue. L\u2019IA ne fixe pas les prix.' },
      members: { title: 'Membres', invite: 'Ajouter un membre', email: 'Email', name: 'Nom', role: 'R\u00f4le', password: 'Mot de passe temp.', add: 'Ajouter', no_members: 'Aucun membre' },
      audit: { title: 'Journal d\u2019audit', actor: 'Acteur', action: 'Action', when: 'Quand', no_logs: 'Aucune activit\u00e9' },
      settings: { title: 'Int\u00e9grations', tab_ai: 'Moteur IA', tab_company: 'Soci\u00e9t\u00e9 & PDF devis', ai_provider: 'Fournisseur IA', ai_model: 'Mod\u00e8le', ai_key: 'Cl\u00e9 API (optionnelle)', ai_key_hint: 'Laissez vide pour utiliser le moteur int\u00e9gr\u00e9. Ajoutez votre cl\u00e9 quand vous voulez.', key_set: 'Une cl\u00e9 est configur\u00e9e', n8n: 'URL webhook n8n', n8n_hint: 'Pointez vers votre orchestration n8n / ZimaBoard.', save: 'Enregistrer', saved: 'Param\u00e8tres enregistr\u00e9s', company: { intro: 'Ces informations apparaissent dans l\u2019en-t\u00eate et le pied de page des devis / factures pro forma g\u00e9n\u00e9r\u00e9s.', name: 'Nom de la soci\u00e9t\u00e9', subtitle: 'Sous-titre / slogan', address1: 'Adresse', address2: 'Code postal & ville', country: 'Pays', phone: 'T\u00e9l\u00e9phone', email: 'Email', siret: 'SIRET', tva: 'N\u00b0 TVA intracom.', capital: 'Capital social', ape: 'Code APE / NAF', assurance: 'Assurance', iban: 'IBAN', validity: 'Validit\u00e9 du devis', payment_terms: 'Modalit\u00e9s de paiement (une par ligne)', acceptance: 'Mention d\u2019acceptation client', saved: 'Profil soci\u00e9t\u00e9 enregistr\u00e9' } },
      billing: { title: 'Facturation', current_plan: 'Offre actuelle', soon: 'La facturation Stripe sera disponible dans une phase ult\u00e9rieure.', manage: 'G\u00e9rer l\u2019abonnement' },
      common: { loading: 'Chargement\u2026', cancel: 'Annuler', close: 'Fermer', search: 'Rechercher', status: 'Statut', all: 'Tous', actions: 'Actions', open: 'Ouvrir', back: 'Retour' },
      status: { received: 'Re\u00e7u', processing: 'En traitement', needs_review: '\u00c0 revoir', done: 'Termin\u00e9', failed: '\u00c9chec', draft: 'Brouillon', validated: 'Valid\u00e9', sent: 'Envoy\u00e9', matched: 'Rapproch\u00e9', proposed: 'Propos\u00e9', to_confirm: '\u00c0 confirmer', confirmed: 'Confirm\u00e9' },
    },
  },
};

i18n.use(initReactI18next).init({
  resources,
  lng: localStorage.getItem('bs_lang') || 'fr',
  fallbackLng: 'en',
  interpolation: { escapeValue: false },
});

export default i18n;
