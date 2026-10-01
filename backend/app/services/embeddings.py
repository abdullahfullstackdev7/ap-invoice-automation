from functools import lru_cache

import numpy as np

from app.core.settings import get_settings

EMBEDDING_BATCH_SIZE = 64


@lru_cache
def _get_model() -> object:
    """Loaded once per worker process, per Plan.md section 6.1 / Phase 6."""
    from fastembed import TextEmbedding

    settings = get_settings()
    return TextEmbedding(model_name=settings.embedding_model)


def _l2_normalize(vector: np.ndarray) -> list[float]:
    norm = np.linalg.norm(vector)
    if norm == 0:
        return [float(x) for x in vector]
    return [float(x) for x in (vector / norm)]


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Batch-embeds text locally (no API tokens), L2-normalized so cosine
    distance and dot product agree.
    """
    if not texts:
        return []

    model = _get_model()
    vectors: list[list[float]] = []
    for i in range(0, len(texts), EMBEDDING_BATCH_SIZE):
        batch = texts[i : i + EMBEDDING_BATCH_SIZE]
        for raw_vector in model.embed(batch):  # type: ignore[attr-defined]
            vectors.append(_l2_normalize(np.asarray(raw_vector)))
    return vectors


def embed_text(text: str) -> list[float]:
    return embed_texts([text])[0]
