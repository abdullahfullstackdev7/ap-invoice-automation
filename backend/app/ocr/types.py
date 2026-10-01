from pydantic import BaseModel


class BoundingBox(BaseModel):
    x0: float
    y0: float
    x1: float
    y1: float


class OCRWord(BaseModel):
    text: str
    bbox: BoundingBox
    conf: float
    page: int


class OCRLine(BaseModel):
    text: str
    words: list[OCRWord]
    bbox: BoundingBox
    page: int


class OCRPageResult(BaseModel):
    page: int
    words: list[OCRWord]
    lines: list[OCRLine]
    mean_confidence: float
    engine: str


class OCRDocumentResult(BaseModel):
    pages: list[OCRPageResult]
    engine: str
    source: str  # "text_layer" | "rapidocr" | "tesseract"

    @property
    def mean_confidence(self) -> float:
        confidences = [p.mean_confidence for p in self.pages if p.words]
        return sum(confidences) / len(confidences) if confidences else 0.0
