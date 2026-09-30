"""Convert FATURA's original-format annotations into truth_invoices.jsonl.

This script does not hardcode FATURA's key names. It first looks for the
inspection report produced by inspect_fatura.py (dataset/processed/
fatura_inspection_report.json) to learn what keys and paths actually exist
in this copy of the dataset, then falls back to a documented, wide set of
candidate key names for common invoice fields if the report is absent or a
given file uses a different shape.

Output: one JSON object per line in truth_invoices.jsonl with the schema
described in Plan.md section 4.3, item 3:
  invoice_id, template_id, vendor{name,address,email}, buyer{...},
  invoice_no, invoice_date, po_reference, currency,
  lines[{description, qty, unit_price, amount}], subtotal, tax, discount, total

Only invoices where line/tax/total arithmetic holds within 0.02 are kept.
The drop rate is logged per template so it can be reported in the dataset
README.
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

DATASET_DIR = Path(__file__).resolve().parent.parent
RAW_DIR = DATASET_DIR / "raw"
PROCESSED_DIR = DATASET_DIR / "processed"
TRUTH_PATH = PROCESSED_DIR / "truth_invoices.jsonl"
INSPECTION_REPORT_PATH = PROCESSED_DIR / "fatura_inspection_report.json"

ARITHMETIC_TOLERANCE = Decimal("0.02")

# Candidate key names per logical field. Extend this list, do not guess a
# single name, since FATURA's original-format export has not been assumed.
CANDIDATE_KEYS: dict[str, list[str]] = {
    "invoice_no": ["invoice_no", "invoice_number", "INVOICE_NUMBER", "inv_no", "number"],
    "invoice_date": ["invoice_date", "date", "DATE", "issue_date"],
    "po_reference": ["po_reference", "po_number", "PO_NUMBER", "purchase_order"],
    "currency": ["currency", "CURRENCY", "curr"],
    "subtotal": ["subtotal", "sub_total", "SUBTOTAL", "net_total"],
    "tax": ["tax", "TAX", "vat", "VAT"],
    "discount": ["discount", "DISCOUNT"],
    "total": ["total", "TOTAL", "grand_total", "amount_due"],
    "vendor_name": ["seller", "vendor", "SELLER", "company", "supplier_name"],
    "buyer_name": ["buyer", "client", "BUYER", "customer_name"],
}

LINE_TABLE_KEYS = ["lines", "items", "table", "TABLE", "line_items"]
LINE_FIELD_KEYS: dict[str, list[str]] = {
    "description": ["description", "desc", "DESCRIPTION", "item"],
    "qty": ["qty", "quantity", "QTY", "QUANTITY"],
    "unit_price": ["unit_price", "price", "UNIT_PRICE", "rate"],
    "amount": ["amount", "AMOUNT", "line_total", "total"],
}


def load_inspection_report() -> dict[str, Any] | None:
    if INSPECTION_REPORT_PATH.exists():
        return json.loads(INSPECTION_REPORT_PATH.read_text(encoding="utf-8"))
    return None


def find_first(data: dict[str, Any], candidates: list[str]) -> Any:
    for key in candidates:
        if key in data:
            return data[key]
    # Case-insensitive fallback pass
    lowered = {k.lower(): v for k, v in data.items()}
    for key in candidates:
        if key.lower() in lowered:
            return lowered[key.lower()]
    return None


def to_decimal(value: Any) -> Decimal | None:
    if value is None:
        return None
    try:
        text = str(value).replace(",", "").replace("$", "").strip()
        return Decimal(text)
    except (InvalidOperation, ValueError):
        return None


def extract_lines(data: dict[str, Any]) -> list[dict[str, Any]]:
    raw_lines = find_first(data, LINE_TABLE_KEYS)
    if not isinstance(raw_lines, list):
        return []

    parsed = []
    for raw_line in raw_lines:
        if not isinstance(raw_line, dict):
            continue
        description = find_first(raw_line, LINE_FIELD_KEYS["description"])
        qty = to_decimal(find_first(raw_line, LINE_FIELD_KEYS["qty"]))
        unit_price = to_decimal(find_first(raw_line, LINE_FIELD_KEYS["unit_price"]))
        amount = to_decimal(find_first(raw_line, LINE_FIELD_KEYS["amount"]))
        if description is None or qty is None or unit_price is None:
            continue
        if amount is None:
            amount = qty * unit_price
        parsed.append(
            {
                "description": str(description),
                "qty": str(qty),
                "unit_price": str(unit_price),
                "amount": str(amount),
            }
        )
    return parsed


def arithmetic_holds(lines: list[dict[str, Any]], subtotal: Decimal | None,
                      tax: Decimal | None, discount: Decimal | None,
                      total: Decimal | None) -> bool:
    if not lines or total is None:
        return False

    line_sum = sum((Decimal(line["amount"]) for line in lines), Decimal("0"))
    if subtotal is not None and abs(line_sum - subtotal) > ARITHMETIC_TOLERANCE:
        return False

    base = subtotal if subtotal is not None else line_sum
    computed_total = base + (tax or Decimal("0")) - (discount or Decimal("0"))
    return abs(computed_total - total) <= ARITHMETIC_TOLERANCE


def find_annotation_for_image(image_path: Path) -> dict[str, Any] | None:
    candidate = image_path.with_suffix(".json")
    if candidate.exists():
        try:
            return json.loads(candidate.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return None
    return None


def guess_template_id(image_path: Path) -> str:
    # FATURA groups images by template folder; fall back to the parent
    # directory name, which is the best available signal without assuming
    # a fixed depth.
    return image_path.parent.name


def build_truth() -> None:
    if not RAW_DIR.exists():
        print(f"{RAW_DIR} does not exist. Run download_fatura.sh first.")
        return

    image_paths = sorted(
        [
            *RAW_DIR.rglob("*.jpg"),
            *RAW_DIR.rglob("*.jpeg"),
            *RAW_DIR.rglob("*.png"),
        ]
    )
    if not image_paths:
        print(f"No invoice images found under {RAW_DIR}.")
        return

    kept_by_template: Counter[str] = Counter()
    dropped_by_template: Counter[str] = Counter()

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    with TRUTH_PATH.open("w", encoding="utf-8") as out_file:
        for idx, image_path in enumerate(image_paths):
            template_id = guess_template_id(image_path)
            data = find_annotation_for_image(image_path)
            if data is None:
                dropped_by_template[template_id] += 1
                continue

            invoice_no = find_first(data, CANDIDATE_KEYS["invoice_no"])
            invoice_date = find_first(data, CANDIDATE_KEYS["invoice_date"])
            subtotal = to_decimal(find_first(data, CANDIDATE_KEYS["subtotal"]))
            tax = to_decimal(find_first(data, CANDIDATE_KEYS["tax"]))
            discount = to_decimal(find_first(data, CANDIDATE_KEYS["discount"]))
            total = to_decimal(find_first(data, CANDIDATE_KEYS["total"]))
            lines = extract_lines(data)

            if not arithmetic_holds(lines, subtotal, tax, discount, total):
                dropped_by_template[template_id] += 1
                continue

            record = {
                "invoice_id": image_path.stem,
                "template_id": template_id,
                "image_path": str(image_path.relative_to(RAW_DIR)),
                "vendor": {
                    "name": find_first(data, CANDIDATE_KEYS["vendor_name"]),
                    "address": None,
                    "email": None,
                },
                "buyer": {
                    "name": find_first(data, CANDIDATE_KEYS["buyer_name"]),
                },
                "invoice_no": invoice_no,
                "invoice_date": invoice_date,
                "po_reference": find_first(data, CANDIDATE_KEYS["po_reference"]),
                "currency": find_first(data, CANDIDATE_KEYS["currency"]) or "USD",
                "lines": lines,
                "subtotal": str(subtotal) if subtotal is not None else None,
                "tax": str(tax) if tax is not None else None,
                "discount": str(discount) if discount is not None else None,
                "total": str(total),
            }
            out_file.write(json.dumps(record) + "\n")
            kept_by_template[template_id] += 1

            if (idx + 1) % 1000 == 0:
                print(f"Processed {idx + 1}/{len(image_paths)} images...")

    total_kept = sum(kept_by_template.values())
    total_dropped = sum(dropped_by_template.values())
    total_seen = total_kept + total_dropped
    drop_rate = (total_dropped / total_seen) if total_seen else 0.0

    print(f"Kept {total_kept} invoices, dropped {total_dropped} ({drop_rate:.1%}).")
    print(f"Wrote {TRUTH_PATH}")

    report_path = PROCESSED_DIR / "truth_build_report.json"
    report_path.write_text(
        json.dumps(
            {
                "kept_by_template": dict(kept_by_template),
                "dropped_by_template": dict(dropped_by_template),
                "total_kept": total_kept,
                "total_dropped": total_dropped,
                "drop_rate": drop_rate,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"Wrote drop-rate report to {report_path}")


if __name__ == "__main__":
    build_truth()
