"""Inspect the extracted FATURA dataset and report its actual structure.

Never assume FATURA's directory layout, annotation key names or class names.
This script reads them straight from the files on disk and writes a short
report so dataset/README.md can be filled in with real, observed facts
instead of guesses.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

DATASET_DIR = Path(__file__).resolve().parent.parent
RAW_DIR = DATASET_DIR / "raw"
REPORT_PATH = DATASET_DIR / "processed" / "fatura_inspection_report.json"


def list_top_level(raw_dir: Path) -> dict[str, object]:
    if not raw_dir.exists():
        return {"error": f"{raw_dir} does not exist. Run download_fatura.sh first."}

    entries = sorted(p.name for p in raw_dir.iterdir())
    return {"top_level_entries": entries}


def find_annotation_files(raw_dir: Path, limit: int = 500) -> list[Path]:
    candidates: list[Path] = []
    for ext in ("*.json", "*.xml", "*.txt"):
        candidates.extend(raw_dir.rglob(ext))
        if len(candidates) >= limit:
            break
    return candidates[:limit]


def sample_json_keys(paths: list[Path], sample_size: int = 20) -> dict[str, object]:
    json_paths = [p for p in paths if p.suffix == ".json"][:sample_size]
    samples = []
    key_counter: Counter[str] = Counter()

    for path in json_paths:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            continue
        keys = _flatten_keys(data)
        key_counter.update(keys)
        samples.append({"file": str(path.relative_to(RAW_DIR)), "top_level_keys": _top_keys(data)})

    return {
        "json_files_sampled": len(samples),
        "samples": samples,
        "key_frequency": key_counter.most_common(50),
    }


def _top_keys(data: object) -> list[str]:
    if isinstance(data, dict):
        return list(data.keys())
    if isinstance(data, list) and data and isinstance(data[0], dict):
        return list(data[0].keys())
    return []


def _flatten_keys(data: object, prefix: str = "") -> list[str]:
    keys: list[str] = []
    if isinstance(data, dict):
        for key, value in data.items():
            full_key = f"{prefix}.{key}" if prefix else key
            keys.append(full_key)
            keys.extend(_flatten_keys(value, full_key))
    elif isinstance(data, list):
        for item in data[:1]:
            keys.extend(_flatten_keys(item, prefix))
    return keys


def collect_class_names(paths: list[Path]) -> Counter[str]:
    """Best-effort collection of annotation class or category names.

    Looks for common keys used by COCO-style and label-studio-style exports
    (category_id/name, label, class) without assuming which one FATURA uses.
    """
    class_counter: Counter[str] = Counter()
    candidate_keys = {"label", "class", "category", "category_name", "name", "class_name"}

    for path in [p for p in paths if p.suffix == ".json"]:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            continue
        _walk_for_classes(data, candidate_keys, class_counter)

    return class_counter


def _walk_for_classes(data: object, candidate_keys: set[str], counter: Counter[str]) -> None:
    if isinstance(data, dict):
        for key, value in data.items():
            if key in candidate_keys and isinstance(value, str):
                counter[value] += 1
            _walk_for_classes(value, candidate_keys, counter)
    elif isinstance(data, list):
        for item in data:
            _walk_for_classes(item, candidate_keys, counter)


def main() -> None:
    report: dict[str, object] = {}
    report.update(list_top_level(RAW_DIR))

    if "error" in report:
        print(json.dumps(report, indent=2))
        return

    annotation_files = find_annotation_files(RAW_DIR)
    report["annotation_files_found"] = len(annotation_files)
    report["json_inspection"] = sample_json_keys(annotation_files)
    report["candidate_class_names"] = collect_class_names(annotation_files).most_common(30)

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(f"Wrote inspection report to {REPORT_PATH}")
    print(json.dumps({k: v for k, v in report.items() if k != "json_inspection"}, indent=2)[:3000])


if __name__ == "__main__":
    main()
