# Token Flow — Backend

Python 3.11 + FastAPI + DuckDB.

## Dev

Requires [`uv`](https://docs.astral.sh/uv/) for Python package management. `pip` is not supported.

```bash
cd backend
uv venv                        # create .venv
uv pip install -e ".[dev]"     # install into the uv-managed venv
uv run tokenflow serve --dev   # backend on :8765, expects Vite on :5173
```

Health check: `curl http://127.0.0.1:8765/api/system/health`

## Tests

```bash
uv run pytest
```

## Layout (hexagonal / clean architecture)

```
tokenflow/
├── domain/        # pure entities, values, services (stdlib only)
├── use_cases/     # application logic
├── adapters/
│   ├── hook/         # stdin event receiver
│   ├── transcript/   # JSONL tail (tokens)
│   ├── persistence/  # DuckDB
│   ├── coach/        # Anthropic SDK
│   └── web/          # FastAPI routes + SSE
└── harness/       # CLI entry + DI wiring
```

Migrations in `migrations/V1..V5.sql` inherited from ccprophet (schema-compatible for import).
