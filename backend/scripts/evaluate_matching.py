"""Recall/precision of the 3-way match rule engine against
dataset/processed/anomaly_labels.csv, per reason code.

Acceptance target (Plan.md section 7): recall >= 0.95 and precision >= 0.90
against anomaly_labels.csv, confusion matrix per reason code (see
dataset/README.md for why this has only been smoke-tested, not run
against the real FATURA-derived evaluation set, in this environment).

anomaly_labels.csv is expected to have one row per synthetic invoice with
columns invoice_id, po_number, injected_anomaly (a reason code, or
"none"), plus the fields needed to rebuild a MatchContext. That dataset
has not been generated in this environment (see dataset/README.md), so
this script smoke-tests the same run_match() entry point against a small
synthetic fixture built in-process (clean cases and one case per reason
code), verifying the engine fires the expected reason code and nothing
else, rather than claiming the real recall/precision numbers.
"""

import json
import uuid
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path

from app.matching.context import LineMapping, MatchContext
from app.matching.engine import run_match
from app.matching.policy import DEFAULT_POLICY
from app.models.enums import POStatus
from app.models.invoicing import Invoice, InvoiceLine
from app.models.masterdata import Vendor
from app.models.procurement import POLine, PurchaseOrder

BACKEND_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = BACKEND_DIR.parent
DATASET_DIR = REPO_ROOT / "dataset"
ANOMALY_LABELS_PATH = DATASET_DIR / "processed" / "anomaly_labels.csv"

DOCS_DIR = REPO_ROOT / "docs"
EVALUATION_MD = DOCS_DIR / "evaluation.md"
EVALUATION_JSON = DOCS_DIR / "evaluation_matching.json"


@dataclass
class ReasonCodeCounts:
    true_positive: int = 0
    false_positive: int = 0
    false_negative: int = 0

    def precision(self) -> float:
        denom = self.true_positive + self.false_positive
        return self.true_positive / denom if denom else 0.0

    def recall(self) -> float:
        denom = self.true_positive + self.false_negative
        return self.true_positive / denom if denom else 0.0


def _vendor() -> Vendor:
    return Vendor(id=uuid.uuid4(), code="V1", name="Acme", name_normalized="acme")


def _po(vendor_id: uuid.UUID, *, status: POStatus = POStatus.open) -> PurchaseOrder:
    return PurchaseOrder(
        id=uuid.uuid4(),
        po_number="PO-1",
        vendor_id=vendor_id,
        currency="USD",
        status=status,
        po_date=date(2026, 9, 1),
        total=Decimal("100.00"),
    )


def _po_line(po_id: uuid.UUID, *, qty: Decimal, unit_price: Decimal) -> POLine:
    return POLine(
        id=uuid.uuid4(),
        po_id=po_id,
        line_no=1,
        item_id=None,
        description="Widget",
        qty=qty,
        unit_price=unit_price,
        amount=qty * unit_price,
        qty_invoiced_cum=Decimal("0"),
    )


def _invoice_line(invoice_id: uuid.UUID, *, qty: Decimal, unit_price: Decimal) -> InvoiceLine:
    return InvoiceLine(
        id=uuid.uuid4(),
        invoice_id=invoice_id,
        line_no=1,
        description="Widget",
        qty=qty,
        unit_price=unit_price,
        amount=qty * unit_price,
    )


def _ctx_for_case(reason_code: str) -> tuple[MatchContext, bool, bool]:
    """Returns (ctx, is_exact_duplicate, expect_fire) for one labeled case."""
    vendor = _vendor()
    invoice_id = uuid.uuid4()

    if reason_code == "PO_CLOSED":
        po = _po(vendor.id, status=POStatus.closed)
        po_line = _po_line(po.id, qty=Decimal("2"), unit_price=Decimal("10.00"))
        inv_line = _invoice_line(invoice_id, qty=Decimal("2"), unit_price=Decimal("10.00"))
        invoice = Invoice(
            id=invoice_id,
            document_id=uuid.uuid4(),
            vendor_id=vendor.id,
            invoice_no="INV-1",
            invoice_date=date(2026, 9, 5),
            currency="USD",
            subtotal=Decimal("20.00"),
            tax=Decimal("0"),
            total=Decimal("20.00"),
        )
        ctx = MatchContext(
            invoice=invoice,
            invoice_lines=[inv_line],
            vendor=vendor,
            po=po,
            po_lines=[po_line],
            po_lines_by_id={po_line.id: po_line},
            qty_received_by_po_line={po_line.id: Decimal("2")},
            line_mappings=[LineMapping(inv_line.id, po_line.id, 1.0, "sku")],
            policy=DEFAULT_POLICY,
            auto_approve_limit=Decimal("5000"),
        )
        return ctx, False, True

    if reason_code == "PRICE_VARIANCE":
        po = _po(vendor.id)
        po_line = _po_line(po.id, qty=Decimal("2"), unit_price=Decimal("10.00"))
        inv_line = _invoice_line(invoice_id, qty=Decimal("2"), unit_price=Decimal("12.00"))
        invoice = Invoice(
            id=invoice_id,
            document_id=uuid.uuid4(),
            vendor_id=vendor.id,
            invoice_no="INV-2",
            invoice_date=date(2026, 9, 5),
            currency="USD",
            subtotal=Decimal("24.00"),
            tax=Decimal("0"),
            total=Decimal("24.00"),
        )
        ctx = MatchContext(
            invoice=invoice,
            invoice_lines=[inv_line],
            vendor=vendor,
            po=po,
            po_lines=[po_line],
            po_lines_by_id={po_line.id: po_line},
            qty_received_by_po_line={po_line.id: Decimal("2")},
            line_mappings=[LineMapping(inv_line.id, po_line.id, 1.0, "sku")],
            policy=DEFAULT_POLICY,
            auto_approve_limit=Decimal("5000"),
        )
        return ctx, False, True

    if reason_code == "QTY_NOT_RECEIVED":
        po = _po(vendor.id)
        po_line = _po_line(po.id, qty=Decimal("2"), unit_price=Decimal("10.00"))
        inv_line = _invoice_line(invoice_id, qty=Decimal("2"), unit_price=Decimal("10.00"))
        invoice = Invoice(
            id=invoice_id,
            document_id=uuid.uuid4(),
            vendor_id=vendor.id,
            invoice_no="INV-3",
            invoice_date=date(2026, 9, 5),
            currency="USD",
            subtotal=Decimal("20.00"),
            tax=Decimal("0"),
            total=Decimal("20.00"),
        )
        ctx = MatchContext(
            invoice=invoice,
            invoice_lines=[inv_line],
            vendor=vendor,
            po=po,
            po_lines=[po_line],
            po_lines_by_id={po_line.id: po_line},
            qty_received_by_po_line={},
            line_mappings=[LineMapping(inv_line.id, po_line.id, 1.0, "sku")],
            policy=DEFAULT_POLICY,
            auto_approve_limit=Decimal("5000"),
        )
        return ctx, False, True

    # "none": a clean invoice, nothing should fire.
    po = _po(vendor.id)
    po_line = _po_line(po.id, qty=Decimal("2"), unit_price=Decimal("10.00"))
    inv_line = _invoice_line(invoice_id, qty=Decimal("2"), unit_price=Decimal("10.00"))
    invoice = Invoice(
        id=invoice_id,
        document_id=uuid.uuid4(),
        vendor_id=vendor.id,
        invoice_no="INV-4",
        invoice_date=date(2026, 9, 5),
        currency="USD",
        subtotal=Decimal("20.00"),
        tax=Decimal("0"),
        total=Decimal("20.00"),
    )
    ctx = MatchContext(
        invoice=invoice,
        invoice_lines=[inv_line],
        vendor=vendor,
        po=po,
        po_lines=[po_line],
        po_lines_by_id={po_line.id: po_line},
        qty_received_by_po_line={po_line.id: Decimal("2")},
        line_mappings=[LineMapping(inv_line.id, po_line.id, 1.0, "sku")],
        policy=DEFAULT_POLICY,
        auto_approve_limit=Decimal("5000"),
    )
    return ctx, False, False


LABELED_REASON_CODES = ("PO_CLOSED", "PRICE_VARIANCE", "QTY_NOT_RECEIVED", "none")


def evaluate() -> dict[str, object]:
    if ANOMALY_LABELS_PATH.exists():
        raise NotImplementedError(
            f"{ANOMALY_LABELS_PATH} exists but the real-dataset evaluation loader has not "
            "been implemented; this script currently only smoke-tests the synthetic fixture "
            "below. Wire up a real loader here once the dataset pipeline (dataset/README.md) "
            "has produced anomaly_labels.csv."
        )

    counts: dict[str, ReasonCodeCounts] = {
        code: ReasonCodeCounts() for code in LABELED_REASON_CODES if code != "none"
    }
    cases_run = 0

    for expected_reason_code in LABELED_REASON_CODES:
        ctx, is_exact_duplicate, expect_fire = _ctx_for_case(expected_reason_code)
        decision = run_match(ctx, is_exact_duplicate=is_exact_duplicate, duplicate_draft=None)
        fired_codes = {d.reason_code for d in decision.exceptions}
        cases_run += 1

        if expected_reason_code == "none":
            for code, bucket in counts.items():
                if code in fired_codes:
                    bucket.false_positive += 1
            continue

        target = counts[expected_reason_code]
        if expected_reason_code in fired_codes:
            target.true_positive += 1
        else:
            target.false_negative += 1
        for code, bucket in counts.items():
            if code != expected_reason_code and code in fired_codes:
                bucket.false_positive += 1

    total_tp = sum(c.true_positive for c in counts.values())
    total_fp = sum(c.false_positive for c in counts.values())
    total_fn = sum(c.false_negative for c in counts.values())
    overall_precision = total_tp / (total_tp + total_fp) if (total_tp + total_fp) else 0.0
    overall_recall = total_tp / (total_tp + total_fn) if (total_tp + total_fn) else 0.0

    return {
        "cases_run": cases_run,
        "overall": {
            "precision": round(overall_precision, 3),
            "recall": round(overall_recall, 3),
        },
        "by_reason_code": {
            code: {
                "precision": round(bucket.precision(), 3),
                "recall": round(bucket.recall(), 3),
                "true_positive": bucket.true_positive,
                "false_positive": bucket.false_positive,
                "false_negative": bucket.false_negative,
            }
            for code, bucket in counts.items()
        },
        "note": (
            "Smoke test only: dataset/processed/anomaly_labels.csv does not exist in this "
            "environment (see dataset/README.md), so this exercises run_match() directly "
            "against one synthetic case per labeled reason code (PO_CLOSED, PRICE_VARIANCE, "
            "QTY_NOT_RECEIVED) plus one clean case, rather than the real FATURA-derived "
            "evaluation set. Re-run against anomaly_labels.csv once it exists."
        ),
    }


def render_markdown(results: dict[str, object]) -> str:
    overall = results["overall"]
    by_code = results["by_reason_code"]
    lines = [
        "## 3-way match rule engine accuracy",
        "",
        f"Cases run: {results['cases_run']}",
        f"Overall precision: {overall['precision']:.3f} (target: >= 0.90, Plan.md section 7)",  # type: ignore[index]
        f"Overall recall: {overall['recall']:.3f} (target: >= 0.95)",  # type: ignore[index]
        "",
        "| Reason code | Precision | Recall | TP | FP | FN |",
        "|---|---|---|---|---|---|",
    ]
    for code, metrics in by_code.items():  # type: ignore[attr-defined]
        lines.append(
            f"| {code} | {metrics['precision']:.3f} | {metrics['recall']:.3f} | "
            f"{metrics['true_positive']} | {metrics['false_positive']} | "
            f"{metrics['false_negative']} |"
        )
    lines.append("")
    lines.append(str(results.get("note", "")))
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    results = evaluate()
    section = render_markdown(results)

    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    EVALUATION_JSON.write_text(json.dumps(results, indent=2), encoding="utf-8")

    existing = (
        EVALUATION_MD.read_text(encoding="utf-8") if EVALUATION_MD.exists() else "# Evaluation\n"
    )
    marker = "## 3-way match rule engine accuracy"
    if marker in existing:
        before, _, after_start = existing.partition(marker)
        next_heading = after_start.find("\n## ", 1)
        remainder = after_start[next_heading + 1 :] if next_heading != -1 else ""
        existing = before + section + remainder
    else:
        existing = existing.rstrip() + "\n\n" + section

    EVALUATION_MD.write_text(existing, encoding="utf-8")
    print(section)
    print(f"Wrote {EVALUATION_MD} and {EVALUATION_JSON}")


if __name__ == "__main__":
    main()
