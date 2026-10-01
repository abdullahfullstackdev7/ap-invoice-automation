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
