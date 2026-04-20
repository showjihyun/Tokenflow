# Token Flow — Frontend

React 18 + TypeScript strict + Vite.

## Dev

```bash
cd frontend
pnpm install
pnpm dev         # http://localhost:5173, proxies /api to 127.0.0.1:8765
```

Run the backend separately: `tokenflow serve --dev` (from `../backend`).

## Build

```bash
pnpm build       # outputs to dist/, served by backend when running in non-dev mode
```

## Layout

```
src/
├── views/          # LiveMonitor, Analytics, WasteRadar, AICoach, Replay, Settings, Onboarding
├── components/     # AppShell, Sidebar, Topbar (+ CSS co-located)
├── hooks/          # useSessionStream, useBudget, useWastes (Phase B)
├── api/            # client.ts — fetch wrappers
├── lib/            # fmt helpers, i18n
└── styles/         # tokens.css, base.css, theme.css
```

Design tokens live in `src/styles/tokens.css`; see `DESIGN.md` (repo root) for the full system.
