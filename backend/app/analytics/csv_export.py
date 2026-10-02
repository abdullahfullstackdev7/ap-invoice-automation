import csv
import io
from typing import Any

from fastapi.encoders import jsonable_encoder
from fastapi.responses import Response


def rows_to_csv_response(rows: list[dict[str, Any]], filename: str) -> Response:
    encoded_rows = jsonable_encoder(rows)
    fieldnames = list(encoded_rows[0].keys()) if encoded_rows else []
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(encoded_rows)
    return Response(
        content=buf.getvalue().encode("utf-8"),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
