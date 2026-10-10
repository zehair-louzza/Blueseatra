-- Etape de lecture en cours, affichee sur la page de la demande (07/10/2026).
-- Contenu : {"etape": 2, "total": 6, "libelle": "GLM-OCR", "debut": "2026-10-07T00:25:54+00:00"}.
-- Remise a NULL a la fin du traitement (reussi ou en echec). Additive et idempotente.
ALTER TABLE blueseatra.requests ADD COLUMN IF NOT EXISTS progression jsonb;
