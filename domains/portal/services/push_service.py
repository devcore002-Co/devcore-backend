import json
import logging
import os
from typing import Any, Dict, Optional
from config import get_settings

logger = logging.getLogger("devcore-portal")

_firebase_initialized = False


def _init_firebase():
    global _firebase_initialized
    if _firebase_initialized:
        return
    s = get_settings()
    try:
        import firebase_admin
        from firebase_admin import credentials
        if not firebase_admin._apps:
            if s.firebase_credentials_json:
                cred = credentials.Certificate(json.loads(s.firebase_credentials_json))
            elif os.path.exists(s.firebase_credentials_path):
                cred = credentials.Certificate(s.firebase_credentials_path)
            else:
                logger.warning("Firebase credentials not found. Push notifications disabled.")
                return
            firebase_admin.initialize_app(cred)
            _firebase_initialized = True
            logger.info("Firebase initialized.")
    except ImportError:
        logger.warning("firebase-admin not installed. Push notifications disabled.")


class PushService:
    async def send(
        self,
        token: str,
        title: str,
        body: str,
        data: Optional[Dict[str, Any]] = None,
    ) -> bool:
        _init_firebase()
        if not _firebase_initialized:
            return False
        try:
            from firebase_admin import messaging
            message = messaging.Message(
                notification=messaging.Notification(title=title, body=body),
                data={k: str(v) for k, v in (data or {}).items()},
                token=token,
                android=messaging.AndroidConfig(
                    priority="high",
                    notification=messaging.AndroidNotification(
                        channel_id="default",
                        priority="high",
                    ),
                ),
            )
            response = messaging.send(message)
            logger.info(f"Push notification sent: {response}")
            return True
        except Exception as exc:
            logger.error(f"Push notification failed: {exc}")
            return False
