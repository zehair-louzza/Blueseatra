-- Facturation Stripe (ticket #90) — additive, rejouable.
--
-- stripe_evenements : un événement Stripe reçu = une ligne, clé = identifiant
--   Stripe (evt_…). Un webhook rejoué ne peut donc produire qu'un seul effet.
-- stripe_abonnements : lien entreprise ↔ client et abonnement Stripe.
-- Aucune suppression : un impayé suspend l'espace, il ne purge rien.

CREATE TABLE IF NOT EXISTS blueseatra.stripe_evenements (
    id           varchar PRIMARY KEY,                -- evt_… (unicité = idempotence)
    type         varchar NOT NULL,
    tenant_id    varchar,
    mode_test    boolean NOT NULL,
    statut       varchar NOT NULL DEFAULT 'recu' CHECK (statut IN ('recu', 'traite', 'ignore', 'erreur')),
    detail       text,
    charge       jsonb NOT NULL,
    recu_le      timestamptz NOT NULL DEFAULT now(),
    traite_le    timestamptz
);
CREATE INDEX IF NOT EXISTS stripe_evenements_tenant ON blueseatra.stripe_evenements (tenant_id, recu_le DESC);

CREATE TABLE IF NOT EXISTS blueseatra.stripe_abonnements (
    tenant_id          varchar PRIMARY KEY,
    customer_id        varchar UNIQUE,
    subscription_id    varchar UNIQUE,
    price_id           varchar,
    offre_code         varchar REFERENCES blueseatra.offres(code),
    periodicite        varchar CHECK (periodicite IS NULL OR periodicite IN ('mensuel', 'annuel')),
    statut_stripe      varchar,
    periode_fin        timestamptz,
    annulation_fin_periode boolean NOT NULL DEFAULT false,
    mode_test          boolean NOT NULL DEFAULT true,
    maj_le             timestamptz NOT NULL DEFAULT now()
);

-- Le webhook arrive sans utilisateur : il écrit via le moteur système. Les
-- lectures de l'application restent cloisonnées par entreprise.
ALTER TABLE blueseatra.stripe_evenements ENABLE ROW LEVEL SECURITY;
ALTER TABLE blueseatra.stripe_abonnements ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS stripe_evenements_tenant ON blueseatra.stripe_evenements;
CREATE POLICY stripe_evenements_tenant ON blueseatra.stripe_evenements FOR SELECT TO authenticated, blueseatra_app
    USING ((tenant_id)::text = blueseatra.current_tenant());
DROP POLICY IF EXISTS stripe_abonnements_tenant ON blueseatra.stripe_abonnements;
CREATE POLICY stripe_abonnements_tenant ON blueseatra.stripe_abonnements FOR SELECT TO authenticated, blueseatra_app
    USING ((tenant_id)::text = blueseatra.current_tenant());
GRANT SELECT ON blueseatra.stripe_evenements, blueseatra.stripe_abonnements TO blueseatra_app;
