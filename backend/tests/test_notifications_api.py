from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import UserRole
from app.services.notifications import notify_role, notify_user
from tests.conftest import TEST_PASSWORD, make_user


async def _login(client: AsyncClient, email: str) -> None:
    response = await client.post(
        "/api/v1/auth/login", json={"email": email, "password": TEST_PASSWORD}
    )
    assert response.status_code == 200


async def test_list_notifications_returns_only_the_current_users(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    clerk = await make_user(db_session, "clerk@example.com", UserRole.ap_clerk)
    other = await make_user(db_session, "other@example.com", UserRole.ap_clerk)

    await notify_user(db_session, clerk.id, "For clerk", "body")
    await notify_user(db_session, other.id, "For other", "body")
    await db_session.commit()

    await _login(client, "clerk@example.com")
    response = await client.get("/api/v1/notifications")
    assert response.status_code == 200
    titles = {row["title"] for row in response.json()}
    assert titles == {"For clerk"}


async def test_notify_role_fans_out_to_every_active_user_with_that_role(
    db_session: AsyncSession,
) -> None:
    approver_a = await make_user(db_session, "approver_a@example.com", UserRole.approver)
    approver_b = await make_user(db_session, "approver_b@example.com", UserRole.approver)
    await make_user(db_session, "clerk@example.com", UserRole.ap_clerk)

    notifications = await notify_role(db_session, UserRole.approver, "Needs approval", "body")
    await db_session.commit()

    notified_user_ids = {n.user_id for n in notifications}
    assert notified_user_ids == {approver_a.id, approver_b.id}


async def test_mark_read_sets_read_at(client: AsyncClient, db_session: AsyncSession) -> None:
    clerk = await make_user(db_session, "clerk2@example.com", UserRole.ap_clerk)
    notification = await notify_user(db_session, clerk.id, "Title", "body")
    await db_session.commit()

    await _login(client, "clerk2@example.com")
    csrf = client.cookies["csrf_token"]
    response = await client.post(
        f"/api/v1/notifications/{notification.id}/read", headers={"X-CSRF-Token": csrf}
    )
    assert response.status_code == 200
    assert response.json()["read_at"] is not None


async def test_cannot_mark_another_users_notification_read(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    other = await make_user(db_session, "other2@example.com", UserRole.ap_clerk)
    await make_user(db_session, "clerk3@example.com", UserRole.ap_clerk)
    notification = await notify_user(db_session, other.id, "Title", "body")
    await db_session.commit()

    await _login(client, "clerk3@example.com")
    csrf = client.cookies["csrf_token"]
    response = await client.post(
        f"/api/v1/notifications/{notification.id}/read", headers={"X-CSRF-Token": csrf}
    )
    assert response.status_code == 403
