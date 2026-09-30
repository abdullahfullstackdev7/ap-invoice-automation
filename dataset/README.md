# Dataset

This folder builds the data behind Veridian Payables: the FATURA invoice
image set plus a fully synthetic layer of linked purchase orders, goods
receipts, payment history and injected anomalies that drives the 3-way
match engine.

## Sources

| Purpose | Dataset | Location | License |
|---|---|---|---|
| Primary: invoice images and annotations | FATURA (10,000 invoices, 50 templates, 24 annotated classes) | https://zenodo.org/records/10371464 (DOI 10.5281/zenodo.10371464), file `FATURA2.zip`, 690.7 MB, md5 `4c9404462f22c5241eb1a290a02eb2a2` | CC BY 4.0. Cite: Limam, Dhiaf, Kessentini, "FATURA: A Multi-Layout Invoice Image Dataset for Document Analysis and Understanding," 2023. |
| Optional: scanned receipt robustness test | SROIE (ICDAR 2019) | Official ICDAR 2019 competition page or a Hugging Face mirror. Verify terms before use. | Verify before use |
| Generated: linked business documents | Synthetic vendor master, item catalog, POs, goods receipts, historical payments | Produced by `scripts/generate_synthetic.py` | Ours |

FATURA is synthetic and template-based, so it is cleaner than a real inbox.
`scripts/augment_scans.py` applies scan-like degradation to a fraction of
the demo set to narrow that gap. FATURA supports two evaluation strategies;
this project uses the unseen-template split (see `select_demo_set.py`) so
extraction accuracy reflects generalization, not memorization of a layout.

## Rebuild steps

Run in order from `dataset/`:

```bash
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows
pip install -r requirements.txt

bash download_fatura.sh          # resumable, verifies md5 before extracting
python scripts/inspect_fatura.py # writes processed/fatura_inspection_report.json
python scripts/build_truth.py    # writes processed/truth_invoices.jsonl
python scripts/select_demo_set.py
python scripts/generate_synthetic.py
python scripts/augment_scans.py
python scripts/validate_dataset.py
```

`make dataset` from the repo root runs the same sequence.

### A note on `inspect_fatura.py` and `build_truth.py`

FATURA ships three annotation formats (original, COCO, Hugging Face token
classification). This project does not hardcode which key names the
"original" format uses. `inspect_fatura.py` reads whatever is actually on
disk and reports the observed top-level keys, sample records and candidate
class names to `processed/fatura_inspection_report.json`. `build_truth.py`
then extracts header and line fields using a documented, wide set of
candidate key names (see `CANDIDATE_KEYS` and `LINE_FIELD_KEYS` at the top
of the script) and only keeps an invoice if line-sum, tax and total
arithmetic holds within 0.02. Expect a subset to be dropped; the per
template drop rate is written to `processed/truth_build_report.json` and
should be reported here once a full run has completed.

If a full inspection run finds that FATURA's original-format keys do not
match any candidate above, extend `CANDIDATE_KEYS` in `build_truth.py`
rather than special-casing the parser, and re-run.

**Verified against a small synthetic fixture** (8 mock invoices across 2
templates, mixed-case keys) to prove the pipeline is structurally correct:
build_truth, select_demo_set, generate_synthetic and validate_dataset all
ran end to end and produced referentially consistent output. That fixture
was deleted after the check; it never became part of this dataset. The
actual FATURA-derived numbers below are filled in after a real
`download_fatura.sh` run completes.

## Folder structure

```
dataset/
  README.md                    this file
  download_fatura.sh           curl + md5 check + unzip
  requirements.txt             generator dependencies
  raw/                         (gitignored) FATURA2 extracted here
  processed/
    truth_invoices.jsonl       canonical invoice ground truth per invoice_id
    template_index.csv         invoice_id, template_id, split
    fatura_inspection_report.json   observed structure, written by inspect_fatura.py
    truth_build_report.json         per-template keep/drop counts
  synthetic/
    vendors.csv
    items_catalog.csv
    purchase_orders.csv
    po_lines.csv
    goods_receipts.csv
    gr_lines.csv
    payments_history.csv
    anomaly_labels.csv         invoice_id, anomaly_type, expected_reason_code
    users_seed.csv
  demo/
    invoices/                  (gitignored) 1,000 selected files, PDF and JPG mix
    extraction_cache.jsonl     precomputed extraction results, added in Phase 4/5
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

Only `README.md`, the scripts, `synthetic/*.csv` and `demo/manifest.json`
are committed. `raw/` and the full demo image set stay out of git; rebuild
them locally with the steps above.

## Anomaly injection targets

`generate_synthetic.py` targets the following shares (see
`ANOMALY_SHARES` in the script and `validate_dataset.py`, which checks the
actual output stays within 1 point of each target):

| Anomaly | Share | Expected reason code |
|---|---|---|
| Clean match | 68% | none |
| Quantity short | 8% | QTY_OVER_RECEIVED |
| Price drift | 7% | PRICE_VARIANCE |
| Within-tolerance drift | 4% | none (pass) |
| Duplicate exact | 3% | DUPLICATE_EXACT |
| Duplicate near | 3% | DUPLICATE_SUSPECTED |
| Missing receipt | 3% | QTY_NOT_RECEIVED |
| Partial receipt, invoiced in full | 2% | QTY_OVER_RECEIVED |
| PO not found or closed | 1% | PO_NOT_FOUND, PO_CLOSED |
| Vendor mismatch | 1% | VENDOR_MISMATCH |

## Known constraint: FATURA download speed

`download_fatura.sh` is resumable (`curl -C -`) because Zenodo can be slow
from some networks. In this environment the sustained transfer rate for
the 690.7 MB archive has been on the order of 10 to 20 KB/s, which does not
complete in a single working session. Re-run `download_fatura.sh` from a
network with normal throughput to finish the download; it will resume from
wherever the partial `raw/FATURA2.zip` left off. Once the archive is fully
extracted, run the rebuild steps above in order to produce real numbers
for this section and for `docs/evaluation.md`.

## Status of this rebuild

- [ ] `download_fatura.sh` completed and md5 verified
- [ ] `inspect_fatura.py` run against the real archive, candidate key list
      in `build_truth.py` confirmed or extended
- [ ] `build_truth.py` run, drop rate recorded here
- [ ] `select_demo_set.py`, `generate_synthetic.py`, `augment_scans.py` run
- [ ] `validate_dataset.py` exits 0 against real data
- [ ] 20-invoice manual spot check against PO and GRN (Phase 1 acceptance)
