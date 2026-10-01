import re
import uuid
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.masterdata import Vendor
from app.services.embeddings import embed_text

ACCEPT_SCORE_THRESHOLD = 0.90
ACCEPT_MARGIN_THRESHOLD = 0.05

ResolutionMethod = str  # "tax_id" | "trigram" | "embedding" | "unresolved"


@dataclass
class VendorResolutionResult:
    vendor_id: uuid.UUID | None
    method: ResolutionMethod
    score: float
    margin: float | None = None

    @property
    def resolved(self) -> bool:
        return self.vendor_id is not None


def normalize_vendor_name(name: str) -> str:
    return re.sub(r"\s+", " ", name.strip().lower())


async def _resolve_by_tax_id(session: AsyncSession, tax_id: str) -> Vendor | None:
    result = await session.execute(select(Vendor).where(Vendor.tax_id == tax_id))
    return result.scalar_one_or_none()


async def _resolve_by_trigram(
    session: AsyncSession, normalized_name: str
) -> list[tuple[Vendor, float]]:
    result = await session.execute(
        select(Vendor, func.similarity(Vendor.name_normalized, normalized_name).label("score"))
        .order_by(func.similarity(Vendor.name_normalized, normalized_name).desc())
        .limit(2)
    )
    return [(row[0], float(row[1])) for row in result.all()]


async def _resolve_by_embedding(
    session: AsyncSession, query_text: str
) -> list[tuple[Vendor, float]]:
    query_embedding = embed_text(query_text)
    distance = Vendor.embedding.cosine_distance(query_embedding)
    result = await session.execute(
        select(Vendor, (1 - distance).label("score"))
        .where(Vendor.embedding.is_not(None))
        .order_by(distance)
        .limit(2)
    )
    return [(row[0], float(row[1])) for row in result.all()]


def _accept(candidates: list[tuple[Vendor, float]]) -> tuple[Vendor, float, float] | None:
    if not candidates:
        return None
    top_vendor, top_score = candidates[0]
    second_score = candidates[1][1] if len(candidates) > 1 else 0.0
    margin = top_score - second_score
    if top_score >= ACCEPT_SCORE_THRESHOLD and margin >= ACCEPT_MARGIN_THRESHOLD:
        return top_vendor, top_score, margin
    return None


async def resolve_vendor(
    session: AsyncSession,
    *,
    vendor_name: str | None,
    vendor_address: str | None = None,
    tax_id: str | None = None,
) -> VendorResolutionResult:
    """Vendor resolution funnel per Plan.md section 6 / Phase 6:
    exact tax id, then trigram similarity, then pgvector cosine on
    name + address. Accepted only if the top score clears 0.90 AND beats
    the runner-up by at least 0.05, so a close call falls through to
    VENDOR_UNRESOLVED rather than guessing.
    """
    if tax_id:
        vendor = await _resolve_by_tax_id(session, tax_id)
        if vendor is not None:
            return VendorResolutionResult(vendor.id, "tax_id", 1.0, margin=1.0)

    if not vendor_name:
        return VendorResolutionResult(None, "unresolved", 0.0)

    normalized_name = normalize_vendor_name(vendor_name)

    trigram_candidates = await _resolve_by_trigram(session, normalized_name)
    accepted = _accept(trigram_candidates)
    if accepted:
        vendor, score, margin = accepted
        return VendorResolutionResult(vendor.id, "trigram", score, margin)

    query_text = f"{vendor_name} {vendor_address or ''}".strip()
    embedding_candidates = await _resolve_by_embedding(session, query_text)
    accepted = _accept(embedding_candidates)
    if accepted:
        vendor, score, margin = accepted
        return VendorResolutionResult(vendor.id, "embedding", score, margin)

    best_score = embedding_candidates[0][1] if embedding_candidates else 0.0
    return VendorResolutionResult(None, "unresolved", best_score)
