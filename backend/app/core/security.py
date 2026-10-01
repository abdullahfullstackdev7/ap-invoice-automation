import base64
import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

import jwt
import pyotp
from cryptography.fernet import Fernet, InvalidToken
from pwdlib import PasswordHash

from app.core.settings import get_settings

password_hasher = PasswordHash.recommended()

MIN_PASSWORD_LENGTH = 12
JWT_ALGORITHM = "HS256"


class PasswordPolicyError(ValueError):
    pass


def validate_password_policy(password: str) -> None:
    if len(password) < MIN_PASSWORD_LENGTH:
        raise PasswordPolicyError(f"Password must be at least {MIN_PASSWORD_LENGTH} characters.")


def hash_password(password: str) -> str:
    return password_hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return password_hasher.verify(password, password_hash)
    except Exception:
        return False


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def generate_opaque_token() -> str:
    return secrets.token_urlsafe(48)


def create_access_token(user_id: uuid.UUID, role: str) -> str:
    settings = get_settings()
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "role": role,
        "type": "access",
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_minutes),
        "jti": str(uuid.uuid4()),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=JWT_ALGORITHM)


def decode_token(token: str) -> dict[str, Any]:
    settings = get_settings()
    return jwt.decode(token, settings.jwt_secret, algorithms=[JWT_ALGORITHM])


def create_mfa_challenge_token(user_id: uuid.UUID) -> str:
    settings = get_settings()
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "type": "mfa_challenge",
        "iat": now,
        "exp": now + timedelta(minutes=5),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=JWT_ALGORITHM)


def _fernet() -> Fernet:
    settings = get_settings()
    key_bytes = hashlib.sha256(settings.field_encryption_key.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(key_bytes))


def encrypt_field(plaintext: str) -> bytes:
    return _fernet().encrypt(plaintext.encode("utf-8"))


def decrypt_field(ciphertext: bytes) -> str | None:
    try:
        return _fernet().decrypt(ciphertext).decode("utf-8")
    except InvalidToken:
        return None


def generate_totp_secret() -> str:
    return pyotp.random_base32()


def totp_provisioning_uri(secret: str, email: str, issuer: str = "Veridian Payables") -> str:
    return pyotp.totp.TOTP(secret).provisioning_uri(name=email, issuer_name=issuer)


def verify_totp_code(secret: str, code: str) -> bool:
    return pyotp.totp.TOTP(secret).verify(code, valid_window=1)


LockoutState = Literal["ok", "locked"]


def next_lockout_until(attempt_number: int, now: datetime) -> datetime | None:
    """Exponential backoff lockout, starting after the 5th consecutive failure.

    attempt_number is the failed_login_attempts count after this failure.
    """
    if attempt_number < 5:
        return None
    backoff_minutes = min(2 ** (attempt_number - 5), 60)
    return now + timedelta(minutes=backoff_minutes)
