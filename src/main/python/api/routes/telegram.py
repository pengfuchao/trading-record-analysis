from __future__ import annotations

import dataclasses
import os
import uuid
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.main.python.api.dependencies import get_db, get_account_repo, get_trade_repo, require_account
from src.main.python.core.account_analytics import AccountAnalytics
from src.main.python.models.trade_plan import TradePlan
from src.main.python.services.account_repository import AccountRepository
from src.main.python.services.telegram_command_parser import (
    JOURNAL_USAGE,
    PLAN_USAGE,
    STATUS_USAGE,
    ParsedCommand,
    coerce_bool,
    coerce_float,
    coerce_list,
    parse_command,
)
from src.main.python.services.telegram_notifier import get_notifier
from src.main.python.services.trade_plan_repository import TradePlanRepository
from src.main.python.services.trade_repository import TradeRepository
from src.main.python.utils.logging_utils import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/telegram", tags=["Telegram"])


# ── Telegram update schema (only fields we use) ───────────────────────────────

class _TgChat(BaseModel):
    id: int


class _TgMessage(BaseModel):
    message_id: int
    chat: _TgChat
    text: Optional[str] = None


class _TgUpdate(BaseModel):
    update_id: int
    message: Optional[_TgMessage] = None


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/test-ping")
def test_telegram_ping() -> dict:
    """Send a test message to verify Telegram integration is working."""
    sent = get_notifier().send("\U0001f514 Trading Journal: Telegram is connected.")
    return {
        "sent": sent,
        "message": "ping sent" if sent else "not configured or send failed",
    }


@router.post("/webhook")
def telegram_webhook(update: _TgUpdate, db: Session = Depends(get_db)) -> dict:
    """
    Telegram Bot webhook receiver.

    Register with:
      curl -X POST "https://api.telegram.org/bot<TOKEN>/setWebhook" \
           -d "url=https://your-server.com/api/v1/telegram/webhook"

    Always returns {"ok": True} — Telegram requires HTTP 200 on every update
    or it will retry indefinitely.
    """
    try:
        if not update.message or not update.message.text:
            return {"ok": True}

        # Guard: only respond to the configured chat
        authorized_chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")
        if str(update.message.chat.id) != authorized_chat_id:
            logger.warning(
                "Telegram webhook: ignored message from unknown chat %d",
                update.message.chat.id,
            )
            return {"ok": True}

        text = update.message.text.strip()
        cmd = parse_command(text)

        if cmd.command == "ping":
            reply = "\U0001f514 Trading Journal is online."
        elif cmd.command == "plan":
            reply = _handle_plan(cmd, db)
        elif cmd.command == "journal":
            reply = _handle_journal(cmd, db)
        elif cmd.command == "status":
            reply = _handle_status(cmd, db)
        else:
            reply = (
                f"\u2753 Unknown command <b>{cmd.raw_command}</b>\n\n"
                "Supported commands:\n"
                "/plan \u2014 create a trade plan\n"
                "/journal \u2014 update trade notes &amp; flags\n"
                "/status \u2014 account &amp; FTMO status\n"
                "/ping \u2014 test connection"
            )

        get_notifier().send(reply)

    except Exception as exc:
        logger.error("Telegram webhook unhandled error: %s", exc, exc_info=True)
        try:
            get_notifier().send("\u274c Internal error processing command. Check server logs.")
        except Exception:
            pass

    return {"ok": True}


# ── Command handlers ──────────────────────────────────────────────────────────

def _handle_plan(cmd: ParsedCommand, db: Session) -> str:
    """Create a trade plan from /plan command fields."""
    fields = cmd.fields

    account_id = fields.get("account", "").strip()
    if not account_id:
        return f"\u274c /plan error: <b>account</b> is required\n\nUsage:\n<pre>{PLAN_USAGE}</pre>"

    account_repo = AccountRepository(db)
    account = account_repo.get_by_id(account_id)
    if not account:
        return f"\u274c Account <b>{account_id}</b> not found"

    # Coerce numeric fields
    sl, sl_err = coerce_float(fields["sl"]) if "sl" in fields else (None, None)
    tp, tp_err = coerce_float(fields["tp"]) if "tp" in fields else (None, None)
    rr, rr_err = coerce_float(fields["rr"]) if "rr" in fields else (None, None)
    for err in (sl_err, tp_err, rr_err):
        if err:
            return f"\u274c /plan error: {err}"

    a_plus_raw = fields.get("a_plus")
    is_a_plus = coerce_bool(a_plus_raw) if a_plus_raw is not None else None

    plan = TradePlan(
        plan_id=str(uuid.uuid4()),
        account_id=account_id,
        status="planned",
        symbol=fields.get("symbol") or None,
        intended_direction=fields.get("direction") or None,
        setup_type=fields.get("setup") or None,
        strategy=fields.get("strategy") or None,
        bias=fields.get("bias") or None,
        thesis=fields.get("thesis") or None,
        entry_logic=fields.get("entry_logic") or None,
        stop_loss_logic=fields.get("sl_logic") or None,
        take_profit_logic=fields.get("tp_logic") or None,
        planned_entry_zone=fields.get("entry_zone") or None,
        planned_stop_loss=sl,
        planned_take_profit=tp,
        planned_rr=rr,
        is_a_plus_setup=is_a_plus,
        notes=fields.get("notes") or None,
    )

    repo = TradePlanRepository(db)
    saved = repo.create(account_id, plan)

    # Build concise reply
    parts = [f"\u2705 Plan created \u2014 <b>{account_id}</b>"]
    if saved.symbol or saved.intended_direction:
        line = []
        if saved.symbol:
            line.append(f"Symbol: {saved.symbol}")
        if saved.intended_direction:
            line.append(f"Dir: {saved.intended_direction.capitalize()}")
        parts.append(" | ".join(line))
    if saved.setup_type or saved.is_a_plus_setup is not None:
        line = []
        if saved.setup_type:
            line.append(f"Setup: {saved.setup_type}")
        if saved.is_a_plus_setup is not None:
            line.append(f"A+: {'Yes' if saved.is_a_plus_setup else 'No'}")
        parts.append(" | ".join(line))
    if any(v is not None for v in (saved.planned_stop_loss, saved.planned_take_profit, saved.planned_rr)):
        line = []
        if saved.planned_stop_loss is not None:
            line.append(f"SL: {saved.planned_stop_loss}")
        if saved.planned_take_profit is not None:
            line.append(f"TP: {saved.planned_take_profit}")
        if saved.planned_rr is not None:
            line.append(f"R:R: {saved.planned_rr}")
        parts.append(" | ".join(line))
    parts.append(f"ID: <code>{saved.plan_id[:8]}</code>")
    return "\n".join(parts)


def _handle_journal(cmd: ParsedCommand, db: Session) -> str:
    """Update trade enrichment fields from /journal command."""
    fields = cmd.fields

    account_id = fields.get("account", "").strip()
    trade_id = fields.get("trade_id", "").strip()

    if not account_id:
        return f"\u274c /journal error: <b>account</b> is required\n\nUsage:\n<pre>{JOURNAL_USAGE}</pre>"
    if not trade_id:
        return f"\u274c /journal error: <b>trade_id</b> is required\n\nUsage:\n<pre>{JOURNAL_USAGE}</pre>"

    account_repo = AccountRepository(db)
    if not account_repo.get_by_id(account_id):
        return f"\u274c Account <b>{account_id}</b> not found"

    trade_repo = TradeRepository(db)
    trade = trade_repo.get_by_id(trade_id)
    if not trade:
        return f"\u274c Trade <b>{trade_id}</b> not found"
    if trade.account_id != account_id:
        return f"\u274c Trade <b>{trade_id}</b> does not belong to account <b>{account_id}</b>"

    # Build update dict from provided fields only
    updates: dict = {}

    if "followed_plan" in fields:
        val = coerce_bool(fields["followed_plan"])
        if val is not None:
            updates["followed_plan"] = val

    for key in ("setup_type", "exit_reason", "notes", "problem_source", "trade_quality"):
        if key in fields and fields[key]:
            updates[key] = fields[key]

    if "lesson" in fields and fields["lesson"]:
        updates["lesson_learned"] = fields["lesson"]

    if "mistakes" in fields:
        updates["mistake_tags"] = coerce_list(fields["mistakes"])

    if not updates:
        return "\u274c /journal error: no fields provided to update"

    updated = dataclasses.replace(trade, **updates)
    saved = trade_repo.save(updated)

    parts = [f"\u2705 Trade updated \u2014 <b>{account_id}</b>"]
    parts.append(f"Trade: <code>{saved.trade_id[:8]}</code>")
    if "followed_plan" in updates:
        parts.append(f"Followed plan: {'Yes' if updates['followed_plan'] else 'No'}")
    if "lesson_learned" in updates:
        parts.append(f"Lesson: {updates['lesson_learned']}")
    if "mistake_tags" in updates:
        tags = updates["mistake_tags"]
        parts.append(f"Mistakes: {', '.join(tags) if tags else 'none'}")
    if "notes" in updates:
        parts.append(f"Notes: {updates['notes']}")
    return "\n".join(parts)


def _handle_status(cmd: ParsedCommand, db: Session) -> str:
    """Return account + FTMO status summary."""
    fields = cmd.fields

    account_id = fields.get("account", "").strip()
    if not account_id:
        return f"\u274c /status error: <b>account</b> is required\n\nUsage:\n<pre>{STATUS_USAGE}</pre>"

    account_repo = AccountRepository(db)
    account = account_repo.get_by_id(account_id)
    if not account:
        return f"\u274c Account <b>{account_id}</b> not found"

    trade_repo = TradeRepository(db)
    trades = trade_repo.get_by_account(account_id)

    status = AccountAnalytics.compute_ftmo_status(trades, account)

    account_status = status.get("account_status", "UNKNOWN")
    icons = {"SAFE": "\U0001f7e2", "AT_RISK": "\U0001f7e1", "BREACHED": "\U0001f534", "UNKNOWN": "\u26aa"}
    icon = icons.get(account_status, "\u26aa")

    def _pct(v) -> str:
        return f"{v:.1f}%" if v is not None else "—"

    def _usd(v) -> str:
        return f"${v:,.0f}" if v is not None else "—"

    broker_label = f"{account.broker}" if account.broker else account_id
    balance_line = (
        f"Balance: {_usd(status.get('estimated_current_balance'))} "
        f"(starting: {_usd(account.starting_balance)})"
        if account.starting_balance else "Balance: unknown (no starting balance set)"
    )

    daily_used = _pct(status.get("daily_loss_used_pct"))
    daily_rem = _usd(status.get("daily_loss_remaining"))
    daily_limit = _pct(status.get("daily_loss_limit_pct"))

    dd_used = _pct(status.get("current_max_drawdown_pct"))
    dd_rem = _usd(status.get("max_loss_remaining"))
    dd_limit = _pct(status.get("max_loss_limit_pct"))

    lines = [
        f"\U0001f4ca <b>{account_id}</b> ({broker_label})",
        balance_line,
        f"Daily: {daily_used} used of {daily_limit} limit ({daily_rem} remaining)",
        f"Drawdown: {dd_used} used of {dd_limit} limit ({dd_rem} remaining)",
        f"Status: {icon} <b>{account_status}</b>",
    ]
    return "\n".join(lines)
