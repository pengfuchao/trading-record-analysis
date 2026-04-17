from __future__ import annotations

from fastapi import APIRouter

from src.main.python.services.telegram_notifier import get_notifier

router = APIRouter(prefix="/telegram", tags=["Telegram"])


@router.post("/test-ping")
def test_telegram_ping() -> dict:
    """Send a test message to verify Telegram integration is working."""
    sent = get_notifier().send("\U0001f514 Trading Journal: Telegram is connected.")
    return {
        "sent": sent,
        "message": "ping sent" if sent else "not configured or send failed",
    }
