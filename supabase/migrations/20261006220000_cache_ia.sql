-- =====================================================================
-- Cache des extractions IA par empreinte du contenu (diagnostic du 06/10/2026)
-- =====================================================================
--
-- Stocke uniquement le résultat structuré d'une extraction (JSON), jamais le
-- fichier. La clé (cle) est un SHA-256 qui mélange l'empreinte de la
-- configuration (modèle, consigne, schéma, code d'extraction) et le contenu :
-- un changement de modèle ou de consigne produit une autre clé.
--
--   - Par entreprise : clé primaire (tenant_id, cle) + RLS sur current_tenant().
--   - Conservation de 30 jours : l'API ignore les entrées plus anciennes et les
--     supprime à chaque écriture de l'entreprise.
--   - Contient des données personnelles extraites : vidé par l'anonymisation RGPD.
--   - Sans effet sur la facturation : les quotas se réservent avant, comme toujours.
--
-- Additive et idempotente : aucune table existante n'est modifiée. Tant qu'elle
-- n'est pas appliquée, l'API ignore silencieusement le cache.
-- =====================================================================

CREATE TABLE IF NOT EXISTS blueseatra.cache_ia (
    tenant_id      varchar     NOT NULL,
    cle            char(64)    NOT NULL,
    source         varchar(20) NOT NULL,          -- texte | image | pdf_ocr
    resultat       jsonb       NOT NULL,
    cree_le        timestamptz NOT NULL DEFAULT now(),
    dernier_acces  timestamptz NOT NULL DEFAULT now(),
    reutilisations integer     NOT NULL DEFAULT 0,
    PRIMARY KEY (tenant_id, cle)
);

CREATE INDEX IF NOT EXISTS cache_ia_tenant_cree_idx
    ON blueseatra.cache_ia (tenant_id, cree_le);

ALTER TABLE blueseatra.cache_ia ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS cache_ia_tenant ON blueseatra.cache_ia;
CREATE POLICY cache_ia_tenant ON blueseatra.cache_ia
    TO blueseatra_app
    USING ((tenant_id)::text = blueseatra.current_tenant())
    WITH CHECK ((tenant_id)::text = blueseatra.current_tenant());

GRANT SELECT, INSERT, UPDATE, DELETE ON blueseatra.cache_ia TO blueseatra_app;
