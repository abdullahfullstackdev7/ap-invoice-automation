"""Schema-driven contract test, Plan.md section 13: fuzz every operation in
the generated OpenAPI schema and assert the API never answers with a 5xx.

The schema comes from app.openapi() and requests go through httpx's ASGI
transport, so the app's lifespan (which opens the psycopg pool on Windows'
ProactorEventLoop) never runs. The schema is the source of truth, so a new
route is covered automatically. Requests are unauthenticated and randomly
generated, so most answer 401 or 422; what matters is that none crash.
"""

import asyncio
from collections.abc import AsyncGenerator
from typing import Any

import httpx
import schemathesis
from hypothesis import settings
from schemathesis import Case
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db_session
from app.main import app
from tests.conftest import TestSessionLocal


async def _test_db_session() -> AsyncGenerator[AsyncSession, None]:
    async with TestSessionLocal() as session:
        yield session


app.dependency_overrides[get_db_session] = _test_db_session

schema = schemathesis.openapi.from_dict(app.openapi())


async def _send(case: Case[Any]) -> httpx.Response:
    kwargs = case.as_transport_kwargs(base_url="http://test")
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.request(**kwargs)


@schema.parametrize()
@settings(max_examples=25, deadline=None)
def test_api_never_returns_5xx(case: Case[Any]) -> None:
    response = asyncio.run(_send(case))
    assert response.status_code < 500, f"{case.method} {case.path} returned {response.status_code}"
