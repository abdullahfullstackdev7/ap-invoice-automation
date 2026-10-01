from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import UserRole
from tests.conftest import TEST_PASSWORD, make_user


async def test_login_success_sets_cookies(client: AsyncClient, db_session: AsyncSession) -> None:
    await make_user(db_session, "admin@example.com", UserRole.admin)

    response = await client.post(
        "/api/v1/auth/login", json={"email": "admin@example.com", "password": TEST_PASSWORD}
    )

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "mfa_token": None}
    assert "access_token" in response.cookies
    assert "refresh_token" in response.cookies
    assert "csrf_token" in response.cookies


async def test_login_wrong_password_generic_error(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await make_user(db_session, "admin@example.com", UserRole.admin)

    response = await client.post(
        "/api/v1/auth/login", json={"email": "admin@example.com", "password": "wrong-password"}
    )

    assert response.status_code == 401
    assert response.json()["title"] == "Invalid email or password"


async def test_login_unknown_email_same_generic_error(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/auth/login", json={"email": "nobody@example.com", "password": "whatever12345"}
    )

    assert response.status_code == 401
    assert response.json()["title"] == "Invalid email or password"


async def test_me_requires_authentication(client: AsyncClient) -> None:
    response = await client.get("/api/v1/auth/me")
    assert response.status_code == 401


async def test_me_returns_current_user(client: AsyncClient, db_session: AsyncSession) -> None:
    await make_user(db_session, "admin@example.com", UserRole.admin)
    await client.post(
        "/api/v1/auth/login", json={"email": "admin@example.com", "password": TEST_PASSWORD}
    )

    response = await client.get("/api/v1/auth/me")

    assert response.status_code == 200
    assert response.json()["email"] == "admin@example.com"


async def test_logout_without_csrf_header_is_rejected(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await make_user(db_session, "admin@example.com", UserRole.admin)
    await client.post(
        "/api/v1/auth/login", json={"email": "admin@example.com", "password": TEST_PASSWORD}
    )

    response = await client.post("/api/v1/auth/logout")

    assert response.status_code == 403


async def test_logout_with_csrf_header_succeeds_and_revokes_session(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await make_user(db_session, "admin@example.com", UserRole.admin)
    await client.post(
        "/api/v1/auth/login", json={"email": "admin@example.com", "password": TEST_PASSWORD}
    )
    csrf = client.cookies["csrf_token"]

    response = await client.post(
        "/api/v1/auth/logout", headers={"X-CSRF-Token": csrf}
    )
    assert response.status_code == 204

    me_response = await client.get("/api/v1/auth/me")
    assert me_response.status_code == 401
