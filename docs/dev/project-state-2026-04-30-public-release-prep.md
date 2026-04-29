# Project State — 2026-04-30 (Public-Release Prep + Long-Term Testing Handoff)

This document is the **resume point** for any future Claude Code session. Read this first before starting work.

Predecessors:
- `project-state-2026-04-28.md` — R1–R6 + SL/TP integrity fix
- `project-state-2026-04-30.md` — R7 done + first R9 slices

---

## 1. Maturity / Status

**Maturity: 9.7 / 10** — Feature-complete, data-integrity hardened, ops solid, UI polished, public-release-safe.

The project is **entering long-term testing / observation mode**. No urgent code work remains. Do not restart feature expansion until either real-use pain appears or the operator selects a planned roadmap item.

---

## 2. What Is Fully Complete

### Backend
- Phase 1–13 (all backend phases — see CLAUDE.md / RPD.md)
- 588+ pytest tests (all non-Postgres tests pass; 9 pre-existing Postgres smoke errors require live DB)
- `runtime_state` table (migration 011) for FTMO dedup + scheduler cooldown persistence
- SL/TP null-overwrite data-integrity guard (`_SL_TP_PROTECTED_FIELDS`)
- MT5 password env-var presence indicator (R6) — `GET /accounts/{id}/mt5-config/password-status`

### Frontend
- All pages wired to real API data
- E2E Playwright smoke tests (8 tests, mocked API)
- TypeScript strict mode, zero errors
- R9 polish (in progress — see below)

### Operations
- `backup.ps1` / `backup.sh` / `restore.ps1` / `restore.sh` — manual + Task Scheduler / cron schedule
- `reset-data.ps1` / `reset-data.sh` — guarded `docker compose down -v` (auto-backup + confirmation)
- `_lifespan` WARN log when `UVICORN_WORKERS != 1`

### Reliability hardening (R1–R7)
| Item | Status | Validation |
|---|---|---|
| R1 — Backup discipline (manual) | DONE | Operator verified scheduled backups + off-host copy + restore drill |
| R2 — SL/TP doc + UX consolidation | DONE | README, RPD, import page, MT5 sync page |
| R3 — reset-data guardrail | DONE | reset-data.sh + reset-data.ps1 |
| R4 — Single-worker enforcement | DONE | _lifespan WARN |
| R5 — runtime_state persistence | DONE | Migration 011 applied + restart drills passed |
| R6 — MT5 password presence badge | DONE | UI badge live-validated |
| R7 — SL/TP backfill UX polish | DONE | Error banner + helper text + success card; full async job system deferred |

### UI polish (R9, in progress — non-urgent)
| Slice | Status |
|---|---|
| MT5 Sync section reorder + status pill | DONE |
| Trade Log SL/TP missing-value visibility | DONE |
| Dashboard section heading consistency | DONE |
| Import page Enrich SL/TP heading consistency | DONE |
| Trade Log "Dir" → "Side" | DONE |
| Plans list date display | OPEN (optional) |
| Daily / Coaching workflow polish | OPEN (optional) |
| Other dashboard refinements | OPEN (optional) |

---

## 3. Live-Validated (Operator on 2026-04-28)

All 6 manual validations passed:
1. `alembic upgrade head` applied; `runtime_state` table verified live
2. MT5 sync after SL/TP enrichment — enriched SL/TP/R survived intact
3. Backend restart — no duplicate FTMO Telegram alert (R5 dedup persisted)
4. Scheduler error cooldown survived restart (R5 persisted)
5. `/mt5-sync` password env-var presence badge confirmed
6. Full CSV-enrich → MT5 sync → SL/TP persistence flow — verified end-to-end

---

## 4. Critical Invariants (DO NOT REGRESS)

> **Normal MT5 sync must never use incoming `null` `stop_loss`, `take_profit`, or `actual_r_multiple` to overwrite existing non-null enriched/manual values.**

Implemented in `src/main/python/services/trade_repository.py` via `_SL_TP_PROTECTED_FIELDS`. Do not remove this guard. Do not add SL/TP-adjacent fields to `_BROKER_FIELDS` without also adding them to `_SL_TP_PROTECTED_FIELDS` if they can be enriched independently. Regression tests live in `test_repositories.py::TestSaveBatchImportUpdateBroker`.

> **MT5 scheduler must run with `--workers 1`.**

Overlap protection is in-memory (`_running` set) — multi-worker deployments would silently corrupt sync state. `_lifespan` logs WARN if `UVICORN_WORKERS != 1`. `docker-entrypoint.sh` enforces single worker.

> **MT5 password is never stored in the database.**

Read from env var `MT5_<ACCOUNT_ID_UPPER_UNDERSCORED>_PASSWORD` at sync time. The R6 password-status endpoint returns presence boolean only — never the value.

---

## 5. Operating Modes

**Mode 1 — Full Docker stack** (daily journaling, analytics, coaching):
```bash
cp .env.example .env
docker compose up -d
```

**Mode 2 — Local Windows backend + Docker Postgres** (MT5 live sync):
```powershell
docker compose stop backend
.\venv\Scripts\activate
$env:PYTHONPATH = "."
python -m uvicorn src.main.python.api.app:app --reload --host 0.0.0.0 --port 8000
```

The Docker backend cannot run MT5 sync (`MetaTrader5` is Windows-only). MT5 sync routes degrade gracefully on Linux/Mac.

---

## 6. CI / Test Status

**GitHub Actions** runs on every push and PR to `main`:
- Backend tests (SQLite) — full pytest suite
- Postgres migration check — `alembic upgrade head` + 9 ORM smoke tests on real Postgres 15
- Frontend typecheck — `tsc --noEmit`
- Frontend E2E — 8 Playwright smoke tests with mocked API

All green at handoff time.

---

## 7. Known Limitations (Intentional)

| Limitation | Why |
|---|---|
| No authentication | Single-user local-trust scope. Do not expose publicly without adding auth. |
| MT5 requires Windows | `MetaTrader5` Python package is Windows-only |
| MT5 sync is single-process | In-memory overlap protection only |
| Screenshot upload not implemented | `screenshot_examples` field exists but no storage wired |
| Telegram NLP deferred | `/journal` requires exact UUID; no broker ticket lookup |
| Setup Library not auto-populated | New setup names from imports don't auto-create Library entries |
| Coaching covers closed trades only | No open-position awareness |

---

## 8. Intentionally Deferred

- **R7 full async job system** — only revisit if backfill blocking wait becomes painful in real use. Current synchronous run with disabled-button + spinner + helper text is sufficient.
- **R8 real-data Playwright E2E** — only revisit after a regression slips through the mocked tests. Current 8 mocked tests have been catching issues.
- **Multi-user auth, hosted SaaS, mobile UI, MT4 bridge, screenshot storage, Telegram NLP** — long-term roadmap; not on the near-term path.

---

## 9. Long-Term Monitoring Checklist

During the testing / observation period, watch for:

| Area | What to monitor | Trigger |
|---|---|---|
| MT5 sync | Sync success rate, error patterns in run history | Repeated errors → investigate |
| SL/TP integrity | After repeated MT5 syncs, verify enriched SL/TP not lost | Spot-check Trade Log monthly |
| Telegram alerts | No duplicate alerts after backend restarts | Verify R5 dedup still works |
| Scheduled backups | Backup files appearing in `backups/` on schedule | Missing backup → investigate cron / Task Scheduler |
| Restore drill | Run quarterly restore drill on throwaway DB | Operator discipline |
| UI friction | Note specific friction points during daily use | Feed into R9 polish backlog |

---

## 10. Public Repository Safety Audit (this session)

Repo audited for public release. **Verdict: safe to make public after the `.gitignore` update committed in this session.**

Audit checks:
- All 185 tracked files scanned
- No API keys, tokens, PATs, PEM material, real credentials
- `.env.example` uses placeholders only
- `docker-compose.yml` uses dev-default `trading:trading` (appropriate for single-user local; documented)
- Sample CSV fixtures use synthetic IDs `12345001+`
- All `ftmo-p1`, `ic.markets.01`, `ICMarkets-Live` references are placeholders
- `pengfuchao` GitHub username already public via repo URL
- `OneDrive` references are generic backup-location examples
- All real backup dumps, DB files, env files, logs are correctly gitignored and untracked

Remediation applied this session:
- Added `.claude/`, `.cursor/`, `.aider*` to project `.gitignore` (previously relied on the operator's global gitignore — would not protect new contributors)

No git-history rewrite is required. No tracked file contains private data.

---

## 11. What Future Claude Sessions Should Read First

1. `CLAUDE.md` — critical rules + project status
2. **This file** (`docs/dev/project-state-2026-04-30-public-release-prep.md`)
3. `RPD.md` — full product roadmap
4. `README.md` — public-facing setup
5. The most recent `docs/dev/project-state-*.md` if a newer one exists

If you are a new Claude Code session: **the project is in observation mode. Do not start a new feature unless the operator explicitly requests one or selects a planned roadmap item.**

---

## 12. Future Roadmap (Consolidated)

### A. Monitor during real use (no code yet)
- MT5 sync stability under repeated syncs over months
- SL/TP persistence after long sync history (R6/R7 invariants holding)
- Telegram alert behavior after backend restarts (R5 holding)
- Scheduled backup reliability + quarterly restore drill cadence
- UI friction during daily journaling — collect specific friction points

### B. Optional near-term polish (R9 continuation)
| Item | Value | Risk | Trigger |
|---|---|---|---|
| Plans list date display | Small UX improvement | Low | Operator notes scanning friction |
| Daily/Coaching workflow polish | Daily usability | Low | Specific friction reported |
| Dashboard refinement | Visual rhythm | Low | Operator highlights |
| Trade Log readability | Daily use | Low | Specific issue noted |

### C. Quality / testing upgrades
| Item | Value | Risk | Trigger |
|---|---|---|---|
| R8 — Real-data Playwright E2E | Catches API contract drift | Medium (DB seeding complexity) | Regression slips through mocked tests |
| Public-release CI hardening (Dependabot, secret scanning) | Public-repo hygiene | Low | After repo goes public |

### D. MT5 / runtime enhancements
| Item | Value | Risk | Trigger |
|---|---|---|---|
| R7 full async backfill job | Avoids blocking UI for very large accounts | Medium (new state machine + progress endpoint) | Operator finds blocking wait painful |
| More visible sync diagnostics | Operator awareness | Low | Specific blind spot reported |
| Persistent sync-run history refinements | Audit completeness | Low | Operator wants longer retention or filters |

### E. Analytics / trading intelligence (future modules)
| Item | Value | Risk | Trigger |
|---|---|---|---|
| MAE/MFE analytics | Better entry/exit quality signal | Medium (requires bar data ingestion) | Operator wants entry-vs-exit decomposition with real evidence |
| Advanced execution quality scoring | Granular feedback | Medium | After MAE/MFE foundation |
| Trade review scoring | Personal-coach-style rating | Medium | After sufficient trade volume + data quality |
| Risk-of-ruin / drawdown simulation | Pre-emptive risk awareness | Medium | Operator interest |
| Setup lifecycle tracking | Detect setup drift over time | Medium | After enough setup-tagged trade history |
| Regime/session diagnostics | Better session-aware coaching | Low | Operator wants sharper regime context |
| Playbook recommendation engine | Selective trade-suggestion overlay | High | Long-term, after data quality + analytics depth |

### F. AI coaching future modules
| Item | Value | Risk | Trigger |
|---|---|---|---|
| Open-trade awareness in coaching | Real-time context | Medium (requires open-position state in prompt) | Operator wants "what should I do with this open trade" coaching |
| Multi-provider AI abstraction (OpenAI/Gemini) | Vendor flexibility | Medium | Anthropic outage or pricing change |
| Coaching memory over time | Continuity across reviews | High (requires persistent context store) | Operator wants longitudinal coaching |
| Weekly/monthly coach reports | Time-series narrative | Low | Operator wants periodic digest |
| Automated habit/action checklist | Behavioral discipline | Low | Operator wants structured action items |

### G. Long-term / deferred (do not start without explicit roadmap selection)
- Multi-user authentication
- Hosted SaaS deployment
- Mobile-native UI
- MT4 EA bridge
- Screenshot/file upload storage
- Telegram NLP multi-step flows

---

## 13. Pending Operator Actions

1. **GitHub remote token** — was expired during this work session. After refreshing the PAT, run `git push origin main` to sync local commits.
2. **Decide whether to make repo public** — audit is green; only the `.gitignore` update from this session needs to ship before flipping visibility.
3. **Continue normal daily journaling** — the system is the journal now. Real-use observations feed the long-term monitoring checklist (Section 9) and the trigger-based roadmap (Section 12).
