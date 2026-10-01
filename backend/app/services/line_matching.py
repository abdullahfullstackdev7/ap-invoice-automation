import uuid
from collections import defaultdict
from dataclasses import dataclass

import numpy as np
from rapidfuzz import fuzz
from scipy.optimize import linear_sum_assignment

from app.services.embeddings import embed_texts

MIN_SCORE_THRESHOLD = 0.75
COSINE_WEIGHT = 0.5
FUZZY_WEIGHT = 0.5


@dataclass(frozen=True)
class LineCandidate:
    id: uuid.UUID
    description: str
    sku: str | None = None


@dataclass
class LineMatchResult:
    invoice_line_id: uuid.UUID
    po_line_id: uuid.UUID | None
    score: float
    method: str  # "sku" | "embedding_fuzzy" | "unmatched"


def _combined_score(a: str, b: str, cosine_sim: float) -> float:
    fuzzy = fuzz.token_set_ratio(a, b) / 100
    return COSINE_WEIGHT * cosine_sim + FUZZY_WEIGHT * fuzzy


def match_invoice_lines_to_po_lines(
    invoice_lines: list[LineCandidate], po_lines: list[LineCandidate]
) -> list[LineMatchResult]:
    """Line-to-PO-line mapping per Plan.md section 6 / Phase 6: exact SKU
    first, then description embedding cosine + rapidfuzz token-set ratio,
    solved as a single global optimal assignment (Hungarian algorithm)
    rather than greedy nearest-match, with a 0.75 minimum combined score.
    """
    results: list[LineMatchResult] = []

    po_by_sku: dict[str, list[LineCandidate]] = defaultdict(list)
    for po_line in po_lines:
        if po_line.sku:
            po_by_sku[po_line.sku].append(po_line)

    matched_invoice_ids: set[uuid.UUID] = set()
    matched_po_ids: set[uuid.UUID] = set()
    for inv_line in invoice_lines:
        if inv_line.sku and po_by_sku.get(inv_line.sku):
            po_line = po_by_sku[inv_line.sku].pop(0)
            results.append(LineMatchResult(inv_line.id, po_line.id, 1.0, "sku"))
            matched_invoice_ids.add(inv_line.id)
            matched_po_ids.add(po_line.id)

    remaining_invoice = [line for line in invoice_lines if line.id not in matched_invoice_ids]
    remaining_po = [line for line in po_lines if line.id not in matched_po_ids]

    if not remaining_invoice:
        return results

    if not remaining_po:
        results.extend(
            LineMatchResult(line.id, None, 0.0, "unmatched") for line in remaining_invoice
        )
        return results

    inv_embeddings = embed_texts([line.description for line in remaining_invoice])
    po_embeddings = embed_texts([line.description for line in remaining_po])

    n, m = len(remaining_invoice), len(remaining_po)
    cost = np.zeros((n, m))
    for i in range(n):
        for j in range(m):
            cosine_sim = float(np.dot(inv_embeddings[i], po_embeddings[j]))
            cost[i, j] = -_combined_score(
                remaining_invoice[i].description, remaining_po[j].description, cosine_sim
            )

    row_indices, col_indices = linear_sum_assignment(cost)
    assigned_invoice_rows = set()
    for i, j in zip(row_indices, col_indices, strict=True):
        score = -cost[i, j]
        assigned_invoice_rows.add(i)
        if score >= MIN_SCORE_THRESHOLD:
            results.append(
                LineMatchResult(
                    remaining_invoice[i].id, remaining_po[j].id, score, "embedding_fuzzy"
                )
            )
        else:
            results.append(LineMatchResult(remaining_invoice[i].id, None, score, "unmatched"))

    for i, line in enumerate(remaining_invoice):
        if i not in assigned_invoice_rows:
            results.append(LineMatchResult(line.id, None, 0.0, "unmatched"))

    return results
