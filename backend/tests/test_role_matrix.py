import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import UserRole
from tests.conftest import TEST_PASSWORD, make_user

ALL_ROLES = [
    UserRole.admin,
    UserRole.ap_clerk,
    UserRole.approver,
    UserRole.finance_manager,
    UserRole.auditor,
]


async def _login_as(client: AsyncClient, db_session: AsyncSession, role: UserRole) -> None:
    email = f"{role.value}@example.com"
    await make_user(db_session, email, role)
    response = await client.post(
        "/api/v1/auth/login", json={"email": email, "password": TEST_PASSWORD}
    )
    assert response.status_code == 200


@pytest.mark.parametrize("role", ALL_ROLES)
async def test_list_users_role_matrix(
    client: AsyncClient, db_session: AsyncSession, role: UserRole
) -> None:
    await _login_as(client, db_session, role)

    response = await client.get("/api/v1/users")

    if role in (UserRole.admin, UserRole.auditor):
        assert response.status_code == 200
    else:
        assert response.status_code == 403


@pytest.mark.parametrize("role", ALL_ROLES)
async def test_create_user_role_matrix(
    client: AsyncClient, db_session: AsyncSession, role: UserRole
) -> None:
    await _login_as(client, db_session, role)
    csrf = client.cookies["csrf_token"]

    response = await client.post(
        "/api/v1/users",
        headers={"X-CSRF-Token": csrf},
        json={
            "email": "new.hire@example.com",
            "password": "AnotherValidPassw0rd",
            "full_name": "New Hire",
            "role": "ap_clerk",
        },
    )

    if role == UserRole.admin:
        assert response.status_code == 201
    else:
        assert response.status_code == 403


@pytest.mark.parametrize("role", ALL_ROLES)
async def test_audit_log_role_matrix(
    client: AsyncClient, db_session: AsyncSession, role: UserRole
) -> None:
    await _login_as(client, db_session, role)

    response = await client.get("/api/v1/audit")

    if role in (UserRole.admin, UserRole.auditor):
        assert response.status_code == 200
    else:
        assert response.status_code == 403


async def test_create_user_rejects_weak_password(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _login_as(client, db_session, UserRole.admin)
    csrf = client.cookies["csrf_token"]

    response = await client.post(
        "/api/v1/users",
        headers={"X-CSRF-Token": csrf},
        json={
            "email": "weak@example.com",
            "password": "short1",
            "full_name": "Weak Password",
            "role": "ap_clerk",
        },
    )

    assert response.status_code == 422
