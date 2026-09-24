-- =====================================================================
-- Module Clients : clients, contacts, chantiers, suggestions IA,
-- journal des échanges et relances de devis
-- Spécification : docs/specs/module-clients.md
-- =====================================================================
--
-- STATUT : préparée, NON appliquée en production. À appliquer avec
-- l'accord du propriétaire, après revue de la PR.
--
-- Principes
--   - Additive : nouvelles tables + colonnes NULLables sur requests et
--     quotes. Aucune donnée existante n'est modifiée ni supprimée.
--   - Isolation : RLS sur current_tenant() pour chaque table, et
--     l'application filtre aussi tenant_id explicitement (mode repli).
--   - Jamais de suppression depuis le site : un client, un contact ou un
--     chantier est ARCHIVÉ (archive_le). Seule exception, légale : un
--     contact peut être ANONYMISÉ (droit à l'effacement RGPD), ses données
--     personnelles étant alors remplacées, sans casser l'historique.
--   - L'IA ne remplit jamais une fiche d'elle-même : elle PROPOSE
--     (suggestions_clients) avec la phrase source comme preuve, et un
--     humain valide. Seule une correspondance exacte (SIRET ou e-mail
--     identique) rattache automatiquement une demande à un client existant.
--   - Journal des échanges en ajout seul (comme le registre des quotas).
-- =====================================================================

-- 1. Clients -------------------------------------------------------------
CREATE TABLE IF NOT EXISTS blueseatra.clients (
    id                 varchar(36) PRIMARY KEY,
    tenant_id          varchar(36) NOT NULL,
    type               varchar(20) NOT NULL DEFAULT 'entreprise'
                       CHECK (type IN ('entreprise', 'particulier', 'syndic', 'bailleur',
                                       'collectivite', 'enseigne')),
    raison_sociale     varchar(255) NOT NULL,
    nom_commercial     varchar(255),
    siret              varchar(14)  CHECK (siret IS NULL OR siret ~ '^[0-9]{14}$'),
    tva_intra          varchar(20),
    email              varchar(255),
    telephone          varchar(40),
    adresse            jsonb NOT NULL DEFAULT '{}'::jsonb,   -- {ligne1, ligne2, code_postal, ville, pays}
    site_web           varchar(255),
    langue             varchar(5)  NOT NULL DEFAULT 'fr' CHECK (langue IN ('fr', 'en')),
    delai_paiement_j   integer     CHECK (delai_paiement_j IS NULL OR delai_paiement_j BETWEEN 0 AND 120),
    etiquettes         text[]      NOT NULL DEFAULT '{}',
    notes              text,
    source             varchar(20) NOT NULL DEFAULT 'manuel'
                       CHECK (source IN ('manuel', 'suggestion_ia', 'import', 'devis_existant')),
    recherche_norm     text,       -- nom + ville + SIRET normalisés (sans accents), rempli par l'API
    cree_par           varchar(255),
    cree_le            timestamptz NOT NULL DEFAULT now(),
    maj_le             timestamptz NOT NULL DEFAULT now(),
    archive_le         timestamptz
);
CREATE UNIQUE INDEX IF NOT EXISTS clients_siret_unique
    ON blueseatra.clients (tenant_id, siret) WHERE siret IS NOT NULL AND archive_le IS NULL;
CREATE INDEX IF NOT EXISTS clients_tenant_actifs
    ON blueseatra.clients (tenant_id, raison_sociale) WHERE archive_le IS NULL;
CREATE INDEX IF NOT EXISTS clients_tenant_email
    ON blueseatra.clients (tenant_id, lower(email)) WHERE email IS NOT NULL;

-- 2. Contacts ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS blueseatra.contacts (
    id                 varchar(36) PRIMARY KEY,
    tenant_id          varchar(36) NOT NULL,
    client_id          varchar(36) NOT NULL REFERENCES blueseatra.clients(id),
    civilite           varchar(10),
    prenom             varchar(120),
    nom                varchar(120),
    fonction           varchar(160),
    email              varchar(255),
    telephone          varchar(40),
    mobile             varchar(40),
    langue             varchar(5)  NOT NULL DEFAULT 'fr' CHECK (langue IN ('fr', 'en')),
    principal          boolean     NOT NULL DEFAULT false,
    accepte_relances   boolean     NOT NULL DEFAULT true,     -- opposition RGPD aux relances
    cree_le            timestamptz NOT NULL DEFAULT now(),
    maj_le             timestamptz NOT NULL DEFAULT now(),
    archive_le         timestamptz,
    anonymise_le       timestamptz
);
CREATE INDEX IF NOT EXISTS contacts_tenant_client ON blueseatra.contacts (tenant_id, client_id);
CREATE INDEX IF NOT EXISTS contacts_tenant_email
    ON blueseatra.contacts (tenant_id, lower(email)) WHERE email IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS contacts_un_principal
    ON blueseatra.contacts (tenant_id, client_id) WHERE principal AND archive_le IS NULL;

-- 3. Chantiers (sites d'intervention) ------------------------------------
CREATE TABLE IF NOT EXISTS blueseatra.chantiers (
    id                 varchar(36) PRIMARY KEY,
    tenant_id          varchar(36) NOT NULL,
    client_id          varchar(36) NOT NULL REFERENCES blueseatra.clients(id),
    nom                varchar(255) NOT NULL,
    code_site          varchar(60),              -- n° de magasin, de lot, de résidence…
    adresse            jsonb NOT NULL DEFAULT '{}'::jsonb,
    acces              text,                     -- consignes d'accès, horaires
    cree_le            timestamptz NOT NULL DEFAULT now(),
    maj_le             timestamptz NOT NULL DEFAULT now(),
    archive_le         timestamptz
);
CREATE INDEX IF NOT EXISTS chantiers_tenant_client ON blueseatra.chantiers (tenant_id, client_id);

-- 4. Liens avec les demandes et les devis (colonnes NULLables) ----------
--    donneur d'ordre = client_id (destinataire du devis et de la facture)
--    client final    = client_final_id (enseigne du site), facultatif
ALTER TABLE blueseatra.requests ADD COLUMN IF NOT EXISTS client_id       varchar(36);
ALTER TABLE blueseatra.requests ADD COLUMN IF NOT EXISTS client_final_id varchar(36);
ALTER TABLE blueseatra.requests ADD COLUMN IF NOT EXISTS chantier_id     varchar(36);
ALTER TABLE blueseatra.requests ADD COLUMN IF NOT EXISTS contact_id      varchar(36);
ALTER TABLE blueseatra.quotes   ADD COLUMN IF NOT EXISTS client_id       varchar(36);
ALTER TABLE blueseatra.quotes   ADD COLUMN IF NOT EXISTS client_final_id varchar(36);
ALTER TABLE blueseatra.quotes   ADD COLUMN IF NOT EXISTS chantier_id     varchar(36);
ALTER TABLE blueseatra.quotes   ADD COLUMN IF NOT EXISTS contact_id      varchar(36);
-- Suivi commercial, distinct du statut technique (draft/validated/sent)
ALTER TABLE blueseatra.quotes   ADD COLUMN IF NOT EXISTS issue           varchar(20);
ALTER TABLE blueseatra.quotes   ADD COLUMN IF NOT EXISTS issue_le        timestamptz;
ALTER TABLE blueseatra.quotes   ADD COLUMN IF NOT EXISTS motif_issue     varchar(255);
ALTER TABLE blueseatra.quotes   ADD COLUMN IF NOT EXISTS valable_jusqu_au date;
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'quotes_issue_valide') THEN
        ALTER TABLE blueseatra.quotes ADD CONSTRAINT quotes_issue_valide
            CHECK (issue IS NULL OR issue IN ('en_attente', 'accepte', 'refuse', 'sans_suite'));
    END IF;
END $$;
CREATE INDEX IF NOT EXISTS quotes_tenant_client  ON blueseatra.quotes   (tenant_id, client_id)  WHERE client_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS requests_tenant_client ON blueseatra.requests (tenant_id, client_id) WHERE client_id IS NOT NULL;

-- 5. Suggestions de l'IA, à valider par un humain ------------------------
CREATE TABLE IF NOT EXISTS blueseatra.suggestions_clients (
    id                 varchar(36) PRIMARY KEY,
    tenant_id          varchar(36) NOT NULL,
    demande_id         varchar(36),
    devis_id           varchar(36),
    type               varchar(30) NOT NULL
                       CHECK (type IN ('nouveau_client', 'nouveau_contact', 'nouveau_chantier',
                                       'rattachement', 'mise_a_jour')),
    cible_id           varchar(36),              -- client / contact / chantier concerné
    role               varchar(20) CHECK (role IS NULL OR role IN ('donneur_ordre', 'client_final')),
    valeurs            jsonb NOT NULL,           -- champs proposés
    preuve             text NOT NULL,            -- phrase source recopiée du document
    force              varchar(10) NOT NULL CHECK (force IN ('exacte', 'probable', 'faible')),
    statut             varchar(12) NOT NULL DEFAULT 'a_valider'
                       CHECK (statut IN ('a_valider', 'acceptee', 'rejetee', 'remplacee')),
    traite_par         varchar(255),
    traite_le          timestamptz,
    cree_le            timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS suggestions_tenant_ouvertes
    ON blueseatra.suggestions_clients (tenant_id, cree_le DESC) WHERE statut = 'a_valider';

-- 6. Journal des échanges (ajout seul) -----------------------------------
CREATE TABLE IF NOT EXISTS blueseatra.echanges_clients (
    id                 bigserial PRIMARY KEY,
    tenant_id          varchar(36) NOT NULL,
    client_id          varchar(36) NOT NULL,
    contact_id         varchar(36),
    devis_id           varchar(36),
    chantier_id        varchar(36),
    relance_id         varchar(36),
    type               varchar(20) NOT NULL
                       CHECK (type IN ('appel', 'email', 'visite', 'note', 'relance',
                                       'devis_envoye', 'devis_accepte', 'devis_refuse', 'correction')),
    resume             text NOT NULL,
    corrige_id         bigint REFERENCES blueseatra.echanges_clients(id),
    auteur             varchar(255),
    survenu_le         timestamptz NOT NULL DEFAULT now(),
    cree_le            timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE INDEX IF NOT EXISTS echanges_tenant_client
    ON blueseatra.echanges_clients (tenant_id, client_id, survenu_le DESC);

CREATE OR REPLACE FUNCTION blueseatra.echanges_ajout_seul() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'echanges_clients est en ajout seul : % refusé. Ajouter une ligne de correction.', TG_OP
        USING ERRCODE = 'insufficient_privilege';
END $$;
DROP TRIGGER IF EXISTS echanges_ajout_seul ON blueseatra.echanges_clients;
CREATE TRIGGER echanges_ajout_seul BEFORE UPDATE OR DELETE ON blueseatra.echanges_clients
    FOR EACH ROW EXECUTE FUNCTION blueseatra.echanges_ajout_seul();

-- 7. Règles de relance (une ligne par entreprise) -------------------------
CREATE TABLE IF NOT EXISTS blueseatra.regles_relance (
    tenant_id              varchar(36) PRIMARY KEY,
    actif                  boolean  NOT NULL DEFAULT true,
    delais_jours_ouvres    integer[] NOT NULL DEFAULT '{3,7,14}',   -- après l'envoi, puis entre relances
    delais_urgent          integer[] NOT NULL DEFAULT '{1,2,4}',
    max_relances           integer  NOT NULL DEFAULT 3 CHECK (max_relances BETWEEN 0 AND 6),
    validite_devis_jours   integer  NOT NULL DEFAULT 30 CHECK (validite_devis_jours BETWEEN 7 AND 180),
    rappel_avant_expiration_j integer NOT NULL DEFAULT 3,
    seuil_appel_ht         numeric(12, 2) NOT NULL DEFAULT 10000,  -- au-delà : relance par appel
    heure_relance          time     NOT NULL DEFAULT '09:00',
    fuseau                 varchar(40) NOT NULL DEFAULT 'Europe/Paris',
    maj_par                varchar(255),
    maj_le                 timestamptz NOT NULL DEFAULT now()
);

-- 8. Relances --------------------------------------------------------------
CREATE TABLE IF NOT EXISTS blueseatra.relances (
    id                 varchar(36) PRIMARY KEY,
    tenant_id          varchar(36) NOT NULL,
    devis_id           varchar(36) NOT NULL,
    client_id          varchar(36),
    contact_id         varchar(36),
    rang               integer NOT NULL CHECK (rang BETWEEN 1 AND 7),  -- 7 = rappel d'expiration
    echeance           timestamptz NOT NULL,
    canal              varchar(12) NOT NULL CHECK (canal IN ('email', 'appel', 'tache')),
    raison             text NOT NULL,            -- toujours affichée à l'utilisateur
    brouillon          text,                     -- texte proposé, jamais envoyé seul
    statut             varchar(12) NOT NULL DEFAULT 'prevue'
                       CHECK (statut IN ('prevue', 'faite', 'reportee', 'annulee')),
    resultat           varchar(20) CHECK (resultat IS NULL OR resultat IN
                                          ('sans_reponse', 'a_rappeler', 'accepte', 'refuse', 'en_reflexion')),
    motif_annulation   varchar(255),
    creee_par          varchar(255) NOT NULL DEFAULT 'regle',
    faite_par          varchar(255),
    faite_le           timestamptz,
    cree_le            timestamptz NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS relances_une_par_rang
    ON blueseatra.relances (tenant_id, devis_id, rang) WHERE statut <> 'annulee';
CREATE INDEX IF NOT EXISTS relances_a_faire
    ON blueseatra.relances (tenant_id, echeance) WHERE statut IN ('prevue', 'reportee');

-- 9. Isolation (RLS) et droits ---------------------------------------------
DO $$
DECLARE t text;
BEGIN
    FOREACH t IN ARRAY ARRAY['clients', 'contacts', 'chantiers', 'suggestions_clients',
                             'echanges_clients', 'regles_relance', 'relances'] LOOP
        EXECUTE format('ALTER TABLE blueseatra.%I ENABLE ROW LEVEL SECURITY', t);
        EXECUTE format('DROP POLICY IF EXISTS %I ON blueseatra.%I', t || '_tenant', t);
        EXECUTE format($p$CREATE POLICY %I ON blueseatra.%I FOR ALL TO authenticated, blueseatra_app
                          USING ((tenant_id)::text = blueseatra.current_tenant())
                          WITH CHECK ((tenant_id)::text = blueseatra.current_tenant())$p$, t || '_tenant', t);
    END LOOP;
END $$;
-- Jamais de DELETE depuis l'application : archivage / anonymisation seulement.
GRANT SELECT, INSERT, UPDATE ON blueseatra.clients, blueseatra.contacts, blueseatra.chantiers,
      blueseatra.suggestions_clients, blueseatra.regles_relance, blueseatra.relances TO blueseatra_app;
GRANT SELECT, INSERT ON blueseatra.echanges_clients TO blueseatra_app;
GRANT USAGE ON SEQUENCE blueseatra.echanges_clients_id_seq TO blueseatra_app;

-- Retour arrière (aucune donnée existante touchée) :
--   DROP TABLE blueseatra.relances, blueseatra.regles_relance, blueseatra.echanges_clients,
--              blueseatra.suggestions_clients, blueseatra.chantiers, blueseatra.contacts, blueseatra.clients;
--   ALTER TABLE blueseatra.quotes / requests DROP COLUMN client_id, client_final_id, chantier_id,
--              contact_id [, issue, issue_le, motif_issue, valable_jusqu_au];
