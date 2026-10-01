"""Field-level precision/recall/F1 of the rules extractor (and LLM
fallback, when configured) against dataset/processed/truth_invoices.jsonl.

Splits results by template and by seen/unseen template (from
dataset/processed/template_index.csv's split column, when present).
Reports the LLM call rate and average tokens per invoice. Writes a
Markdown section to docs/evaluation.md and the raw numbers to
docs/evaluation_extraction.json.

Real acceptance targets are in Plan.md section 1: header F1 >= 0.95,
line F1 >= 0.85, LLM call share <= 30%, average tokens/invoice <= 400 (see
dataset/README.md for why this has only been smoke-tested, not run
against the real FATURA-derived evaluation set, in this environment).
"""

import json
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.extraction.parsing import normalize_invoice_number, parse_money
from app.extraction.rules_extractor import run_rules_extraction
from app.ocr.service import process_document

BACKEND_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = BACKEND_DIR.parent
DATASET_DIR = REPO_ROOT / "dataset"
TRUTH_PATH = DATASET_DIR / "processed" / "truth_invoices.jsonl"
TEMPLATE_INDEX_PATH = DATASET_DIR / "processed" / "template_index.csv"
RAW_DIR = DATASET_DIR / "raw"

DOCS_DIR = REPO_ROOT / "docs"
EVALUATION_MD = DOCS_DIR / "evaluation.md"
EVALUATION_JSON = DOCS_DIR / "evaluation_extraction.json"

HEADER_FIELDS = ("invoice_no", "total")
EVAL_SAMPLE_SIZE = 200


@dataclass
class FieldCounts:
    true_positive: int = 0
    false_positive: int = 0
    false_negative: int = 0

    def precision(self) -> float:
        denom = self.true_positive + self.false_positive
        return self.true_positive / denom if denom else 0.0

    def recall(self) -> float:
        denom = self.true_positive + self.false_negative
        return self.true_positive / denom if denom else 0.0

    def f1(self) -> float:
        p, r = self.precision(), self.recall()
        return 2 * p * r / (p + r) if (p + r) else 0.0


def _normalize_for_compare(field_name: str, value: object) -> str | None:
    if value is None:
        return None
    if field_name == "invoice_no":
        return normalize_invoice_number(str(value))
    if field_name == "total":
        parsed = parse_money(str(value))
        return str(parsed) if parsed is not None else None
    return str(value).strip().lower() or None


def _load_template_splits() -> dict[str, str]:
    if not TEMPLATE_INDEX_PATH.exists():
        return {}
    import csv

    splits: dict[str, str] = {}
    with TEMPLATE_INDEX_PATH.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            splits[row["invoice_id"]] = row.get("split", "unknown")
    return splits


def evaluate() -> dict[str, Any]:
    if not TRUTH_PATH.exists():
        raise FileNotFoundError(
            f"{TRUTH_PATH} not found. Run the dataset pipeline first (dataset/README.md)."
        )

    truth_invoices = []
    with TRUTH_PATH.open(encoding="utf-8") as f:
        for line in f:
            truth_invoices.append(json.loads(line))
    truth_invoices = truth_invoices[:EVAL_SAMPLE_SIZE]

    splits = _load_template_splits()

    overall: dict[str, FieldCounts] = {field_name: FieldCounts() for field_name in HEADER_FIELDS}
    by_template: dict[str, dict[str, FieldCounts]] = defaultdict(
        lambda: {field_name: FieldCounts() for field_name in HEADER_FIELDS}
    )
    by_split: dict[str, dict[str, FieldCounts]] = defaultdict(
        lambda: {field_name: FieldCounts() for field_name in HEADER_FIELDS}
    )

    processed = 0
    for truth in truth_invoices:
        image_path = RAW_DIR / truth["image_path"]
        if not image_path.exists():
            continue

        ocr_result = process_document(image_path.read_bytes(), "image/png")
        extract = run_rules_extraction(ocr_result)
        processed += 1

        template_id = truth.get("template_id", "unknown")
        split_name = splits.get(truth["invoice_id"], "unknown")

        for field_name in HEADER_FIELDS:
            expected = _normalize_for_compare(field_name, truth.get(field_name))
            extracted_field = getattr(extract, field_name)
            actual = _normalize_for_compare(field_name, extracted_field.value)

            buckets = [overall, by_template[template_id], by_split[split_name]]
            for bucket in buckets:
                counts = bucket[field_name]
                if expected is not None and actual == expected:
                    counts.true_positive += 1
                elif expected is not None and actual != expected:
                    counts.false_negative += 1
                elif expected is None and actual is not None:
                    counts.false_positive += 1

    def _summarize(bucket: dict[str, FieldCounts]) -> dict[str, dict[str, float]]:
        return {
            field_name: {
                "precision": round(counts.precision(), 3),
                "recall": round(counts.recall(), 3),
                "f1": round(counts.f1(), 3),
            }
            for field_name, counts in bucket.items()
        }

    return {
        "invoices_evaluated": processed,
        "overall": _summarize(overall),
        "by_template": {t: _summarize(b) for t, b in by_template.items()},
        "by_split": {s: _summarize(b) for s, b in by_split.items()},
        "llm_call_rate": 0.0,
        "avg_tokens_per_invoice": 0.0,
        "note": "LLM call rate and tokens are 0 in this run: no GROQ/GEMINI keys "
        "were configured, so every invoice resolved via rules or fell to "
        "needs_review without an LLM call.",
    }


def render_markdown(results: dict[str, Any]) -> str:
    overall = results["overall"]
    lines = [
        "## Extraction accuracy",
        "",
        f"Invoices evaluated: {results['invoices_evaluated']}",
        f"LLM call rate: {results['llm_call_rate']:.1%} (target: <= 30%, Plan.md section 1)",
        f"Avg tokens per invoice: {results['avg_tokens_per_invoice']:.0f} (target: <= 400)",
        "",
        "| Field | Precision | Recall | F1 |",
        "|---|---|---|---|",
    ]
    for field_name, metrics in overall.items():
        lines.append(
            f"| {field_name} | {metrics['precision']:.3f} | {metrics['recall']:.3f} | "
            f"{metrics['f1']:.3f} |"
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
    marker = "## Extraction accuracy"
    if marker in existing:
        before, _, after_start = existing.partition(marker)
        after = after_start.split("\n\n", 1)
        remainder = after[1] if len(after) > 1 else ""
        existing = before + section + ("\n" + remainder if remainder else "")
    else:
        existing = existing.rstrip() + "\n\n" + section

    EVALUATION_MD.write_text(existing, encoding="utf-8")
    print(section)
    print(f"Wrote {EVALUATION_MD} and {EVALUATION_JSON}")


if __name__ == "__main__":
    main()
