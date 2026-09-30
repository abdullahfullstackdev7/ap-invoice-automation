"""Bulk load the synthetic dataset into PostgreSQL with COPY, then generate
vendor and item embeddings in batches and build the HNSW indexes.

This script targets the schema created by the backend's Alembic migrations
(Phase 2 of Plan.md). It is safe to write now and keep here since the
dataset scripts directory is where Plan.md section 4.2 places it, but it
will only run successfully once that schema exists. Target: full load
under 5 minutes.
"""

from __future__ import annotations

import csv
import io
import os
import sys
import time
from pathlib import Path

import psycopg

DATASET_DIR = Path(__file__).resolve().parent.parent
SYNTHETIC_DIR = DATASET_DIR / "synthetic"

TABLE_LOAD_ORDER: list[tuple[str, list[str]]] = [
    ("vendors", ["code", "name", "name_normalized", "tax_id", "address", "email",
                 "payment_terms_days", "discount_pct", "discount_days", "risk_tier",
                 "category", "status"]),
    ("items", ["sku", "description", "unit", "std_price", "category"]),
]

EMBEDDING_BATCH_SIZE = 64


def copy_csv(conn: psycopg.Connection, csv_path: Path, table: str, columns: list[str]) -> int:
    with csv_path.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        row_count = 0
        for row in reader:
            writer.writerow([row.get(col, "") for col in columns])
            row_count += 1
        buffer.seek(0)

    column_list = ", ".join(columns)
    with conn.cursor() as cur, cur.copy(f"COPY {table} ({column_list}) FROM STDIN WITH CSV") as copy:
        copy.write(buffer.read())

    return row_count


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


def build_hnsw_indexes(conn: psycopg.Connection) -> None:
    statements = [
        "CREATE INDEX IF NOT EXISTS ix_vendors_embedding ON vendors "
        "USING hnsw (embedding vector_cosine_ops)",
        "CREATE INDEX IF NOT EXISTS ix_items_embedding ON items "
        "USING hnsw (embedding vector_cosine_ops)",
        "CREATE INDEX IF NOT EXISTS ix_invoice_lines_embedding ON invoice_lines "
        "USING hnsw (embedding vector_cosine_ops)",
    ]
    with conn.cursor() as cur:
        for statement in statements:
            cur.execute(statement)
    conn.commit()


def main() -> None:
    database_url = os.environ.get(
        "DATABASE_URL", "postgresql://app_rw:change_me@localhost:5432/apdb"
    ).replace("postgresql+psycopg://", "postgresql://")

    start = time.perf_counter()
    with psycopg.connect(database_url) as conn:
        for table, columns in TABLE_LOAD_ORDER:
            csv_path = SYNTHETIC_DIR / f"{table if table != 'items' else 'items_catalog'}.csv"
            if not csv_path.exists():
                print(f"Skipping {table}: {csv_path} not found.")
                continue
            count = copy_csv(conn, csv_path, table, columns)
            conn.commit()
            print(f"Loaded {count} rows into {table}")

        generate_embeddings(conn, "vendors", "name")
        generate_embeddings(conn, "items", "description")
        build_hnsw_indexes(conn)

    elapsed = time.perf_counter() - start
    print(f"Load complete in {elapsed:.1f}s")
    if elapsed > 300:
        print("WARNING: load exceeded the 5 minute target from Plan.md section 4.8", file=sys.stderr)


if __name__ == "__main__":
    main()
