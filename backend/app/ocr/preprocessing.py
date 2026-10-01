import io

import cv2
import numpy as np
import pdfplumber
import pypdfium2 as pdfium
from PIL import Image

RENDER_DPI = 200
TEXT_LAYER_MIN_CHARS_PER_PAGE = 20


def pdf_has_text_layer(content: bytes) -> bool:
    """True if the PDF already carries a usable text layer (no OCR needed)."""
    with pdfplumber.open(io.BytesIO(content)) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            if len(text.strip()) >= TEXT_LAYER_MIN_CHARS_PER_PAGE:
                return True
    return False


def extract_pdf_text_layer(content: bytes) -> list[str]:
    """Per-page plain text, for PDFs that already have a text layer."""
    with pdfplumber.open(io.BytesIO(content)) as pdf:
        return [page.extract_text() or "" for page in pdf.pages]


def render_pdf_pages(content: bytes, dpi: int = RENDER_DPI) -> list[np.ndarray]:
    """Renders each PDF page to a BGR numpy array at the given DPI."""
    scale = dpi / 72
    doc = pdfium.PdfDocument(content)
    try:
        images = []
        for page in doc:
            bitmap = page.render(scale=scale)
            pil_image = bitmap.to_pil().convert("RGB")
            images.append(cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR))
        return images
    finally:
        doc.close()


def load_image_bytes(content: bytes) -> np.ndarray:
    pil_image = Image.open(io.BytesIO(content)).convert("RGB")
    return cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)


def deskew(image: np.ndarray) -> np.ndarray:
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    coords = cv2.findNonZero(thresh)
    if coords is None:
        return image

    angle = cv2.minAreaRect(coords)[-1]
    angle = -(90 + angle) if angle < -45 else -angle

    if abs(angle) < 0.1:
        return image

    h, w = image.shape[:2]
    center = (w // 2, h // 2)
    matrix = cv2.getRotationMatrix2D(center, angle, 1.0)
    return cv2.warpAffine(
        image, matrix, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE
    )


def denoise(image: np.ndarray) -> np.ndarray:
    return cv2.fastNlMeansDenoisingColored(image, None, 7, 7, 7, 21)


def normalize_contrast(image: np.ndarray) -> np.ndarray:
    lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
    l_channel, a_channel, b_channel = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    l_channel = clahe.apply(l_channel)
    merged = cv2.merge((l_channel, a_channel, b_channel))
    return cv2.cvtColor(merged, cv2.COLOR_LAB2BGR)


def preprocess_page(image: np.ndarray) -> np.ndarray:
    image = deskew(image)
    image = denoise(image)
    image = normalize_contrast(image)
    return image
