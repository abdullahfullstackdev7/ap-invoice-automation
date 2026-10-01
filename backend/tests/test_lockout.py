from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import UserRole
from app.models.identity import User
from tests.conftest import TEST_PASSWORD, make_user


async def test_lockout_after_five_failures(client: AsyncClient, db_session: AsyncSession) -> None:
    await make_user(db_session, "clerk@example.com", UserRole.ap_clerk)

    for _ in range(5):
        response = await client.post(
            "/api/v1/auth/login",
            json={"email": "clerk@example.com", "password": "wrong-password"},
        )
        assert response.status_code == 401

    # Correct password is still rejected once locked, with the same generic message.
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "clerk@example.com", "password": TEST_PASSWORD},
    )
    assert response.status_code == 401
    assert response.json()["title"] == "Invalid email or password"

    result = await db_session.execute(select(User).where(User.email == "clerk@example.com"))
    user = result.scalar_one()
    assert user.failed_login_attempts == 5
    assert user.locked_until is not None
