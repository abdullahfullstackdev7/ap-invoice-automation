import hashlib
import json
from typing import Any

from fastapi import Request, Response, status
from fastapi.encoders import jsonable_encoder


def _etag_for(payload: Any) -> str:
    encoded = jsonable_encoder(payload)
    canonical = json.dumps(encoded, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def with_etag(request: Request, response: Response, payload: Any) -> Any:
    """Sets a content-hash ETag and short-circuits to 304 when the
    client's If-None-Match already matches, Plan.md section 9."""
    tag = f'"{_etag_for(payload)}"'
    response.headers["ETag"] = tag
    if request.headers.get("if-none-match") == tag:
        response.status_code = status.HTTP_304_NOT_MODIFIED
        return None
    return payload
