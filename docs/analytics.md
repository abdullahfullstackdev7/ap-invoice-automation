# Analytics

KPI and metric definitions behind `/api/v1/analytics/*` (Plan.md section
9). All endpoints are scoped by `date_from`/`date_to` (default: trailing
30 days), and can be narrowed by `vendor_id` and/or `category`. List-shaped
endpoints accept `?format=csv` for a CSV export and support `limit`/
`offset` pagination where the result is a ranked table. Every endpoint
sets a content-hash `ETag`; a matching `If-None-Match` gets a `304` with
no body.

`analytics_daily` is a per-`(date, vendor_id, category)` rollup refreshed
by `refresh_analytics_daily_task`, deferred nightly (`02:00`, via
Procrastinate's `@periodic(cron=...)`) and again after every payment
batch settles. The `kpis`, `volume-value-trend`, `spend-by-vendor` and
`spend-by-category` endpoints read it for speed; everything else reads
the raw tables directly, since reason codes, cycle-time distributions,
aging buckets and heatmaps don't fit a per-day grain.

## Definitions

- **STP rate** (straight-through-processing rate): `auto_approved invoices / total invoices processed` in the period. An invoice is auto-approved when the 3-way match finds no exceptions and its total is at or under `AUTO_APPROVE_LIMIT`.
- **Exception rate**: `exceptions opened / total invoices processed` in the period. Counted by `exceptions.opened_at`, not by invoice, so one invoice with three exceptions counts as three.
- **Cycle time**: hours from `documents.uploaded_at` (intake) to `payments.released_at` (payment released), for invoices that have reached a released payment in the period. Reported as a distribution (under 24h / 24-48h / 48-72h / over 72h) and p50/p95, plus a daily trend of the mean.
- **Aging**: for scheduled or released (not yet settled) payments, days outstanding = `as_of_date - invoices.due_date`. Bucketed 0-30, 31-60, 61-90, 90+. A negative days-outstanding value (not yet due) falls in the 0-30 bucket.
- **Cashflow forecast**: scheduled or released (not yet settled) payments due in the next N days (default 90), summed by the week they fall in.
- **Leakage prevented / savings**:
  - *Duplicates blocked*: invoices with an open or resolved `DUPLICATE_EXACT` exception; value is each invoice's total (the overpayment avoided by not paying it twice).
  - *Price drift prevented*: resolved `PRICE_VARIANCE` exceptions; value is `abs(price_inv - price_po) * qty` read back from the match engine's own stored evidence (`app/matching/rules/price.py`'s `details_json`).
  - *Over-receipt prevented*: resolved `QTY_OVER_RECEIVED` exceptions; value is `(qty_invoiced - qty_allowed) * unit_price`.
  - *Discounts captured / missed*: computed per paid invoice from the vendor's `discount_pct` whenever the vendor has discount terms at all; captured if the payment was scheduled before the invoice's due date (meaning `app/services/payment_scheduling.py` took the early-pay discount), missed if scheduled on or after the due date.
- **Vendor scorecard**: per vendor, `invoices_count`, total `value`, `exception_count`, `exception_rate`, and `stp_rate` over the period, ranked by value.
- **Workflow funnel**: a snapshot count of invoices (intake in the period) at each `InvoiceStatus`, not a true time-based funnel - an invoice is counted once, at its *current* status, not once per stage it passed through. A simplification; call out if a true multi-stage funnel is needed later.
- **Exception heatmap**: count of exceptions by `reason_code` x vendor `category`.
- **LLM usage**: tokens and call counts by provider from `llm_usage`; `calls_avoided_by_rules` = invoices processed in the period minus LLM calls made, i.e. how many invoices the deterministic rules extractor alone handled.
- **Extraction / matching accuracy**: this project has no "evaluation runs" database table (Plan.md section 9 mentions one, but section 5's schema doesn't define it, and adding an unplanned table for a single read-only endpoint wasn't worth the schema churn). The `/extraction-accuracy` endpoint instead serves the latest `docs/evaluation_extraction.json` / `docs/evaluation_matching.json` written by `scripts/evaluate_extraction.py` and `scripts/evaluate_matching.py`. Re-run those scripts to refresh it.

## Known limitations in this environment

The acceptance target in Plan.md section 9 ("each endpoint answers in
under 300ms on the 24-month dataset") has not been measured against a
real 24-month dataset, since the FATURA-derived dataset has not finished
downloading in this sandbox (see `dataset/README.md`). The query
functions were written to read from `analytics_daily` wherever the grain
allows it specifically to keep hot-path endpoints index-scoped rather
than full-table scans, but the 300ms number itself is unverified at
realistic scale here.
