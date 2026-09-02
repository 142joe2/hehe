import hmac
import hashlib
import json
from datetime import datetime, timedelta
from django.conf import settings
from django.utils import timezone


def generate_sit(session_id: str, action: str, action_id: str, timestamp: str) -> str:
    """Generate a Session Integrity Token (SIT) for a specific action.
    
    The SIT is a cryptographic signature binding the action to the current session,
    preventing replay attacks and ensuring per-action confirmation.
    """
    payload = f"{session_id}:{action}:{action_id}:{timestamp}"
    return hmac.new(
        settings.SECRET_KEY.encode(),
        payload.encode(),
        hashlib.sha256,
    ).hexdigest()


def verify_sit(sit: str, session_id: str, action: str, action_id: str, timestamp: str) -> bool:
    """Verify a Session Integrity Token (SIT).
    
    Uses constant-time comparison to prevent timing attacks.
    """
    expected = generate_sit(session_id, action, action_id, timestamp)
    return hmac.compare_digest(expected, sit)


def get_session_fingerprint(request, session) -> dict:
    """Extract session fingerprint information for display in the confirmation modal.
    
    This allows officers to visually verify they are on their own session by checking
    IP address, device, and session duration.
    """
    return {
        "ip": request.META.get("REMOTE_ADDR", "0.0.0.0"),
        "device": request.META.get("HTTP_USER_AGENT", "Unknown")[:255],
        "logged_in_since": session.issued_at.isoformat(),
        "session_id": session.token_id[:12] + "...",
        "trusted_device": session.trusted_device,
    }


def build_action_descriptor(action: str, record_id, details: dict = None) -> str:
    """Build a human-readable action descriptor for the confirmation modal.
    
    Example: "Approve Disbursement #7291 — Amount: ₱45,000.00 · Payee: Juan Dela Cruz"
    """
    desc = action.replace("_", " ").title()
    if details:
        extras = " · ".join(f"{k}: {v}" for k, v in details.items())
        return f"{desc} #{record_id} — {extras}"
    return f"{desc} #{record_id}"
