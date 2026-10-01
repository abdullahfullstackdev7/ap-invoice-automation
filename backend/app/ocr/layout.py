from app.ocr.types import BoundingBox, OCRLine, OCRWord

Y_CLUSTER_TOLERANCE_RATIO = 0.6


def reconstruct_lines(words: list[OCRWord], page: int) -> list[OCRLine]:
    """Groups words into lines by y-center proximity, then orders left to right.

    Tolerance scales with the median word height on the page, so this works
    across different DPIs and font sizes without a fixed pixel threshold.
    """
    if not words:
        return []

    heights = sorted(w.bbox.y1 - w.bbox.y0 for w in words)
    median_height = heights[len(heights) // 2] or 1.0
    tolerance = median_height * Y_CLUSTER_TOLERANCE_RATIO

    sorted_words = sorted(words, key=lambda w: (w.bbox.y0 + w.bbox.y1) / 2)

    clusters: list[list[OCRWord]] = []
    for word in sorted_words:
        y_center = (word.bbox.y0 + word.bbox.y1) / 2
        placed = False
        for cluster in clusters:
            cluster_y_center = sum((w.bbox.y0 + w.bbox.y1) / 2 for w in cluster) / len(cluster)
            if abs(y_center - cluster_y_center) <= tolerance:
                cluster.append(word)
                placed = True
                break
        if not placed:
            clusters.append([word])

    lines = []
    for cluster in clusters:
        ordered = sorted(cluster, key=lambda w: w.bbox.x0)
        bbox = BoundingBox(
            x0=min(w.bbox.x0 for w in ordered),
            y0=min(w.bbox.y0 for w in ordered),
            x1=max(w.bbox.x1 for w in ordered),
            y1=max(w.bbox.y1 for w in ordered),
        )
        lines.append(
            OCRLine(
                text=" ".join(w.text for w in ordered),
                words=ordered,
                bbox=bbox,
                page=page,
            )
        )

    lines.sort(key=lambda line: line.bbox.y0)
    return lines
