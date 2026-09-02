import hashlib
import json
import secrets
from datetime import timedelta

from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.csrf import csrf_protect, requires_csrf_token
from django.views.decorators.http import require_POST

from core_system.auth_utils import (
    create_access_session,
    log_login_attempt,
    verify_officer_password,
)
from core_system.models import AccessSession, LoginAttemptLog, OfficerUser, PushSubscription
from core_system.services.mfa_service import (
    generate_mfa_secret,
    generate_otp,
    send_mfa_email,
    send_mfa_push,
    verify_otp,
)

MFA_EMAIL_RATE_LIMIT_HOURS = 4


def _workspace_redirect(role: str) -> str:
    role_norm = (role or "").strip().lower()
    if role_norm == "treasurer":
        return "/treasurer/"
    if role_norm == "auditor":
        return "/auditor/"
    if role_norm == "president":
        return "/president/"
    return "/"


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
        "has_push": PushSubscription.objects.filter(officer_id_FK=officer).exists(),
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


@require_POST
@csrf_protect
def mfa_challenge(request: HttpRequest) -> HttpResponse:
    username = (request.POST.get("username") or "").strip()
    if not username:
        return JsonResponse({"ok": False, "error": "Username is required."}, status=400)

    try:
        officer = OfficerUser.objects.get(username=username)
    except OfficerUser.DoesNotExist:
        return JsonResponse({"ok": False, "error": "Invalid credentials."}, status=401)

    if not officer.mfa_enabled or not officer.mfa_secret or (officer.account_status or "").lower() != "active":
        return JsonResponse({"ok": False, "error": "Invalid credentials."}, status=401)

    otp = generate_otp(officer.mfa_secret)
    pre_auth_token = secrets.token_urlsafe(32)
    request.session["mfa_pre_auth"] = {
        "officer_id": officer.user_id_PK,
        "username": officer.username,
        "token": pre_auth_token,
        "otp": otp,
        "expires_at": (timezone.now() + timedelta(minutes=5)).isoformat(),
    }

    push_sent = send_mfa_push(officer=officer, otp=otp)
    if push_sent:
        return JsonResponse({
            "ok": True,
            "message": "Verification code sent via push notification.",
            "delivery": "push",
            "sent": True,
            "pre_auth_token": pre_auth_token,
        })

    now = timezone.now()
    last_email = officer.last_mfa_email_sent_at
    can_email = not last_email or (now - last_email).total_seconds() >= MFA_EMAIL_RATE_LIMIT_HOURS * 3600

    if not can_email:
        wait_minutes = int(MFA_EMAIL_RATE_LIMIT_HOURS * 60 - (now - last_email).total_seconds() / 60)
        return JsonResponse({
            "ok": False,
            "error": f"Email OTP was recently sent. Please wait {wait_minutes} minutes or subscribe to push notifications.",
            "delivery": "email",
            "sent": False,
            "rate_limited": True,
        }, status=429)

    email_sent = send_mfa_email(officer=officer, otp=otp)
    if email_sent:
        officer.last_mfa_email_sent_at = now
        officer.save(update_fields=["last_mfa_email_sent_at"])

    return JsonResponse({
        "ok": True,
        "message": "Verification code sent via email.",
        "delivery": "email",
        "sent": email_sent,
        "pre_auth_token": pre_auth_token,
    })


@require_POST
@csrf_protect
def mfa_verify(request: HttpRequest) -> HttpResponse:
    otp_input = (request.POST.get("otp") or "").strip()
    pre_auth_token = (request.POST.get("pre_auth_token") or "").strip()
    stored = request.session.get("mfa_pre_auth")

    if not stored or not otp_input or not pre_auth_token:
        return JsonResponse({"ok": False, "error": "Invalid MFA session."}, status=400)

    if stored.get("token") != pre_auth_token:
        return JsonResponse({"ok": False, "error": "Invalid MFA session."}, status=400)

    try:
        officer = OfficerUser.objects.get(user_id_PK=int(stored["officer_id"]))
    except OfficerUser.DoesNotExist:
        return JsonResponse({"ok": False, "error": "Officer not found."}, status=404)

    if not verify_otp(officer.mfa_secret, otp_input):
        return JsonResponse({"ok": False, "error": "Invalid verification code."}, status=401)

    ip_address = request.META.get("REMOTE_ADDR") or "0.0.0.0"
    user_agent = request.META.get("HTTP_USER_AGENT")
    session, token = create_access_session(
        officer=officer,
        ip_address=ip_address,
        device_info=user_agent,
    )

    request.session["access_token"] = token
    request.session["officer_id"] = officer.user_id_PK
    request.session["role"] = officer.role
    request.session.pop("mfa_pre_auth", None)

    log_login_attempt(
        username=officer.username,
        ip_address=ip_address,
        device_info=user_agent,
        result="Success",
        user_id=officer.user_id_PK,
    )

    return JsonResponse({
        "ok": True,
        "redirect_url": _workspace_redirect(officer.role),
    })


@csrf_protect
def officer_login(request: HttpRequest) -> HttpResponse:
    """Role-based login using OfficerUser (SHA-256 hex stored in password_hash)."""

    if request.method == "GET":
        return render(request, "website/login.html")

    username = (request.POST.get("username") or "").strip()
    password_input = request.POST.get("password") or ""
    ip_address = request.META.get("REMOTE_ADDR") or "0.0.0.0"
    user_agent = request.META.get("HTTP_USER_AGENT")

    try:
        officer = OfficerUser.objects.get(username=username)
    except OfficerUser.DoesNotExist:
        officer = None

    if officer is not None:
        ok = verify_officer_password(officer=officer, password_input=password_input)
        if ok and (officer.account_status or "").lower() == "active":
            if officer.mfa_enabled:
                request.session["mfa_pre_auth"] = {
                    "officer_id": officer.user_id_PK,
                    "username": officer.username,
                    "token": None,
                    "otp": None,
                    "expires_at": None,
                }
                log_login_attempt(
                    username=username,
                    ip_address=ip_address,
                    device_info=user_agent,
                    result="MFA_REQUIRED",
                    user_id=officer.user_id_PK,
                )
                return render(request, "website/login.html", context={
                    "form": {"errors": [], "mfa_required": True, "username": username},
                })

            session, token = create_access_session(
                officer=officer,
                ip_address=ip_address,
                device_info=user_agent,
            )
            log_login_attempt(
                username=username,
                ip_address=ip_address,
                device_info=user_agent,
                result="Success",
                user_id=officer.user_id_PK,
            )
            request.session["access_token"] = token
            request.session["officer_id"] = officer.user_id_PK
            request.session["role"] = officer.role
            return redirect(_workspace_redirect(officer.role))

        log_login_attempt(
            username=username,
            ip_address=ip_address,
            device_info=user_agent,
            result="Invalid credentials",
            user_id=getattr(officer, "user_id_PK", None),
        )
    else:
        log_login_attempt(
            username=username,
            ip_address=ip_address,
            device_info=user_agent,
            result="Invalid credentials",
            user_id=None,
        )

    return render(request, "website/login.html", context={"form": {"errors": [True]}})


@csrf_protect
def mfa_challenge_page(request: HttpRequest) -> HttpResponse:
    return render(request, "website/mfa_challenge.html")


@require_POST
@csrf_protect
def zero_trust_challenge(request: HttpRequest) -> HttpResponse:
    stored_officer_id = request.session.get("officer_id")
    if stored_officer_id is None:
        return JsonResponse({"ok": False, "error": "Not authenticated."}, status=401)

    try:
        officer = OfficerUser.objects.get(user_id_PK=int(stored_officer_id))
    except OfficerUser.DoesNotExist:
        return JsonResponse({"ok": False, "error": "Officer not found."}, status=404)

    if not officer.mfa_enabled or not officer.mfa_secret:
        return JsonResponse({"ok": False, "error": "MFA must be enabled to perform zero trust verification."}, status=400)

    otp = generate_otp(officer.mfa_secret)
    request.session["zero_trust_otp"] = {
        "otp": otp,
        "expires_at": (timezone.now() + timedelta(minutes=5)).isoformat(),
    }

    push_sent = send_mfa_push(officer=officer, otp=otp)
    if push_sent:
        return JsonResponse({
            "ok": True,
            "message": "Verification code sent via push notification.",
            "delivery": "push",
        })

    email_sent = send_mfa_email(officer=officer, otp=otp)
    return JsonResponse({
        "ok": True,
        "message": "Verification code sent via email.",
        "delivery": "email",
        "sent": email_sent,
    })


@require_POST
@csrf_protect
def zero_trust_verify(request: HttpRequest) -> HttpResponse:
    otp_input = (request.POST.get("otp") or "").strip()
    stored = request.session.get("zero_trust_otp")
    stored_officer_id = request.session.get("officer_id")
    token = request.session.get("access_token")

    if not stored or not otp_input or not stored_officer_id or not token:
        return JsonResponse({"ok": False, "error": "Invalid verification session."}, status=400)

    expires_at_str = stored.get("expires_at")
    if expires_at_str:
        expires_at = timezone.datetime.fromisoformat(expires_at_str)
        if timezone.is_naive(expires_at):
            expires_at = timezone.make_aware(expires_at)
        if timezone.now() > expires_at:
            return JsonResponse({"ok": False, "error": "Verification code expired."}, status=400)

    try:
        officer = OfficerUser.objects.get(user_id_PK=int(stored_officer_id))
    except OfficerUser.DoesNotExist:
        return JsonResponse({"ok": False, "error": "Officer not found."}, status=404)

    if not verify_otp(officer.mfa_secret, otp_input):
        return JsonResponse({"ok": False, "error": "Invalid verification code."}, status=401)

    try:
        session = AccessSession.objects.get(token_id=token)
        session.trusted_device = True
        session.ip_address = request.META.get("REMOTE_ADDR") or "0.0.0.0"
        session.device_info = request.META.get("HTTP_USER_AGENT")
        session.last_verified_location = {"ip": session.ip_address}
        session.save()
    except AccessSession.DoesNotExist:
        return JsonResponse({"ok": False, "error": "Access session not found."}, status=404)

    request.session.pop("zero_trust_otp", None)

    return JsonResponse({"ok": True, "message": "Zero Trust verification successful."})

#Gemini
import json
import secrets
from datetime import timedelta
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.csrf import csrf_protect

from core_system.auth_utils import (
    create_access_session,
    log_login_attempt,
    verify_officer_password,
)
from core_system.models import OfficerUser
from core_system.services.mfa_service import (
    generate_mfa_secret,
    generate_otp,
    verify_otp,
    send_mfa_push,
    send_mfa_email,
    MFA_EMAIL_RATE_LIMIT_HOURS,
)

MFA_SESSION_KEY = "mfa_pre_auth_token"
MFA_OFFICER_ID_KEY = "mfa_officer_id"
MFA_USERNAME_KEY = "mfa_username"

def _workspace_redirect(role: str) -> str:
    role_lower = (role or "").lower()
    if role_lower == "admin":
        return "/admin/dashboard/"
    return "/officer/dashboard/"


@csrf_protect
def officer_login(request: HttpRequest) -> HttpResponse:
    if request.method == "GET":
        if "session_token" in request.session:
            return redirect(_workspace_redirect(request.session.get("role", "")))
        return render(request, "website/login.html")

    username = (request.POST.get("username") or "").strip()
    password_input = request.POST.get("password") or ""
    ip_address = request.META.get("REMOTE_ADDR") or "0.0.0.0"
    user_agent = request.META.get("HTTP_USER_AGENT") or "Unknown"

    try:
        officer = OfficerUser.objects.get(username=username)
    except OfficerUser.DoesNotExist:
        officer = None

    password_ok = False
    if officer is not None:
        password_ok = verify_officer_password(officer=officer, password_input=password_input)

    if officer and password_ok and (officer.account_status or "").lower() == "active":
        # Check if MFA is enabled and configured
        if officer.mfa_enabled and officer.mfa_secret:
            otp = generate_otp(officer.mfa_secret)

            # Try to send via push
            push_sent = send_mfa_push(officer, otp)

            # Try to send via email if rate limit allows
            email_sent = False
            now = timezone.now()
            time_limit = now - timedelta(hours=MFA_EMAIL_RATE_LIMIT_HOURS)
            
            if not officer.last_mfa_email_sent_at or officer.last_mfa_email_sent_at < time_limit:
                email_sent = send_mfa_email(officer, otp)
                if email_sent:
                    officer.last_mfa_email_sent_at = now
                    officer.save(update_fields=["last_mfa_email_sent_at"])

            # Save temporary authentication context in session
            pre_auth_token = secrets.token_urlsafe(32)
            request.session[MFA_SESSION_KEY] = pre_auth_token
            request.session[MFA_OFFICER_ID_KEY] = officer.user_id_PK
            request.session[MFA_USERNAME_KEY] = officer.username
            request.session.set_expiry(300)  # Expires in 5 minutes

            log_login_attempt(
                username=username,
                ip_address=ip_address,
                device_info=user_agent,
                result="MFA challenge sent",
                user_id=officer.user_id_PK,
            )

            # Format delivery notification for the UI
            delivery_methods = []
            if push_sent:
                delivery_methods.append("Push Notification")
            if email_sent:
                delivery_methods.append("Email")
            
            delivery_msg = " & ".join(delivery_methods) if delivery_methods else "system options"

            context = {
                "mfa_required": True,
                "pre_auth_token": pre_auth_token,
                "username": officer.username,
                "delivery": delivery_msg,
                "errors": []
            }
            return render(request, "website/login.html", context=context)

        # No MFA: complete login sequence immediately
        session, token = create_access_session(officer, ip_address, user_agent)
        request.session["session_token"] = token
        request.session["role"] = officer.role
        request.session["user_id"] = officer.user_id_PK
        
        log_login_attempt(
            username=username,
            ip_address=ip_address,
            device_info=user_agent,
            result="Success",
            user_id=officer.user_id_PK,
        )
        return redirect(_workspace_redirect(officer.role))

    # Failed credentials fallback
    log_login_attempt(
        username=username,
        ip_address=ip_address,
        device_info=user_agent,
        result="Failed Credentials",
        user_id=officer.user_id_PK if officer else None,
    )
    return render(request, "website/login.html", context={"errors": ["Invalid username or password."]})


@csrf_protect
def mfa_verify(request: HttpRequest) -> JsonResponse:
    if request.method != "POST":
        return JsonResponse({"ok": False, "error": "Method not allowed."}, status=405)

    otp = (request.POST.get("otp") or "").strip()
    pre_auth_token = request.POST.get("pre_auth_token") or request.session.get(MFA_SESSION_KEY)

    if not pre_auth_token or not otp:
        return JsonResponse({"ok": False, "error": "Missing code or token context."}, status=400)

    # Validate the session matches the client-submitted pre-auth token
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
    if not verify_otp(officer.mfa_secret, otp):
        return JsonResponse({"ok": False, "error": "The code you entered is incorrect or expired."}, status=400)

    # Success: Clean up temporary keys to avoid replay/hijack vectors
    request.session.pop(MFA_SESSION_KEY, None)
    request.session.pop(MFA_OFFICER_ID_KEY, None)
    request.session.pop(MFA_USERNAME_KEY, None)

    # Establish full authenticated session
    ip_address = request.META.get("REMOTE_ADDR") or "0.0.0.0"
    user_agent = request.META.get("HTTP_USER_AGENT") or "Unknown"
    session, token = create_access_session(officer, ip_address, user_agent)
    
    request.session["session_token"] = token
    request.session["role"] = officer.role
    request.session["user_id"] = officer.user_id_PK

    log_login_attempt(
        username=officer.username,
        ip_address=ip_address,
        device_info=user_agent,
        result="Success (MFA Verified)",
        user_id=officer.user_id_PK,
    )

    return JsonResponse({"ok": True, "redirect_url": _workspace_redirect(officer.role)})


@csrf_protect
def mfa_challenge(request: HttpRequest) -> JsonResponse:
    """Triggered when user requests to resend OTP via AJAX."""
    if request.method != "POST":
        return JsonResponse({"ok": False, "error": "Method not allowed."}, status=405)

    username = (request.POST.get("username") or "").strip()
    session_username = request.session.get(MFA_USERNAME_KEY)

    if not username or username != session_username:
        return JsonResponse({"ok": False, "error": "Session mismatch. Re-authenticate from the login screen."}, status=400)

    officer_id = request.session.get(MFA_OFFICER_ID_KEY)
    try:
        officer = OfficerUser.objects.get(user_id_PK=officer_id)
    except OfficerUser.DoesNotExist:
        return JsonResponse({"ok": False, "error": "Officer context missing."}, status=404)

    otp = generate_otp(officer.mfa_secret)
    push_sent = send_mfa_push(officer, otp)

    # Respect same 4-hour rate limit for resending email OTPs
    email_sent = False
    now = timezone.now()
    time_limit = now - timedelta(hours=MFA_EMAIL_RATE_LIMIT_HOURS)
    
    if not officer.last_mfa_email_sent_at or officer.last_mfa_email_sent_at < time_limit:
        email_sent = send_mfa_email(officer, otp)
        if email_sent:
            officer.last_mfa_email_sent_at = now
            officer.save(update_fields=["last_mfa_email_sent_at"])

    delivery_methods = []
    if push_sent:
        delivery_methods.append("Push Notification")
    if email_sent:
        delivery_methods.append("Email")

    delivery_msg = " & ".join(delivery_methods) if delivery_methods else "system defaults"

    return JsonResponse({
        "ok": True,
        "message": f"Verification code resent via {delivery_msg}.",
        "delivery": delivery_msg
    })