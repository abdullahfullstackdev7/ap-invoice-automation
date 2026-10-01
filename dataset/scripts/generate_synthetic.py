"""Generate the synthetic, linked business documents that drive matching.

Because FATURA's invoice image content is fixed, purchase orders and goods
receipts are derived from the extracted truth (truth_invoices.jsonl), and
anomalies are injected on the PO/receipt side or by resubmitting documents.
Fully deterministic given SEED. See Plan.md section 4.4 for the anomaly
share table this script targets.
"""

from __future__ import annotations

import random
from datetime import date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

import numpy as np
import pandas as pd
from dateutil.relativedelta import relativedelta
from faker import Faker
from rapidfuzz import fuzz, process

SEED = 42
TODAY = date(2026, 9, 30)
HISTORY_MONTHS = 24
PAYMENT_TERMS_OPTIONS = [15, 30, 45, 60]
DISCOUNT_SHARE = 0.20
EXTRA_OPEN_PO_SHARE = 0.20

ITEM_CATEGORIES = [
    "IT hardware",
    "Office supplies",
    "Logistics",
    "Professional services",
    "Facilities",
    "Marketing",
    "Raw materials",
    "Software",
]

ANOMALY_SHARES = {
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
ANOMALY_REASON_CODES = {
    "CLEAN": "none",
    "QTY_OVER_RECEIVED_SHORT": "QTY_OVER_RECEIVED",
    "PRICE_VARIANCE": "PRICE_VARIANCE",
    "WITHIN_TOLERANCE": "none",
    "DUPLICATE_EXACT": "DUPLICATE_EXACT",
    "DUPLICATE_SUSPECTED": "DUPLICATE_SUSPECTED",
    "QTY_NOT_RECEIVED": "QTY_NOT_RECEIVED",
    "QTY_OVER_RECEIVED_PARTIAL": "QTY_OVER_RECEIVED",
    "PO_NOT_FOUND_OR_CLOSED": "PO_NOT_FOUND",
    "VENDOR_MISMATCH": "VENDOR_MISMATCH",
}

DATASET_DIR = Path(__file__).resolve().parent.parent
PROCESSED_DIR = DATASET_DIR / "processed"
SYNTHETIC_DIR = DATASET_DIR / "synthetic"
TRUTH_PATH = PROCESSED_DIR / "truth_invoices.jsonl"


def money(value: float | Decimal) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def normalize_name(name: str) -> str:
    return " ".join(str(name).strip().lower().split())


def build_vendors(truth: pd.DataFrame, rng: random.Random, faker: Faker) -> pd.DataFrame:
    vendor_names = (
        truth["vendor"].apply(lambda v: v.get("name") if isinstance(v, dict) else None).dropna()
    )
    # Keep the first-seen original casing per normalized name, rather than
    # lowercasing and re-titlecasing, since str.title() mangles acronyms
    # like "IT" -> "It" and "LLC" -> "Llc".
    display_name_by_normalized: dict[str, str] = {}
    for raw_name in vendor_names:
        if not raw_name:
            continue
        normalized = normalize_name(raw_name)
        display_name_by_normalized.setdefault(normalized, str(raw_name).strip())
    unique_names = sorted(display_name_by_normalized.keys())

    if not unique_names:
        unique_names = [normalize_name(faker.company()) for _ in range(180)]
        display_name_by_normalized = {n: n.title() for n in unique_names}

    rows = []
    for idx, normalized in enumerate(unique_names):
        terms = rng.choice(PAYMENT_TERMS_OPTIONS)
        has_discount = rng.random() < DISCOUNT_SHARE
        rows.append(
            {
                "vendor_id": f"VEND-{idx + 1:05d}",
                "code": f"V{idx + 1:05d}",
                "name": display_name_by_normalized[normalized],
                "name_normalized": normalized,
                "tax_id": f"TAX-{faker.unique.random_number(digits=9, fix_len=True)}",
                "address": faker.address().replace("\n", ", "),
                "email": faker.company_email(),
                "payment_terms_days": terms,
                "discount_pct": 2.0 if has_discount else None,
                "discount_days": 10 if has_discount else None,
                "bank_account": f"IBAN{faker.random_number(digits=18, fix_len=True)}",
                "risk_tier": rng.choices(["low", "medium", "high"], weights=[70, 25, 5])[0],
                "category": rng.choice(ITEM_CATEGORIES),
                "status": "active",
            }
        )
    faker.unique.clear()
    return pd.DataFrame(rows)


def build_item_catalog(rng: random.Random, faker: Faker, size: int = 400) -> pd.DataFrame:
    units = ["each", "box", "hour", "license", "kg", "pallet"]
    rows = []
    for idx in range(size):
        category = ITEM_CATEGORIES[idx % len(ITEM_CATEGORIES)]
        rows.append(
            {
                "item_id": f"ITEM-{idx + 1:05d}",
                "sku": f"SKU{idx + 1:06d}",
                "description": f"{category} - {faker.catch_phrase()}",
                "unit": rng.choice(units),
                "std_price": float(money(rng.uniform(5, 2500))),
                "category": category,
            }
        )
    return pd.DataFrame(rows)


def match_item_for_line(description: str, catalog: pd.DataFrame) -> str:
    if not description:
        return catalog.iloc[0]["item_id"]
    match = process.extractOne(
        description, catalog["description"], scorer=fuzz.token_set_ratio
    )
    if match is None:
        return catalog.iloc[0]["item_id"]
    _, _, idx = match
    return catalog.iloc[idx]["item_id"]


def seasonal_weight(d: date) -> float:
    # Higher volume at quarter ends (Mar, Jun, Sep, Dec).
    return 1.6 if d.month in (3, 6, 9, 12) else 1.0


def parse_invoice_date(raw: object) -> date:
    if isinstance(raw, str):
        for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y"):
            try:
                return datetime.strptime(raw, fmt).date()
            except ValueError:
                continue
    return TODAY - timedelta(days=random.randint(0, HISTORY_MONTHS * 30))


def build_documents(
    truth: pd.DataFrame,
    vendors: pd.DataFrame,
    catalog: pd.DataFrame,
    rng: random.Random,
) -> dict[str, pd.DataFrame]:
    vendor_by_norm_name = {row["name_normalized"]: row["vendor_id"] for _, row in vendors.iterrows()}

    pos, po_lines, receipts, gr_lines, anomaly_labels = [], [], [], [], []
    po_counter = 0
    grn_counter = 0

    anomaly_pool = rng.choices(
        list(ANOMALY_SHARES.keys()),
        weights=list(ANOMALY_SHARES.values()),
        k=len(truth),
    )

    for row_idx, (_, invoice) in enumerate(truth.iterrows()):
        anomaly_type = anomaly_pool[row_idx]
        vendor_name = normalize_name(
            invoice["vendor"].get("name") if isinstance(invoice["vendor"], dict) else ""
        )
        vendor_id = vendor_by_norm_name.get(vendor_name)
        if vendor_id is None:
            continue

        invoice_date = parse_invoice_date(invoice.get("invoice_date"))
        po_date = invoice_date - timedelta(days=rng.randint(5, 40))
        po_counter += 1
        po_id = f"PO-{po_counter:06d}"

        effective_vendor_id = vendor_id
        if anomaly_type == "VENDOR_MISMATCH":
            other_vendors = vendors[vendors["vendor_id"] != vendor_id]
            if not other_vendors.empty:
                effective_vendor_id = other_vendors.sample(n=1, random_state=rng.randint(0, 1_000_000)).iloc[0]["vendor_id"]

        po_status = "open"
        if anomaly_type == "PO_NOT_FOUND_OR_CLOSED":
            po_status = "closed"

        lines = invoice.get("lines") or []
        if not lines:
            continue

        po_total = Decimal("0")
        line_records = []
        for line_no, line in enumerate(lines, start=1):
            description = line.get("description") or "Line item"
            item_id = match_item_for_line(description, catalog)
            qty = Decimal(str(line.get("qty") or "1"))
            unit_price = Decimal(str(line.get("unit_price") or "0"))

            if anomaly_type == "PRICE_VARIANCE":
                drift = Decimal(str(rng.uniform(0.03, 0.15)))
                unit_price = money(unit_price * (Decimal("1") - drift))
            elif anomaly_type == "WITHIN_TOLERANCE":
                drift = Decimal(str(rng.uniform(0.001, 0.009)))
                unit_price = money(unit_price * (Decimal("1") + drift))

            amount = money(qty * unit_price)
            po_total += amount

            po_line_id = f"{po_id}-L{line_no:03d}"
            line_records.append(
                {
                    "po_line_id": po_line_id,
                    "po_id": po_id,
                    "line_no": line_no,
                    "item_id": item_id,
                    "description": description,
                    "qty": float(qty),
                    "unit_price": float(unit_price),
                    "amount": float(amount),
                    "qty_invoiced_cum": float(qty) if anomaly_type != "QTY_NOT_RECEIVED" else 0.0,
                }
            )

        pos.append(
            {
                "po_id": po_id,
                "po_number": po_id,
                "vendor_id": effective_vendor_id,
                "currency": invoice.get("currency") or "USD",
                "status": po_status,
                "po_date": po_date.isoformat(),
                "total": float(po_total),
                "linked_invoice_id": invoice["invoice_id"],
            }
        )
        po_lines.extend(line_records)

        if anomaly_type != "QTY_NOT_RECEIVED":
            receipt_dates = [po_date + timedelta(days=rng.randint(1, 15))]
            if rng.random() < 0.15:
                receipt_dates.append(po_date + timedelta(days=rng.randint(1, 15)))
            receipt_dates = [min(d, invoice_date - timedelta(days=1)) for d in receipt_dates]

            receive_fraction = 1.0
            if anomaly_type == "QTY_OVER_RECEIVED_SHORT":
                receive_fraction = rng.uniform(0.5, 0.9)
            elif anomaly_type == "QTY_OVER_RECEIVED_PARTIAL":
                receive_fraction = rng.uniform(0.5, 0.8)

            for receipt_date in receipt_dates:
                grn_counter += 1
                grn_id = f"GRN-{grn_counter:06d}"
                receipts.append(
                    {
                        "grn_id": grn_id,
                        "grn_number": grn_id,
                        "po_id": po_id,
                        "received_date": receipt_date.isoformat(),
                        "received_by": "warehouse_seed",
                    }
                )
                for line in line_records:
                    received_qty = round(line["qty"] * receive_fraction / len(receipt_dates), 2)
                    gr_lines.append(
                        {
                            "gr_line_id": f"{grn_id}-{line['po_line_id']}",
                            "grn_id": grn_id,
                            "po_line_id": line["po_line_id"],
                            "qty_received": received_qty,
                        }
                    )

        anomaly_labels.append(
            {
                "invoice_id": invoice["invoice_id"],
                "po_id": po_id,
                "anomaly_type": anomaly_type,
                "expected_reason_code": ANOMALY_REASON_CODES[anomaly_type],
                "is_duplicate_exact": anomaly_type == "DUPLICATE_EXACT",
                "is_duplicate_suspected": anomaly_type == "DUPLICATE_SUSPECTED",
            }
        )

    extra_po_count = int(len(pos) * EXTRA_OPEN_PO_SHARE)
    for i in range(extra_po_count):
        po_counter += 1
        po_id = f"PO-{po_counter:06d}"
        vendor = vendors.sample(n=1, random_state=SEED + i).iloc[0]
        po_date = TODAY - timedelta(days=rng.randint(0, HISTORY_MONTHS * 30))
        item = catalog.sample(n=1, random_state=SEED + i).iloc[0]
        qty = Decimal(str(rng.randint(1, 50)))
        unit_price = money(item["std_price"])
        amount = money(qty * unit_price)
        pos.append(
            {
                "po_id": po_id,
                "po_number": po_id,
                "vendor_id": vendor["vendor_id"],
                "currency": "USD",
                "status": "open",
                "po_date": po_date.isoformat(),
                "total": float(amount),
                "linked_invoice_id": None,
            }
        )
        po_lines.append(
            {
                "po_line_id": f"{po_id}-L001",
                "po_id": po_id,
                "line_no": 1,
                "item_id": item["item_id"],
                "description": item["description"],
                "qty": float(qty),
                "unit_price": float(unit_price),
                "amount": float(amount),
                "qty_invoiced_cum": 0.0,
            }
        )

    return {
        "purchase_orders": pd.DataFrame(pos),
        "po_lines": pd.DataFrame(po_lines),
        "goods_receipts": pd.DataFrame(receipts),
        "gr_lines": pd.DataFrame(gr_lines),
        "anomaly_labels": pd.DataFrame(anomaly_labels),
    }


def build_payment_history(pos: pd.DataFrame, vendors: pd.DataFrame, rng: random.Random) -> pd.DataFrame:
    vendor_terms = vendors.set_index("vendor_id")["payment_terms_days"].to_dict()
    rows = []
    for _, po in pos.iterrows():
        if po["linked_invoice_id"] is None:
            continue
        po_date = datetime.fromisoformat(po["po_date"]).date()
        terms_days = vendor_terms.get(po["vendor_id"], 30)
        due_date = po_date + timedelta(days=terms_days)
        is_old = due_date < TODAY - relativedelta(months=1)
        status = "paid" if is_old else rng.choice(["scheduled", "paid", "pending"])
        payment_date = due_date if status == "paid" else None
        rows.append(
            {
                "invoice_id": po["linked_invoice_id"],
                "po_id": po["po_id"],
                "vendor_id": po["vendor_id"],
                "amount": po["total"],
                "due_date": due_date.isoformat(),
                "payment_date": payment_date.isoformat() if payment_date else "",
                "status": status,
            }
        )
    return pd.DataFrame(rows)


def build_users_seed() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"email": "admin@veridianpayables.demo", "full_name": "Demo Admin", "role": "admin", "approval_limit": None},
            {"email": "clerk@veridianpayables.demo", "full_name": "Demo Clerk", "role": "ap_clerk", "approval_limit": 2500},
            {"email": "approver@veridianpayables.demo", "full_name": "Demo Approver", "role": "approver", "approval_limit": 25000},
            {"email": "manager@veridianpayables.demo", "full_name": "Demo Finance Manager", "role": "finance_manager", "approval_limit": None},
            {"email": "auditor@veridianpayables.demo", "full_name": "Demo Auditor", "role": "auditor", "approval_limit": None},
        ]
    )


def main() -> None:
    if not TRUTH_PATH.exists():
        print(f"{TRUTH_PATH} not found. Run build_truth.py first.")
        return

    rng = random.Random(SEED)
    np.random.seed(SEED)
    faker = Faker()
    faker.seed_instance(SEED)

    truth = pd.read_json(TRUTH_PATH, lines=True)

    vendors = build_vendors(truth, rng, faker)
    catalog = build_item_catalog(rng, faker)
    documents = build_documents(truth, vendors, catalog, rng)
    payments = build_payment_history(documents["purchase_orders"], vendors, rng)
    users_seed = build_users_seed()

    SYNTHETIC_DIR.mkdir(parents=True, exist_ok=True)
    vendors.to_csv(SYNTHETIC_DIR / "vendors.csv", index=False)
    catalog.to_csv(SYNTHETIC_DIR / "items_catalog.csv", index=False)
    documents["purchase_orders"].to_csv(SYNTHETIC_DIR / "purchase_orders.csv", index=False)
    documents["po_lines"].to_csv(SYNTHETIC_DIR / "po_lines.csv", index=False)
    documents["goods_receipts"].to_csv(SYNTHETIC_DIR / "goods_receipts.csv", index=False)
    documents["gr_lines"].to_csv(SYNTHETIC_DIR / "gr_lines.csv", index=False)
    documents["anomaly_labels"].to_csv(SYNTHETIC_DIR / "anomaly_labels.csv", index=False)
    payments.to_csv(SYNTHETIC_DIR / "payments_history.csv", index=False)
    users_seed.to_csv(SYNTHETIC_DIR / "users_seed.csv", index=False)

    print(f"Vendors: {len(vendors)}, items: {len(catalog)}")
    print(f"Purchase orders: {len(documents['purchase_orders'])}, PO lines: {len(documents['po_lines'])}")
    print(f"Goods receipts: {len(documents['goods_receipts'])}, GR lines: {len(documents['gr_lines'])}")
    print(f"Anomaly labels: {len(documents['anomaly_labels'])}")
    print(f"Payment history rows: {len(payments)}")
    print(f"Wrote CSVs to {SYNTHETIC_DIR}")


if __name__ == "__main__":
    main()
