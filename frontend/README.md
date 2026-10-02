# Frontend

React 19 + TypeScript + Vite client for Veridian Payables. See the root
`README.md` for the full project overview and `Plan.md` for the build plan.

## Commands

```bash
npm install
npm run dev          # dev server on :5173
npm run build         # tsc -b && vite build
npm run lint          # eslint .
npm run typecheck     # tsc -b --noEmit
npm run test          # vitest run
npm run test:e2e      # playwright test
```

Set `VITE_API_BASE_URL` in `.env` (see `.env.example`) to point at the
backend, default `http://localhost:8000/api/v1`. `VITE_DEMO_MODE`
(default `true`) controls whether the login page shows the "Demo access"
credentials box; set it to `false` for a non-demo deployment.

`npm run test:e2e` starts its own dev server on port 5173 by default. If
that port is already taken (for example by another project's dev server
in a shared environment), set `PLAYWRIGHT_PORT` to use a different one:
`PLAYWRIGHT_PORT=5183 npm run test:e2e`.
