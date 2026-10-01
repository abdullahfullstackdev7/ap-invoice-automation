# Veridian Payables

Accounts payable invoice processing and 3-way match automation: intake,
OCR and extraction, validation, 3-way match (invoice vs. purchase order vs.
goods receipt), exception handling, approval routing, simulated payment
release, and a financial performance dashboard.

Working product name (placeholder, fictional): **Veridian Payables**.

Build status: Phase 0 (foundation), Phase 1 (dataset pipeline), Phase 2
(database, migrations and loading), Phase 3 (authentication and
authorization), Phase 4 (document intake and OCR), Phase 5 (extraction,
validation and the LLM router) and Phase 6 (embeddings and entity
resolution) complete. See `Plan.md` for the full phase-by-phase plan and
`dataset/README.md` for dataset rebuild status.

## Authentication and authorization (Phase 3)

Email/password login with Argon2id hashing, 15-minute JWT access tokens
and rotating 7-day refresh tokens, all delivered as `HttpOnly` cookies.
Refresh tokens are stored hashed with per-family reuse detection: replaying
a rotated-out token revokes the whole session family. Double-submit CSRF
protection on every state-changing request. Lockout after 5 failed logins
with exponential backoff. Optional TOTP MFA for admin/approver roles.
RBAC via `require_role`/`require_limit` FastAPI dependencies, deny by
default. Every access denial (401/403) and every login/logout/password
change writes a hash-chained, append-only `audit_log` entry; `app_rw`
cannot UPDATE or DELETE it at the database level. Verify the chain with
`make verify-audit` or `GET /api/v1/audit/verify`.

Endpoints: `POST /auth/login`, `/auth/refresh`, `/auth/logout`,
`/auth/mfa/verify`, `/auth/password/change`, `GET /auth/me`;
`GET/POST /users`, `PATCH /users/{id}`, `POST /users/{id}/mfa/enable`
(all admin-only except `GET /users` which auditors can also read);
`GET /audit`, `GET /audit/verify` (admin/auditor).

Demo credentials (change via `SEED_<ROLE>_PASSWORD` env vars outside a
demo deployment): `admin@veridianpayables.demo`,
`clerk@veridianpayables.demo`, `approver@veridianpayables.demo`,
`manager@veridianpayables.demo`, `auditor@veridianpayables.demo`, all with
password `ChangeMe123Demo!`. Seed them with `make seed`.

Verified: 34 tests green against the real dockerized Postgres, covering
the full role matrix on `/users` and `/audit`, refresh-token rotation and
reuse detection (with family revocation confirmed at the database level),
lockout after 5 failures, CSRF rejection and success paths, and audit
chain tamper detection (including a test that `app_rw` genuinely cannot
UPDATE `audit_log`, a database-level permission error, not just an
application check).

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

`make up` also applies Alembic migrations (`make migrate`) against the
database. Load the synthetic dataset with `make load-data` once
`dataset/synthetic/*.csv` exists (see `dataset/README.md`). Database
seeding of demo users (`make seed`), the demo export (`make demo`) and the
FATURA rebuild (`make dataset`) are wired into the `Makefile` and are
implemented as each phase lands; see `Plan.md` section 8.

## Database

Schema and migrations: `backend/alembic/`, SQLAlchemy 2.0 models under
`backend/app/models/`, Pydantic read/write schemas under
`backend/app/schemas/`, a thin repository layer (including vendor/item
pgvector similarity search) in `backend/app/db/repository.py`.

Three Postgres roles, matching Plan.md section 5 and 7:

| Role | Used by | Rights |
|---|---|---|
| `apdb_admin` | Alembic migrations only (`DATABASE_ADMIN_URL`) | Owns the schema, full DDL |
| `app_rw` | API and worker at runtime (`DATABASE_URL`) | SELECT/INSERT/UPDATE/DELETE on business tables; INSERT/SELECT only on the append-only `audit_log` (no UPDATE/DELETE); no DDL |
| `app_ro` | Analytics (`DATABASE_RO_URL`) | SELECT only, all tables |

`apdb_admin` is the Postgres bootstrap user (`POSTGRES_USER` in
`docker-compose.yml`); `app_rw` and `app_ro` are created by the
`create app roles and grants` migration and are never used to run DDL.

## Dataset

The invoice images come from FATURA (CC BY 4.0, Limam, Dhiaf, Kessentini).
Purchase orders, goods receipts, payment history and injected match
anomalies are generated synthetically from that ground truth. Full
provenance, license, citation and rebuild steps: `dataset/README.md`.

## Document intake and OCR (Phase 4)

`POST /api/v1/invoices/upload` accepts multiple files (PDF/JPG/PNG,
admin or ap_clerk only). Each file is validated (magic bytes, 15 MB size
limit, 20-page limit, malformed/encrypted PDF rejection) before anything
is written to disk, stored under a randomized name (never the client's
filename), and hashed with SHA-256: an exact duplicate is flagged
immediately (`status: "duplicate_exact"`) with no storage write and no
OCR job, per Plan.md section 4.3. A new upload creates a `documents` row
and an `invoices` row (`status: uploaded`) and enqueues the
`process_invoice` Procrastinate job (Postgres-backed queue, no Redis).

That job: detects a PDF's existing text layer with pdfplumber and skips
OCR entirely when one is present; otherwise renders pages at 200 DPI
(pypdfium2), deskews/denoises/normalizes contrast (OpenCV), and runs
RapidOCR (primary) with a Tesseract fallback when RapidOCR's mean
confidence is low. Words are reconstructed into lines by y-coordinate
clustering. The job is idempotent (a retry or duplicate enqueue is a
no-op once the invoice has moved past `uploaded`) and transitions
`invoices.status` to `ocr_done`, storing OCR output in
`invoices.extracted_json` and a latency/engine record in
`extraction_runs`.

`GET /api/v1/invoices/{id}` and `GET /api/v1/invoices/{id}/document`
(any authenticated role) return the invoice record and the stored file.

Run the bake-off comparing RapidOCR and Tesseract on the evaluation set
with `make ocr-bakeoff`; results are written to `docs/evaluation.md`.
Real FATURA-based numbers are pending the dataset download (see below);
a synthetic smoke test is documented there instead, and it exercised the
same acceptance metrics Plan.md targets (mean word confidence, time per
page).

Verified: 62 backend tests green, including upload validation (size,
mime allow-list, malformed/oversized/too-many-pages PDF rejection), the
full upload role matrix, exact-duplicate detection, OCR line
reconstruction, PDF text-layer skip-detection, and the `process_invoice`
job's status transition and idempotency, run against the real dockerized
Postgres and a real OCR engine (RapidOCR) on genuinely readable synthetic
invoice images (98%+ mean confidence).

## Extraction, validation and the LLM router (Phase 5)

`extract_invoice_fields`, chained automatically after OCR, runs a rules
extractor over the OCR word/line geometry: anchor-based label-proximity
search for header fields (invoice number, dates, PO reference, totals),
x-position column clustering for the line-item table, and a top-of-page
plus regex pass for the vendor block (name, email, tax id). A validator
then checks line and total arithmetic (tolerance 0.02), date sanity, and
required-field presence, and flags any field below a 0.8 confidence
threshold.

Only fields the rules extractor couldn't produce confidently are sent to
an LLM (`app/llm/router.py`): Groq (`openai` SDK against Groq's
OpenAI-compatible endpoint) as primary, Gemini as secondary and the only
vision-capable option. The router fails over to the secondary on
429/5xx/timeout, retrying the same provider once first; two consecutive
failures open a 60-second circuit breaker for that provider. A schema
validation failure gets one repair retry (previous output plus the
validation error) before escalating to the next provider. RPM/TPM are
tracked in-process; RPD is checked against the `llm_usage` table and
capped at 90% of the configured daily quota. Every attempt, success or
failure, is logged to `llm_usage` and `extraction_runs`.

An extraction cache keyed on the SHA-256 of normalized OCR text (stored
in `invoices.dup_key`) means a re-scanned or re-submitted copy of an
already-extracted invoice reuses that result instead of re-running rules
or an LLM call.

Verified: 108 backend tests green, including rules-extractor accuracy
against real RapidOCR output (header fields, vendor block, table column
assignment), the full validator (arithmetic, date sanity, confidence
thresholds), and the LLM router's failover, circuit breaker, repair
retry, vision-only routing and budget gating - proven with fake
providers implementing the same protocol as Groq/Gemini, including the
specific acceptance scenario of forcing a 429 on the primary and
confirming failover to the secondary. `scripts/evaluate_extraction.py`
was smoke-tested against a synthetic fixture (1.0 precision/recall/F1 on
header fields); real FATURA-based numbers are pending the dataset
download, same as the OCR bake-off. No GROQ/GEMINI API keys are
configured in this environment, so the real providers have not made a
live network call here; the router logic itself does not depend on that
and is fully covered.

## Embeddings and entity resolution (Phase 6)

`resolve_invoice_entities`, chained automatically after extraction,
resolves each extracted invoice against existing vendor and purchase
order master data. Vendor resolution tries exact tax id first, then
Postgres trigram similarity (`pg_trgm`) on the normalized name, then
pgvector cosine similarity on name plus address embedding (local,
`fastembed`/BAAI/bge-small-en-v1.5, no API tokens); a candidate is only
accepted if its score clears 0.90 and beats the runner-up by at least
0.05, so an ambiguous or low-confidence match is left for a human
reviewer (a `VENDOR_UNRESOLVED` exception row) rather than guessed. PO
resolution tries the normalized PO number first (case/space/prefix
insensitive), then scores open POs for the resolved vendor within a
120-day window by total-amount closeness and line-description overlap.
Invoice lines are mapped to PO lines by exact SKU first, then a single
globally optimal assignment (`scipy.optimize.linear_sum_assignment`,
the Hungarian algorithm) over a combined description-embedding-cosine
and `rapidfuzz` token-set-ratio score, with a 0.75 minimum - a real fix
over greedy nearest-match, which can grab a locally-best pair at the
cost of a worse overall assignment.

Verified: 129 backend tests green, including vendor resolution across
realistic case/punctuation/whitespace OCR noise (the >= 98% accuracy
target), a dedicated test proving that genuine character-level noise
(a dropped or substituted letter - trigram ~0.71-0.84, embedding
~0.81-0.89 for the exact strings measured) correctly falls through to
`VENDOR_UNRESOLVED` rather than risking a wrong vendor match, PO exact
and candidate-scoring resolution (including a 120-day window boundary
test), and line mapping (SKU priority, global-vs-greedy assignment,
unmatched lines on both sides). The full pipeline (upload through OCR,
extraction and resolution) is proven end to end against a seeded
vendor/PO/PO-line fixture and the real dockerized Postgres.

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
is green and the Vite dev server serves the app. `alembic upgrade head`
creates the full 23-table schema plus the `app_rw`/`app_ro` roles; the
role boundaries were checked directly (`app_rw` insert/select works, DDL
and `audit_log` UPDATE/DELETE are denied; `app_ro` select-only works,
insert is denied). `load_to_db.py` was run against a small synthetic
fixture (20 vendors, not committed): full load completed in under 3
seconds once the embedding model was cached, and an HNSW cosine-distance
query (`ORDER BY embedding <=> :q LIMIT 5`) returned the correct vendor
as the top match for all 20 noisy name variants tested.

Two things are blocked by this sandbox's outbound network, not by the
code: the `api`/`worker` Docker images cannot finish `apt-get` during
`docker compose build` here, and `dataset/download_fatura.sh` cannot pull
the full 690.7 MB FATURA archive (sustained throughput has been on the
order of 8 to 20 KB/s, and long transfers get dropped mid-download). Both
Dockerfiles and the download script are otherwise complete and correct;
re-run them from a network with normal throughput to finish. See
`dataset/README.md` for the dataset side of this in detail.

A third, smaller one: this sandbox has no `tesseract` binary on `PATH`
(the backend Docker image installs it via apt, but that image can't
finish building here for the network reason above). RapidOCR, the
primary engine, needs no system binary and was verified directly,
including the full upload-to-OCR pipeline. `app/ocr/tesseract_engine.py`
was written against pytesseract's documented API and exercised structurally
(it raises the expected `TesseractNotFoundError` when the binary is
missing, which is what surfaced this gap), but has not been run against
real output in this sandbox. Install `tesseract-ocr` locally, or build
the Docker image on a normal network, to verify it directly; CI installs
it via apt and runs the full suite against both engines.

## License and attributions

FATURA dataset: CC BY 4.0, credit Limam, Dhiaf, Kessentini. See
`dataset/README.md` for the full citation. Additional third-party
attributions (fonts, imagery, models) are tracked in
`docs/image-credits.md` as they are added.
