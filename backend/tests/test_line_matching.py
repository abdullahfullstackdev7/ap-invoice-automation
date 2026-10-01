import uuid

from app.services.line_matching import LineCandidate, match_invoice_lines_to_po_lines


def _id() -> uuid.UUID:
    return uuid.uuid4()


def test_exact_sku_match_takes_priority_over_fuzzy() -> None:
    inv_id, po_id = _id(), _id()
    invoice_lines = [LineCandidate(inv_id, "Widget A, premium grade", sku="SKU-100")]
    po_lines = [LineCandidate(po_id, "Widget A", sku="SKU-100")]

    results = match_invoice_lines_to_po_lines(invoice_lines, po_lines)

    assert len(results) == 1
    assert results[0].invoice_line_id == inv_id
    assert results[0].po_line_id == po_id
    assert results[0].method == "sku"
    assert results[0].score == 1.0


def test_description_similarity_matches_without_sku() -> None:
    inv_id, po_id = _id(), _id()
    invoice_lines = [LineCandidate(inv_id, "Wireless Mouse - Ergonomic")]
    po_lines = [LineCandidate(po_id, "Wireless Mouse Ergonomic Design")]

    results = match_invoice_lines_to_po_lines(invoice_lines, po_lines)

    assert len(results) == 1
    assert results[0].po_line_id == po_id
    assert results[0].method == "embedding_fuzzy"
    assert results[0].score >= 0.75


def test_global_assignment_prefers_overall_best_not_greedy() -> None:
    """A deliberately adversarial case for greedy nearest-match: line A is
    the single best match for PO line 2, but globally optimal assignment
    requires giving PO line 2 to line B so both lines match well, instead
    of greedily grabbing the best individual pair first.
    """
    a_id, b_id = _id(), _id()
    po1_id, po2_id = _id(), _id()

    invoice_lines = [
        LineCandidate(a_id, "Laptop Stand Aluminum"),
        LineCandidate(b_id, "Laptop Stand Aluminum Adjustable"),
    ]
    po_lines = [
        LineCandidate(po1_id, "Laptop Stand Aluminum"),
        LineCandidate(po2_id, "Laptop Stand Aluminum Adjustable"),
    ]

    results = match_invoice_lines_to_po_lines(invoice_lines, po_lines)
    by_invoice = {r.invoice_line_id: r for r in results}

    assert by_invoice[a_id].po_line_id == po1_id
    assert by_invoice[b_id].po_line_id == po2_id


def test_unrelated_lines_are_unmatched() -> None:
    inv_id, po_id = _id(), _id()
    invoice_lines = [LineCandidate(inv_id, "Office Chair Ergonomic Mesh Back")]
    po_lines = [LineCandidate(po_id, "Industrial Steel Beam 10 Meter")]

    results = match_invoice_lines_to_po_lines(invoice_lines, po_lines)

    assert len(results) == 1
    assert results[0].method == "unmatched"
    assert results[0].po_line_id is None


def test_more_invoice_lines_than_po_lines_leaves_extras_unmatched() -> None:
    inv1, inv2 = _id(), _id()
    po_id = _id()
    invoice_lines = [
        LineCandidate(inv1, "Widget A"),
        LineCandidate(inv2, "Completely Unrelated Service Fee"),
    ]
    po_lines = [LineCandidate(po_id, "Widget A")]

    results = match_invoice_lines_to_po_lines(invoice_lines, po_lines)

    assert len(results) == 2
    matched = [r for r in results if r.po_line_id is not None]
    unmatched = [r for r in results if r.po_line_id is None]
    assert len(matched) == 1
    assert len(unmatched) == 1


def test_empty_po_lines_returns_all_unmatched() -> None:
    inv_id = _id()
    invoice_lines = [LineCandidate(inv_id, "Widget A")]

    results = match_invoice_lines_to_po_lines(invoice_lines, [])

    assert len(results) == 1
    assert results[0].method == "unmatched"


def test_empty_invoice_lines_returns_empty() -> None:
    po_id = _id()
    results = match_invoice_lines_to_po_lines([], [LineCandidate(po_id, "Widget A")])
    assert results == []
