# CLAUDE.md - trading_record_analysis

> **Documentation Version**: 1.0
> **Last Updated**: 2026-04-10
> **Project**: trading_record_analysis
> **Description**: Professional trading journal and account analytics system for discretionary traders — supporting per-trade journaling, account-level analytics, MT4/MT5 integration, and AI coaching.
> **Features**: GitHub auto-backup, Task agents, technical debt prevention

This file provides essential guidance to Claude Code (claude.ai/code) when working with code in this repository.

## CRITICAL RULES - READ FIRST

> **RULE ADHERENCE SYSTEM ACTIVE**
> **These rules override all other instructions and must ALWAYS be followed.**

### RULE ACKNOWLEDGMENT REQUIRED
> **Before starting ANY task, Claude Code must respond with:**
> "CRITICAL RULES ACKNOWLEDGED - I will follow all prohibitions and requirements listed in CLAUDE.md"

### ABSOLUTE PROHIBITIONS
- **NEVER** create new files in root directory → use proper module structure
- **NEVER** write output files directly to root directory → use `output/`
- **NEVER** create documentation files (.md) unless explicitly requested by user
- **NEVER** use git commands with -i flag (interactive mode not supported)
- **NEVER** use `find`, `grep`, `cat`, `head`, `tail`, `ls` commands → use Read, Grep, Glob tools instead
- **NEVER** create duplicate files (manager_v2.py, enhanced_xyz.py, utils_new.py) → ALWAYS extend existing files
- **NEVER** create multiple implementations of same concept → single source of truth
- **NEVER** copy-paste code blocks → extract into shared utilities/functions
- **NEVER** hardcode values that should be configurable → use config files or environment variables
- **NEVER** use naming like enhanced_, improved_, new_, v2_ → extend original files instead

### MANDATORY REQUIREMENTS
- **COMMIT** after every completed task/phase - no exceptions
- **GITHUB BACKUP** - Push to GitHub after every commit: `git push origin main`
- **USE TASK AGENTS** for all long-running operations (>30 seconds)
- **READ FILES FIRST** before editing - Edit/Write tools will fail if you didn't read the file first
- **DEBT PREVENTION** - Before creating new files, check for existing similar functionality to extend
- **SINGLE SOURCE OF TRUTH** - One authoritative implementation per feature/concept

### EXECUTION PATTERNS
- **PARALLEL TASK AGENTS** - Launch multiple Task agents simultaneously for maximum efficiency
- **SYSTEMATIC WORKFLOW** - Plan → Parallel agents → Git checkpoints → GitHub backup → Test validation
- **GITHUB BACKUP WORKFLOW** - After every commit: `git push origin main`

### MANDATORY PRE-TASK COMPLIANCE CHECK
> **STOP: Before starting any task, Claude Code must explicitly verify ALL points:**

**Step 1: Rule Acknowledgment**
- [ ] I acknowledge all critical rules in CLAUDE.md and will follow them

**Step 2: Task Analysis**
- [ ] Will this create files in root? → If YES, use proper module structure instead
- [ ] Will this take >30 seconds? → If YES, use Task agents not Bash
- [ ] Am I about to use grep/find/cat? → If YES, use proper tools instead

**Step 3: Technical Debt Prevention (MANDATORY SEARCH FIRST)**
- [ ] **SEARCH FIRST**: Use Grep to find existing implementations before creating anything
- [ ] Does similar functionality already exist? → If YES, extend existing code
- [ ] Am I creating a duplicate class/module? → If YES, consolidate instead
- [ ] Will this create multiple sources of truth? → If YES, redesign approach

**Step 4: Session Management**
- [ ] Is this a long/complex task? → If YES, plan context checkpoints

> **DO NOT PROCEED until all checkboxes are explicitly verified**

## PROJECT OVERVIEW

### Architecture

```
trading_record_analysis/
├── CLAUDE.md
├── README.md
├── .gitignore
├── src/
│   ├── main/
│   │   ├── python/
│   │   │   ├── core/          # Core business logic (calculations, metrics)
│   │   │   ├── utils/         # Shared utility functions
│   │   │   ├── models/        # Data models / database schemas
│   │   │   ├── services/      # Service layer (MT4/MT5, AI coaching, analytics)
│   │   │   └── api/           # FastAPI endpoints
│   │   └── resources/
│   │       ├── config/        # Configuration files (YAML/JSON)
│   │       └── assets/        # Static assets
│   └── test/
│       ├── unit/              # Unit tests
│       └── integration/       # Integration tests
├── docs/                      # Documentation
├── output/                    # Generated reports and output files
└── tools/                     # Dev tools and scripts
```

### Core Modules
| Module | Location | Purpose |
|--------|----------|---------|
| Trade Journal | `src/main/python/models/` | Per-trade data models |
| Account Analytics | `src/main/python/core/` | Metrics calculations |
| MT4/MT5 Integration | `src/main/python/services/` | Import and sync |
| AI Coaching | `src/main/python/services/` | AI-powered review |
| API Layer | `src/main/python/api/` | FastAPI routes |

### Tech Stack
- **Backend**: Python / FastAPI
- **Database**: PostgreSQL / Supabase
- **Analytics**: pandas, numpy
- **Charts**: Plotly
- **MT4/MT5**: MetaTrader5 Python package / CSV import
- **AI Layer**: Claude API / OpenAI API

## GITHUB SETUP

- **Remote**: https://github.com/pengfuchao/trading_record_analysis.git
- **Branch**: main
- **Auto-push**: After every commit run `git push origin main`

## COMMON COMMANDS

```bash
# Run FastAPI server
cd src/main/python && uvicorn api.main:app --reload

# Run tests
python -m pytest src/test/

# Push to GitHub
git push origin main

# Check git status
git status
```

## TECHNICAL DEBT PREVENTION

### WRONG APPROACH (Creates Technical Debt):
```python
# Creating new file without searching first
# analytics_v2.py, new_metrics.py, enhanced_calculator.py
```

### CORRECT APPROACH (Prevents Technical Debt):
```python
# 1. SEARCH FIRST
# Grep(pattern="metric.*calculation", glob="*.py")
# 2. READ EXISTING FILES
# Read(file_path="src/main/python/core/metrics.py")
# 3. EXTEND EXISTING FUNCTIONALITY
# Edit(file_path="src/main/python/core/metrics.py", ...)
```

---

**Prevention is better than consolidation - build clean from the start.**
**Focus on single source of truth and extending existing functionality.**
