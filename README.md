# Token Flow

> The local-first command center for Claude Code spend, waste, and prompt quality.

[![CI](https://github.com/showjihyun/tokenflow/actions/workflows/ci.yml/badge.svg)](https://github.com/showjihyun/tokenflow/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white)
![React](https://img.shields.io/badge/React-18-61DAFB?logo=react&logoColor=111)
![TypeScript](https://img.shields.io/badge/TypeScript-strict-3178C6?logo=typescript&logoColor=white)
![DuckDB](https://img.shields.io/badge/DuckDB-local--first-FFF000)
![License](https://img.shields.io/badge/license-MIT-black)

Token Flow turns Claude Code from a black-box bill into an observable, testable, locally stored workflow: live token flow, waste detection, session replay, budget pressure, AI coaching, and prompt-quality feedback in one dashboard.

No SaaS account. No cloud database. No default external calls. Your usage data stays in `~/.tokenflow/events.duckdb`.

## Why It Exists

Claude Code is powerful enough to burn money quietly. Token Flow makes that visible:

- See the active session, token velocity, model mix, context pressure, and projected spend.
- Catch waste patterns before they become habits: context bloat, wrong model, repeated questions, tool loops, oversized file loads.
- Replay expensive sessions with paused transcript messages excluded by default.
- Ask the AI Coach how to rewrite the next request before you pay for a bad one.
- Keep the whole stack local on `127.0.0.1:8765`.

## Product Surface

| View | What it does |
|---|---|
| Live Monitor | Current session, 60-minute token flow SSE, efficiency score, wasted tokens, model distribution, budget pressure |
| Usage Analytics | Range/project filters, daily usage, heatmap, cost breakdown, top waste ranking |
| Waste Radar | Waste pattern cards, savings estimate, `CLAUDE.md` diff preview/apply flow |
| AI Coach | Sonnet-backed coaching, query quality score, estimated cost before send |
| Session Replay | Session picker, transcript events, better prompt actions, `include_paused` forensic mode |
| Settings | Budget, routing rules, notifications, API key, LLM model, vacuum/backups/import jobs |

## Quick Start

Prerequisites:

- Python 3.11+
- Node.js 20+
- [`uv`](https://docs.astral.sh/uv/)
- npm, using the checked-in `frontend/package-lock.json`

```bash
git clone https://github.com/showjihyun/tokenflow.git
cd tokenflow

# backend
cd backend
uv venv
uv pip install -e ".[dev]"
uv run tokenflow serve --dev
```

Open another terminal:

```bash
cd tokenflow/frontend
npm ci
npm run dev
```

Then open:

- App: `http://127.0.0.1:5173`
- Backend health: `http://127.0.0.1:8765/api/system/health`

For packaged/local runtime, the backend serves the React build from `127.0.0.1:8765`.

## Test It Like You Mean It

```bash
# backend
cd backend
uv run ruff check tokenflow tests
uv run mypy tokenflow tests
uv run pytest -q

# frontend
cd frontend
npm run typecheck
npm run lint
npm run test -- --run
npm run test:e2e       # mocked SPEC-critical browser suite
npm run test:e2e:real  # real local server/data suite on :8765
npm run build
```

Current Playwright coverage hits the SPEC-critical flows: Live Monitor, Bell notifications, Usage Analytics project filtering, Waste Radar apply preview, AI Coach quality/cost/send, Session Replay paused toggle, Settings data/notification wiring, and Onboarding.

## Architecture

```text
Claude Code hooks + transcript JSONL
              |
              v
tokenflow-hook / transcript tailer
              |
              v
FastAPI @ 127.0.0.1:8765  <---- SSE + REST ---->  React dashboard
              |
              v
DuckDB @ ~/.tokenflow/events.duckdb
```

Core choices:

- FastAPI + DuckDB for a local, inspectable backend.
- React 18 + TypeScript + TanStack Query for the dashboard.
- SSE for activity ticker and token-flow invalidation.
- Plain CSS variables and direct SVG charts. No Tailwind dependency.
- Forward-only migrations, retention rollup, and backup-before-migration behavior.

## Privacy Model

Token Flow is local-first by design.

- Binds to `127.0.0.1`.
- Stores telemetry in local DuckDB.
- Does not call external LLM APIs unless AI Coach or LLM better-prompt mode is enabled.
- Coach context intentionally excludes raw file bodies, full paths, API responses, and secrets.

## Status

The implementation has moved beyond scaffold status. The current baseline includes:

- Hook/onboarding flow
- Transcript ingestion and pause-aware analysis
- Live Monitor SSE
- Analytics project filters and top-waste aggregation
- Waste Radar apply preview/confirm
- AI Coach query quality and send flow
- Session Replay paused-message controls
- Settings Data card for vacuum, backups, and ccprophet import jobs
- Persisted in-app notifications and system notification permission flow
- Playwright SPEC suite plus real-data E2E suite

See [SPEC.md](./SPEC.md) for the product/API contract and [DESIGN.md](./DESIGN.md) for the visual system.

## Repository Map

```text
tokenflow/
├─ backend/      Python 3.11+, FastAPI, DuckDB, CLI, migrations
├─ frontend/     React 18, TypeScript, Vite, Playwright
├─ SPEC.md       Product, API, and implementation contract
├─ DESIGN.md     Visual design system
└─ README.md     You are here
```

## License

MIT
