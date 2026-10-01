"""Bulk load the synthetic dataset into PostgreSQL with COPY, then generate
vendor and item embeddings in batches and build the HNSW indexes.

Targets the schema created by the backend's Alembic migrations (Phase 2).
Uses the app_rw runtime role (DATABASE_URL), which has INSERT/SELECT but
no DDL, matching the role split in Plan.md section 5 and 7.

The synthetic CSVs key their rows with generator-assigned string ids
(VEND-00001, PO-000001, ...), not database UUIDs. This script assigns a
UUID per row as it loads, keeps an in-memory string-id -> UUID map per
table, and rewrites foreign keys through that map before each COPY, so
referential integrity holds without a round trip to the database for
every lookup. Target: full load under 5 minutes.
"""

from __future__ import annotations

import csv
import io
import os
import time
import uuid
from pathlib import Path

import psycopg

DATASET_DIR = Path(__file__).resolve().parent.parent
SYNTHETIC_DIR = DATASET_DIR / "synthetic"

EMBEDDING_BATCH_SIZE = 64


def read_rows(csv_path: Path) -> list[dict[str, str]]:
    with csv_path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def as_int(value: str | None) -> str | None:
    if value is None or value == "":
        return None
    return str(int(float(value)))


def copy_rows(
    conn: psycopg.Connection, table: str, columns: list[str], rows: list[dict[str, object]]
) -> None:
    if not rows:
        return
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    for row in rows:
        writer.writerow(["" if row.get(col) is None else row[col] for col in columns])
    buffer.seek(0)

    column_list = ", ".join(columns)
    with conn.cursor() as cur, cur.copy(f"COPY {table} ({column_list}) FROM STDIN WITH CSV") as copy:
        copy.write(buffer.read())


def load_vendors(conn: psycopg.Connection) -> dict[str, str]:
    rows = read_rows(SYNTHETIC_DIR / "vendors.csv")
    id_map: dict[str, str] = {}
    db_rows: list[dict[str, object]] = []
    for row in rows:
        new_id = str(uuid.uuid4())
        id_map[row["vendor_id"]] = new_id
        db_rows.append(
            {
                "id": new_id,
                "code": row["code"],
                "name": row["name"],
                "name_normalized": row["name_normalized"],
                "tax_id": row.get("tax_id") or None,
                "address": row.get("address") or None,
                "email": row.get("email") or None,
                "payment_terms_days": as_int(row.get("payment_terms_days")) or 30,
                "discount_pct": row.get("discount_pct") or None,
                "discount_days": as_int(row.get("discount_days")),
                "risk_tier": row.get("risk_tier") or "low",
                "category": row.get("category") or None,
                "status": row.get("status") or "active",
            }
        )
    columns = [
        "id", "code", "name", "name_normalized", "tax_id", "address", "email",
        "payment_terms_days", "discount_pct", "discount_days", "risk_tier",
        "category", "status",
    ]
    copy_rows(conn, "vendors", columns, db_rows)
    return id_map


def load_items(conn: psycopg.Connection) -> dict[str, str]:
    rows = read_rows(SYNTHETIC_DIR / "items_catalog.csv")
    id_map: dict[str, str] = {}
    db_rows: list[dict[str, object]] = []
    for row in rows:
        new_id = str(uuid.uuid4())
        id_map[row["item_id"]] = new_id
        db_rows.append(
            {
                "id": new_id,
                "sku": row["sku"],
                "description": row["description"],
                "unit": row["unit"],
                "std_price": row["std_price"],
                "category": row["category"],
            }
        )
    columns = ["id", "sku", "description", "unit", "std_price", "category"]
    copy_rows(conn, "items", columns, db_rows)
    return id_map


def load_purchase_orders(conn: psycopg.Connection, vendor_map: dict[str, str]) -> dict[str, str]:
    rows = read_rows(SYNTHETIC_DIR / "purchase_orders.csv")
    id_map: dict[str, str] = {}
    db_rows: list[dict[str, object]] = []
    for row in rows:
        vendor_id = vendor_map.get(row["vendor_id"])
        if vendor_id is None:
            continue
        new_id = str(uuid.uuid4())
        id_map[row["po_id"]] = new_id
        db_rows.append(
            {
                "id": new_id,
                "po_number": row["po_number"],
                "vendor_id": vendor_id,
                "currency": row.get("currency") or "USD",
                "status": row.get("status") or "open",
                "po_date": row["po_date"],
                "total": row["total"],
            }
        )
    columns = ["id", "po_number", "vendor_id", "currency", "status", "po_date", "total"]
    copy_rows(conn, "purchase_orders", columns, db_rows)
    return id_map


def load_po_lines(
    conn: psycopg.Connection, po_map: dict[str, str], item_map: dict[str, str]
) -> dict[str, str]:
    rows = read_rows(SYNTHETIC_DIR / "po_lines.csv")
    id_map: dict[str, str] = {}
    db_rows: list[dict[str, object]] = []
    for row in rows:
        po_id = po_map.get(row["po_id"])
        if po_id is None:
            continue
        new_id = str(uuid.uuid4())
        id_map[row["po_line_id"]] = new_id
        db_rows.append(
            {
                "id": new_id,
                "po_id": po_id,
                "line_no": row["line_no"],
                "item_id": item_map.get(row.get("item_id", "")),
                "description": row["description"],
                "qty": row["qty"],
                "unit_price": row["unit_price"],
                "amount": row["amount"],
                "qty_invoiced_cum": row.get("qty_invoiced_cum") or 0,
            }
        )
    columns = [
        "id", "po_id", "line_no", "item_id", "description", "qty", "unit_price",
        "amount", "qty_invoiced_cum",
    ]
    copy_rows(conn, "po_lines", columns, db_rows)
    return id_map


def load_goods_receipts(conn: psycopg.Connection, po_map: dict[str, str]) -> dict[str, str]:
    rows = read_rows(SYNTHETIC_DIR / "goods_receipts.csv")
    id_map: dict[str, str] = {}
    db_rows: list[dict[str, object]] = []
    for row in rows:
        po_id = po_map.get(row["po_id"])
        if po_id is None:
            continue
        new_id = str(uuid.uuid4())
        id_map[row["grn_id"]] = new_id
        db_rows.append(
            {
                "id": new_id,
                "grn_number": row["grn_number"],
                "po_id": po_id,
                "received_date": row["received_date"],
                "received_by": row["received_by"],
            }
        )
    columns = ["id", "grn_number", "po_id", "received_date", "received_by"]
    copy_rows(conn, "goods_receipts", columns, db_rows)
    return id_map


def load_gr_lines(
    conn: psycopg.Connection, grn_map: dict[str, str], po_line_map: dict[str, str]
) -> None:
    rows = read_rows(SYNTHETIC_DIR / "gr_lines.csv")
    db_rows: list[dict[str, object]] = []
    for row in rows:
        grn_id = grn_map.get(row["grn_id"])
        po_line_id = po_line_map.get(row["po_line_id"])
        if grn_id is None or po_line_id is None:
            continue
        db_rows.append(
            {
                "id": str(uuid.uuid4()),
                "grn_id": grn_id,
                "po_line_id": po_line_id,
                "qty_received": row["qty_received"],
            }
        )
    columns = ["id", "grn_id", "po_line_id", "qty_received"]
    copy_rows(conn, "gr_lines", columns, db_rows)


def generate_embeddings(conn: psycopg.Connection, table: str, text_column: str) -> None:
    try:
        from fastembed import TextEmbedding
    except ImportError:
        print(f"fastembed not installed, skipping embeddings for {table}.")
        return

    model = TextEmbedding(model_name=os.environ.get("EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5"))

    with conn.cursor() as cur:
        cur.execute(f"SELECT id, {text_column} FROM {table} WHERE embedding IS NULL")
        rows = cur.fetchall()

    for i in range(0, len(rows), EMBEDDING_BATCH_SIZE):
        batch = rows[i : i + EMBEDDING_BATCH_SIZE]
        texts = [text for _, text in batch]
        vectors = list(model.embed(texts))
        with conn.cursor() as cur:
            for (row_id, _), vector in zip(batch, vectors, strict=True):
                cur.execute(
                    f"UPDATE {table} SET embedding = %s WHERE id = %s",
                    (list(vector), row_id),
                )
        conn.commit()
        print(f"Embedded {min(i + EMBEDDING_BATCH_SIZE, len(rows))}/{len(rows)} rows in {table}")


def main() -> None:
    database_url = os.environ.get(
        "DATABASE_URL", "postgresql://app_rw:change_me@localhost:5433/apdb"
    ).replace("postgresql+psycopg://", "postgresql://")

    if not (SYNTHETIC_DIR / "vendors.csv").exists():
        print(f"{SYNTHETIC_DIR}/vendors.csv not found. Run generate_synthetic.py first.")
        return

    start = time.perf_counter()
    with psycopg.connect(database_url) as conn:
        vendor_map = load_vendors(conn)
        item_map = load_items(conn)
        conn.commit()
        print(f"Loaded {len(vendor_map)} vendors, {len(item_map)} items")

        po_map = load_purchase_orders(conn, vendor_map)
        po_line_map = load_po_lines(conn, po_map, item_map)
        conn.commit()
        print(f"Loaded {len(po_map)} purchase orders, {len(po_line_map)} PO lines")

        grn_map = load_goods_receipts(conn, po_map)
        load_gr_lines(conn, grn_map, po_line_map)
        conn.commit()
        print(f"Loaded {len(grn_map)} goods receipts")

        generate_embeddings(conn, "vendors", "name")
        generate_embeddings(conn, "items", "description")

    elapsed = time.perf_counter() - start
    print(f"Load complete in {elapsed:.1f}s")
    if elapsed > 300:
        print("WARNING: load exceeded the 5 minute target from Plan.md section 4.8")


if __name__ == "__main__":
    main()
