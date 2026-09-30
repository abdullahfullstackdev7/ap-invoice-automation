"""Select the 1,000-invoice demo set and the held-out evaluation set.

About 20 invoices per template across all 50 templates go into the demo
set (seeded, seed=42). The remaining invoices, including any fully unseen
templates, form the evaluation set. Demo and evaluation sets never overlap.
Writes dataset/processed/template_index.csv with the split assignment, and
copies the selected demo images (60% converted to PDF, 40% kept as JPG)
into dataset/demo/invoices/.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import img2pdf
import pandas as pd

SEED = 42
DEMO_PER_TEMPLATE = 20
DEMO_PDF_FRACTION = 0.6

DATASET_DIR = Path(__file__).resolve().parent.parent
RAW_DIR = DATASET_DIR / "raw"
PROCESSED_DIR = DATASET_DIR / "processed"
TRUTH_PATH = PROCESSED_DIR / "truth_invoices.jsonl"
DEMO_INVOICES_DIR = DATASET_DIR / "demo" / "invoices"
TEMPLATE_INDEX_PATH = PROCESSED_DIR / "template_index.csv"


def load_truth() -> pd.DataFrame:
    if not TRUTH_PATH.exists():
        raise FileNotFoundError(f"{TRUTH_PATH} not found. Run build_truth.py first.")
    return pd.read_json(TRUTH_PATH, lines=True)


def assign_splits(truth: pd.DataFrame) -> pd.DataFrame:
    demo_rows = []
    for _template_id, group in truth.groupby("template_id"):
        sample_size = min(DEMO_PER_TEMPLATE, len(group))
        sample = group.sample(n=sample_size, random_state=SEED)
        demo_rows.append(sample)

    demo_df = pd.concat(demo_rows) if demo_rows else truth.iloc[0:0]
    demo_ids = set(demo_df["invoice_id"])

    truth = truth.copy()
    truth["split"] = truth["invoice_id"].apply(lambda i: "demo" if i in demo_ids else "eval")
    return truth


def materialize_demo_images(truth_with_split: pd.DataFrame) -> None:
    demo = truth_with_split[truth_with_split["split"] == "demo"]
    DEMO_INVOICES_DIR.mkdir(parents=True, exist_ok=True)

    demo_sorted = demo.sort_values("invoice_id").reset_index(drop=True)
    pdf_cutoff = int(len(demo_sorted) * DEMO_PDF_FRACTION)

    for idx, row in demo_sorted.iterrows():
        src = RAW_DIR / row["image_path"]
        if not src.exists():
            continue

        as_pdf = idx < pdf_cutoff
        if as_pdf:
            dst = DEMO_INVOICES_DIR / f"{row['invoice_id']}.pdf"
            with open(dst, "wb") as f:
                f.write(img2pdf.convert(str(src)))
        else:
            dst = DEMO_INVOICES_DIR / f"{row['invoice_id']}{src.suffix}"
            shutil.copyfile(src, dst)


def main() -> None:
    truth = load_truth()
    truth_with_split = assign_splits(truth)

    template_index = truth_with_split[["invoice_id", "template_id", "split"]]
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    template_index.to_csv(TEMPLATE_INDEX_PATH, index=False)

    materialize_demo_images(truth_with_split)

    demo_count = (truth_with_split["split"] == "demo").sum()
    eval_count = (truth_with_split["split"] == "eval").sum()
    unseen_templates = set(
        truth_with_split.loc[truth_with_split["split"] == "eval", "template_id"]
    ) - set(truth_with_split.loc[truth_with_split["split"] == "demo", "template_id"])

    print(f"Demo set: {demo_count} invoices. Evaluation set: {eval_count} invoices.")
    print(f"Fully unseen templates in the evaluation set: {len(unseen_templates)}")
    print(f"Wrote {TEMPLATE_INDEX_PATH}")


if __name__ == "__main__":
    main()
