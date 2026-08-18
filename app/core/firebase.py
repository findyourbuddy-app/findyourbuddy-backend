import json
import logging
from functools import lru_cache

from app.config import get_settings

logger = logging.getLogger(__name__)


@lru_cache
def get_firestore_client():
    """Lazily initializes the Firebase Admin app and returns a Firestore
    client. Returns None if no service account is configured, so callers
    degrade gracefully (message still lands in Postgres, just not relayed
    to Firestore for real-time delivery)."""
    settings = get_settings()
    if not settings.firebase_service_account_json:
        logger.warning("FIREBASE_SERVICE_ACCOUNT_JSON not set -- Firestore relay disabled.")
        return None

    import firebase_admin
    from firebase_admin import credentials, firestore

    if not firebase_admin._apps:
        cred = credentials.Certificate(json.loads(settings.firebase_service_account_json))
        firebase_admin.initialize_app(cred)

    return firestore.client()
