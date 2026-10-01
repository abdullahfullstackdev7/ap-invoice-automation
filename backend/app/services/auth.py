import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import (
    create_access_token,
    generate_opaque_token,
    hash_token,
    next_lockout_until,
    verify_password,
)
from app.core.settings import get_settings
from app.models.identity import RefreshToken, User
from app.services.audit import AuditService


class InvalidCredentials(Exception):
    pass


class AccountLocked(Exception):
    def __init__(self, locked_until: datetime) -> None:
        self.locked_until = locked_until


class RefreshTokenInvalid(Exception):
    pass


class RefreshTokenReused(Exception):
    """A rotated-out refresh token was presented again: likely theft.

    The entire token family has been revoked; the user must log in again.
    """


class AuthService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.audit = AuditService(session)

    async def authenticate(self, email: str, password: str, *, ip: str | None = None) -> User:
        result = await self.session.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()

        if user is None:
            # Constant-shape failure path: no user enumeration via timing or message.
            raise InvalidCredentials

        now = datetime.now(UTC)
        if user.locked_until is not None and user.locked_until > now:
            raise AccountLocked(user.locked_until)

        if not user.is_active or not verify_password(password, user.password_hash):
            user.failed_login_attempts += 1
            locked_until = next_lockout_until(user.failed_login_attempts, now)
            user.locked_until = locked_until
            await self.session.flush()
            await self.audit.record(
                "login_failed",
                "user",
                entity_id=user.id,
                ip=ip,
                after={"failed_login_attempts": user.failed_login_attempts},
            )
            if locked_until is not None:
                raise AccountLocked(locked_until)
            raise InvalidCredentials

        user.failed_login_attempts = 0
        user.locked_until = None
        user.last_login_at = now
        await self.session.flush()
        await self.audit.record(
            "login_succeeded", "user", actor_id=user.id, entity_id=user.id, ip=ip
        )
        return user

    async def issue_tokens(
        self, user: User, *, ip: str | None = None, user_agent: str | None = None
    ) -> tuple[str, str]:
        settings = get_settings()
        access_token = create_access_token(user.id, user.role)

        refresh_plain = generate_opaque_token()
        refresh_row = RefreshToken(
            user_id=user.id,
            token_hash=hash_token(refresh_plain),
            family_id=uuid.uuid4(),
            expires_at=datetime.now(UTC) + timedelta(days=settings.refresh_token_days),
            ip=ip,
            user_agent=user_agent,
        )
        self.session.add(refresh_row)
        await self.session.flush()
        return access_token, refresh_plain

    async def rotate_refresh(
        self, refresh_plain: str, *, ip: str | None = None, user_agent: str | None = None
    ) -> tuple[str, str]:
        settings = get_settings()
        token_hash = hash_token(refresh_plain)
        result = await self.session.execute(
            select(RefreshToken).where(RefreshToken.token_hash == token_hash)
        )
        token_row = result.scalar_one_or_none()

        if token_row is None:
            raise RefreshTokenInvalid

        if token_row.revoked_at is not None:
            # This token was already rotated out once before: reuse means
            # the token (or its successor) may have been stolen. Burn the
            # whole family so both the attacker's and the victim's
            # sessions are cut off.
            await self._revoke_family(token_row.family_id)
            await self.audit.record(
                "refresh_token_reuse_detected",
                "refresh_token",
                actor_id=token_row.user_id,
                entity_id=token_row.id,
                ip=ip,
            )
            raise RefreshTokenReused

        now = datetime.now(UTC)
        if token_row.expires_at < now:
            raise RefreshTokenInvalid

        token_row.revoked_at = now

        user = await self.session.get(User, token_row.user_id)
        if user is None or not user.is_active:
            raise RefreshTokenInvalid

        access_token = create_access_token(user.id, user.role)
        new_refresh_plain = generate_opaque_token()
        new_row = RefreshToken(
            user_id=user.id,
            token_hash=hash_token(new_refresh_plain),
            family_id=token_row.family_id,
            expires_at=now + timedelta(days=settings.refresh_token_days),
            ip=ip,
            user_agent=user_agent,
        )
        self.session.add(new_row)
        await self.session.flush()
        return access_token, new_refresh_plain

    async def logout(self, refresh_plain: str) -> None:
        token_hash = hash_token(refresh_plain)
        result = await self.session.execute(
            select(RefreshToken).where(RefreshToken.token_hash == token_hash)
        )
        token_row = result.scalar_one_or_none()
        if token_row is None:
            return
        await self._revoke_family(token_row.family_id)

    async def _revoke_family(self, family_id: uuid.UUID) -> None:
        now = datetime.now(UTC)
        await self.session.execute(
            update(RefreshToken)
            .where(RefreshToken.family_id == family_id, RefreshToken.revoked_at.is_(None))
            .values(revoked_at=now)
        )
        await self.session.flush()
