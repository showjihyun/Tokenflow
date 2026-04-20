# Token Flow

Personal Claude Code token tracker, analyzer, and coach. Local-first web dashboard built on top of the [ccprophet](https://github.com/showjihyun/ccprophet) core engine.

See [`SPEC.md`](./SPEC.md) for the product & architecture spec, [`DESIGN.md`](./DESIGN.md) for the design system.

## Status

- [x] SPEC v0.3 approved
- [x] DESIGN v0.1 approved
- [x] **Phase A — scaffolding** (current)
- [ ] Phase B — Live Monitor vertical slice (UI + mock API)
- [ ] Phase C — Hook receiver + transcript tailer wiring
- [ ] Phase D — remaining views
- [ ] Phase E — AI Coach + Better prompt
- [ ] Phase F — ccprophet import + polish

## Layout

```
tokenflow/
├── backend/     # Python 3.11 + FastAPI + DuckDB
├── frontend/    # React 18 + TypeScript + Vite
├── SPEC.md      # what & why
├── DESIGN.md    # visual design system
└── README.md    # this file
```

## Quickstart (dev)

Prereqs: [`uv`](https://docs.astral.sh/uv/) for Python, Node.js 20+ for the frontend. `pip` is not supported — all Python workflows go through `uv`.

Two terminals:

```bash
# Terminal A — backend
cd backend
uv venv                      # creates .venv
uv pip install -e ".[dev]"
uv run tokenflow serve --dev
# → http://127.0.0.1:8765/api/system/health

# Terminal B — frontend
cd frontend
npm install                  # or pnpm install
npm run dev
# → http://localhost:5173 (proxies /api to backend)
```

## Tech

- **Backend**: FastAPI, uvicorn, DuckDB, watchdog, typer, rich, anthropic, pydantic v2
- **Frontend**: React 18, TypeScript (strict), Vite, TanStack Query v5, Zustand, Lucide React, CSS Variables (no Tailwind), direct SVG charts
- **Runtime**: 127.0.0.1:8765 local-only bind, SSE for real-time
- **Data**: ~/.tokenflow/events.duckdb (ccprophet schema V1–V5 compatible for import)

## License

MIT
