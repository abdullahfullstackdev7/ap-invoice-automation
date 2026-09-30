"""Validate the generated dataset end to end.

Exits 0 only if every check passes. Run after generate_synthetic.py,
select_demo_set.py and augment_scans.py.

Checks:
  - Referential integrity across all synthetic CSVs
  - Money arithmetic on purchase orders and goods receipts
  - Anomaly shares within 1 point of the target table in Plan.md section 4.4
  - No overlap between the demo set and the evaluation set
  - Date range covers 24 months
  - Checksums match manifest.json (when the manifest exists)
"""

from __future__ import annotations

import hashlib
import json
import sys
from decimal import Decimal
from pathlib import Path

import pandas as pd

DATASET_DIR = Path(__file__).resolve().parent.parent
SYNTHETIC_DIR = DATASET_DIR / "synthetic"
PROCESSED_DIR = DATASET_DIR / "processed"
DEMO_DIR = DATASET_DIR / "demo"

TARGET_ANOMALY_SHARES = {
    "CLEAN": 0.68,
    "QTY_OVER_RECEIVED_SHORT": 0.08,
    "PRICE_VARIANCE": 0.07,
    "WITHIN_TOLERANCE": 0.04,
    "DUPLICATE_EXACT": 0.03,
    "DUPLICATE_SUSPECTED": 0.03,
    "QTY_NOT_RECEIVED": 0.03,
    "QTY_OVER_RECEIVED_PARTIAL": 0.02,
    "PO_NOT_FOUND_OR_CLOSED": 0.01,
    "VENDOR_MISMATCH": 0.01,
}
ANOMALY_TOLERANCE_POINTS = 0.01
MONEY_TOLERANCE = Decimal("0.02")

errors: list[str] = []
warnings: list[str] = []


def fail(message: str) -> None:
    errors.append(message)


def warn(message: str) -> None:
    warnings.append(message)


def load_csv(path: Path) -> pd.DataFrame | None:
    if not path.exists():
        fail(f"Missing required file: {path.relative_to(DATASET_DIR)}")
        return None
    return pd.read_csv(path)


def check_referential_integrity() -> None:
    vendors = load_csv(SYNTHETIC_DIR / "vendors.csv")
    items = load_csv(SYNTHETIC_DIR / "items_catalog.csv")
    pos = load_csv(SYNTHETIC_DIR / "purchase_orders.csv")
    po_lines = load_csv(SYNTHETIC_DIR / "po_lines.csv")
    receipts = load_csv(SYNTHETIC_DIR / "goods_receipts.csv")
    gr_lines = load_csv(SYNTHETIC_DIR / "gr_lines.csv")

    if vendors is None or pos is None:
        return

    if not set(pos["vendor_id"]).issubset(set(vendors["vendor_id"])):
        fail("purchase_orders.vendor_id references vendors that do not exist")

    if po_lines is not None:
        if not set(po_lines["po_id"]).issubset(set(pos["po_id"])):
            fail("po_lines.po_id references purchase_orders that do not exist")
        if items is not None and not set(po_lines["item_id"].dropna()).issubset(
            set(items["item_id"])
        ):
            fail("po_lines.item_id references items that do not exist")

    if receipts is not None and pos is not None:
        if not set(receipts["po_id"]).issubset(set(pos["po_id"])):
            fail("goods_receipts.po_id references purchase_orders that do not exist")

    if gr_lines is not None and receipts is not None and po_lines is not None:
        if not set(gr_lines["grn_id"]).issubset(set(receipts["grn_id"])):
            fail("gr_lines.grn_id references goods_receipts that do not exist")
        if not set(gr_lines["po_line_id"]).issubset(set(po_lines["po_line_id"])):
            fail("gr_lines.po_line_id references po_lines that do not exist")


def check_money_arithmetic() -> None:
    po_lines = load_csv(SYNTHETIC_DIR / "po_lines.csv")
    pos = load_csv(SYNTHETIC_DIR / "purchase_orders.csv")
    if po_lines is None or pos is None:
        return

    computed = po_lines.groupby("po_id").apply(
        lambda g: (g["qty"] * g["unit_price"]).sum(), include_groups=False
    )
    merged = pos.set_index("po_id")["total"].to_frame().join(computed.rename("computed_total"))
    merged = merged.dropna()

    bad = merged[
        (merged["total"] - merged["computed_total"]).abs() > float(MONEY_TOLERANCE) + 0.01
    ]
    if not bad.empty:
        fail(f"{len(bad)} purchase orders fail line-sum-to-total arithmetic check")


def check_anomaly_shares() -> None:
    labels = load_csv(SYNTHETIC_DIR / "anomaly_labels.csv")
    if labels is None:
        return

    total = len(labels)
    if total == 0:
        fail("anomaly_labels.csv is empty")
        return

    observed = labels["anomaly_type"].value_counts(normalize=True).to_dict()

    for anomaly_type, target_share in TARGET_ANOMALY_SHARES.items():
        actual = observed.get(anomaly_type, 0.0)
        if abs(actual - target_share) > ANOMALY_TOLERANCE_POINTS:
            warn(
                f"Anomaly share for {anomaly_type} is {actual:.3f}, "
                f"target {target_share:.3f} (tolerance {ANOMALY_TOLERANCE_POINTS})"
            )


def check_demo_eval_overlap() -> None:
    template_index_path = PROCESSED_DIR / "template_index.csv"
    if not template_index_path.exists():
        fail("Missing processed/template_index.csv")
        return

    template_index = pd.read_csv(template_index_path)
    if "split" not in template_index.columns:
        fail("template_index.csv is missing the split column")
        return

    demo_ids = set(template_index.loc[template_index["split"] == "demo", "invoice_id"])
    eval_ids = set(template_index.loc[template_index["split"] == "eval", "invoice_id"])
    overlap = demo_ids & eval_ids
    if overlap:
        fail(f"{len(overlap)} invoice ids appear in both demo and eval splits")


def check_date_range() -> None:
    payments = load_csv(SYNTHETIC_DIR / "payments_history.csv")
    if payments is None or payments.empty:
        return

    dates = pd.to_datetime(payments["payment_date"], errors="coerce").dropna()
    if dates.empty:
        fail("payments_history.csv has no parseable payment_date values")
        return

    span_days = (dates.max() - dates.min()).days
    if span_days < 24 * 28:
        fail(f"Payment history date range is only {span_days} days, expected roughly 24 months")


def check_manifest_checksums() -> None:
    manifest_path = DEMO_DIR / "manifest.json"
    if not manifest_path.exists():
        warn("demo/manifest.json not found, skipping checksum verification")
        return

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    checksums = manifest.get("checksums", {})
    for relative_path, expected_sha256 in checksums.items():
        file_path = DATASET_DIR / relative_path
        if not file_path.exists():
            fail(f"Manifest references missing file: {relative_path}")
            continue
        actual = hashlib.sha256(file_path.read_bytes()).hexdigest()
        if actual != expected_sha256:
            fail(f"Checksum mismatch for {relative_path}")


def main() -> int:
    check_referential_integrity()
    check_money_arithmetic()
    check_anomaly_shares()
    check_demo_eval_overlap()
    check_date_range()
    check_manifest_checksums()

    for warning in warnings:
        print(f"WARNING: {warning}")
    for error in errors:
        print(f"ERROR: {error}")

    if errors:
        print(f"\nValidation failed with {len(errors)} error(s).")
        return 1

    print(f"\nValidation passed ({len(warnings)} warning(s)).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
