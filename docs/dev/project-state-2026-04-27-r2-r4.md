# Project State Update — 2026-04-27 (R2–R4 session)

## Session Summary

Implemented roadmap items R2, R3, and R4 from the 2026-04-27 project state doc.
Commit: `b4f208f` on `main`.

---

## What Was Done

### R1 — Backup discipline (MANUAL — flagged, not implemented)
R1 requires operator action, not code:
- Set up Task Scheduler (Windows) or cron (WSL) to run `backup.sh` daily
- Copy `backups/` to OneDrive or an external drive
- Run a `restore.sh` drill on a throwaway database
- Set rotation policy (14 daily + 12 monthly suggested)

**This is the single highest-impact remaining action and must be done by the operator.**

---

### R2 — SL/TP enrichment doc sweep (DONE)

**README.md:**
- "Core Workflow" now has a step 3 ("If SL/TP shows blank in Trade Log") with the two-path decision tree — CSV enrichment vs MT5 backfill
- Feature table updated with the three new MT5/CSV SL/TP features
- `docker compose down -v` section now shows ⚠️ warning with reference to `reset-data.sh`

**RPD.md:**
- Phase 12 entry added covering all work done between 2026-04-26 and 2026-04-27
- Version bumped to 2.3

**Import page (`frontend/app/import/page.tsx`):**
- "Enrich SL/TP from CSV" panel description now includes: "Use this path if you have a CSV export — for historical trades without a CSV, use the MT5 Backfill on the MT5 Sync page."

**MT5 sync page (`frontend/app/mt5-sync/page.tsx`) + api.ts:**
- New "SL / TP Backfill" panel added (Section 4, before Open Positions)
- Button triggers `POST /accounts/{id}/mt5-sync/backfill-sl-tp`
- Shows result summary: SL filled / R computed / SL=0 on order / no order / checked
- Copy explicitly says "may take several minutes — do not click twice"
- Disabled if MT5 config not saved
- `BackfillSLTPResponse` interface added to `api.ts`
- `api.backfillSlTp()` method added to `api.ts`

---

### R3 — `docker compose down -v` guardrail (DONE)

**New files:**
- `reset-data.sh` — bash wrapper: runs `backup.sh` first, prompts "type reset to continue", then runs `docker compose down -v`. Safe to run accidentally — it will cancel on anything other than "reset".
- `reset-data.ps1` — PowerShell equivalent with colored output; aborts if backup fails.

**README.md:**
- `docker compose down -v` block now shows ⚠️ WARNING and references `reset-data.sh` / `reset-data.ps1` as the safe path.

---

### R4 — Single-worker startup enforcement (DONE)

**`src/main/python/api/app.py` (`_lifespan`):**
- Reads `UVICORN_WORKERS` env var at startup
- Logs a WARN if the value is set and != "1"
- Message explicitly names the risk: MT5 sync overlap protection is in-memory, multi-worker deployments silently corrupt sync state
- Non-fatal — does not refuse to start; operators who know what they're doing can ignore it

---

## Validation

- `python3 -m pytest src/test/ -x -q` → **533 passed, 9 skipped** (no regressions)
- `npx tsc --noEmit` in `frontend/` → **clean** (no type errors)
- New TypeScript types are used correctly; `BackfillSLTPResponse` mirrors backend schema

---

## Remaining Roadmap (updated)

| Item | Status | Notes |
|---|---|---|
| **R1** — Backup discipline | **Manual — not done** | Highest-priority remaining action; operator must set up scheduling + off-host copy |
| R2 — SL/TP doc sweep | **Done** | README, RPD, import page, MT5 sync page |
| R3 — reset-data guardrail | **Done** | reset-data.sh + reset-data.ps1 |
| R4 — single-worker enforcement | **Done** | _lifespan WARN log |
| R5 — Persist FTMO/scheduler cooldown | Open | DB migration + runtime_state table; prevents restart-induced false alerts |
| R6 — MT5 password env var presence indicator | Open | GET .../mt5-config/password-status + UI green✓/red✗ |
| R7 — SL/TP backfill UX | Partially done | UI panel added in R2; async/progress only if user feels pain |
| R8 — Real-data Playwright E2E | Deferred | No real regression has slipped through mocked tests yet |

**Next session should start with:** R1 reminder (manual), then R5 (persistent cooldown state) as the highest-value remaining code item.
