from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


@dataclass
class ParsedCommand:
    command: str                      # "plan"|"journal"|"status"|"ping"|"unknown"
    fields: Dict[str, str] = field(default_factory=dict)  # lowercase-keyed raw values
    raw_command: str = ""             # original first token, for error messages


def parse_command(text: str) -> ParsedCommand:
    """
    Parse a Telegram message into a structured command.

    Expected format:
        /command
        key: value
        key: value

    Rules:
    - First non-empty line must start with '/' → command name
    - Remaining lines are 'key: value' pairs; lines without ':' are ignored
    - Keys are lowercased and stripped; values are stripped
    - Unknown keys are silently accepted (forward-compatible)
    - Multi-word values are preserved as-is on the same line
    """
    lines = [ln.strip() for ln in text.strip().splitlines()]
    lines = [ln for ln in lines if ln]  # drop blank lines

    if not lines:
        return ParsedCommand(command="unknown", raw_command="")

    first = lines[0]
    if not first.startswith("/"):
        return ParsedCommand(command="unknown", raw_command=first)

    raw_command = first
    command = first[1:].lower().split()[0] if len(first) > 1 else "unknown"

    fields: Dict[str, str] = {}
    for line in lines[1:]:
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        key = key.strip().lower()
        value = value.strip()
        if key:
            fields[key] = value

    return ParsedCommand(command=command, fields=fields, raw_command=raw_command)


# ── Type coercions ────────────────────────────────────────────────────────────

def coerce_bool(value: str) -> Optional[bool]:
    """'yes'/'true'/'1' → True; 'no'/'false'/'0' → False; else None."""
    v = value.strip().lower()
    if v in ("yes", "true", "1"):
        return True
    if v in ("no", "false", "0"):
        return False
    return None


def coerce_float(value: str) -> Tuple[Optional[float], Optional[str]]:
    """Returns (float, None) on success or (None, error_message) on failure."""
    try:
        return float(value.strip()), None
    except (ValueError, TypeError):
        return None, f"'{value}' is not a valid number"


def coerce_list(value: str) -> List[str]:
    """
    'tag1, tag2' → ['tag1', 'tag2']
    'none' / '' → []
    """
    stripped = value.strip().lower()
    if not stripped or stripped == "none":
        return []
    return [t.strip() for t in value.split(",") if t.strip()]


# ── Usage strings (shown in error replies) ───────────────────────────────────

PLAN_USAGE = """\
/plan
account: <account_id>
symbol: XAUUSD
direction: long | short
setup: OB Retest
strategy: London reversal
bias: bullish
thesis: reclaim + pullback
entry_logic: retest OB
sl_logic: below structure
tp_logic: prior high
entry_zone: 3320-3325
sl: 3312
tp: 3345
rr: 2.5
a_plus: yes | no
notes: only if NY confirms"""

JOURNAL_USAGE = """\
/journal
account: <account_id>
trade_id: <trade_id>
followed_plan: yes | no
setup_type: OB Retest
exit_reason: TP hit
lesson: patient entry
notes: held too long
problem_source: execution | analysis | psychology | risk
trade_quality: good trade | bad trade
mistakes: fomo, chasing | none"""

STATUS_USAGE = """\
/status
account: <account_id>"""
