"""Adresse publique de contact de Blueseatra, citée dans les messages d'erreur de l'API.

Boîte Hostinger du domaine blueseatra.com (voir docs/contact-blueseatra.md).
BLUESEATRA_CONTACT_EMAIL permet de la changer sans modifier le code.
"""
import os

CONTACT_EMAIL = os.environ.get("BLUESEATRA_CONTACT_EMAIL", "").strip() or "contact@blueseatra.com"
