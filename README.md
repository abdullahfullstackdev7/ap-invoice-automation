# Veridian Payables

Accounts payable invoice processing and 3-way match automation: intake,
OCR and extraction, validation, 3-way match (invoice vs. purchase order vs.
goods receipt), exception handling, approval routing, simulated payment
release, and a financial performance dashboard.

Working product name (placeholder, fictional): **Veridian Payables**.

Build status: Phase 0 (foundation) and Phase 1 (dataset) in progress. See
`Plan.md` for the full phase-by-phase plan and `dataset/README.md` for
dataset rebuild status.

## Problem and approach

AP teams reconcile invoices against purchase orders and goods receipts by
hand. This project automates that reconciliation end to end, using rules
first and a small LLM call only when rules cannot resolve a field, so the
system stays fast, auditable and cheap to run. See `Plan.md` section 6 for
the token-minimizing LLM strategy.

## Technology stack

**Backend**: Python 3.12, FastAPI, SQLAlchemy 2.0 (async), Alembic,
PostgreSQL 16 with pgvector, Procrastinate for background jobs, RapidOCR
with Tesseract fallback, fastembed (BAAI/bge-small-en-v1.5), Groq and
Gemini free-tier LLM clients with automatic failover.

**Frontend**: React 18, TypeScript, Vite, Tailwind CSS, shadcn/ui, TanStack
Query and Table, Apache ECharts, pdfjs-dist.

**Infra**: Docker Compose, GitHub Actions CI (lint, type check, tests,
pip-audit, npm audit, Gitleaks, a long-dash character check, Docker build).

See `Plan.md` section 2 for the full stack table with license notes.

## Prerequisites

- Docker and Docker Compose
- Python 3.12 and [uv](https://docs.astral.sh/uv/) (backend, dataset scripts)
- Node.js 22 and npm (frontend)

## Quick start

```bash
cp .env.example .env       # edit secrets locally; never commit .env
make up                    # builds and starts db, api, worker, web
```

- API: http://localhost:8000 (interactive docs at `/docs` outside production)
- Web: http://localhost:5173
- Health checks: `GET /api/v1/healthz`, `GET /api/v1/readyz`

Database seeding (`make seed`), the demo export (`make demo`) and the
dataset rebuild (`make dataset`) are wired into the `Makefile` and are
implemented as each phase lands; see `Plan.md` section 8.

## Dataset

The invoice images come from FATURA (CC BY 4.0, Limam, Dhiaf, Kessentini).
Purchase orders, goods receipts, payment history and injected match
anomalies are generated synthetically from that ground truth. Full
provenance, license, citation and rebuild steps: `dataset/README.md`.

## Repository structure

```
ap-invoice-automation/
  README.md
  Plan.md
  docker-compose.yml
  .env.example
  Makefile
  docs/                 architecture, api, security, runbook, evaluation notes
  dataset/              FATURA download, synthetic data generator, validation
  backend/              FastAPI app, workers, tests
  frontend/             React app, tests
  scripts/              seed, evaluate, export_demo (added as each phase lands)
  .github/workflows/    ci.yml
```

## Development

```bash
make backend-install     # uv sync inside backend/
make frontend-install    # npm install inside frontend/
make lint                # ruff + eslint
make typecheck           # mypy + tsc
make test                # pytest + vitest
```

## Configuration reference

All configuration comes from environment variables; see `.env.example`
for the full list (database, JWT, LLM provider keys and rate limits,
embedding model, OCR engine, demo mode). No secrets are committed to git.

## Testing

- Backend: `cd backend && uv run pytest`
- Frontend unit/component: `cd frontend && npm run test`
- Frontend end-to-end: `cd frontend && npm run test:e2e` (Playwright)

## Project ground rules

See `Plan.md` section 0. Notably: `Decimal` for all money, never `float`;
no long dash character (U+2014) anywhere in the repo, enforced in CI; no
AI tool names in any repo artifact; every phase ends with green tests and
an updated README.

## Known environment constraints (development sandbox)

Verified so far in this environment: `docker compose up -d db` builds and
starts a healthy `pgvector/pgvector:pg16` container; the backend (`uv run
pytest`, `ruff`, `mypy --strict`, `bandit`) is green; the backend app runs
with `uvicorn` and answers `/api/v1/healthz` and `/api/v1/readyz` against
that database; the frontend (`npm run build`, `lint`, `typecheck`, `test`)
is green and the Vite dev server serves the app.

Two things are blocked by this sandbox's outbound network, not by the
code: the `api`/`worker` Docker images cannot finish `apt-get` during
`docker compose build` here, and `dataset/download_fatura.sh` cannot pull
the full 690.7 MB FATURA archive (sustained throughput has been on the
order of 8 to 20 KB/s, and long transfers get dropped mid-download). Both
Dockerfiles and the download script are otherwise complete and correct;
re-run them from a network with normal throughput to finish. See
`dataset/README.md` for the dataset side of this in detail.

## License and attributions

FATURA dataset: CC BY 4.0, credit Limam, Dhiaf, Kessentini. See
`dataset/README.md` for the full citation. Additional third-party
attributions (fonts, imagery, models) are tracked in
`docs/image-credits.md` as they are added.
