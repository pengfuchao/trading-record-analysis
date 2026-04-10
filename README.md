# Trading Record Analysis

A professional trading journal and account analytics system for discretionary traders, with focus on FTMO/prop firm evaluation, execution improvement, behavioral analysis, and overall account performance monitoring.

## Overview

This system supports:
- Detailed per-trade journaling and analysis
- Account-level portfolio and performance dashboard analytics
- MT4/MT5 account history import and synchronization
- AI-powered coaching and performance review

## Core Modules

| Module | Description |
|--------|-------------|
| Trade Journal | Detailed per-trade recording with execution quality tracking |
| Account Analytics | Dashboard with balance curve, drawdown, and performance metrics |
| Mistake Analysis | Recurring error detection, ranking by frequency and cost |
| Setup Library | Playbook management with per-setup performance statistics |
| Pre/Post Market | Daily planning and review with plan vs execution comparison |
| MT4/MT5 Integration | Account history import and synchronization |
| AI Coaching | Automated performance summaries and coaching insights |

## Project Structure

```
trading_record_analysis/
├── CLAUDE.md                  # Claude Code rules and guidelines
├── README.md                  # This file
├── .gitignore
├── src/
│   ├── main/
│   │   ├── python/
│   │   │   ├── core/          # Core business logic
│   │   │   ├── utils/         # Utility functions
│   │   │   ├── models/        # Data models
│   │   │   ├── services/      # Service layer
│   │   │   └── api/           # API endpoints
│   │   └── resources/
│   │       ├── config/        # Configuration files
│   │       └── assets/        # Static assets
│   └── test/
│       ├── unit/              # Unit tests
│       └── integration/       # Integration tests
├── docs/                      # Documentation
├── output/                    # Generated output files
└── tools/                     # Development tools
```

## Quick Start

1. Read `CLAUDE.md` before working with Claude Code
2. Set up Python virtual environment: `python -m venv venv && source venv/bin/activate`
3. Install dependencies: `pip install -r requirements.txt` (once created)
4. See `docs/` for detailed setup and usage guides

## Tech Stack

- **Backend**: Python / FastAPI
- **Database**: PostgreSQL / Supabase
- **Analytics**: Python (pandas, numpy)
- **Charts**: Plotly
- **MT4/MT5 Integration**: MetaTrader5 Python package / CSV import
- **AI Layer**: OpenAI API / Claude API
