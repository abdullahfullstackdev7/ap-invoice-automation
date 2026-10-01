"""Compare RapidOCR and Tesseract on the evaluation invoice set.

Reads dataset/processed/truth_invoices.jsonl (the eval split; see
dataset/README.md for how to rebuild it from FATURA) and dataset/raw/
images, runs both OCR engines on each page, and reports mean word
confidence, median time per page, and a field-presence rate (how often
each invoice's known invoice_no and total appear as substrings of the
recognized text - a cheap proxy for downstream field accuracy, since the
Phase 5 rules extractor does not exist yet to compute a real field F1).

Writes results as a Markdown table to docs/evaluation.md.

If Tesseract is not installed (no system binary), its column is marked
"unavailable" rather than failing the whole bake-off, since RapidOCR
alone still produces a useful comparison and is the Plan's primary engine.
"""

import json
import statistics
import time
from pathlib import Path
from typing import Any

from app.ocr.preprocessing import load_image_bytes
from app.ocr.rapidocr_engine import run_rapidocr
from app.ocr.tesseract_engine import run_tesseract

BACKEND_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = BACKEND_DIR.parent
DATASET_DIR = REPO_ROOT / "dataset"
TRUTH_PATH = DATASET_DIR / "processed" / "truth_invoices.jsonl"
RAW_DIR = DATASET_DIR / "raw"
EVAL_SAMPLE_SIZE = 200

DOCS_DIR = REPO_ROOT / "docs"
EVALUATION_MD = DOCS_DIR / "evaluation.md"


def _tesseract_available() -> bool:
    try:
        import pytesseract

        pytesseract.get_tesseract_version()
        return True
    except Exception:
        return False


def _field_presence_rate(text: str, invoice: dict[str, Any]) -> float:
    fields = [str(invoice.get("invoice_no") or ""), str(invoice.get("total") or "")]
    fields = [f for f in fields if f]
    if not fields:
        return 0.0
    hits = sum(1 for f in fields if f in text)
    return hits / len(fields)


def run_bakeoff() -> dict[str, Any]:
    if not TRUTH_PATH.exists():
        raise FileNotFoundError(
            f"{TRUTH_PATH} not found. Run the dataset pipeline first "
            "(dataset/README.md) to produce the evaluation split."
        )

    invoices = []
    with TRUTH_PATH.open(encoding="utf-8") as f:
        for line in f:
            invoices.append(json.loads(line))
    invoices = invoices[:EVAL_SAMPLE_SIZE]

    tesseract_ok = _tesseract_available()

    rapidocr_confidences: list[float] = []
    rapidocr_times: list[float] = []
    rapidocr_field_rates: list[float] = []

    tesseract_confidences: list[float] = []
    tesseract_times: list[float] = []
    tesseract_field_rates: list[float] = []

    processed = 0
    for invoice in invoices:
        image_path = RAW_DIR / invoice["image_path"]
        if not image_path.exists():
            continue

        image = load_image_bytes(image_path.read_bytes())

        start = time.perf_counter()
        rapid_result = run_rapidocr(image, page=1)
        rapidocr_times.append(time.perf_counter() - start)
        rapidocr_confidences.append(rapid_result.mean_confidence)
        rapid_text = " ".join(line.text for line in rapid_result.lines)
        rapidocr_field_rates.append(_field_presence_rate(rapid_text, invoice))

        if tesseract_ok:
            start = time.perf_counter()
            tess_result = run_tesseract(image, page=1)
            tesseract_times.append(time.perf_counter() - start)
            tesseract_confidences.append(tess_result.mean_confidence)
            tess_text = " ".join(line.text for line in tess_result.lines)
            tesseract_field_rates.append(_field_presence_rate(tess_text, invoice))

        processed += 1

    return {
        "processed": processed,
        "tesseract_available": tesseract_ok,
        "rapidocr": {
            "mean_confidence": statistics.mean(rapidocr_confidences)
            if rapidocr_confidences
            else 0.0,
            "median_time_s": statistics.median(rapidocr_times) if rapidocr_times else 0.0,
            "field_presence_rate": statistics.mean(rapidocr_field_rates)
            if rapidocr_field_rates
            else 0.0,
        },
        "tesseract": {
            "mean_confidence": statistics.mean(tesseract_confidences)
            if tesseract_confidences
            else None,
            "median_time_s": statistics.median(tesseract_times) if tesseract_times else None,
            "field_presence_rate": statistics.mean(tesseract_field_rates)
            if tesseract_field_rates
            else None,
        },
    }


def render_markdown(results: dict[str, Any]) -> str:
    def fmt(value: float | None, suffix: str = "") -> str:
        return "unavailable" if value is None else f"{value:.3f}{suffix}"

    lines = [
        "## OCR engine bake-off",
        "",
        f"Pages evaluated: {results['processed']}",
        "",
        "| Engine | Mean word confidence | Median time/page | Field presence rate |",
        "|---|---|---|---|",
        f"| RapidOCR | {fmt(results['rapidocr']['mean_confidence'])} | "
        f"{fmt(results['rapidocr']['median_time_s'], 's')} | "
        f"{fmt(results['rapidocr']['field_presence_rate'])} |",
        f"| Tesseract | {fmt(results['tesseract']['mean_confidence'])} | "
        f"{fmt(results['tesseract']['median_time_s'], 's')} | "
        f"{fmt(results['tesseract']['field_presence_rate'])} |",
        "",
    ]
    if not results["tesseract_available"]:
        lines.append(
            "Tesseract was not installed in the environment this bake-off ran in "
            "(no system binary); only RapidOCR was measured. Re-run inside the "
            "`api`/`worker` Docker image, which installs `tesseract-ocr`, for a "
            "full comparison."
        )
        lines.append("")

    return "\n".join(lines)


def main() -> None:
    results = run_bakeoff()
    section = render_markdown(results)

    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    existing = (
        EVALUATION_MD.read_text(encoding="utf-8") if EVALUATION_MD.exists() else "# Evaluation\n"
    )

    marker = "## OCR engine bake-off"
    if marker in existing:
        before, _, after_start = existing.partition(marker)
        after = after_start.split("\n\n", 1)
        remainder = after[1] if len(after) > 1 else ""
        existing = before + section + ("\n" + remainder if remainder else "")
    else:
        existing = existing.rstrip() + "\n\n" + section

    EVALUATION_MD.write_text(existing, encoding="utf-8")
    print(section)
    print(f"Wrote {EVALUATION_MD}")


if __name__ == "__main__":
    main()
