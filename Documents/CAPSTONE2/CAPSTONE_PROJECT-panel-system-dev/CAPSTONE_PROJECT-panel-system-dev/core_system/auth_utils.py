import hashlib
import secrets
from datetime import timedelta
from ipaddress import ip_address

from typing import Optional


from django.db import transaction
from django.utils import timezone

from core_system.models import AccessSession, LoginAttemptLog, OfficerUser


def sha256_hex(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


_PIN_PBKDF2_ITERATIONS = 200_000
_PIN_PREFIX = "pin_pbkdf2_sha256"


def hash_pin(pin: str) -> str:
    """Hash a 6-digit PIN using salted PBKDF2-HMAC-SHA256.

    Format: pin_pbkdf2_sha256$<iterations>$<salt_hex>$<dk_hex>
    This replaces the old unsalted SHA-256 scheme to prevent offline
    brute-force of the 1M possible 6-digit PINs.
    """
    salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac(
        "sha256",
        pin.encode("utf-8"),
        bytes.fromhex(salt),
        _PIN_PBKDF2_ITERATIONS,
    )
    return f"{_PIN_PREFIX}${_PIN_PBKDF2_ITERATIONS}${salt}${dk.hex()}"


def verify_pin(pin: str, stored: str) -> bool:
    """Verify a PIN against a salted PBKDF2 hash, falling back to legacy SHA-256."""
    if not stored:
        return False
    if stored.startswith(_PIN_PREFIX + "$"):
        try:
            _prefix, iterations_s, salt_hex, expected_hex = stored.split("$", 3)
            dk = hashlib.pbkdf2_hmac(
                "sha256",
                pin.encode("utf-8"),
                bytes.fromhex(salt_hex),
                int(iterations_s),
            )
            return secrets.compare_digest(dk.hex(), expected_hex)
        except (ValueError, TypeError):
            return False
    return secrets.compare_digest(sha256_hex(pin), stored)


_PBKDF2_ITERATIONS = 260_000
_PBKDF2_PREFIX = "pbkdf2_sha256"


def hash_password(password: str) -> str:
    """Hash a password using salted PBKDF2-HMAC-SHA256.

    Format: pbkdf2_sha256$<iterations>$<salt_hex>$<dk_hex>
    """
    salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        bytes.fromhex(salt),
        _PBKDF2_ITERATIONS,
    )
    return f"{_PBKDF2_PREFIX}${_PBKDF2_ITERATIONS}${salt}${dk.hex()}"


def verify_password(password: str, stored: str) -> bool:
    """Verify a password against either a salted PBKDF2 hash or a legacy SHA-256 hash."""
    if not stored:
        return False
    if stored.startswith(_PBKDF2_PREFIX + "$"):
        try:
            _prefix, iterations_s, salt_hex, expected_hex = stored.split("$", 3)
            dk = hashlib.pbkdf2_hmac(
                "sha256",
                password.encode("utf-8"),
                bytes.fromhex(salt_hex),
                int(iterations_s),
            )
            return secrets.compare_digest(dk.hex(), expected_hex)
        except (ValueError, TypeError):
            return False
    return secrets.compare_digest(sha256_hex(password), stored)


@transaction.atomic
def create_access_session(
    *,
    officer: OfficerUser,
    ip_address: str | None = None,
    device_info: str | None = None
):
    """Creates an ACCESS_SESSION row and returns (session, token). Revokes all existing sessions for the user to enforce NO MULTI-LOGIN."""

    # Revoke all existing active sessions for this user (NO MULTI-LOGIN)
    AccessSession.objects.filter(
        user_id_FK=officer,
        session_status="Active"
    ).update(
        session_status="Revoked",
        revoked_at=timezone.now(),
        expires_at=timezone.now()  # Immediately expire old sessions
    )

    token_id = secrets.token_urlsafe(32)

    session = AccessSession.objects.create(
        user_id_FK=officer,
        token_id=token_id,
        ip_address=ip_address or "0.0.0.0",
        device_info=device_info,
        expires_at=timezone.now() + timedelta(hours=8),
        session_status="Active",
        last_activity_at=timezone.now(),
        trusted_device=False,
        session_policy={},
    )
    return session, token_id


def verify_officer_password(*, officer: OfficerUser, password_input: str) -> bool:
    if not officer.account_status or officer.account_status.lower() != "active":
        return False
    return verify_password(password_input, officer.password_hash)


@transaction.atomic
def log_login_attempt(
    *,
    username: str,
    ip_address: str,
    device_info: str | None,
    result: str,
    user_id: int | None
):
    LoginAttemptLog.objects.create(
        user_id_FK_id=user_id,
        username_used=username,
        ip_address=ip_address,
        device_info=device_info,
        result=result,
    )
