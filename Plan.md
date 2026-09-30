# Accounts Payable Invoice Processing and 3-Way Match Automation

Development plan for an end-to-end build. Every tool named here is free and open source, or has a free tier, as of 30 Sep 2026.

Working product name (placeholder, fictional): **Veridian Payables**. Rename freely.

---

## 0. Ground rules for the developer

1. Use professional wording everywhere: code, comments, commit messages, UI copy, docs, seed data. Do not mention AI assistants or AI tools by name in any repo artifact.
2. Never use the long dash character (U+2014) anywhere: code, docs, UI text, data. Use a hyphen, comma, colon or a new sentence. Add a CI check that fails the build if this character appears (`grep -rP "\x{2014}" --exclude-dir=node_modules --exclude-dir=.git .`).
3. Use `Decimal` for all money. Never `float`.
4. All configuration comes from environment variables. No secrets in git.
5. Every phase ends with its acceptance checks passing, tests green, and README updated.
6. Marketing numbers on the website and dashboard must come from real measured results in the demo data or be labeled "sample data". No invented claims, no real company logos, no fake certifications.
7. Interpretation note: AP has no sales revenue. The "revenue and analytics" requirement is delivered as a **Financial Performance dashboard**: spend, savings and leakage prevented, cash outflow, discounts captured, with 24 months of history.

---

## 1. Scope and target outcomes

Flow: invoice intake -> OCR and extraction -> validation -> 3-way match (invoice vs PO vs goods receipt) -> discrepancy flags -> approval routing -> payment release (simulated bank file) -> analytics.

Targets:

| Metric | Target |
|---|---|
| Header field extraction F1 (invoice no, date, vendor, total, PO ref) | >= 0.95 on held-out FATURA split |
| Line item extraction F1 | >= 0.85 |
| Injected anomaly detection recall / precision | >= 0.95 / >= 0.90 |
| Invoices needing an LLM call | <= 30 percent |
| Average LLM tokens per processed invoice (all invoices) | <= 400; per LLM-assisted invoice <= 1,500 |
| Match engine time per invoice | < 300 ms (excluding OCR) |
| Straight-through processing (clean match, auto-approved) on demo data | ~65 to 75 percent |

---

## 2. Technology stack (all free)

**Backend**
- Python 3.12, FastAPI, Uvicorn, Pydantic v2, pydantic-settings
- SQLAlchemy 2.0 (async), Alembic, psycopg 3 (or asyncpg)
- PostgreSQL 16 + **pgvector** (Docker image `pgvector/pgvector:pg16`)
- Background jobs: **Procrastinate** (Postgres-backed queue, no Redis needed). Fallback: custom worker using `SELECT ... FOR UPDATE SKIP LOCKED`
- Auth: `pwdlib[argon2]` (Argon2id), `PyJWT`, `slowapi` (rate limiting), `python-multipart`, `python-magic`
- Document handling: `pdfplumber` (MIT), `pypdfium2` (page rendering), `Pillow`, `img2pdf`, `opencv-python-headless` (deskew, denoise). Do not use PyMuPDF (AGPL).
- OCR: **RapidOCR (ONNX runtime, PaddleOCR models, Apache-2.0)** as primary, **Tesseract 5** as fallback. Run a bake-off on 200 invoices in Phase 4 and keep the higher field-level F1.
- Embeddings: **BAAI/bge-small-en-v1.5** (MIT, 384 dimensions) via `fastembed` (ONNX, CPU friendly). Alternative: `sentence-transformers/all-MiniLM-L6-v2` (Apache-2.0, 384 dimensions).
- Matching helpers: `rapidfuzz`, `scipy` (Hungarian assignment), `python-dateutil`, `babel`, `price-parser`
- LLM clients: `openai` SDK pointed at Groq (`https://api.groq.com/openai/v1`), `google-genai` SDK for Gemini, `tenacity` for retries, `httpx`
- Quality: `pytest`, `pytest-asyncio`, `hypothesis`, `ruff`, `mypy`, `bandit`, `pip-audit`, `pre-commit`, `structlog`

**Frontend**
- React 18, TypeScript, Vite, React Router
- Tailwind CSS + **shadcn/ui** (Radix primitives), `lucide-react` icons, `framer-motion`
- TanStack Query, TanStack Table, React Hook Form + Zod
- Charts: **Apache ECharts** (`echarts-for-react`). Covers combo, stacked area, treemap, sankey, heatmap, gauge, waterfall.
- Document viewer: `pdfjs-dist` plus custom canvas overlay for bounding boxes, `react-zoom-pan-pinch`
- Fonts (self-hosted via `@fontsource`): Inter (UI), Source Serif 4 (marketing headlines)
- Tests: Vitest, Testing Library, Playwright, axe-core (accessibility), Lighthouse CI

**Infra and tooling (free)**
- Docker + Docker Compose, GitHub Actions, Trivy (image scan), Gitleaks (secret scan)
- Optional free hosting: Neon (Postgres with pgvector), Render or Fly.io free allowances for API, Cloudflare Pages or Vercel hobby tier for the web app. Re-check current free-tier terms before choosing.

**LLMs (free tiers, both used with automatic switching)**
- Groq: model id `openai/gpt-oss-20b`. Text only. Free tier limits found in provider docs and third-party summaries: about 30 requests/min, 1,000 requests/day, **8,000 tokens/min**. The 8K tokens/min cap is the binding limit, so every call must stay small.
- Gemini API (Google AI Studio free key): default `gemini-2.5-flash-lite` (multimodal). Google no longer publishes fixed free-tier numbers and shows live limits per project in AI Studio, and limits and model names change often. Read limits from env vars, never hard-code them.
- Both are configured in `.env` (model ids, RPM, TPM, RPD). Re-verify at build time.

---

## 3. Architecture

```
React (Vite) --HTTPS--> FastAPI (REST, JWT cookies, RBAC)
                          |
                          +--> PostgreSQL 16 + pgvector (data, vectors, job queue, audit)
                          +--> Object store: local volume /data/files (encrypted-at-rest option)
                          +--> Worker process (Procrastinate)
                                 intake -> preprocess -> OCR -> rules extractor -> validator
                                        -> [LLM router: Groq | Gemini] only if needed
                                        -> embeddings -> vendor/PO/item resolution
                                        -> 3-way match engine -> exceptions -> approval routing
                                        -> analytics aggregates
```

Repository layout:

```
ap-automation/
  README.md
  docker-compose.yml
  .env.example
  Makefile
  docs/                 architecture.md, api.md, security.md, runbook.md, evaluation.md, images/
  dataset/              see section 4
  backend/
    app/ api/ core/ db/ models/ schemas/ services/ workers/ llm/ ocr/ extraction/ matching/ analytics/
    alembic/
    tests/
  frontend/
    src/ app/ components/ features/ pages/ lib/ styles/
    public/images/
  scripts/              seed, evaluate, export_demo
  .github/workflows/    ci.yml
```

---

## 4. Dataset section (dedicated)

### 4.1 Sources

| Purpose | Dataset | Location | License |
|---|---|---|---|
| Primary: invoice images + annotations | **FATURA** (10,000 invoices, 50 templates, 200 per template, 24 annotated classes, white-background and colored-background JPG sets, annotations in 3 formats: original, COCO, Hugging Face compatible) | https://zenodo.org/records/10371464 (DOI 10.5281/zenodo.10371464). File `FATURA2.zip`, 690.7 MB, md5 `4c9404462f22c5241eb1a290a02eb2a2` | CC BY 4.0 (credit the authors: Limam, Dhiaf, Kessentini) |
| Optional: scanned receipt robustness test | SROIE (ICDAR 2019) | Obtain from the official ICDAR 2019 competition page or a Hugging Face mirror. Check the terms before use. | Verify before use |
| Generated: linked business documents | Synthetic vendor master, item catalog, POs, goods receipts, historical payments | Produced by our generator (4.4) | Ours |

FATURA is synthetic and template-based, so it is cleaner than real inbox invoices. Add scan-like augmentation (4.5) to reduce that gap. FATURA has two evaluation strategies (same templates with new images, or unseen templates). Use the unseen-template split for the extraction evaluation to show generalization.

### 4.2 Folder structure

```
dataset/
  README.md                    provenance, license, citation, how to rebuild
  download_fatura.sh           curl + md5 check + unzip
  requirements.txt             generator dependencies
  raw/                         (gitignored) FATURA2 extracted here
  processed/
    truth_invoices.jsonl       canonical invoice ground truth per invoice_id
    template_index.csv         invoice_id, template_id, split
  synthetic/
    vendors.csv
    items_catalog.csv
    purchase_orders.csv
    po_lines.csv
    goods_receipts.csv
    gr_lines.csv
    payments_history.csv
    anomaly_labels.csv         invoice_id, anomaly_type, expected_reason_codes
    users_seed.csv
  demo/
    invoices/                  1,000 selected files (PDF and JPG mix)
    extraction_cache.jsonl     precomputed extraction results keyed by file hash
    manifest.json              counts, seed, generator version, checksums
  scripts/
    inspect_fatura.py
    build_truth.py
    generate_synthetic.py
    augment_scans.py
    select_demo_set.py
    load_to_db.py
    validate_dataset.py
```

Commit only `dataset/README.md`, scripts, `synthetic/*.csv`, `demo/manifest.json` and a 50-invoice sample. Keep `raw/` and the full demo image set out of git (use a release asset or the download script).

### 4.3 Download and prepare

1. `download_fatura.sh`: download `https://zenodo.org/records/10371464/files/FATURA2.zip?download=1`, verify md5, unzip into `dataset/raw/`. Zenodo can be slow, so support resume (`curl -C -`).
2. `inspect_fatura.py`: print the directory layout, one annotation per format, and the set of class names. **Do not assume key names. Read them from the files**, then document them in `dataset/README.md`.
3. `build_truth.py`: convert the original-format annotations into `truth_invoices.jsonl`:
   `invoice_id, template_id, vendor{name,address,email}, buyer{...}, invoice_no, invoice_date, po_reference (if present), currency, lines[{description, qty, unit_price, amount}], subtotal, tax, discount, total`.
   Parse lines from the item-table annotation text. Keep only invoices where arithmetic holds (sum of lines, tax, total within 0.02). Expect a subset. Log the drop rate by template.
4. `select_demo_set.py`: choose 1,000 invoices, about 20 per template across all 50 templates, seeded (`seed=42`). Reserve 2,500 other invoices (including 8 fully unseen templates) as the evaluation set. The demo set and evaluation set must not overlap.
5. Convert 60 percent of demo images to PDF (`img2pdf`); keep 40 percent as JPG.

### 4.4 Synthetic linked documents (drives the matching logic)

Because the invoice image content is fixed, the PO and receipt must be **derived from the extracted truth**, and anomalies are injected on the PO and receipt side or by re-submitting documents.

Generator rules (`generate_synthetic.py`, seeded, deterministic):

- **Vendor master**: one vendor per distinct FATURA seller (about 150 to 300 vendors), with normalized name, tax id, payment terms (Net 15/30/45/60), early-pay discount terms for about 20 percent (for example 2/10 net 30), bank account (fake, IBAN-like), risk tier, category.
- **Item catalog**: 300 to 500 SKUs across 8 categories (IT hardware, office supplies, logistics, professional services, facilities, marketing, raw materials, software). SKU, description, unit, standard price.
- **Purchase orders**: one PO per invoice with lines mirroring invoice truth (SKU assigned by best description match against the catalog). PO date 5 to 40 days before invoice date. Add 20 percent extra open POs with no invoice (for realistic tables).
- **Goods receipts**: one or two receipts per PO (partial deliveries supported), receipt date 1 to 15 days after PO and before invoice.
- **History**: distribute invoice, PO, receipt and payment dates across **24 months ending today**, with seasonality weights (higher volume at quarter ends), and payment lag consistent with terms. Older invoices are paid, recent ones are in various states.
- **Anomaly injection** with ground-truth labels in `anomaly_labels.csv`:

| Anomaly | How it is created | Share | Expected reason code |
|---|---|---|---|
| Clean match | PO and GRN equal invoice | 68% | none |
| Quantity short | GRN qty lower than invoice qty on 1 to 2 lines | 8% | QTY_OVER_RECEIVED |
| Price drift | PO unit price differs 3 to 15% from invoice price | 7% | PRICE_VARIANCE |
| Within-tolerance drift | Difference under 1% or under 1.00 | 4% | none (pass) |
| Duplicate exact | Same file uploaded again | 3% | DUPLICATE_EXACT |
| Duplicate near | Same invoice in the other background color set, or scan-augmented copy with edited invoice number formatting | 3% | DUPLICATE_SUSPECTED |
| Missing receipt | No GRN for the PO | 3% | QTY_NOT_RECEIVED |
| Partial receipt, invoiced in full | GRN covers 50 to 80% | 2% | QTY_OVER_RECEIVED |
| PO not found or closed | PO reference removed or status closed | 1% | PO_NOT_FOUND, PO_CLOSED |
| Vendor mismatch | PO issued to another vendor | 1% | VENDOR_MISMATCH |

### 4.5 Scan-like augmentation

`augment_scans.py` applies to 25 percent of demo files: small rotation (up to 2 degrees), Gaussian noise, JPEG compression, slight blur, contrast shifts, and page shadow. Keep the clean originals for accuracy comparisons.

### 4.6 Demo reliability

Precompute extraction for all 1,000 demo files in batch mode, throttled to free-tier limits, resumable across days. Store in `demo/extraction_cache.jsonl` keyed by SHA-256 of the file. In the demo, cached files return instantly, and only fresh uploads trigger live OCR and LLM calls. This keeps the demo fast and protects quotas.

### 4.7 Dataset validation (`validate_dataset.py`)

- Referential integrity across all CSVs
- Money arithmetic checks
- Anomaly shares within 1 point of the table above
- No overlap between demo and evaluation sets
- Date range covers 24 months
- Checksums match `manifest.json`

### 4.8 Loading

`load_to_db.py` bulk loads with `COPY`, then generates embeddings for vendors and catalog items in batches, then builds the HNSW indexes. Target: full load under 5 minutes.

---

## 5. Data model (PostgreSQL)

Enable: `CREATE EXTENSION vector; CREATE EXTENSION pg_trgm; CREATE EXTENSION pgcrypto;`

| Table | Key columns |
|---|---|
| users | id, email (unique), password_hash, full_name, role, approval_limit, is_active, mfa_secret_enc, last_login_at |
| refresh_tokens | id, user_id, token_hash, family_id, expires_at, revoked_at, ip, user_agent |
| vendors | id, code, name, name_normalized, tax_id, address, email, payment_terms_days, discount_pct, discount_days, risk_tier, category, status, embedding vector(384) |
| items | id, sku, description, unit, std_price, category, embedding vector(384) |
| purchase_orders | id, po_number (unique), vendor_id, currency, status, po_date, total |
| po_lines | id, po_id, line_no, item_id, description, qty, unit_price, amount, qty_invoiced_cum |
| goods_receipts | id, grn_number, po_id, received_date, received_by |
| gr_lines | id, grn_id, po_line_id, qty_received |
| documents | id, sha256 (unique), filename, mime, size, storage_path, page_count, uploaded_by, uploaded_at |
| invoices | id, document_id, vendor_id, invoice_no, invoice_date, due_date, currency, subtotal, tax, freight, discount, total, po_number_ref, status, extraction_confidence, dup_key, extracted_json |
| invoice_lines | id, invoice_id, line_no, sku, description, qty, unit_price, amount, bbox_json, embedding vector(384) |
| extraction_runs | id, invoice_id, stage_path (rules, llm_text, llm_vision), provider, model, tokens_in, tokens_out, latency_ms, cache_hit, errors_json |
| match_results | id, invoice_id, po_id, outcome, score, tolerance_policy_id, run_at |
| match_line_results | id, match_id, invoice_line_id, po_line_id, qty_inv, qty_po, qty_recv, qty_prev_invoiced, price_inv, price_po, qty_var, price_var_pct, status |
| exceptions | id, invoice_id, reason_code, severity, details_json, status, assigned_to, sla_due_at, resolved_by, resolution, resolved_at |
| tolerance_policies | id, scope (global, vendor, category), qty_pct, price_pct, price_abs, total_abs, tax_abs |
| approval_policies | id, min_amount, max_amount, reason_code (nullable), required_role, steps |
| approvals | id, invoice_id, step, approver_id, decision, comment, decided_at |
| payments | id, invoice_id, batch_id, amount, scheduled_date, released_at, status, method |
| payment_batches | id, created_by, released_by, total, file_path, status |
| audit_log | id, ts, actor_id, action, entity, entity_id, before_json, after_json, ip, hash_prev, hash_self |
| llm_usage | id, ts, provider, model, purpose, tokens_in, tokens_out, latency_ms, status, invoice_id |
| analytics_daily | date, vendor_id, category, invoices_count, value, exceptions_by_type_json, stp_count, savings_prevented, discounts_captured, discounts_missed |

Indexes:
- HNSW: `CREATE INDEX ON vendors USING hnsw (embedding vector_cosine_ops);` same for `items` and `invoice_lines`
- GIN trigram on `vendors.name_normalized`
- Unique `(vendor_id, invoice_no)`; index on `dup_key`, `invoices.status`, `exceptions.status`, `payments.scheduled_date`
- `audit_log` is append-only: revoke UPDATE and DELETE for the app role; each row stores a hash chained to the previous row.

---

## 6. Token-minimizing LLM strategy

Principle: **deterministic first, LLM last, smallest possible prompt, cache everything.**

1. **Zero-token paths** (about 70 percent of invoices): PDF text layer or OCR -> rules extractor -> arithmetic validation -> match -> done.
2. **Content hash cache**: SHA-256 of file and SHA-256 of normalized OCR text. Same input never reaches an LLM twice.
3. **One call per invoice at most** for extraction. No multi-turn chains.
4. **Send only what failed**: if header fields pass but the line table fails, send only the table region text. If header fails, send only the top 25 percent and the bottom totals block. Never send the full page unless needed.
5. **Compact prompt**: system prompt under 150 tokens, schema as a short type string (not verbose JSON Schema), OCR text stripped of empty lines and repeated whitespace, currency and numbers kept verbatim. Set `max_tokens` (600 for lines, 250 for header) and `temperature=0`. For `openai/gpt-oss-20b` set `reasoning_effort="low"` to cut hidden reasoning tokens (confirm the parameter in current Groq docs).
6. **Vision only as the last resort** (Gemini): when OCR confidence is under 0.6 or the text is nearly empty. Downscale to a max side of 1,024 px, grayscale, JPEG quality 70.
7. **No LLM in matching, routing, analytics or explanations.** Discrepancy explanations are rendered from templates using the numeric variances. Optional "Summarize this exception" button: on demand, under 300 tokens, cached per exception.
8. **Embeddings run locally** (fastembed), zero API tokens.
9. **Batching**: never batch invoices in one prompt (risks cross-contamination). Batch only when the same invoice has multiple failing regions.
10. **Budget guard**: `llm_usage` table plus in-memory counters. Stop at 90 percent of daily quota per provider and mark the invoice `needs_review` instead of failing.

Token budget per LLM-assisted invoice: prompt about 350 to 700, output about 200 to 500. Report actual averages on the analytics page.

### 6.1 Router design (`backend/app/llm/`)

- `LLMProvider` protocol: `async def extract(task, payload, schema) -> LLMResult` with `tokens_in`, `tokens_out`, `raw`, `latency_ms`.
- `GroqProvider` (text only) and `GeminiProvider` (text + vision).
- `Router` policy (configurable via env `LLM_PRIMARY=groq`, `LLM_SECONDARY=gemini`, plus an admin UI toggle):
  1. Vision task -> Gemini only.
  2. Text task -> primary if it has budget; otherwise secondary.
  3. On HTTP 429, 5xx, timeout or schema failure twice -> switch provider for this call, open a circuit breaker for that provider for 60 seconds (or the `retry-after` value).
  4. Respect provider limits with a token bucket for RPM and TPM and a daily counter for RPD, all values from env.
  5. Estimate tokens before sending (`tiktoken` cl100k approximation or char/4) and refuse oversize prompts by trimming.
- All outputs are validated with Pydantic. On failure: one repair retry that sends only the validation error and the previous output, then escalate to the other provider, then `needs_review`.
- Treat OCR text as untrusted input (prompt injection): the LLM has no tools, output is schema-constrained, and any field not matching the schema is discarded.

---

## 7. Security, authentication and authorization

**Authentication**
- Email + password, Argon2id hashing, password policy (12+ chars, breach-list check optional), lockout after 5 failures (exponential backoff), generic error messages.
- Short-lived JWT access token (15 min) and rotating refresh token (7 days) stored **hashed** in DB with token-family reuse detection. Both delivered as `HttpOnly; Secure; SameSite=Strict` cookies. CSRF protection with double-submit token header for state-changing requests.
- Optional TOTP MFA (`pyotp`) for approver and admin roles.

**Authorization (RBAC + attribute rules)**

| Role | Capabilities |
|---|---|
| admin | Users, policies, LLM settings, all data |
| ap_clerk | Upload, edit extraction, work exceptions up to their limit |
| approver | Approve or reject within `approval_limit` |
| finance_manager | Approvals above limits, payment batches, analytics |
| auditor | Read-only everywhere, audit log access |

- Enforce with FastAPI dependencies (`require_role`, `require_limit`). Deny by default.
- **Segregation of duties**: uploader cannot approve the same invoice; approver cannot release its payment; vendor bank detail changes require a second user.
- Object-level checks on every resource id.

**Data and platform security**
- TLS everywhere (Caddy or Nginx reverse proxy with auto certificates in deployment; self-signed in local compose).
- Field-level encryption for vendor bank accounts (`pgcrypto` or Fernet key from env). Files encrypted at rest with a key from env (optional).
- Upload safety: allow-list PDF, JPG, PNG; verify magic bytes, size limit (15 MB), page limit (20), reject encrypted or malformed PDFs, randomized storage names, optional ClamAV container scan.
- Strict Pydantic validation on all inputs, parameterized SQL only, security headers (CSP, HSTS, X-Content-Type-Options, Referrer-Policy), tight CORS, request size limits, rate limits per IP and per user.
- Append-only, hash-chained audit log for every state change and every login.
- Logging without PII or secrets; correlation ids on every request.
- Supply chain: `pip-audit`, `npm audit`, Trivy, Gitleaks in CI. Pin dependencies with lock files.
- Follow OWASP ASVS Level 2 and OWASP Top 10 as a checklist in `docs/security.md`.
- Backups: nightly `pg_dump` script and restore test in the runbook.

---

## 8. Phase-wise implementation

Each phase lists tasks, deliverables and acceptance criteria. Suggested duration assumes one full-time developer.

### Phase 0: Foundation (2 days)

Tasks
- Create the monorepo layout from section 3. Add `docker-compose.yml` with `db` (pgvector), `api`, `worker`, `web`, optional `clamav`.
- Backend skeleton: app factory, settings via `pydantic-settings`, structured logging, health endpoints (`/healthz`, `/readyz`), error handler returning a consistent problem-details format.
- Frontend skeleton: Vite + TypeScript + Tailwind + shadcn/ui, routing, API client with typed hooks, ESLint, Prettier.
- CI: lint, type check, unit tests, `pip-audit`, `npm audit`, Gitleaks, the long-dash check, Docker build.
- `Makefile`: `make up`, `make seed`, `make test`, `make demo`.
- `.env.example` with all variables in section 10.

Acceptance: `make up` starts every service; CI is green on an empty test suite.

### Phase 1: Dataset acquisition and synthetic data (4 days)

Tasks: implement everything in section 4, in order: download, inspect, truth build, demo/eval split, generator, augmentation, validation, `dataset/README.md`.

Deliverables: complete `dataset/` folder, `validate_dataset.py` passing, 1,000 demo invoices and 24 months of linked history.

Acceptance: validation script exits 0; anomaly shares match; a random sample of 20 invoices manually checked against their PO and GRN.

### Phase 2: Database, migrations and loading (2 days)

Tasks
- Alembic migrations for all tables in section 5, extensions, indexes, enums.
- Repository layer with SQLAlchemy models and Pydantic schemas (separate read and write schemas).
- `load_to_db.py` using `COPY`; embedding generation for vendors and items in batches of 64 with fastembed; HNSW index creation after load.
- Roles: `app_rw` (no DDL, no UPDATE/DELETE on `audit_log`), `app_ro` for analytics.

Acceptance: fresh database reaches full demo state with one command in under 5 minutes; vector query `ORDER BY embedding <=> :q LIMIT 5` returns the right vendor for 20 noisy names.

### Phase 3: Authentication and authorization backend (3 days)

Tasks
- Implement section 7: registration by admin only, login, refresh rotation, logout, password change, lockout, optional TOTP.
- `require_role`, `require_limit`, SoD checks, object-level guards.
- Rate limiting, security headers, CORS, CSRF.
- Audit log writer with hash chain and a verifier script.
- Seed users: admin, clerk, approver, manager, auditor (documented demo credentials, changed via env in any non-demo deployment).

Tests: role matrix tests for every endpoint, refresh token reuse detection, lockout, CSRF failures, audit chain verification.

Acceptance: security test suite green; unauthorized access attempts return 401 or 403 with audit entries.

### Phase 4: Document intake and OCR (4 days)

Tasks
- `POST /api/v1/invoices/upload` (multi-file), `GET /api/v1/invoices/{id}/document`. Validation per section 7, SHA-256 dedup (exact duplicate flagged immediately with reason DUPLICATE_EXACT and no processing cost).
- Preprocessing: PDF to images at 200 dpi (`pypdfium2`), deskew, denoise, contrast normalization (OpenCV). Detect PDF text layer first with `pdfplumber` and skip OCR when present.
- OCR service: RapidOCR primary, Tesseract fallback. Output normalized words `{text, bbox, conf, page}`, reconstruct lines and blocks by y-clustering.
- Job queue: `process_invoice(document_id)` with retries, idempotency, status transitions `uploaded -> ocr_done -> extracted -> matched -> ...`.
- Bake-off script: run both OCR engines on 200 evaluation invoices, compare word accuracy and downstream field F1, record in `docs/evaluation.md`.

Acceptance: 95 percent of clean FATURA pages produce OCR words with mean confidence above 0.85; median OCR time per page under 3 seconds on CPU.

### Phase 5: Extraction, validation and LLM router (6 days)

Tasks
1. **Pydantic schemas** (`InvoiceExtract`, `LineItem`) with `Decimal` money, ISO dates, currency codes, normalized invoice number, per-field `confidence` and `source` (`rules`, `llm_text`, `llm_vision`) and `bbox`.
2. **Rules extractor**:
   - Anchor-based header fields: label proximity search (Invoice No, Invoice Date, Due Date, PO, Total, Subtotal, Tax, Currency) using the OCR geometry.
   - Table detection: locate header row by keyword set (description, qty, price, amount), cluster columns by x-position, split rows by y-gaps, parse numbers with locale aware parsing.
   - Vendor block: top-of-page text near logo area plus email/tax id regex.
3. **Validator**: arithmetic checks (line qty x price = amount, sum lines = subtotal, subtotal + tax - discount = total, tolerance 0.02), date sanity (not future, due >= invoice date), required fields present, confidence threshold 0.8.
4. **LLM fallback** per section 6: build the minimal prompt, call router, validate, merge only the failing fields back into the rules result, record source per field.
5. **Extraction cache** (file hash and OCR-text hash) and preloaded demo cache.
6. **Evaluation harness** `scripts/evaluate_extraction.py`: field-level precision, recall, F1 versus `truth_invoices.jsonl`, split by template and by seen/unseen templates, tokens per invoice, LLM call rate. Output Markdown and JSON to `docs/evaluation.md`.
7. **Optional stretch**: fine-tuned LayoutLMv3 token classifier using FATURA Hugging Face format annotations. Note the model weights are non-commercial licensed, so keep it optional and off by default.

Acceptance: targets in section 1 met on the held-out set; LLM call share <= 30 percent; average tokens per invoice <= 400; router failover proven by a test that forces 429 on the primary.

### Phase 6: Embeddings and entity resolution (3 days)

Tasks
- Embedding service (`fastembed`, bge-small-en-v1.5), model loaded once per worker, batch size 64, L2 normalized.
- **Vendor resolution**: exact tax id, then trigram similarity (`pg_trgm`), then pgvector cosine on `name + address`. Accept if top score >= 0.90 and margin >= 0.05 over the second; otherwise create a `VENDOR_UNRESOLVED` review task.
- **PO resolution**: exact PO number (normalize case, spaces, prefixes), else candidate POs for the resolved vendor within 120 days, scored by total and line similarity.
- **Line to PO line mapping**: SKU exact, else description embedding cosine + `rapidfuzz` token set ratio, solved as a global assignment with the Hungarian algorithm, minimum score 0.75.
- Unit tests with noisy names (abbreviations, punctuation, casing, typos).

Acceptance: vendor resolution accuracy >= 98 percent, line mapping accuracy >= 95 percent on demo data.

### Phase 7: 3-way match and rules engine (5 days)

Rules run in this order, each producing zero or more `exceptions` with reason code, severity and numeric details.

1. **Duplicate check**: exact file hash; `(vendor_id, normalized invoice_no)`; near duplicate via same vendor + amount within 0.5 percent + date within 7 days + invoice number similarity >= 0.85 (`rapidfuzz`) + line embedding similarity. Exact -> BLOCKED. Suspected -> exception.
2. **Header checks**: PO exists and open, vendor matches PO vendor, currency matches, invoice date after PO date.
3. **Quantity check (3-way)**: `qty_invoiced_now <= qty_received_total - qty_previously_invoiced`, using cumulative invoiced quantity per PO line. Tolerance from policy (default 0 percent over). Missing GRN -> QTY_NOT_RECEIVED.
4. **Price check**: `abs(price_inv - price_po) / price_po`. Default policy: pass if within max(1 percent, 1.00 currency unit), warning up to 5 percent, exception above 5 percent. Also compare to vendor 6-month price history (SQL window) and flag drift above 10 percent even if PO matches.
5. **Totals and tax**: recompute from matched lines, tolerance 0.02; tax rate consistency versus vendor history.
6. **Terms check**: due date vs vendor payment terms; capture early-pay discount eligibility.
7. **Overall outcome**:
   - `AUTO_APPROVED`: no exceptions and amount <= auto-approve limit (default 5,000)
   - `EXCEPTION`: one or more exceptions
   - `BLOCKED`: exact duplicate, or PO closed and vendor mismatch

Design points
- Rules are pure functions over a `MatchContext` dataclass; each rule in its own module with unit tests, registered in a list so rules are easy to add.
- Policies loaded from `tolerance_policies` with precedence vendor > category > global.
- Idempotent re-run when a PO or GRN arrives late ("re-match" job).
- Each result stores the full numeric evidence so the UI and audit can reproduce it.

Acceptance: on the demo set, recall >= 0.95 and precision >= 0.90 against `anomaly_labels.csv` (report confusion matrix per reason code); property-based tests (Hypothesis) confirm Decimal arithmetic invariants and no false positive on within-tolerance cases.

### Phase 8: Exceptions, approval routing and payment release (4 days)

Tasks
- **Exception workflow**: statuses `open -> in_review -> resolved | escalated`; assignment rules by reason code; SLA timers by severity (high 4h, medium 1 business day, low 3 days).
- **Actions**: approve with override (mandatory reason), reject, request credit note, request corrected invoice, hold, reassign, add comment, re-match.
- **Approval routing** from `approval_policies`. Default matrix:

| Situation | Amount | Approver |
|---|---|---|
| Clean match | <= 5,000 | Auto |
| Clean match | > 5,000 | approver |
| Exception | <= 2,500 | ap_clerk with reason |
| Exception | <= 25,000 | approver |
| Exception | > 25,000 | finance_manager |
| Duplicate suspected | any | approver + finance_manager |

- Enforce SoD and `approval_limit`.
- **Payment scheduling**: pay on due date, or earlier when the early-pay discount is worth it (annualized return above a configurable hurdle, default 10 percent).
- **Payment batches**: create batch, review, release by a different user than the creator. Generate a bank-style CSV file per batch (simulated, no real bank connection). Status flow `scheduled -> released -> settled` (settle via a simulated job).
- Notifications: in-app only (bell menu). Optional email with local SMTP catcher (MailHog) in dev.

Acceptance: end-to-end scenario tests: clean invoice paid; price drift routed to approver; duplicate blocked; SoD violation rejected; audit log complete for each scenario.

### Phase 9: Analytics backend (3 days)

Tasks
- `analytics_daily` refresh job (nightly and after each batch), plus SQL views for drill-downs. Use materialized views where simpler.
- Endpoints under `/api/v1/analytics/*` with `from`, `to`, `granularity`, `vendor`, `category` filters, ETag caching, pagination for tables:
  - `kpis` (with previous-period comparison)
  - `volume-value-trend`
  - `spend-by-vendor`, `spend-by-category`
  - `exceptions-trend`, `exceptions-by-reason`
  - `stp-rate`, `cycle-time` (distribution and trend)
  - `aging` (0-30, 31-60, 61-90, 90+)
  - `cashflow-forecast` (next 90 days from scheduled payments)
  - `savings` (duplicates blocked, price drift prevented, over-receipt prevented, discounts captured, discounts missed)
  - `vendor-scorecards`
  - `workflow-funnel`
  - `exception-heatmap`
  - `llm-usage` (tokens by provider, calls avoided by rules, cache hit rate)
  - `extraction-accuracy` (from evaluation runs stored in DB)
- KPI definitions documented in `docs/analytics.md` (for example STP rate = auto-approved invoices / processed invoices; leakage prevented = sum of prevented overpayment amounts on resolved exceptions).
- CSV export endpoints.

Acceptance: each endpoint answers in under 300 ms on the 24-month dataset; totals reconcile with raw tables in tests.

### Phase 10: Frontend foundation and public website (6 days)

Goal: a public site that looks like a Fortune 100 enterprise software vendor, with a clear **Log in** entry point.

**Design system**
- Tokens: navy `#0B1F3A` (primary), blue `#1F5EFF` (accent), teal `#12B5A6` (success accent), slate neutrals, semantic colors for success, warning, danger. 8 px spacing grid, 12 column layout, max content width 1240 px, radius 8 to 12 px, subtle shadows.
- Typography: Source Serif 4 for marketing headlines, Inter for everything else. Clear scale (display 56, h1 44, h2 32, h3 24, body 16/18).
- Motion: restrained; fade and rise on scroll, animated counters, hover elevation; respect `prefers-reduced-motion`.
- Accessibility WCAG 2.2 AA: contrast, focus rings, keyboard navigation, aria labels, skip link.
- Performance: Lighthouse >= 90 on all four scores; images in WebP/AVIF with `srcset`, lazy loading, fonts self-hosted with `font-display: swap`.
- Responsive breakpoints 360, 768, 1024, 1280, 1536.

**Imagery (free)**: Unsplash or Pexels photos (finance teams, offices, warehouse and logistics, documents, modern workspaces) and open illustration sets (unDraw, Storyset). Keep credits in `docs/image-credits.md`. Hero and dashboard visuals are real screenshots of the built app (generate through a Playwright script) inside a device frame. No real brand logos: use neutral placeholder wordmarks for "customer" strips, labeled as illustrative.

**Global layout**
- Top utility bar (Support, Contact sales, language selector placeholder).
- Sticky main nav with the brand mark; menus: Platform (mega menu with icons and descriptions), Solutions, Resources, Company; right side: **Log in** (text link) and **Request a demo** (filled button). On mobile a full-screen drawer with the same links.
- Footer: 5 link columns, newsletter field (front-end only), social icons, legal links, copyright, small "Sample product for demonstration" notice.

**Home page sections, in order**
1. Hero: headline (for example "Every invoice matched, verified and paid with confidence"), 2-line subhead, primary CTA **Log in to the platform**, secondary **Watch the product tour** (opens a modal with a screen recording or animated walkthrough), dashboard screenshot on the right with floating stat cards.
2. Trust strip: 6 placeholder wordmarks with the line "Built for finance teams that process thousands of invoices a month".
3. Impact metrics band: 4 animated counters populated from real evaluation and demo statistics (extraction accuracy, exceptions caught, average cycle time reduction, invoices processed).
4. "How it works": four numbered steps (Capture, Extract, Match, Approve and pay) with icons and one small illustration each, connected by a line.
5. Interactive 3-way match preview: a static but polished side-by-side of Invoice, PO and Receipt with highlighted variances; toggle between "Price drift", "Short receipt", "Duplicate" scenarios.
6. Feature grid (8 cards): Document capture, Intelligent extraction, 3-way match, Exception workflow, Approval routing, Payment scheduling, Analytics, Audit trail.
7. Role-based value: tabs for AP Team, Controllers, Procurement, Internal Audit with three bullets and an image each.
8. Analytics showcase: large dashboard image with callouts.
9. Security and governance: 6 tiles (role-based access, encryption, audit trail, segregation of duties, data retention, secure uploads). Describe controls only; do not claim certifications.
10. Integrations: "Connect to your ERP" grid using generic icons (ERP, Bank file, Email inbox, SFTP, API) with status "Planned" where not built.
11. Customer stories: 3 cards clearly labeled "Illustrative scenario".
12. FAQ accordion (8 questions: accuracy, supported formats, what happens on mismatch, data security, deployment, integrations, LLM usage and data handling, pricing model).
13. Final CTA banner with **Log in** and **Request a demo**.

**Other public pages**: Platform overview, Solutions (by role and by industry), Security, Resources (article cards, 6 written posts about AP automation and 3-way match), About, Contact (form with validation, stored via API), Privacy, Terms, Cookie notice, 404 and 500 pages.

**Login page** (`/login`): split layout, brand panel with imagery on the left, form on the right (email, password, show/hide, remember device, forgot password link, MFA step when required), inline error states, loading state, link back to home. Demo credentials shown in a collapsible "Demo access" box for the sample deployment only (controlled by env flag).

Acceptance: every public route responsive and accessible; axe shows no serious violations; Lighthouse targets met; login flow works end to end with cookie auth.

### Phase 11: Authenticated application (8 days)

Shell: collapsible sidebar (grouped: Overview, Invoices, Exceptions, Approvals, Payments, Vendors, Purchase Orders, Receipts, Analytics, Settings, Audit), top bar with global search (vendors, invoices, POs), notifications bell, user menu, breadcrumbs, light and dark theme, role-aware menu items.

Pages

1. **Overview**: KPI cards (invoices today, awaiting review, exceptions open, due this week, savings this month), work queue shortcuts, recent activity, SLA-at-risk list.
2. **Invoices**: table (TanStack Table) with server-side sort, filter, search, column chooser, saved views, status chips; drag-and-drop multi-file upload panel with per-file progress and processing stage indicator (uploaded, OCR, extracting, matching).
3. **Invoice detail**: left: document viewer (zoom, pan, page nav, bounding box overlays that highlight the field selected on the right); right: extracted fields with confidence badges, source label (rules or LLM), inline edit with validation; tabs: Lines, Match result, Timeline, Audit.
4. **Exceptions queue**: filters by reason code, severity, vendor, assignee, SLA; bulk assign; severity and SLA badges; keyboard shortcuts.
5. **Exception resolution (3-way comparison)**: the signature screen.
   - Three aligned columns: Invoice, Purchase Order, Goods Receipt, with line rows aligned by the match mapping.
   - Variance highlighting per cell (quantity, unit price, amount), variance chips (for example "+8.2 percent price"), totals row, tolerance shown next to each check with pass/fail icons.
   - Right rail: reason codes, template-generated explanation, vendor price history sparkline, related invoices (duplicates), comments, actions (Approve override, Reject, Request credit note, Hold, Reassign, Re-match).
   - Side by side original document image toggle.
6. **Approvals inbox**: cards or table with amount, vendor, exception summary, approve/reject with comment; shows the user's limit.
7. **Payments**: upcoming schedule (calendar and table), discount opportunities, batch builder, release confirmation dialog with summary, download bank file, status tracking.
8. **Vendors**: list with risk tier and spend; vendor profile: contacts, terms, price history chart, exception rate, scorecard, documents.
9. **Purchase Orders and Receipts**: list and detail with linked invoices, receipt status, remaining quantities.
10. **Settings** (admin): users and roles, tolerance policies (form with live preview), approval matrix editor, **LLM providers** page (primary and secondary selection, live token and request usage against configured limits, provider health and circuit state, test call button), data retention.
11. **Audit log**: filterable, exportable, chain verification indicator.

Cross-cutting UI requirements: skeleton loaders, empty states with guidance, optimistic updates where safe, toast notifications, error boundaries, form validation with Zod, unsaved change guards, consistent table density, full keyboard access, timezone aware dates, currency formatting via `Intl.NumberFormat`.

Acceptance: Playwright tests cover login, upload, exception resolution, approval, payment release for the roles above; no console errors; SoD messages shown clearly.

### Phase 12: Analytics dashboard, Financial Performance (5 days)

Page `/analytics` with tabs: **Executive**, **Operations**, **Vendors**, **Savings and Cash**, **Platform**.

Global controls: date range picker (presets: 30d, 90d, YTD, 12m, 24m, custom), comparison toggle (previous period, previous year), vendor and category filters, export (CSV for tables, PNG for charts, print-friendly PDF via browser print styles).

**Executive tab**
- KPI cards with delta and sparkline: Invoice value processed, Invoices processed, Straight-through rate, Average cycle time, Leakage prevented, Discounts captured.
- Combo chart: monthly invoice value (bars) and count (line), 24 months.
- Cumulative savings area chart with annotations at milestones.
- Spend by category treemap and top 10 vendors bar.

**Operations tab**
- Workflow funnel (Sankey): received, extracted, matched, approved, paid, with drop-offs to exceptions.
- Exception rate stacked area by reason code, plus a table with drill-down to the queue.
- Cycle time histogram and trend; SLA compliance gauge.
- Exception heatmap by weekday and hour.

**Vendors tab**
- Scatter: exception rate vs spend, bubble size by invoice count, click to open the vendor.
- Vendor scorecard table with sparkline, price drift indicator, on-time rate.

**Savings and Cash tab**
- Waterfall: gross exposure -> duplicates blocked -> price variance prevented -> over-receipt prevented -> net savings.
- Discounts captured vs missed by month.
- Cash outflow forecast (next 90 days, stacked by due week) and AP aging buckets (stacked bars).

**Platform tab**
- Extraction accuracy over time (from stored evaluation runs), rules-only vs LLM-assisted share, cache hit rate.
- LLM tokens by provider and by day, calls avoided, average tokens per invoice, quota usage gauges.

Chart quality rules: consistent palette from design tokens, accessible color pairs, labeled axes with units, thousands separators and currency, tooltips with exact values and period comparison, legends that toggle series, responsive resizing, loading skeletons, empty and error states, downsample long series, ECharts theme file shared across all charts.

Acceptance: all charts render from real API data with 24 months of history; filters update every chart; totals on charts match table exports; no layout shift on load.

### Phase 13: Quality, evaluation and hardening (4 days)

- **Testing pyramid**: unit tests (rules, parsers, router), integration tests with Postgres in Docker (`testcontainers` or compose), API contract tests (schemathesis against the OpenAPI schema), end-to-end Playwright suite, load test with Locust (50 concurrent users on read endpoints, 10 concurrent uploads).
- **Coverage gate**: backend >= 80 percent, matching engine >= 95 percent.
- **Security pass**: run OWASP ZAP baseline against the running stack, `bandit`, Trivy, dependency audits; fix all high findings; document residual risks.
- **Evaluation report** `docs/evaluation.md`: OCR bake-off, extraction metrics by template and seen/unseen split, match confusion matrix, token usage summary, failover test results.
- **Observability**: request ids, structured logs, `/metrics` (Prometheus format) optional, Grafana optional.
- **Resilience**: worker crash recovery, job retries with backoff, idempotent reprocessing, graceful degradation when both LLMs are exhausted (fallback to rules-only with `needs_review`).

Acceptance: all gates above pass; report committed.

### Phase 14: Packaging, demo and documentation (3 days)

- **Demo mode**: `DEMO_MODE=true` loads the cache, seeds users and data, shows the demo access box on login.
- **Demo script** (`docs/demo_script.md`): a 10 minute walkthrough: login as clerk, upload a clean invoice (instant via cache), upload a price-drift invoice and open the 3-way comparison, resolve as approver, release a payment batch as manager, open analytics, show LLM usage page and the provider switch.
- **Deployment guide**: Docker Compose on a single VM; optional free hosting steps (Neon + Render + Cloudflare Pages) with environment variable mapping.
- **Backup and restore** scripts and test.
- **Final review checklist**: no long dash character, no AI tool names in the repo, no secrets, image credits complete, README complete.

Acceptance: a new developer can clone the repo and reach a running demo by following the README only.

---

## 9. README requirements (mandatory, professional)

The root `README.md` must be clear, current and polished. Required sections:

1. Title, one-line description, status badges (CI, license)
2. Screenshots or GIF of the dashboard, 3-way comparison and analytics
3. Problem statement and solution overview
4. Key features
5. Architecture diagram (Mermaid) and component descriptions
6. Technology stack table with versions and licenses
7. Prerequisites
8. Quick start: clone, `.env` setup, `make up`, `make seed`, open URLs, demo credentials
9. Dataset section: sources, licenses and citation, download and rebuild steps (link to `dataset/README.md`)
10. Configuration reference: every environment variable with default and meaning
11. LLM setup: getting free Groq and Gemini keys, how switching works, token-saving design, quota configuration
12. Matching rules and tolerance policy reference, reason code glossary
13. Roles and permissions matrix, security model summary
14. API overview with link to interactive docs at `/docs`
15. Analytics KPI definitions
16. Testing: how to run each suite
17. Evaluation results summary with link to `docs/evaluation.md`
18. Project structure
19. Deployment and backup
20. Troubleshooting (OCR install issues, Zenodo download resume, rate limit errors)
21. Contributing guidelines, code style, commit convention
22. License and third-party attributions (FATURA CC BY 4.0 citation, images, fonts, models)

Also maintain `docs/architecture.md`, `docs/api.md`, `docs/security.md`, `docs/analytics.md`, `docs/evaluation.md`, `docs/runbook.md`, `docs/demo_script.md`, `docs/image-credits.md`.

---

## 10. Environment variables (`.env.example`)

```
APP_ENV=development
DATABASE_URL=postgresql+psycopg://app_rw:change_me@db:5432/apdb
JWT_SECRET=change_me
ACCESS_TOKEN_MINUTES=15
REFRESH_TOKEN_DAYS=7
COOKIE_SECURE=false
CORS_ORIGINS=http://localhost:5173
FILE_STORAGE_PATH=/data/files
FIELD_ENCRYPTION_KEY=change_me
MAX_UPLOAD_MB=15

LLM_PRIMARY=groq
LLM_SECONDARY=gemini
GROQ_API_KEY=
GROQ_MODEL=openai/gpt-oss-20b
GROQ_RPM=30
GROQ_TPM=8000
GROQ_RPD=1000
GEMINI_API_KEY=
GEMINI_MODEL=gemini-2.5-flash-lite
GEMINI_RPM=10
GEMINI_TPM=250000
GEMINI_RPD=200
LLM_DAILY_BUDGET_STOP_PCT=90
LLM_MAX_TOKENS_HEADER=250
LLM_MAX_TOKENS_LINES=600

EMBEDDING_MODEL=BAAI/bge-small-en-v1.5
OCR_ENGINE=rapidocr
DEMO_MODE=true
AUTO_APPROVE_LIMIT=5000
```

Set the Gemini limits from the values shown in your own AI Studio project.

---

## 11. API surface (v1, prefix `/api/v1`)

| Area | Endpoints |
|---|---|
| Auth | `POST /auth/login`, `/auth/refresh`, `/auth/logout`, `/auth/mfa/verify`, `GET /auth/me` |
| Users (admin) | `GET/POST /users`, `PATCH /users/{id}` |
| Invoices | `POST /invoices/upload`, `GET /invoices`, `GET /invoices/{id}`, `PATCH /invoices/{id}/fields`, `POST /invoices/{id}/rematch` |
| Matching | `GET /invoices/{id}/match` (returns aligned invoice, PO and receipt lines with variances) |
| Exceptions | `GET /exceptions`, `GET /exceptions/{id}`, `POST /exceptions/{id}/actions` |
| Approvals | `GET /approvals`, `POST /approvals/{id}/decision` |
| Payments | `GET /payments`, `POST /payment-batches`, `POST /payment-batches/{id}/release`, `GET /payment-batches/{id}/file` |
| Master data | `GET /vendors`, `/vendors/{id}`, `/purchase-orders`, `/purchase-orders/{id}`, `/receipts` |
| Settings | `GET/PUT /settings/tolerances`, `/settings/approval-policies`, `/settings/llm` |
| Analytics | as listed in Phase 9 |
| Audit | `GET /audit`, `GET /audit/verify` |
| System | `/healthz`, `/readyz`, `/metrics` |

OpenAPI docs must be enabled at `/docs` in non-production and describe every schema and error.

---

## 12. Definition of done for the project

- All 15 phases accepted; targets in section 1 met and documented.
- Fresh clone to running demo using README only.
- No secrets in git, no long dash character, no AI tool names in any file.
- Demo shows: login, upload, extraction with highlights, 3-way comparison with variances, approval routing, payment release, and a 24 month analytics dashboard with real numbers.
