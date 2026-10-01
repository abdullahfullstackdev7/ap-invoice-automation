import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import UserRole
from app.models.identity import User
from app.models.notifications import Notification


async def notify_user(
    session: AsyncSession, user_id: uuid.UUID, title: str, body: str, *, link: str | None = None
) -> Notification:
    notification = Notification(
        user_id=user_id, title=title, body=body, link=link, created_at=datetime.now(UTC)
    )
    session.add(notification)
    await session.flush()
    return notification


async def notify_role(
    session: AsyncSession, role: UserRole, title: str, body: str, *, link: str | None = None
) -> list[Notification]:
    result = await session.execute(
        select(User.id).where(User.role == role, User.is_active.is_(True))
    )
    user_ids = [row[0] for row in result.all()]
    notifications = [
        Notification(
            user_id=user_id, title=title, body=body, link=link, created_at=datetime.now(UTC)
        )
        for user_id in user_ids
    ]
    session.add_all(notifications)
    await session.flush()
    return notifications
