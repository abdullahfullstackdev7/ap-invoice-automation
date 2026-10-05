# Evaluation

## OCR engine bake-off (Phase 4)

Acceptance target (Plan.md section 8, Phase 4): on clean FATURA pages, 95%
of pages should produce OCR words with mean confidence above 0.85, and
median OCR time per page should be under 3 seconds on CPU.

**Status: smoke-tested, not yet run against the real evaluation set.** The
FATURA archive has not finished downloading in this environment (see
`dataset/README.md`, "Known constraint: FATURA download speed"), so
`dataset/processed/truth_invoices.jsonl` does not yet exist with real
data. `scripts/ocr_bakeoff.py` was verified end to end against a 10-image
synthetic fixture built the same way `dataset/scripts/generate_synthetic.py`
and prior phases' smoke tests were: real, readable text rendered with
PIL, not blank placeholders, so RapidOCR has something genuine to
recognize. That fixture was deleted after the run; it was never part of
the committed dataset.

Smoke-test result (10 synthetic pages, RapidOCR only):

| Engine | Mean word confidence | Median time/page | Field presence rate |
|---|---|---|---|
| RapidOCR | 0.982 | 2.845s | 0.950 |
| Tesseract | unavailable | unavailable | unavailable |

Mean confidence (0.982) clears the 0.85 target comfortably. Median time
per page (2.845s) is close to the 3s target but the sample is only 10
pages on CPU, including RapidOCR's one-time ONNX model load on the first
call in the process (`rapidocr_engine.py` caches the loaded model with
`@lru_cache`, so only the very first page in a worker process pays that
cost) - with only 10 samples the median can still be pulled toward that
cold-start page. Re-run with the full 200-page eval set once it exists to
get a stable median.

Tesseract was not installed in this sandbox (no system binary; `which
tesseract` finds nothing here). `scripts/ocr_bakeoff.py` handles this by
skipping the Tesseract column rather than failing, and the code path
itself (`app/ocr/tesseract_engine.py`) is exercised by
`tests/test_ocr_service.py`'s fallback logic whenever RapidOCR confidence
is low; the backend Docker image installs `tesseract-ocr` via apt, so a
real bake-off with both engines should be run there, or on a machine with
Tesseract installed, once the real eval set is available.

### Rebuilding this report with real data

```bash
bash dataset/download_fatura.sh          # resume until it fully completes
cd dataset && python scripts/inspect_fatura.py && python scripts/build_truth.py
cd ../backend && uv run python -m scripts.ocr_bakeoff
```

This overwrites the "OCR engine bake-off" section of this file in place.

## Extraction accuracy (Phase 5)

Acceptance target (Plan.md section 1): header field F1 >= 0.95 on the
held-out FATURA split, line item F1 >= 0.85, LLM call share <= 30% of
invoices, average tokens per invoice <= 400.

**Status: smoke-tested, not yet run against the real evaluation set**,
for the same reason as the OCR bake-off above: the FATURA archive has
not finished downloading in this environment. `scripts/evaluate_extraction.py`
was verified end to end against a 10-image synthetic fixture (2
templates, known invoice_no/total values), built the same way as the
bake-off's fixture and deleted after the run.

Smoke-test result (10 synthetic pages, rules extractor only, header
fields only - line-item F1 needs the real table-layout data the
synthetic fixture doesn't have):

| Field | Precision | Recall | F1 |
|---|---|---|---|
| invoice_no | 1.000 | 1.000 | 1.000 |
| total | 1.000 | 1.000 | 1.000 |

LLM call rate and average tokens were both 0 in this run: no
`GROQ_API_KEY`/`GEMINI_API_KEY` were configured, so every invoice that
the rules extractor couldn't confidently complete fell straight to
`needs_review` rather than calling an LLM (see
`app/extraction/llm_fallback.py:build_router_from_settings`, which
returns `None` with no keys configured, and `README.md`'s known
environment constraints). The LLM router itself (failover, circuit
breaker, schema-repair retry, budget gating) is fully unit-tested with
fake providers in `tests/test_llm_router.py`, proving the routing logic
independently of having real API keys available.

### Rebuilding this report with real data

```bash
bash dataset/download_fatura.sh          # resume until it fully completes
cd dataset && python scripts/inspect_fatura.py && python scripts/build_truth.py
cd ../backend && uv run python -m scripts.evaluate_extraction
```

Set `GROQ_API_KEY`/`GEMINI_API_KEY` first to measure the LLM call rate
and token usage columns for real; this overwrites the "Extraction
accuracy" section of this file in place.

## 3-way match rule engine accuracy

Cases run: 4
Overall precision: 1.000 (target: >= 0.90, Plan.md section 7)
Overall recall: 1.000 (target: >= 0.95)

| Reason code | Precision | Recall | TP | FP | FN |
|---|---|---|---|---|---|
| PO_CLOSED | 1.000 | 1.000 | 1 | 0 | 0 |
| PRICE_VARIANCE | 1.000 | 1.000 | 1 | 0 | 0 |
| QTY_NOT_RECEIVED | 1.000 | 1.000 | 1 | 0 | 0 |

Smoke test only: dataset/processed/anomaly_labels.csv does not exist in this environment (see dataset/README.md), so this exercises run_match() directly against one synthetic case per labeled reason code (PO_CLOSED, PRICE_VARIANCE, QTY_NOT_RECEIVED) plus one clean case, rather than the real FATURA-derived evaluation set. Re-run against anomaly_labels.csv once it exists.

## Quality gates (Phase 13)

Measured in this environment on the current commit plus the Phase 13 changes.

| Gate | Target | Result |
|---|---|---|
| Backend line coverage | >= 80% | 81.3% (4,987 statements, `pytest --cov=app`) |
| Matching engine coverage | >= 95% | 95.5% (353 statements, `app/matching`, matching test selection) |
| Schema contract fuzzing (schemathesis, all 68 operations) | no 5xx | 68 passed, 25 generated examples per operation |
| Load: 50 concurrent users, read endpoints, 2 min | 0 failures | 4,165 requests, 0 failures, median 720 ms, p95 1.7 s |
| Load: 10 concurrent uploads, 1 min | 0 failures | 283 uploads, 0 failures, median 87 ms |
| Dependency audit, Python (pip-audit) | no known vulnerabilities | none found |
| Dependency audit, frontend (npm audit, production, high) | no high findings | 0 vulnerabilities |
| Static security (bandit, app/) | no findings | no findings |

Caveats, stated plainly:

- The load test ran against the Windows development machine with other projects also running, so latency is a floor-to-ceiling read, not a production benchmark. Login is throttled per IP by design (10 per minute), so the test logs in once before users spawn and shares that session.
- Schema fuzzing sends unauthenticated, random requests. It proves the API never crashes, not that every authorized path is correct; the functional tests cover those.
- Trivy and OWASP ZAP were not run: neither binary is installed here, and this sandbox cannot pull their images reliably. They remain outstanding for the security pass.
- Resilience: a database outage now answers 503 with a problem body instead of 500, covered by a test. Graceful rules-only degradation when both LLM providers are exhausted is covered by the Phase 5 router tests. Worker crash recovery and idempotent re-processing rest on Procrastinate retries and the status guards in each task; a crash-injection test has not been written.
- Observability: every request carries a request id and logs are structured (structlog). A Prometheus `/metrics` endpoint and Grafana were not built; both are marked optional in Plan.md section 13.
