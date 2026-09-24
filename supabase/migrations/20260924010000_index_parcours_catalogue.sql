-- Parcours d'un catalogue fournisseur page par page, trie par designation
-- (backend/catalogue_navigation.py). Sans cet index, afficher la page 1 de
-- Rexel (747 771 offres) trie toute la version a chaque requete.
-- Index seul : aucune donnee modifiee. En production, cree avec
-- CREATE INDEX CONCURRENTLY (hors transaction) pour ne pas bloquer les ecritures.
CREATE INDEX IF NOT EXISTS idx_offers_tenant_version_label
    ON blueseatra.supplier_offers (tenant_id, version_id, raw_label, id);

-- Filtre par famille (raw_row->>'famille') + tri par designation, et
-- liste des familles d'une version. Mesure sans index : 20 s pour la
-- page 1 de Rexel (tri de 747 771 lignes).
CREATE INDEX IF NOT EXISTS idx_offers_tenant_version_famille
    ON blueseatra.supplier_offers (tenant_id, version_id, (raw_row->>'famille'), raw_label, id);
