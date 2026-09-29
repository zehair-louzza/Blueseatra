-- Le choix « Modèle OCR préféré » de la page Paramètres n'était jamais
-- enregistré : la colonne n'existait pas et l'adaptateur ignore les champs
-- inconnus. Additive, rejouable. Défaut : PaddleOCR-VL, local sur le VPS.
ALTER TABLE blueseatra.settings_integrations
    ADD COLUMN IF NOT EXISTS ocr_model_preference varchar(40) NOT NULL DEFAULT 'paddleocr';
