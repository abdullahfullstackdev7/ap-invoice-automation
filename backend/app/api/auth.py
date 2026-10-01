import uuid

import jwt
import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.cookies import REFRESH_COOKIE_NAME, clear_auth_cookies, set_auth_cookies
from app.core.csrf import require_csrf
from app.core.rate_limit import limiter
from app.core.security import (
    PasswordPolicyError,
    create_mfa_challenge_token,
    decode_token,
    decrypt_field,
    hash_password,
    validate_password_policy,
    verify_password,
    verify_totp_code,
)
from app.db.session import get_db_session
from app.models.identity import User
from app.schemas.auth import LoginRequest, LoginResponse, MFAVerifyRequest, PasswordChangeRequest
from app.schemas.identity import UserRead
from app.services.audit import AuditService
from app.services.auth import (
    AccountLocked,
    AuthService,
    InvalidCredentials,
    RefreshTokenInvalid,
    RefreshTokenReused,
)

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])

GENERIC_LOGIN_ERROR = "Invalid email or password"


@router.post("/login", response_model=LoginResponse)
@limiter.limit("10/minute")
async def login(
    request: Request,
    response: Response,
    credentials: LoginRequest,
    session: AsyncSession = Depends(get_db_session),
) -> LoginResponse:
    service = AuthService(session)
    client_ip = request.client.host if request.client else None

    try:
        user = await service.authenticate(credentials.email, credentials.password, ip=client_ip)
    except (InvalidCredentials, AccountLocked) as exc:
        await session.commit()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, GENERIC_LOGIN_ERROR) from exc

    if user.mfa_secret_enc:
        await session.commit()
        return LoginResponse(status="mfa_required", mfa_token=create_mfa_challenge_token(user.id))

    access_token, refresh_token = await service.issue_tokens(
        user, ip=client_ip, user_agent=request.headers.get("user-agent")
    )
    await session.commit()
    set_auth_cookies(response, access_token, refresh_token)
    return LoginResponse(status="ok")


@router.post("/mfa/verify", response_model=LoginResponse)
@limiter.limit("10/minute")
async def verify_mfa(
    request: Request,
    response: Response,
    body: MFAVerifyRequest,
    session: AsyncSession = Depends(get_db_session),
) -> LoginResponse:
    try:
        payload = decode_token(body.mfa_token)
    except jwt.PyJWTError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired challenge") from exc

    if payload.get("type") != "mfa_challenge":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid challenge token")

    user = await session.get(User, uuid.UUID(payload["sub"]))
    if user is None or not user.mfa_secret_enc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid challenge")

    secret = decrypt_field(user.mfa_secret_enc.encode("utf-8"))
    if secret is None or not verify_totp_code(secret, body.code):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid MFA code")

    service = AuthService(session)
    access_token, refresh_token = await service.issue_tokens(
        user, ip=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    await session.commit()
    set_auth_cookies(response, access_token, refresh_token)
    return LoginResponse(status="ok")


@router.post("/refresh", response_model=LoginResponse)
@limiter.limit("20/minute")
async def refresh(
    request: Request,
    response: Response,
    session: AsyncSession = Depends(get_db_session),
    _csrf: None = Depends(require_csrf),
) -> LoginResponse:
    refresh_token = request.cookies.get(REFRESH_COOKIE_NAME)
    if not refresh_token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "No refresh token")

    service = AuthService(session)
    client_ip = request.client.host if request.client else None
    try:
        access_token, new_refresh_token = await service.rotate_refresh(
            refresh_token, ip=client_ip, user_agent=request.headers.get("user-agent")
        )
    except RefreshTokenReused as exc:
        await session.commit()
        clear_auth_cookies(response)
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, "Session revoked, please log in again"
        ) from exc
    except RefreshTokenInvalid as exc:
        await session.commit()
        clear_auth_cookies(response)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid refresh token") from exc

    await session.commit()
    set_auth_cookies(response, access_token, new_refresh_token)
    return LoginResponse(status="ok")


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    request: Request,
    response: Response,
    session: AsyncSession = Depends(get_db_session),
    _csrf: None = Depends(require_csrf),
) -> None:
    refresh_token = request.cookies.get(REFRESH_COOKIE_NAME)
    if refresh_token:
        service = AuthService(session)
        await service.logout(refresh_token)
        await session.commit()
    clear_auth_cookies(response)


@router.get("/me", response_model=UserRead)
async def me(user: User = Depends(get_current_user)) -> User:
    return user


@router.post("/password/change", status_code=status.HTTP_204_NO_CONTENT)
async def change_password(
    request: Request,
    body: PasswordChangeRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
    _csrf: None = Depends(require_csrf),
) -> None:
    if not verify_password(body.current_password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Current password is incorrect")

    try:
        validate_password_policy(body.new_password)
    except PasswordPolicyError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc

    user.password_hash = hash_password(body.new_password)
    await AuditService(session).record(
        "password_changed", "user", actor_id=user.id, entity_id=user.id,
        ip=request.client.host if request.client else None,
    )
    await session.commit()
