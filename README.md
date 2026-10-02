# Veridian Payables

Accounts payable invoice processing and 3-way match automation: intake,
OCR and extraction, validation, 3-way match (invoice vs. purchase order vs.
goods receipt), exception handling, approval routing, simulated payment
release, and a financial performance dashboard.

Working product name (placeholder, fictional): **Veridian Payables**.

Build status: Phase 0 (foundation), Phase 1 (dataset pipeline), Phase 2
(database, migrations and loading), Phase 3 (authentication and
authorization), Phase 4 (document intake and OCR), Phase 5 (extraction,
validation and the LLM router), Phase 6 (embeddings and entity
resolution), Phase 7 (3-way match and rules engine), Phase 8
(exceptions, approval routing and payment release), Phase 9 (analytics
backend) and Phase 10 (frontend foundation and public website) complete.
See `Plan.md` for the full phase-by-phase plan and `dataset/README.md`
for dataset rebuild status.

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

## 3-way match and rules engine (Phase 7)

`match_invoice`, chained automatically after entity resolution, runs the
duplicate check and five ordered rules over an immutable `MatchContext`
snapshot: duplicate (exact `vendor_id`+normalized `invoice_no`, then a
near-duplicate check combining `rapidfuzz` invoice-number similarity,
amount-within-0.5%, date-within-7-days and line embedding similarity),
header (PO exists and open, vendor and currency match, invoice date on
or after PO date), quantity (3-way: invoiced-to-date against received
minus previously-invoiced, missing goods receipt flagged as
`QTY_NOT_RECEIVED`), price (within `max(1%, $1)` passes, up to 5% is a
warning, above 5% or a >10% six-month vendor price drift is an
exception), totals and tax (recomputed from matched lines within 0.02,
tax rate checked against vendor history), and payment terms (due date
and early-pay discount eligibility). Each rule is a pure function
(`app/matching/rules/*.py`) tested in isolation; `app/matching/engine.py`
only orchestrates and decides the outcome - `AUTO_APPROVED` with no
exceptions, `BLOCKED` on an exact duplicate or any of
`PO_NOT_FOUND`/`PO_CLOSED`/`VENDOR_MISMATCH`, `EXCEPTION` otherwise - and
`app/matching/service.py` is the only layer that touches the database,
assembling the `MatchContext` from `Invoice`/`PurchaseOrder`/`POLine`/
`GRLine` rows. Tolerance policy lookup follows vendor > category >
global precedence (`app/matching/policy.py`). The match is safe to
re-run (a late-arriving PO or goods receipt can trigger a clean
re-match): an existing open exception with the same reason code is
never duplicated.

A hard `UNIQUE(vendor_id, invoice_no)` database constraint (added in
Phase 2) turned out to be incompatible with this phase's own duplicate
handling - a true duplicate invoice has to be persisted as its own row,
flagged `DUPLICATE_EXACT` and `BLOCKED`, not rejected by the database
before the match engine ever sees it. That constraint was replaced with
a plain non-unique index; `app/matching/duplicate.py` now owns exact
and near-duplicate detection at the application layer, which is also
where Plan.md's near-duplicate case lives in the first place.

Verified: 42 new tests (20 rule unit tests, 8 engine outcome tests, 14
Hypothesis property-based tests confirming Decimal-only arithmetic and
no false positive at or within each tolerance boundary, as required by
Plan.md section 7) plus a dedicated pipeline integration test
(`tests/test_matching_pipeline.py`) proving a clean invoice against a
received PO auto-approves, a >5% price variance raises a `PRICE_VARIANCE`
exception, and a missing goods receipt raises `QTY_NOT_RECEIVED` without
duplicating it on re-run - 170 backend tests green overall. `ruff`,
`mypy` and `bandit` are clean. `scripts/evaluate_matching.py` targets
the recall >= 0.95 / precision >= 0.90 acceptance criterion against
`dataset/processed/anomaly_labels.csv`; that file does not exist in this
environment (see `dataset/README.md`), so the script smoke-tests
`run_match()` directly against one synthetic case per labeled reason
code instead of claiming real recall/precision numbers (see
`docs/evaluation.md`).

## Exceptions, approval routing and payment release (Phase 8)

`route_invoice`, chained automatically after a non-blocked match, applies
Plan.md section 8's default approval matrix: a clean match at or under
`AUTO_APPROVE_LIMIT` (default $5,000) skips human approval entirely and
goes straight to payment scheduling; everything else - an exception, or
a clean match over the limit - waits for the role
`app/services/approval_routing.py` computes, with a notification sent to
every active user in that role (the in-app bell menu,
`app/models/notifications.py`). The matrix itself lives in the
`approval_policies` table (seeded by `scripts/seed.py`) with amount and
reason-code lookup and a two-step `approver` then `finance_manager`
override for `DUPLICATE_SUSPECTED`, falling back to a hardcoded copy of
the same matrix if no row matches, so routing degrades safely rather
than silently approving.

The exceptions queue (`app/api/exceptions.py`) supports every action
Plan.md lists - approve with a mandatory reason, reject, request a
credit note, request a corrected invoice, hold, reassign, add a comment,
and re-match (re-runs `match_invoice`, which is idempotent by design
since Phase 7) - plus SLA timers set at exception-creation time (high 4h,
medium next business day, low 3 days) and a default assignee role by
reason code (header-level problems to `approver`, line-level variances to
`ap_clerk`). Approval itself (`app/services/approvals.py`) is shared
between the exceptions queue's "approve" action and the dedicated
`/invoices/{id}/approvals/decision` endpoint, and enforces segregation of
duties on every decision: the invoice's uploader can never approve it,
regardless of role or amount fit, using the same `forbid_same_actor`
helper Phase 3 built for refresh-token reuse detection.

Payment scheduling (`app/services/payment_scheduling.py`) pays on the due
date unless an early-pay discount clears an annualized-return hurdle
(default 10%, `EARLY_PAY_DISCOUNT_HURDLE_PCT`) using the standard AP
formula `[discount% / (100% - discount%)] * [365 / (net_days -
discount_days)]`. Payment batches (`app/api/payments.py`) bundle
scheduled payments, generate a simulated bank-file CSV
(`app/services/payment_batch.py`, no real bank connection), and enforce
the same SoD rule on release: the batch's creator can never release it.
Settlement (`settle_payment_batch`) runs as a follow-up job so `released`
and `settled` are distinct, auditable moments.

Verified: the four acceptance scenarios Plan.md section 8 names end to
end against the real dockerized Postgres - a clean invoice auto-approves
and is paid through a full batch create/release/settle cycle; a price
drift lands in the approver's queue and is approved; an exact-duplicate
invoice is blocked with no approval routing or payment ever created; and
an uploader attempting to approve their own invoice is rejected with 403
even though their role and approval limit would otherwise qualify - plus
unit tests for every approval-routing tier, every exception action, SLA
timers (including the weekend-skipping medium tier), default assignment
by reason code, and the early-pay discount formula's edge cases (no
discount terms, a thin discount below the hurdle, a discount date on or
after the due date). `ruff`, `mypy` and `bandit` are clean.

## Analytics backend (Phase 9)

Seventeen read endpoints under `/api/v1/analytics/*` (admin,
finance_manager and auditor only, per the RBAC table), all scoped by
`date_from`/`date_to` (default: trailing 30 days) and optionally by
`vendor_id`/`category`: `kpis` (with previous-period comparison),
`volume-value-trend`, `spend-by-vendor`, `spend-by-category`,
`exceptions-trend`, `exceptions-by-reason`, `stp-rate`, `cycle-time`
(distribution and trend), `aging`, `cashflow-forecast`, `savings`
(duplicates blocked, price drift prevented, over-receipt prevented,
discounts captured/missed), `vendor-scorecards`, `workflow-funnel`,
`exception-heatmap`, `llm-usage` and `extraction-accuracy`. Every
response carries a content-hash `ETag`; a matching `If-None-Match` gets a
`304` with no body. List-shaped endpoints take `?format=csv` for a CSV
export and `limit`/`offset` pagination where the result is a ranked
table. KPI and metric definitions are in `docs/analytics.md`.

`analytics_daily` (a `(date, vendor_id, category)` rollup from Phase 2's
schema) is refreshed by `refresh_analytics_daily_task`
(`app/analytics/refresh.py`), deferred nightly at 02:00 via
Procrastinate's native `@periodic(cron=...)` support and again after
every payment batch settles; `kpis`, `volume-value-trend` and
`spend-by-*` read it for speed, while everything else (reason codes,
cycle-time, aging, heatmaps, ...) reads the raw tables directly since
their grain doesn't fit a daily rollup. Dollar amounts for "savings
prevented" are read back from the numeric evidence the match engine
already writes into each exception's `details_json` (Phase 7), not
re-derived or guessed. A column Phase 7/8 didn't need -
`exceptions.opened_at` - was added here (with a migration) because
trend and heatmap analysis have no other reliable per-exception
timestamp to group by.

`extraction-accuracy` serves the latest
`docs/evaluation_extraction.json` / `docs/evaluation_matching.json`
files rather than a DB table: Plan.md section 9 says this data should
come "from evaluation runs stored in DB", but no such table exists in
section 5's schema, and adding one for a single read-only endpoint
wasn't worth the schema churn.

Verified: 23 new backend tests - reconciliation tests proving
`analytics_daily`'s refresh matches hand-computed totals from the raw
tables (invoice counts, value, STP count, price-variance savings down to
the cent, discount capture/miss by due-date comparison), correctness
tests for the raw-table endpoints (aging buckets, cashflow-forecast
weekly bucketing, exceptions-by-reason percentages, workflow funnel,
savings breakdown), and API tests for the RBAC matrix, ETag 304
behavior, CSV export and pagination - 243 backend tests green overall.
`ruff`, `mypy` and `bandit` are clean. The acceptance target ("each
endpoint answers in under 300ms on the 24-month dataset") has not been
measured against a real 24-month dataset, since the FATURA-derived
dataset has not finished downloading in this environment (see
`dataset/README.md` and `docs/analytics.md`'s "Known limitations"
section for the honest caveat).

## Frontend foundation and public website (Phase 10)

A full public marketing site and a real login flow, built on the
existing React 19 + Vite + Tailwind v4 scaffold: a sticky nav with a
Platform mega menu, Solutions and Company dropdowns and an accessible
mobile drawer; a footer with five link columns; and the 13-section home
page Plan.md section 10 specifies in order - hero, trust strip, four
animated impact-metric counters, a four-step "how it works", an
interactive 3-way match preview (toggle between price drift, short
receipt and duplicate scenarios), an 8-card feature grid, role-based
value tabs (AP team, controllers, procurement, internal audit), an
analytics showcase, a 6-tile security and governance section, an
integrations grid (status "Planned" where not built), three
illustrative-labeled customer stories, an 8-question FAQ accordion and a
final CTA banner. `/platform`, `/solutions`, `/security`, `/resources`
(with 6 real written articles and a detail page), `/about`, `/contact`,
`/privacy`, `/terms`, `/cookies`, a 404 and a 500 page round out the
public routes.

The `/login` page is wired to the real backend: email/password,
show/hide password, an MFA step when the account has one enabled,
inline validation and loading states, and a collapsible "Demo access"
box (env-flagged via `VITE_DEMO_MODE`) listing the seeded demo accounts.
A successful login lands on `/app`, a placeholder that calls `GET
/auth/me` to prove cookie auth end to end - Phase 11 builds the real
authenticated shell behind it. The Contact page's form validates
client-side and posts to a new `POST /api/v1/contact` backend endpoint
(public, rate-limited, stores to a `contact_submissions` table) rather
than only pretending to submit.

**No external images were used.** Plan.md section 10 asks for
Unsplash/Pexels photography, unDraw/Storyset illustrations and a real
Playwright-captured screenshot of the running app. This sandbox cannot
reach external image services, and no seeded, screenshot-ready instance
of the app was running to capture from, so every visual is instead a
CSS/SVG construction - `lucide-react` icons, gradients, and a
hand-built "dashboard mockup" component explicitly commented in the
source as a documented stand-in. See `docs/image-credits.md` for the
full explanation and what to swap in given network access.

Verified: an axe-core scan (via Playwright) of every public route plus
the 404 page shows zero serious or critical violations - the first scan
surfaced four real WCAG AA color-contrast failures (the warning/success/
danger semantic tokens, a teal used as text, and several light-gray
captions), all fixed in `src/index.css` and the affected components, not
just loosened in the test. 18 Playwright e2e tests (navigation, the mega
menu, the FAQ accordion, login validation, the 404 page, and the
accessibility scans) and 9 Vitest component tests (accordion toggle
state, mobile drawer open/close, login validation/submission/MFA-step/
demo-panel behavior) are green; `eslint`, `tsc` and `prettier` are
clean; `vite build` succeeds. Lighthouse's >= 90 score targets have not
been measured - this sandbox has no way to run a real Lighthouse pass -
so that acceptance item is unverified rather than falsely claimed.

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
