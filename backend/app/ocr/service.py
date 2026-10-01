import structlog

from app.core.settings import get_settings
from app.ocr.preprocessing import (
    extract_pdf_text_layer,
    load_image_bytes,
    pdf_has_text_layer,
    preprocess_page,
    render_pdf_pages,
)
from app.ocr.rapidocr_engine import run_rapidocr
from app.ocr.tesseract_engine import run_tesseract
from app.ocr.types import BoundingBox, OCRDocumentResult, OCRLine, OCRPageResult, OCRWord

logger = structlog.get_logger(__name__)

LOW_CONFIDENCE_THRESHOLD = 0.6


def _run_engine(image: object, page: int, engine_name: str) -> OCRPageResult:
    if engine_name == "tesseract":
        return run_tesseract(image, page)  # type: ignore[arg-type]
    return run_rapidocr(image, page)  # type: ignore[arg-type]


def run_ocr_on_images(images: list[object]) -> OCRDocumentResult:
    settings = get_settings()
    primary = settings.ocr_engine
    fallback = "tesseract" if primary == "rapidocr" else "rapidocr"

    pages: list[OCRPageResult] = []
    for idx, image in enumerate(images, start=1):
        processed = preprocess_page(image)  # type: ignore[arg-type]
        result = _run_engine(processed, idx, primary)

        if result.mean_confidence < LOW_CONFIDENCE_THRESHOLD:
            logger.info(
                "ocr_low_confidence_fallback",
                page=idx,
                primary=primary,
                primary_confidence=result.mean_confidence,
            )
            fallback_result = _run_engine(processed, idx, fallback)
            if fallback_result.mean_confidence > result.mean_confidence:
                result = fallback_result

        pages.append(result)

    return OCRDocumentResult(pages=pages, engine=primary, source=primary)


def process_document(content: bytes, mime_type: str) -> OCRDocumentResult:
    """Full intake pipeline for one document: skip OCR entirely when a PDF
    already has a usable text layer, otherwise render pages and run OCR.
    """
    if mime_type == "application/pdf":
        if pdf_has_text_layer(content):
            logger.info("pdf_text_layer_detected_skipping_ocr")
            texts = extract_pdf_text_layer(content)
            pages = []
            for idx, text in enumerate(texts, start=1):
                word = OCRWord(
                    text=text, bbox=BoundingBox(x0=0, y0=0, x1=0, y1=0), conf=1.0, page=idx
                )
                line = OCRLine(text=text, words=[word], bbox=word.bbox, page=idx)
                pages.append(
                    OCRPageResult(
                        page=idx, words=[word], lines=[line], mean_confidence=1.0,
                        engine="text_layer",
                    )
                )
            return OCRDocumentResult(pages=pages, engine="text_layer", source="text_layer")

        images = render_pdf_pages(content)
    else:
        images = [load_image_bytes(content)]

    return run_ocr_on_images(list(images))
