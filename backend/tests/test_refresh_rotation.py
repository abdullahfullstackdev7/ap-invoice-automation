from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import UserRole
from tests.conftest import TEST_PASSWORD, make_user


async def _login(client: AsyncClient, email: str) -> None:
    response = await client.post(
        "/api/v1/auth/login", json={"email": email, "password": TEST_PASSWORD}
    )
    assert response.status_code == 200


async def test_refresh_rotates_token(client: AsyncClient, db_session: AsyncSession) -> None:
    await make_user(db_session, "admin@example.com", UserRole.admin)
    await _login(client, "admin@example.com")

    old_refresh = client.cookies["refresh_token"]
    csrf = client.cookies["csrf_token"]

    response = await client.post("/api/v1/auth/refresh", headers={"X-CSRF-Token": csrf})

    assert response.status_code == 200
    assert client.cookies["refresh_token"] != old_refresh


async def test_reused_refresh_token_is_rejected_and_revokes_session(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await make_user(db_session, "admin@example.com", UserRole.admin)
    await _login(client, "admin@example.com")

    stolen_refresh = client.cookies["refresh_token"]
    csrf = client.cookies["csrf_token"]

    # Legitimate rotation: the old token is now revoked, a new one issued.
    first = await client.post("/api/v1/auth/refresh", headers={"X-CSRF-Token": csrf})
    assert first.status_code == 200
    new_refresh = client.cookies["refresh_token"]
    new_csrf = client.cookies["csrf_token"]
    assert new_refresh != stolen_refresh

    # An attacker replays the stolen (now-rotated-out) refresh token. The
    # CSRF cookie also rotated on the legitimate refresh above, so use the
    # current one here too: this test is about refresh-token reuse, not CSRF.
    client.cookies.set("refresh_token", stolen_refresh)
    replay = await client.post("/api/v1/auth/refresh", headers={"X-CSRF-Token": new_csrf})
    assert replay.status_code == 401

    # The legitimate, never-before-used successor token is also burned,
    # because reuse detection revokes the whole token family.
    client.cookies.set("refresh_token", new_refresh)
    victim_retry = await client.post("/api/v1/auth/refresh", headers={"X-CSRF-Token": new_csrf})
    assert victim_retry.status_code == 401
