import hashlib
import json
import logging
import secrets
import time
import threading
from datetime import timedelta

logger = logging.getLogger(__name__)

from django.contrib import messages
from django.core.signing import BadSignature, Signer
from django.http import HttpRequest, HttpResponse, JsonResponse, HttpResponseRedirect
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_GET, require_POST

from core_system.auth_utils import (
    create_access_session,
    hash_password,
    log_login_attempt,
    verify_password,
)
from core_system.constants.status_constants import RegistrationStatus
from core_system.models import AccessSession, OfficerUser, MemberRegistrationRequest
from core_system.shared_view_utils import _record_audit_trail
from core_system.services.mfa_service import (
    generate_mfa_secret,
    generate_otp,
    send_mfa_email,
    verify_otp,
    MFA_EMAIL_RATE_LIMIT_SECONDS,
)
from core_system.turnstile import (
    get_turnstile_site_key,
    is_turnstile_enabled,
    validate_turnstile_token,
)

MFA_SESSION_KEY = "mfa_pre_auth_token"
MFA_OFFICER_ID_KEY = "mfa_officer_id"
MFA_USERNAME_KEY = "mfa_username"

TRUSTED_DEVICE_COOKIE = "caufa_trusted_device"
TRUSTED_DEVICE_MAX_AGE = 30 * 24 * 60 * 60  # 30 days


def _device_fingerprint(user_agent: str) -> str:
    """Stable fingerprint of the client device/browser, used to scope the trusted-device cookie."""
    ua = (user_agent or "").strip().lower()
    return hashlib.sha256(ua.encode("utf-8")).hexdigest()[:16]


def _set_trusted_device_cookie(response: HttpResponse, officer: OfficerUser, user_agent: str) -> None:
    """Sign a cookie that lets this officer skip OTP on this device for TRUSTED_DEVICE_MAX_AGE."""
    payload = f"{officer.user_id_PK}:{_device_fingerprint(user_agent)}"
    signer = Signer(salt="caufa-trusted-device")
    response.set_cookie(
        TRUSTED_DEVICE_COOKIE,
        signer.sign(payload),
        max_age=TRUSTED_DEVICE_MAX_AGE,
        httponly=True,
        samesite="Lax",
        secure=False,
        path="/",
    )


def _is_trusted_device(request: HttpRequest, officer: OfficerUser) -> bool:
    """Return True when a valid, signed trusted-device cookie matches this officer on this device."""
    raw = request.COOKIES.get(TRUSTED_DEVICE_COOKIE)
    if not raw:
        return False
    try:
        payload = Signer(salt="caufa-trusted-device").unsign(raw)
    except BadSignature:
        return False
    parts = payload.split(":")
    if len(parts) != 2:
        return False
    try:
        uid, fp = parts
        if int(uid) != officer.user_id_PK:
            return False
    except ValueError:
        return False
    return fp == _device_fingerprint(request.META.get("HTTP_USER_AGENT"))


def _queue_mfa_email(officer, otp):
    from core_system.services.mfa_service import send_mfa_email
    return send_mfa_email(officer, otp)


def _check_term_validity(officer: OfficerUser) -> tuple[bool, str]:
    term_start = getattr(officer, "term_start", None)
    term_end = getattr(officer, "term_end", None)
    if not term_start or not term_end:
        return True, ""
    today = timezone.localdate()
    if today < term_start:
        return False, f"Your officer term has not started yet. Term begins on {term_start.isoformat()}."
    if today > term_end:
        return False, f"Your officer term expired on {term_end.isoformat()}. Please contact the board."
    return True, ""


def _term_info(officer: OfficerUser) -> dict:
    term_start = getattr(officer, "term_start", None)
    term_end = getattr(officer, "term_end", None)
    today = timezone.localdate()
    is_expired = False
    days_until_expiry = None
    if term_start and term_end:
        if today > term_end:
            is_expired = True
        else:
            days_until_expiry = (term_end - today).days
    return {
        "term_start": term_start.isoformat() if term_start else "",
        "term_end": term_end.isoformat() if term_end else "",
        "is_expired": is_expired,
        "days_until_expiry": days_until_expiry,
    }


def _workspace_redirect(role: str) -> str:
    role_norm = (role or "").strip().lower()
    if role_norm == "member":
        return "/member/"
    if role_norm == "treasurer":
        return "/treasurer/"
    if role_norm == "auditor":
        return "/auditor/"
    if role_norm == "president":
        return "/president/"
    if role_norm == "secretary":
        return "/secretary/"
    if role_norm == "superadmin":
        return "/superadmin/"
    if role_norm == "public information officer":
        return "/pio/"
    if role_norm == "system":
        return "/systembackup/"
    return "/"


def _login_success_redirect(officer: OfficerUser) -> str:
    if getattr(officer, "must_change_password", False):
        return "/change-password/"
    return _workspace_redirect(officer.role)


def _resolve_login_state_code(officer: OfficerUser) -> str | None:
    status = (officer.account_status or "").strip()
    normalized = status.lower()

    if status == RegistrationStatus.PENDING_TREASURER_REVIEW:
        return "pending_treasurer_review"
    if status == RegistrationStatus.RETURNED_FOR_REVISION:
        return "returned_for_revision"
    if status == RegistrationStatus.TREASURER_VERIFIED:
        return "pending_auditor_review"
    if status == RegistrationStatus.AUDITOR_VERIFIED:
        return "pending_president_approval"
    if normalized in {"inactive", "inactive_account"}:
        return "inactive_account"
    if normalized in {"suspended", "suspended_account", "account_suspended"}:
        return "suspended_account"
    if normalized in {"retired", "retired_member", "retired_account"}:
        return "retired_member"
    if normalized in {"locked", "account_locked", "temporarily locked", "temporarily_locked"}:
        return "account_locked"

    return None


def _login_error_info(code: str) -> dict:
    return {
        "incorrect_password": {
            "title": "Password Incorrect",
            "detail": "The password you entered is incorrect. Please try again.",
        },
        "account_not_found": {
            "title": "Account Not Found",
            "detail": "No ISU CAUFA account is associated with the entered Faculty ID or Email. Please check your credentials or register for a new account.",
        },
        "pending_treasurer_review": {
            "title": "Registration Pending",
            "detail": "Your registration is currently under review by the Treasurer. You will receive a notification once your registration has been reviewed.",
        },
        "pending_auditor_review": {
            "title": "Pending Auditor Review",
            "detail": "Your registration has been verified by the Treasurer and is now awaiting review by the Auditor. You will be notified once the Auditor has completed the review.",
        },
        "pending_president_approval": {
            "title": "Pending President Approval",
            "detail": "Your registration has been verified by the Auditor and is now awaiting final approval from the President. Your account will become active once approved.",
        },
        "returned_for_revision": {
            "title": "Registration Returned",
            "detail": "Your registration requires corrections. Please review the remarks, update the required information, and submit again.",
        },
        "inactive_account": {
            "title": "Account Inactive",
            "detail": "Your account is currently inactive. Please contact the Treasurer or System Administrator.",
        },
        "suspended_account": {
            "title": "Account Suspended",
            "detail": "Your account has been temporarily suspended. Please contact the CAUFA officers for assistance.",
        },
        "retired_member": {
            "title": "Retired Membership",
            "detail": "Your membership is classified as Retired. Please contact the Treasurer if you believe this is incorrect.",
        },
        "device_not_registered": {
            "title": "Unrecognized Device",
            "detail": "This device is not registered for your account. Please verify your identity before continuing.",
        },
        "location_restricted": {
            "title": "Location Verification Failed",
            "detail": "Login from your current location is not permitted. Please try again from an authorized location.",
        },
        "account_locked": {
            "title": "Account Temporarily Locked",
            "detail": "Too many unsuccessful login attempts. Please try again later or reset your password.",
        },
    }.get(code, {
        "title": "Login Failed",
        "detail": "Please check your credentials and try again.",
    })


@csrf_protect
def officer_login(request: HttpRequest) -> HttpResponse:
    """Role-based login using OfficerUser (SHA-256 hex stored in password_hash)."""
    if request.method == "GET":
        force_login = (request.GET.get("force") or "").strip().lower() in {"1", "true", "yes", "on"}
        if "access_token" in request.session and not force_login:
            officer_id = request.session.get("officer_id")
            if officer_id:
                try:
                    existing = OfficerUser.objects.get(user_id_PK=officer_id)
                    if getattr(existing, "must_change_password", False):
                        return redirect("/change-password/")
                except OfficerUser.DoesNotExist:
                    pass
            return redirect(_workspace_redirect(request.session.get("role", "")))

        if force_login:
            request.session.flush()

        # If the MFA keys were set by the POST handler (redirect from login POST),
        # preserve them and clear the flag. Otherwise clear stale MFA state.
        if request.session.pop("_mfa_initiated", None):
            pass  # MFA keys are fresh from POST — keep them
        else:
            for key in (MFA_SESSION_KEY, MFA_OFFICER_ID_KEY, MFA_USERNAME_KEY, "mfa_email_warning"):
                request.session.pop(key, None)

        context = {
            "turnstile_enabled": is_turnstile_enabled(),
            "turnstile_site_key": get_turnstile_site_key(),
        }
        if request.session.get(MFA_SESSION_KEY):
            context["form"] = {
                "errors": [],
                "mfa_required": True,
                "pre_auth_token": request.session.get(MFA_SESSION_KEY, ""),
                "username": request.session.get(MFA_USERNAME_KEY, ""),
                "delivery": "Email",
            }
            if request.session.get("mfa_email_warning"):
                context["form"]["email_warning"] = request.session.get("mfa_email_warning")
                del request.session["mfa_email_warning"]
        return render(request, "website/login.html", context)

    is_ajax = request.headers.get("X-Requested-With") == "XMLHttpRequest"

    username = (request.POST.get("username") or "").strip()
    password_input = request.POST.get("password") or ""
    ip_address = request.META.get("REMOTE_ADDR") or "0.0.0.0"
    user_agent = request.META.get("HTTP_USER_AGENT") or "Unknown"
    turnstile_token = (request.POST.get("cf-turnstile-response") or "").strip()

    try:
        officer = OfficerUser.objects.get(username=username)
    except OfficerUser.DoesNotExist:
        officer = None

    # Only validate turnstile if user exists - avoid security verification for non-existent accounts
    if officer is not None and is_turnstile_enabled(request) and not validate_turnstile_token(turnstile_token, remote_ip=ip_address, request=request):
        error_info = {
            "title": "Security Verification Failed",
            "detail": "Please complete the security check and try again.",
        }
        if is_ajax:
            return JsonResponse({
                "ok": False,
                "error_code": "turnstile_failed",
                "error_title": error_info["title"],
                "error_detail": error_info["detail"],
                "error": error_info["detail"],
            }, status=403)
        context = {
            "login_error_code": "turnstile_failed",
            "login_error_title": error_info["title"],
            "login_error_detail": error_info["detail"],
            "turnstile_enabled": True,
            "turnstile_site_key": get_turnstile_site_key(),
        }
        return render(request, "website/login.html", context)

    password_hash_ok = False
    if officer is not None:
        password_hash_ok = verify_password(password_input, officer.password_hash)

    # Check if user is on mobile device for Member role
    # NOTE: User agent detection has limitations - it can be spoofed via DevTools
    # This blocks casual attempts but determined users can bypass it
    def is_mobile_device(user_agent_str):
        if not user_agent_str:
            return True  # Allow if no user agent
        
        user_agent_lower = user_agent_str.lower()
        
        # Block obvious desktop Windows - this is the most reliable desktop indicator
        if 'windows nt' in user_agent_lower:
            return False
        
        # Allow everything else (mobile phones, tablets, Mac, Linux, etc.)
        return True

    state_code = None
    if officer is not None and password_hash_ok:
        state_code = _resolve_login_state_code(officer)

    if officer and password_hash_ok and state_code is None:
        # Check if member trying to login on desktop
        if officer.role == "Member" and not is_mobile_device(user_agent):
            log_login_attempt(
                username=username,
                ip_address=ip_address,
                device_info=user_agent,
                result="Desktop login blocked for member",
                user_id=officer.user_id_PK,
            )
            if is_ajax:
                return JsonResponse({
                    "ok": False, 
                    "error": "Member login is only available on mobile devices. Please use a mobile device to access the member dashboard."
                }, status=403)
            messages.error(request, "Member login is only available on mobile devices. Please use a mobile device to access the member dashboard.")
            return redirect("login")
        term_ok, term_error = _check_term_validity(officer)
        if not term_ok:
            log_login_attempt(
                username=username,
                ip_address=ip_address,
                device_info=user_agent,
                result="Term expired",
                user_id=officer.user_id_PK,
            )
            if is_ajax:
                return JsonResponse({"ok": False, "error": term_error, "term_expired": True}, status=400)
            messages.error(request, term_error, extra_tags="term_expired")
            return redirect("login")

        if officer.mfa_enabled and officer.mfa_secret and not _is_trusted_device(request, officer):
            now = timezone.now()
            time_limit = now - timedelta(seconds=MFA_EMAIL_RATE_LIMIT_SECONDS)
            rate_limited = False

            if not officer.last_mfa_email_sent_at or officer.last_mfa_email_sent_at < time_limit:
                otp = generate_otp(officer.mfa_secret)
                email_sent = _queue_mfa_email(officer, otp)
                if email_sent:
                    officer.last_mfa_email_sent_at = now
                    officer.save(update_fields=["last_mfa_email_sent_at"])
            else:
                email_sent = False
                rate_limited = True

            pre_auth_token = secrets.token_urlsafe(32)
            request.session[MFA_SESSION_KEY] = pre_auth_token
            request.session[MFA_OFFICER_ID_KEY] = officer.user_id_PK
            request.session[MFA_USERNAME_KEY] = officer.username
            request.session.set_expiry(600)

            if rate_limited:
                request.session["mfa_email_warning"] = "A verification code was already sent recently. Please check your inbox."
            elif not email_sent:
                request.session["mfa_email_warning"] = "Failed to send verification email. Please use the resend option or contact support."

            log_login_attempt(
                username=username,
                ip_address=ip_address,
                device_info=user_agent,
                result="MFA_REQUIRED",
                user_id=officer.user_id_PK,
            )
            request.session["_mfa_initiated"] = True
            if is_ajax:
                return JsonResponse({"ok": True, "mfa_required": True, "redirect_url": "/login/"})
            return redirect("login")

        session, token = create_access_session(officer=officer, ip_address=ip_address, device_info=user_agent)
        session.trusted_device = True
        session.last_verified_location = {"ip": ip_address, "ua": user_agent}
        session.session_policy = {
            "zt_verified_at": timezone.now().isoformat(),
            "auth_method": "password",
        }
        session.save(update_fields=["trusted_device", "last_verified_location", "session_policy"])
        request.session["access_token"] = token
        request.session["officer_id"] = officer.user_id_PK
        request.session["role"] = officer.role
        
        log_login_attempt(
            username=username,
            ip_address=ip_address,
            device_info=user_agent,
            result="Success",
            user_id=officer.user_id_PK,
        )
        if is_ajax:
            response = JsonResponse({"ok": True, "redirect_url": _login_success_redirect(officer)})
            if _is_trusted_device(request, officer):
                _set_trusted_device_cookie(response, officer, user_agent)
            return response
        response = redirect(_login_success_redirect(officer))
        if _is_trusted_device(request, officer):
            _set_trusted_device_cookie(response, officer, user_agent)
        return response

    if officer is None:
        # Check if there's a member registration with this username at any stage
        pending_registration = MemberRegistrationRequest.objects.filter(
            employee_id__iexact=username,
        ).exclude(
            status__in={
                RegistrationStatus.PRESIDENT_APPROVED,
                RegistrationStatus.REJECTED,
            }
        ).first()
        if pending_registration:
            status = pending_registration.status
            if status == RegistrationStatus.PENDING_TREASURER_REVIEW:
                error_code = "pending_treasurer_review"
            elif status == RegistrationStatus.TREASURER_VERIFIED:
                error_code = "pending_auditor_review"
            elif status == RegistrationStatus.AUDITOR_VERIFIED:
                error_code = "pending_president_approval"
            elif status == RegistrationStatus.RETURNED_FOR_REVISION:
                error_code = "returned_for_revision"
            else:
                error_code = "pending_treasurer_review"
        else:
            error_code = "account_not_found"
    elif not password_hash_ok:
        error_code = "incorrect_password"
    else:
        error_code = state_code or "account_not_found"

    error_info = _login_error_info(error_code)
    log_login_attempt(
        username=username,
        ip_address=ip_address,
        device_info=user_agent,
        result=error_code,
        user_id=officer.user_id_PK if officer else None,
    )

    if is_ajax:
        return JsonResponse(
            {
                "ok": False,
                "error_code": error_code,
                "error_title": error_info["title"],
                "error_detail": error_info["detail"],
                "error": error_info["detail"],
            },
            status=401,
        )

    context = {
        "login_error_code": error_code,
        "login_error_title": error_info["title"],
        "login_error_detail": error_info["detail"],
        "turnstile_enabled": is_turnstile_enabled(),
        "turnstile_site_key": get_turnstile_site_key(),
    }
    return render(request, "website/login.html", context)


@require_POST
@csrf_protect
def mfa_verify(request: HttpRequest) -> JsonResponse:
    """Verifies incoming OTP code for step-up login flow."""
    otp = (request.POST.get("otp") or "").strip()
    pre_auth_token = (request.POST.get("pre_auth_token") or "").strip() or request.session.get(MFA_SESSION_KEY)

    if not pre_auth_token or not otp:
        return JsonResponse({"ok": False, "error": "Missing code or token context."}, status=400)

    # Validate session pre-auth token
    session_token = request.session.get(MFA_SESSION_KEY)
    if not session_token or session_token != pre_auth_token:
        return JsonResponse({"ok": False, "error": "Invalid or expired session. Please log in again."}, status=400)

    officer_id = request.session.get(MFA_OFFICER_ID_KEY)
    if not officer_id:
        return JsonResponse({"ok": False, "error": "Pre-auth context expired."}, status=400)

    try:
        officer = OfficerUser.objects.get(user_id_PK=officer_id)
    except OfficerUser.DoesNotExist:
        return JsonResponse({"ok": False, "error": "Officer account not found."}, status=404)

    # Verify the code
    import logging as _lg
    _log = _lg.getLogger(__name__)
    _log.info("mfa_verify: officer=%s otp_input=%s", officer.full_name, otp)
    if not verify_otp(officer.mfa_secret, otp):
        _log.warning("mfa_verify FAILED: secret=%s...", officer.mfa_secret[:8])
        return JsonResponse({"ok": False, "error": "Invalid verification code."}, status=401)

    term_ok, term_error = _check_term_validity(officer)
    if not term_ok:
        request.session.pop(MFA_SESSION_KEY, None)
        request.session.pop(MFA_OFFICER_ID_KEY, None)
        request.session.pop(MFA_USERNAME_KEY, None)
        log_login_attempt(
            username=officer.username,
            ip_address=request.META.get("REMOTE_ADDR") or "0.0.0.0",
            device_info=request.META.get("HTTP_USER_AGENT"),
            result="Term expired",
            user_id=officer.user_id_PK,
        )
        return JsonResponse({"ok": False, "error": term_error, "term_expired": True}, status=403)

    # Success: Clean up temporary keys
    request.session.pop(MFA_SESSION_KEY, None)
    request.session.pop(MFA_OFFICER_ID_KEY, None)
    request.session.pop(MFA_USERNAME_KEY, None)

    # Establish full session
    ip_address = request.META.get("REMOTE_ADDR") or "0.0.0.0"
    user_agent = request.META.get("HTTP_USER_AGENT")
    session, token = create_access_session(
        officer=officer,
        ip_address=ip_address,
        device_info=user_agent,
    )

    session.trusted_device = True
    session.last_verified_location = {"ip": ip_address, "ua": user_agent}
    session.session_policy = {
        "zt_verified_at": timezone.now().isoformat(),
        "auth_method": "mfa_email",
    }
    session.save(update_fields=["trusted_device", "last_verified_location", "session_policy"])

    request.session["access_token"] = token
    request.session["officer_id"] = officer.user_id_PK
    request.session["role"] = officer.role
    request.session.set_expiry(None)

    log_login_attempt(
        username=officer.username,
        ip_address=ip_address,
        device_info=user_agent,
        result="Success",
        user_id=officer.user_id_PK,
    )

    response = JsonResponse({
        "ok": True,
        "redirect_url": _login_success_redirect(officer),
    })
    _set_trusted_device_cookie(response, officer, user_agent)
    return response


@require_POST
@csrf_protect
def mfa_challenge(request: HttpRequest) -> JsonResponse:
    """Triggered when user requests to resend OTP via AJAX during login."""
    username = (request.POST.get("username") or "").strip()
    session_username = request.session.get(MFA_USERNAME_KEY)

    if not username or username != session_username:
        return JsonResponse({"ok": False, "error": "Session mismatch. Re-authenticate from login screen."}, status=400)

    officer_id = request.session.get(MFA_OFFICER_ID_KEY)
    try:
        officer = OfficerUser.objects.get(user_id_PK=officer_id)
    except OfficerUser.DoesNotExist:
        return JsonResponse({"ok": False, "error": "Officer context missing."}, status=404)

    now = timezone.now()
    time_limit = now - timedelta(seconds=MFA_EMAIL_RATE_LIMIT_SECONDS)

    if not officer.last_mfa_email_sent_at or officer.last_mfa_email_sent_at < time_limit:
        otp = generate_otp(officer.mfa_secret)
        email_sent = send_mfa_email(officer, otp)
        if email_sent:
            officer.last_mfa_email_sent_at = now
            officer.save(update_fields=["last_mfa_email_sent_at"])
            request.session.set_expiry(600)
        return JsonResponse({
            "ok": email_sent,
            "message": "Verification code sent via email." if email_sent else "Failed to send email. Try again.",
            "delivery": "email",
        })

    wait_minutes = int(MFA_EMAIL_RATE_LIMIT_SECONDS / 60 - (now - officer.last_mfa_email_sent_at).total_seconds() / 60)
    return JsonResponse({
        "ok": False,
        "error": f"Email OTP was recently sent. Please wait {wait_minutes} minutes.",
        "rate_limited": True,
    }, status=429)


@require_POST
@csrf_protect
def mfa_enable(request: HttpRequest) -> HttpResponse:
    stored_officer_id = request.session.get("officer_id")
    if stored_officer_id is None:
        return JsonResponse({"ok": False, "error": "Not authenticated."}, status=401)

    try:
        officer = OfficerUser.objects.get(user_id_PK=int(stored_officer_id))
    except OfficerUser.DoesNotExist:
        return JsonResponse({"ok": False, "error": "Officer not found."}, status=404)

    if not officer.mfa_enabled:
        officer.mfa_enabled = True
        officer.mfa_secret = generate_mfa_secret()
        officer.save(update_fields=["mfa_enabled", "mfa_secret"])

    return JsonResponse({
        "ok": True,
        "message": "MFA enabled. You will be asked for a code at login.",
    })


@require_POST
@csrf_protect
def mfa_disable(request: HttpRequest) -> HttpResponse:
    stored_officer_id = request.session.get("officer_id")
    if stored_officer_id is None:
        return JsonResponse({"ok": False, "error": "Not authenticated."}, status=401)

    try:
        officer = OfficerUser.objects.get(user_id_PK=int(stored_officer_id))
    except OfficerUser.DoesNotExist:
        return JsonResponse({"ok": False, "error": "Officer not found."}, status=404)

    officer.mfa_enabled = False
    officer.mfa_secret = None
    officer.save(update_fields=["mfa_enabled", "mfa_secret"])

    return JsonResponse({"ok": True, "message": "MFA disabled."})


def _get_officer_and_access_session(request: HttpRequest):
    token = request.session.get("access_token")
    if not token:
        return None, None, JsonResponse({"ok": False, "error": "Not authenticated."}, status=401)

    try:
        session = AccessSession.objects.select_related("user_id_FK").get(token_id=token)
    except AccessSession.DoesNotExist:
        request.session.pop("access_token", None)
        return None, None, JsonResponse(
            {"ok": False, "error": "Session invalid. Please log in again."},
            status=401,
        )

    return session.user_id_FK, session, None


@csrf_protect
def mfa_challenge_page(request: HttpRequest) -> HttpResponse:
    return render(request, "website/mfa_challenge.html")


@require_POST
@csrf_protect
def zero_trust_challenge(request: HttpRequest) -> HttpResponse:
    # DISABLED: Return success immediately without OTP during transition
    return JsonResponse({
        "ok": True,
        "message": "ZT challenge disabled during transition",
        "delivery": "disabled",
        "sent": True,
    })


@require_GET
def zero_trust_status(request: HttpRequest) -> HttpResponse:
    stored_officer_id = request.session.get("officer_id")
    token = request.session.get("access_token")
    if not stored_officer_id or not token:
        return JsonResponse({"ok": False, "verified": False, "error": "Not authenticated."}, status=401)

    try:
        from core_system.models import AccessSession
        from core_system.services.zt_service import get_session_fingerprint
        session = AccessSession.objects.get(token_id=token)
    except AccessSession.DoesNotExist:
        return JsonResponse({"ok": False, "verified": False, "error": "Session not found."}, status=401)

    fingerprint = get_session_fingerprint(request, session)
    policy = session.session_policy or {}

    return JsonResponse({
        "ok": True,
        "verified": session.trusted_device,
        "fingerprint": fingerprint,
        "zt_confirm_count": policy.get("zt_confirm_count", 0),
        "zt_last_confirmed": policy.get("zt_last_confirmed"),
    })


@require_POST
@csrf_protect
def zero_trust_verify(request: HttpRequest) -> HttpResponse:
    otp_input = (request.POST.get("otp") or "").strip()
    stored = request.session.get("zero_trust_otp")
    token = request.session.get("access_token")

    if not stored or not otp_input or not token:
        return JsonResponse({"ok": False, "error": "Invalid verification session."}, status=400)

    expires_at_str = stored.get("expires_at")
    if expires_at_str:
        expires_at = timezone.datetime.fromisoformat(expires_at_str)
        if timezone.is_naive(expires_at):
            expires_at = timezone.make_aware(expires_at)
        if timezone.now() > expires_at:
            return JsonResponse({"ok": False, "error": "Verification code expired."}, status=400)

    officer, session, auth_error = _get_officer_and_access_session(request)
    if auth_error is not None:
        return auth_error

    computed_otp = generate_otp(officer.mfa_secret)
    logger.info(
        "ZT verify: officer=%s otp_input=%s computed_otp=%s now=%s",
        officer.full_name,
        otp_input,
        computed_otp,
        time.time(),
    )
    if not verify_otp(officer.mfa_secret, otp_input):
        return JsonResponse({"ok": False, "error": "Invalid verification code."}, status=401)

    session.trusted_device = True
    session.ip_address = request.META.get("REMOTE_ADDR") or "0.0.0.0"
    session.device_info = request.META.get("HTTP_USER_AGENT")
    session.last_verified_location = {"ip": session.ip_address}
    session.last_activity_at = timezone.now()
    policy = session.session_policy or {}
    policy["zt_verified_at"] = timezone.now().isoformat()
    session.session_policy = policy
    session.save()

    request.session.pop("zero_trust_otp", None)

    return JsonResponse({"ok": True, "message": "Zero Trust verification successful."})


@require_POST
@csrf_protect
def zero_trust_confirm(request: HttpRequest) -> HttpResponse:
    """Per-action confirmation endpoint - replaces OTP-based verification.
    
    This endpoint generates a Session Integrity Token (SIT) for a specific action,
    logs the confirmation to the audit trail, and returns the SIT for use in
    subsequent requests.
    """
    try:
        from core_system.services.zt_service import (
            generate_sit,
            build_action_descriptor,
        )

        stored_officer_id = request.session.get("officer_id")
        token = request.session.get("access_token")
        if not stored_officer_id or not token:
            return JsonResponse({"ok": False, "error": "Not authenticated."}, status=401)

        action = (request.POST.get("action") or "").strip()
        action_id = (request.POST.get("action_id") or "").strip()
        details_raw = (request.POST.get("details") or "{}")

        # Provide defaults if missing to avoid blocking during testing
        if not action:
            action = "sensitive_action"
        if not action_id:
            action_id = str(int(time.time()))

        try:
            details = json.loads(details_raw) if isinstance(details_raw, str) else details_raw
        except json.JSONDecodeError:
            details = {}

        try:
            officer = OfficerUser.objects.get(user_id_PK=int(stored_officer_id))
            session = AccessSession.objects.get(token_id=token)
        except (OfficerUser.DoesNotExist, AccessSession.DoesNotExist):
            return JsonResponse({"ok": False, "error": "Session not found."}, status=404)

        if not session.trusted_device:
            return JsonResponse({"ok": False, "error": "Device changed. Re-login required."}, status=403)

        timestamp = timezone.now().isoformat()
        sit = generate_sit(session.token_id, action, action_id, timestamp)

        descriptor = build_action_descriptor(action, action_id, details)
        
        # Log the confirmation to audit trail with error handling
        try:
            _record_audit_trail(
                table=action,
                record_id=int(action_id) if action_id.isdigit() else 0,
                action="ZT_CONFIRM",
                actor=officer,
                old=None,
                new=details,
                ip=request.META.get("REMOTE_ADDR"),
                device_info=request.META.get("HTTP_USER_AGENT"),
                notes=f"ZT Confirm: {descriptor} | SIT: {sit[:16]}...",
            )
        except Exception as e:
            logger.error("Failed to record ZT audit trail: %s", e)
            # Continue anyway - the confirmation should still work

        try:
            policy = session.session_policy or {}
            policy["zt_last_confirmed"] = timestamp
            policy["zt_confirm_count"] = (policy.get("zt_confirm_count", 0) or 0) + 1
            session.session_policy = policy
            session.save(update_fields=["session_policy"])
        except Exception as e:
            logger.error("Failed to update session policy: %s", e)
            # Continue anyway - the confirmation should still work

        return JsonResponse({
            "ok": True,
            "sit": sit,
            "timestamp": timestamp,
            "descriptor": descriptor,
            "zt_verified_at": timestamp,
        })
    except Exception as e:
        logger.error("ZT confirm error: %s", e, exc_info=True)
        return JsonResponse({
            "ok": False,
            "error": f"Confirmation failed: {str(e)}"
        }, status=500)


@csrf_protect
def forgot_password(request: HttpRequest) -> HttpResponse:
    if request.method == "GET":
        return render(request, "website/forgot_password.html")

    email = (request.POST.get("email") or "").strip()
    if not email:
        messages.error(request, "Please enter your email address.")
        return render(request, "website/forgot_password.html")

    try:
        officer = OfficerUser.objects.get(email__iexact=email)
    except OfficerUser.DoesNotExist:
        messages.error(request, "No account found with that email address.")
        return render(request, "website/forgot_password.html")

    otp = generate_otp(officer.mfa_secret or generate_mfa_secret())
    if not officer.mfa_secret:
        officer.mfa_secret = generate_mfa_secret()
        officer.save(update_fields=["mfa_secret"])

    email_sent = send_mfa_email(officer, otp)
    if not email_sent:
        messages.error(request, "Failed to send verification email. Please try again later.")
        return render(request, "website/forgot_password.html")

    request.session["reset_email"] = email
    request.session["reset_officer_id"] = officer.user_id_PK
    request.session["reset_otp"] = otp
    request.session["reset_otp_created_at"] = timezone.now().isoformat()
    request.session.set_expiry(600)

    return redirect("reset_password")


@csrf_protect
def reset_password(request: HttpRequest) -> HttpResponse:
    reset_email = request.session.get("reset_email")
    reset_officer_id = request.session.get("reset_officer_id")
    reset_otp = request.session.get("reset_otp")
    otp_created_at = request.session.get("reset_otp_created_at")

    if not reset_email or not reset_officer_id or not reset_otp or not otp_created_at:
        return render(request, "website/reset_password.html", {"expired": True})

    try:
        created = timezone.datetime.fromisoformat(otp_created_at)
        if timezone.is_naive(created):
            created = timezone.make_aware(created)
        if timezone.now() > created + timedelta(minutes=10):
            request.session.pop("reset_email", None)
            request.session.pop("reset_officer_id", None)
            request.session.pop("reset_otp", None)
            request.session.pop("reset_otp_created_at", None)
            return render(request, "website/reset_password.html", {"expired": True})
    except (ValueError, TypeError):
        return render(request, "website/reset_password.html", {"expired": True})

    if request.method == "GET":
        return render(request, "website/reset_password.html", {"email": reset_email})

    otp_input = (request.POST.get("otp") or "").strip()
    new_password = request.POST.get("new_password") or ""
    confirm_password = request.POST.get("confirm_password") or ""

    if otp_input != reset_otp:
        messages.error(request, "Invalid verification code. Please try again.")
        return render(request, "website/reset_password.html", {"email": reset_email})

    if new_password != confirm_password:
        messages.error(request, "Passwords do not match.")
        return render(request, "website/reset_password.html", {"email": reset_email})

    if len(new_password) < 8:
        messages.error(request, "Password must be at least 8 characters.")
        return render(request, "website/reset_password.html", {"email": reset_email})

    try:
        officer = OfficerUser.objects.get(user_id_PK=reset_officer_id)
    except OfficerUser.DoesNotExist:
        messages.error(request, "Account not found.")
        return render(request, "website/reset_password.html", {"email": reset_email})

    officer.password_hash = hash_password(new_password)
    officer.must_change_password = False
    officer.save(update_fields=["password_hash", "must_change_password"])

    request.session.pop("reset_email", None)
    request.session.pop("reset_officer_id", None)
    request.session.pop("reset_otp", None)
    request.session.pop("reset_otp_created_at", None)

    messages.success(request, "Your password has been reset successfully. You can now log in with your new password.")
    return redirect("login")


@csrf_protect
def change_password(request: HttpRequest) -> HttpResponse:
    """Self-service password change. Forced on first login when must_change_password is set.

    Requires an active session. Validates the current password, then updates the hash
    and clears the must_change_password flag.
    """
    from core_system.guards import require_officer_session

    guard = require_officer_session(request)
    if guard is not None:
        return guard

    officer_id = request.session.get("officer_id")
    try:
        officer = OfficerUser.objects.get(user_id_PK=officer_id)
    except OfficerUser.DoesNotExist:
        request.session.flush()
        return redirect("login")

    context = {"forced": bool(officer.must_change_password)}

    if request.method == "GET":
        return render(request, "website/change_password.html", context)

    current_password = request.POST.get("current_password") or ""
    new_password = request.POST.get("new_password") or ""
    confirm_password = request.POST.get("confirm_password") or ""

    if not verify_password(current_password, officer.password_hash):
        messages.error(request, "Your current password is incorrect.")
        return render(request, "website/change_password.html", context)

    if new_password != confirm_password:
        messages.error(request, "Passwords do not match.")
        return render(request, "website/change_password.html", context)

    if len(new_password) < 8:
        messages.error(request, "Password must be at least 8 characters.")
        return render(request, "website/change_password.html", context)

    if new_password == current_password:
        messages.error(request, "New password must be different from your current password.")
        return render(request, "website/change_password.html", context)

    officer.password_hash = hash_password(new_password)
    officer.must_change_password = False
    officer.save(update_fields=["password_hash", "must_change_password"])

    _record_audit_trail(
        table="officer_user",
        record_id=officer.user_id_PK,
        action="PASSWORD_CHANGED",
        actor=officer,
        ip=request.META.get("REMOTE_ADDR"),
        notes="Password changed via change-password flow.",
    )

    messages.success(request, "Your password has been updated successfully.")

    if (officer.role or "").strip().lower() == "member":
        from core_system.models import Member
        linked = Member.objects.filter(officer_user_id_FK=officer).first()
        if linked and not linked.setup_complete:
            return redirect("/member/onboarding/")

    return redirect(_workspace_redirect(officer.role))


@require_GET
def term_info(request: HttpRequest):
    stored_officer_id = request.session.get("officer_id")
    if stored_officer_id is None:
        return JsonResponse({"ok": False, "error": "Not authenticated."}, status=401)

    try:
        officer = OfficerUser.objects.get(user_id_PK=int(stored_officer_id))
    except OfficerUser.DoesNotExist:
        return JsonResponse({"ok": False, "error": "Officer not found."}, status=404)

    return JsonResponse({"ok": True, **_term_info(officer)})