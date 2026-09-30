# Frontend

React 18 + TypeScript + Vite client for Veridian Payables. See the root
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
backend, default `http://localhost:8000/api/v1`.
