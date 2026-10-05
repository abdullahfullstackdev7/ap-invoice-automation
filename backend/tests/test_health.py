from httpx import AsyncClient


async def test_healthz(client: AsyncClient) -> None:
    response = await client.get("/api/v1/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_readyz_is_ok_with_database(client: AsyncClient) -> None:
    response = await client.get("/api/v1/readyz")
    assert response.status_code == 200
    assert response.json() == {"status": "ready"}


async def test_readyz_returns_503_when_database_fails(client: AsyncClient) -> None:
    from sqlalchemy.exc import OperationalError

    from app.db.session import get_db_session
    from app.main import app

    class _BrokenSession:
        async def execute(self, *args: object, **kwargs: object) -> None:
            raise OperationalError("SELECT 1", {}, Exception("connection refused"))

    async def _broken() -> object:
        yield _BrokenSession()

    app.dependency_overrides[get_db_session] = _broken
    try:
        response = await client.get("/api/v1/readyz")
    finally:
        app.dependency_overrides.pop(get_db_session, None)
    assert response.status_code == 503
