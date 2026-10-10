-- =====================================================================
-- Envoi des relances par e-mail depuis la boîte de l'entreprise (SMTP)
-- =====================================================================
--
-- Demande du 10/10/2026 : envoi par clic après relecture, et envoi
-- automatique à l'échéance, au choix de l'entreprise. Le texte et l'objet
-- de chaque relance restent modifiables tant qu'elle n'est pas partie.
--
--   - messagerie_smtp : une boîte d'envoi par entreprise. Mot de passe
--     chiffré par l'API (Fernet, préfixe enc::), jamais renvoyé au site.
--   - relances : objet modifiable et suivi de l'envoi (état, date, auteur,
--     Message-ID, erreur lisible, tentatives).
--   - regles_relance : envoi automatique (désactivé par défaut) et date
--     d'activation ; seules les relances dont l'échéance tombe après cette
--     date partent seules, les retards plus anciens restent manuels.
--
-- Additive et idempotente : aucune donnée existante n'est modifiée.
-- =====================================================================

CREATE TABLE IF NOT EXISTS blueseatra.messagerie_smtp (
    tenant_id          varchar(36) PRIMARY KEY,
    hote               varchar(253) NOT NULL,
    port               integer      NOT NULL CHECK (port IN (465, 587)),
    identifiant        varchar(255) NOT NULL,
    mot_de_passe       text         NOT NULL CHECK (mot_de_passe LIKE 'enc::%'),
    expediteur_email   varchar(255) NOT NULL,
    expediteur_nom     varchar(120) NOT NULL DEFAULT '',
    signature          text         NOT NULL DEFAULT '',
    copie_cachee       boolean      NOT NULL DEFAULT true,
    actif              boolean      NOT NULL DEFAULT false,
    verifie_le         timestamptz,
    derniere_erreur    varchar(500),
    maj_par            varchar(255),
    maj_le             timestamptz  NOT NULL DEFAULT now()
);

ALTER TABLE blueseatra.relances
    ADD COLUMN IF NOT EXISTS objet             varchar(200),
    ADD COLUMN IF NOT EXISTS envoi_statut      varchar(10)
        CHECK (envoi_statut IS NULL OR envoi_statut IN ('envoi', 'envoye', 'echec')),
    ADD COLUMN IF NOT EXISTS envoi_tente_le    timestamptz,
    ADD COLUMN IF NOT EXISTS envoye_le         timestamptz,
    ADD COLUMN IF NOT EXISTS envoye_par        varchar(255),
    ADD COLUMN IF NOT EXISTS envoi_destinataire varchar(255),
    ADD COLUMN IF NOT EXISTS envoi_message_id  varchar(255),
    ADD COLUMN IF NOT EXISTS envoi_erreur      varchar(500),
    ADD COLUMN IF NOT EXISTS envoi_tentatives  integer NOT NULL DEFAULT 0;

ALTER TABLE blueseatra.regles_relance
    ADD COLUMN IF NOT EXISTS envoi_auto        boolean NOT NULL DEFAULT false,
    ADD COLUMN IF NOT EXISTS envoi_auto_depuis timestamptz;

-- Relances à envoyer seules : balayage de la tâche de fond.
CREATE INDEX IF NOT EXISTS relances_envoi_auto_idx
    ON blueseatra.relances (echeance)
    WHERE canal = 'email' AND statut IN ('prevue', 'reportee');

ALTER TABLE blueseatra.messagerie_smtp ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS messagerie_smtp_tenant ON blueseatra.messagerie_smtp;
CREATE POLICY messagerie_smtp_tenant ON blueseatra.messagerie_smtp
    FOR ALL TO authenticated, blueseatra_app
    USING ((tenant_id)::text = blueseatra.current_tenant())
    WITH CHECK ((tenant_id)::text = blueseatra.current_tenant());

GRANT SELECT, INSERT, UPDATE ON blueseatra.messagerie_smtp TO blueseatra_app;

-- Retour arrière (aucune donnée existante touchée) :
--   DROP TABLE blueseatra.messagerie_smtp;
--   DROP INDEX blueseatra.relances_envoi_auto_idx;
--   ALTER TABLE blueseatra.relances DROP COLUMN objet, DROP COLUMN envoi_statut, DROP COLUMN envoi_tente_le,
--     DROP COLUMN envoye_le, DROP COLUMN envoye_par, DROP COLUMN envoi_destinataire,
--     DROP COLUMN envoi_message_id, DROP COLUMN envoi_erreur, DROP COLUMN envoi_tentatives;
--   ALTER TABLE blueseatra.regles_relance DROP COLUMN envoi_auto, DROP COLUMN envoi_auto_depuis;
