import hashlib
import hmac
import secrets
import time

from core_system.models import OfficerUser


MFA_EMAIL_RATE_LIMIT_SECONDS = 300  # 5 minutes exactly


def generate_mfa_secret() -> str:
    return secrets.token_hex(16)


def generate_otp(secret: str) -> str:
    counter = int(time.time() // 30)
    msg = counter.to_bytes(8, "big")
    h = hmac.new(secret.encode(), msg, hashlib.sha256).digest()
    offset = h[-1] & 0xF
    code = int.from_bytes(h[offset:offset + 4], "big") & 0x7FFFFFFF
    return f"{code % 1000000:06d}"


def verify_otp(secret: str, otp: str) -> bool:
    if not secret or not otp:
        return False
    now = time.time()
    # Exactly 10 windows × 30s = 300s = 5 minutes
    for offset in range(0, -300, -30):
        counter = int((now + offset) // 30)
        msg = counter.to_bytes(8, "big")
        h = hmac.new(secret.encode(), msg, hashlib.sha256).digest()
        h_offset = h[-1] & 0xF
        code = int.from_bytes(h[h_offset:h_offset + 4], "big") & 0x7FFFFFFF
        if f"{code % 1000000:06d}" == str(otp).strip():
            return True
    return False


def send_mfa_email(officer: OfficerUser, otp: str) -> bool:
    from core_system.services.email_service import send_html_email

    html_template = "emails/mfa_challenge.html"
    context = {
        "full_name": officer.full_name,
        "otp_code": otp,
        "expiry_minutes": 5,
    }
    _log = __import__("logging").getLogger(__name__)
    if not officer.email:
        _log.error("send_mfa_email: officer %s (pk=%s) has no email address", officer.full_name, officer.user_id_PK)
        return False

    result = send_html_email(
        subject="CAUFA MFA Verification Code",
        recipient_list=[officer.email],
        html_template=html_template,
        context=context,
    )
    _log.info("send_mfa_email to %s (pk=%s) -> %s", officer.email, officer.user_id_PK, result)
    return result
