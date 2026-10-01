import numpy as np
import pytesseract
from PIL import Image

from app.ocr.layout import reconstruct_lines
from app.ocr.types import BoundingBox, OCRPageResult, OCRWord


def run_tesseract(image: np.ndarray, page: int) -> OCRPageResult:
    pil_image = Image.fromarray(image[:, :, ::-1])  # BGR -> RGB
    data = pytesseract.image_to_data(pil_image, output_type=pytesseract.Output.DICT)

    words: list[OCRWord] = []
    for i, text in enumerate(data["text"]):
        if not text.strip():
            continue
        conf_raw = data["conf"][i]
        conf = float(conf_raw) if str(conf_raw) not in ("-1", "") else 0.0
        x, y, w, h = data["left"][i], data["top"][i], data["width"][i], data["height"][i]
        words.append(
            OCRWord(
                text=text,
                bbox=BoundingBox(x0=x, y0=y, x1=x + w, y1=y + h),
                conf=max(conf, 0.0) / 100.0,
                page=page,
            )
        )

    mean_conf = sum(w.conf for w in words) / len(words) if words else 0.0
    return OCRPageResult(
        page=page,
        words=words,
        lines=reconstruct_lines(words, page),
        mean_confidence=mean_conf,
        engine="tesseract",
    )
