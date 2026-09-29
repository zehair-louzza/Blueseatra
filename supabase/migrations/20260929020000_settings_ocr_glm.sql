-- GLM-OCR remplace PaddleOCR-VL comme modèle OCR par défaut (29/09/2026).
-- Additive et rejouable : change la valeur par défaut et convertit l'ancienne
-- préférence « paddleocr » (retirée de la cascade) en « glm-ocr ».
ALTER TABLE blueseatra.settings_integrations ALTER COLUMN ocr_model_preference SET DEFAULT 'glm-ocr';
UPDATE blueseatra.settings_integrations SET ocr_model_preference = 'glm-ocr' WHERE ocr_model_preference = 'paddleocr';
