from functools import lru_cache
from typing import Any

import numpy as np

from app.ocr.layout import reconstruct_lines
from app.ocr.types import BoundingBox, OCRPageResult, OCRWord


@lru_cache
def _get_engine() -> Any:
    from rapidocr_onnxruntime import RapidOCR

    return RapidOCR()


def run_rapidocr(image: np.ndarray, page: int) -> OCRPageResult:
    engine = _get_engine()
    result, _ = engine(image)

    words: list[OCRWord] = []
    if result:
        for box, text, conf in result:
            xs = [point[0] for point in box]
            ys = [point[1] for point in box]
            words.append(
                OCRWord(
                    text=text,
                    bbox=BoundingBox(x0=min(xs), y0=min(ys), x1=max(xs), y1=max(ys)),
                    conf=float(conf),
                    page=page,
                )
            )

    mean_conf = sum(w.conf for w in words) / len(words) if words else 0.0
    return OCRPageResult(
        page=page,
        words=words,
        lines=reconstruct_lines(words, page),
        mean_confidence=mean_conf,
        engine="rapidocr",
    )
