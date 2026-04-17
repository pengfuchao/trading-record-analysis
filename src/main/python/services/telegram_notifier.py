from __future__ import annotations

import os
from typing import Optional, Tuple

import requests

from src.main.python.services.ai_coach import ReviewResult
from src.main.python.services.mt5_sync_service import SyncResult
from src.main.python.utils.logging_utils import get_logger

logger = get_logger(__name__)

_TELEGRAM_API = "https://api.telegram.org/bot{token}/sendMessage"


class TelegramNotifier:
    """
    Thin push-notification service for Telegram.

    Configured via environment variables:
      TELEGRAM_BOT_TOKEN  — bot token from @BotFather
      TELEGRAM_CHAT_ID    — target chat/group ID
      TELEGRAM_ENABLED    — set to "false" to silence without removing tokens

    All send methods are fire-and-forget: they log on failure but never raise.
    """

    def __init__(self) -> None:
        self._bot_token: Optional[str] = os.environ.get("TELEGRAM_BOT_TOKEN")
        self._chat_id: Optional[str] = os.environ.get("TELEGRAM_CHAT_ID")
        enabled_flag = os.environ.get("TELEGRAM_ENABLED", "true").lower()
        self._enabled = bool(
            self._bot_token and self._chat_id and enabled_flag != "false"
        )
        self._last_ftmo_status: dict[str, str] = {}  # account_id → last notified status

        if not self._enabled:
            logger.info(
                "Telegram notifications disabled "
                "(TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID not set, or TELEGRAM_ENABLED=false)"
            )

    # ── Core sender ──────────────────────────────────────────────────────────────

    def send(self, text: str) -> bool:
        """POST a message to Telegram. Returns True on success, False on any error."""
        if not self._enabled:
            logger.debug("Telegram send skipped (not enabled)")
            return False
        url = _TELEGRAM_API.format(token=self._bot_token)
        payload = {
            "chat_id": self._chat_id,
            "text": text,
            "parse_mode": "HTML",
        }
        try:
            resp = requests.post(url, json=payload, timeout=10)
            if resp.status_code == 200:
                return True
            logger.warning(
                "Telegram send failed: HTTP %d — %s", resp.status_code, resp.text[:200]
            )
            return False
        except Exception as exc:
            logger.warning("Telegram send error: %s", exc)
            return False

    # ── MT5 sync notification ────────────────────────────────────────────────────

    def notify_mt5_sync_result(self, account_name: str, result: SyncResult) -> bool:
        """Send a sync success or failure message."""
        if result.status == "success":
            completed = (
                result.completed_at.strftime("%Y-%m-%d %H:%M UTC")
                if result.completed_at else "—"
            )
            text = (
                f"\U0001f4ca MT5 Sync: <b>{account_name}</b>\n"
                f"Status: \u2705 SUCCESS\n"
                f"New: {result.trades_new} | Updated: {result.trades_updated} "
                f"| Skipped: {result.trades_skipped}\n"
                f"Deals fetched: {result.deals_fetched}\n"
                f"Completed: {completed}"
            )
        else:
            error = result.error_message or "Unknown error"
            started = (
                result.started_at.strftime("%Y-%m-%d %H:%M UTC")
                if result.started_at else "—"
            )
            text = (
                f"\u26a0\ufe0f MT5 Sync: <b>{account_name}</b>\n"
                f"Status: \u274c FAILED\n"
                f"Error: {error}\n"
                f"Started: {started}"
            )
        return self.send(text)

    # ── FTMO notifications ───────────────────────────────────────────────────────

    def check_and_notify_ftmo(
        self,
        account_id: str,
        account_name: str,
        status_data: dict,
    ) -> Tuple[bool, Optional[str]]:
        """
        Compare new FTMO status to the last-notified status for this account.
        Sends a Telegram alert only if the status has changed (or on the first call).
        Updates the cache regardless of whether the send succeeded.
        Returns (notification_sent, prev_status).
        """
        new_status = status_data.get("account_status", "UNKNOWN")
        prev_status = self._last_ftmo_status.get(account_id)

        if new_status == prev_status:
            return False, prev_status

        sent = self._notify_ftmo_status_change(account_name, status_data, prev_status)
        self._last_ftmo_status[account_id] = new_status
        return sent, prev_status

    def _notify_ftmo_status_change(
        self,
        account_name: str,
        status_data: dict,
        prev_status: Optional[str],
    ) -> bool:
        new_status = status_data.get("account_status", "UNKNOWN")

        status_icons = {
            "SAFE": "\U0001f7e2",
            "AT_RISK": "\U0001f7e1",
            "BREACHED": "\U0001f534",
            "UNKNOWN": "\u26aa",
        }
        icon = status_icons.get(new_status, "\u26aa")

        prev_label = prev_status or "—"
        transition = f"{prev_label} \u2192 <b>{new_status}</b>"

        daily_used = status_data.get("daily_loss_used_pct")
        daily_limit = status_data.get("daily_loss_limit_pct")
        daily_rem = status_data.get("daily_loss_remaining")
        overall_used = status_data.get("current_max_drawdown_pct")
        overall_limit = status_data.get("max_loss_limit_pct")
        overall_rem = status_data.get("max_loss_remaining")

        def _fmt_pct(v: Optional[float]) -> str:
            return f"{v:.1f}%" if v is not None else "—"

        def _fmt_usd(v: Optional[float]) -> str:
            return f"${v:.0f}" if v is not None else "—"

        lines = [
            f"{icon} FTMO Alert: <b>{account_name}</b>",
            f"Status: {transition}",
            f"Daily loss: {_fmt_pct(daily_used)} / {_fmt_pct(daily_limit)} limit "
            f"({_fmt_usd(daily_rem)} remaining)",
            f"Max drawdown: {_fmt_pct(overall_used)} / {_fmt_pct(overall_limit)} limit "
            f"({_fmt_usd(overall_rem)} remaining)",
        ]

        if new_status == "BREACHED":
            lines.append("<b>Challenge limits exceeded.</b>")
        elif new_status == "SAFE" and prev_status in ("AT_RISK", "BREACHED"):
            lines.append("All limits within range.")

        return self.send("\n".join(lines))

    # ── Coaching notification ────────────────────────────────────────────────────

    def notify_coaching_generated(
        self,
        account_name: str,
        from_date: Optional[str],
        to_date: Optional[str],
        result: ReviewResult,
    ) -> bool:
        """Send coaching notification only for successful AI-generated reviews."""
        if result.source != "ai" or result.status != "success":
            return False
        period = f"{from_date or '—'} \u2192 {to_date or '—'}"
        preview = result.summary[:120] + "…" if len(result.summary) > 120 else result.summary
        text = (
            f"\U0001f9e0 Coaching Review: <b>{account_name}</b>\n"
            f"Period: {period}\n"
            f"<i>{preview}</i>"
        )
        return self.send(text)


# ── Module-level singleton ────────────────────────────────────────────────────

_notifier = TelegramNotifier()


def get_notifier() -> TelegramNotifier:
    return _notifier
