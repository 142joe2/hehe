from __future__ import annotations

import json
import logging

from django.conf import settings
from django.db.models import Q
from django.http import HttpRequest, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from core_system.guards import require_role
from core_system.models import Member, OfficerUser, PushSubscription

logger = logging.getLogger(__name__)


def vapid_public_key(request: HttpRequest) -> JsonResponse:
    return JsonResponse({"publicKey": settings.VAPID_PUBLIC_KEY})


def _current_officer(request: HttpRequest) -> OfficerUser | None:
    stored_officer_id = request.session.get("officer_id")
    if stored_officer_id is None:
        return None
    try:
        return OfficerUser.objects.get(user_id_PK=int(stored_officer_id))
    except (OfficerUser.DoesNotExist, TypeError, ValueError):
        return None


def _linked_member(officer: OfficerUser) -> Member | None:
    return Member.objects.filter(officer_user_id_FK=officer).first()


def _request_origin(request: HttpRequest) -> str:
    """Best-effort origin of the page that triggered this subscribe request."""
    origin = request.META.get("HTTP_ORIGIN", "").strip()
    if origin:
        return origin
    return f"{request.scheme}://{request.get_host()}"


def _is_ngrok_origin(origin: str) -> bool:
    """True when an origin belongs to an ngrok tunnel (or similar transient host)."""
    return "ngrok" in (origin or "").lower()


def _purge_stale_subs(recipient_filter, keep_origin: str, keep_endpoint: str | None) -> int:
    """Delete push subscriptions for a recipient that were registered under a
    different browser origin (e.g. an old ngrok tunnel) so notifications are
    attributed to the current production site."""

    qs = PushSubscription.objects.filter(recipient_filter)
    if keep_endpoint:
        qs = qs.exclude(endpoint=keep_endpoint)
    if keep_origin:
        qs = qs.filter(Q(origin__isnull=True) | ~Q(origin=keep_origin))
    deleted, _ = qs.delete()
    if deleted:
        logger.info("Purged %d stale push subscription(s) for origin %s", deleted, keep_origin or "<unknown>")
    return deleted


@require_POST
@csrf_exempt
def push_subscribe(request: HttpRequest):
    # Allow both officer and member sessions
    recipient_type = (request.body and json.loads(request.body).get("recipient_type") or "officer").strip().lower()
    origin = _request_origin(request)

    if _is_ngrok_origin(origin):
        logger.warning("Rejecting push subscribe from transient origin %s", origin)
        return JsonResponse({"ok": False, "error": "Push subscriptions are not accepted from ngrok origins."}, status=400)

    if recipient_type == "member":
        # Handle member session
        from core_system.member_views import _get_member_from_session
        member, err = _get_member_from_session(request)
        if not member:
            return JsonResponse({"ok": False, "error": "Not authenticated or no member session."}, status=401)
        
        try:
            body = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({"ok": False, "error": "Invalid JSON."}, status=400)

        endpoint = body.get("endpoint", "").strip()
        keys = body.get("keys", {})
        p256dh = keys.get("p256dh", "").strip()
        auth = keys.get("auth", "").strip()
        user_agent = request.META.get("HTTP_USER_AGENT", "")[:500]

        if not endpoint or not p256dh or not auth:
            return JsonResponse({"ok": False, "error": "Missing endpoint or keys."}, status=400)

        # Check for existing subscription with same endpoint to prevent duplicates
        existing = PushSubscription.objects.filter(endpoint=endpoint).first()
        if existing:
            logger.warning("Duplicate subscription detected for endpoint %s, updating existing subscription %s", 
                         endpoint[:50], existing.subscription_id_PK)
            # Update the existing subscription instead of creating a new one
            existing.p256dh_key = p256dh
            existing.auth_key = auth
            existing.user_agent = user_agent
            existing.origin = origin
            existing.member_id_FK = member
            existing.officer_id_FK = None
            existing.save()
            _purge_stale_subs(Q(member_id_FK=member), origin, endpoint)
            logger.info("Updated existing subscription %s for member %s", existing.subscription_id_PK, member.member_id_PK)
            return JsonResponse({"ok": True, "message": "Member subscription updated."})

        PushSubscription.objects.create(
            member_id_FK=member,
            endpoint=endpoint,
            p256dh_key=p256dh,
            auth_key=auth,
            user_agent=user_agent,
            origin=origin,
        )
        _purge_stale_subs(Q(member_id_FK=member), origin, endpoint)
        logger.info("New member push subscription created for member %s, endpoint: %s", member.member_id_PK, endpoint[:50])
        return JsonResponse({"ok": True, "message": "Member subscription saved."})
    
    else:
        # Handle officer session (existing logic)
        guard = require_role(request, role=None)
        if guard is not None:
            return guard

        officer = _current_officer(request)
        if officer is None:
            return JsonResponse({"ok": False, "error": "Not authenticated."}, status=401)

        try:
            body = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({"ok": False, "error": "Invalid JSON."}, status=400)

        endpoint = body.get("endpoint", "").strip()
        keys = body.get("keys", {})
        p256dh = keys.get("p256dh", "").strip()
        auth = keys.get("auth", "").strip()
        user_agent = request.META.get("HTTP_USER_AGENT", "")[:500]

        if not endpoint or not p256dh or not auth:
            return JsonResponse({"ok": False, "error": "Missing endpoint or keys."}, status=400)

        # Check for existing subscription with same endpoint to prevent duplicates
        existing = PushSubscription.objects.filter(endpoint=endpoint).first()
        if existing:
            logger.warning("Duplicate subscription detected for endpoint %s, updating existing subscription %s", 
                         endpoint[:50], existing.subscription_id_PK)
            # Update the existing subscription instead of creating a new one
            existing.p256dh_key = p256dh
            existing.auth_key = auth
            existing.user_agent = user_agent
            existing.origin = origin
            existing.officer_id_FK = officer
            existing.member_id_FK = None
            existing.save()
            _purge_stale_subs(Q(officer_id_FK=officer), origin, endpoint)
            logger.info("Updated existing subscription %s for officer %s", existing.subscription_id_PK, officer.user_id_PK)
            return JsonResponse({"ok": True, "message": "Officer subscription updated."})

        PushSubscription.objects.create(
            officer_id_FK=officer,
            endpoint=endpoint,
            p256dh_key=p256dh,
            auth_key=auth,
            user_agent=user_agent,
            origin=origin,
        )
        _purge_stale_subs(Q(officer_id_FK=officer), origin, endpoint)
        logger.info("New officer push subscription created for officer %s, endpoint: %s", officer.user_id_PK, endpoint[:50])
        return JsonResponse({"ok": True, "message": "Officer subscription saved."})


@require_POST
@csrf_exempt
def push_unsubscribe(request: HttpRequest):
    stored_officer_id = request.session.get("officer_id")
    if stored_officer_id is None:
        from core_system.member_views import _get_member_from_session
        member, err = _get_member_from_session(request)
        if not member:
            return JsonResponse({"ok": False, "error": "Not authenticated."}, status=401)
        officer = None
    else:
        officer = _current_officer(request)
        member = _linked_member(officer) if officer else None

    if member is None and officer is None:
        return JsonResponse({"ok": False, "error": "Not authenticated."}, status=401)

    try:
        body = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"ok": False, "error": "Invalid JSON."}, status=400)

    endpoint = body.get("endpoint", "").strip()

    from django.db.models import Q

    if endpoint:
        qs = PushSubscription.objects.filter(endpoint=endpoint)
    else:
        # No endpoint provided (e.g. the member toggle is switched off):
        # remove every subscription owned by the current recipient.
        qs = PushSubscription.objects.all()
    q_any = Q(pk__in=[])
    if member is not None:
        q_any |= Q(member_id_FK=member)
    if officer is not None:
        q_any |= Q(officer_id_FK=officer)
    qs = qs.filter(q_any)

    deleted, _ = qs.delete()
    logger.info("Deleted %d push subscriptions", deleted)
    return JsonResponse({"ok": True, "deleted": deleted})


@require_POST
@csrf_exempt
def push_health_check(request: HttpRequest):
    """Check the health of push notification system (VAPID config and subscriptions)."""
    from core_system.services.notifications import check_subscription_health
    
    guard = require_role(request, role=["Treasurer", "Auditor", "President"])
    if guard is not None:
        return guard
    
    try:
        health_report = check_subscription_health()
        return JsonResponse({"ok": True, "health": health_report})
    except Exception as e:
        logger.error("Error in push health check: %s", e)
        return JsonResponse({"ok": False, "error": str(e)}, status=500)


@require_POST
@csrf_exempt
def push_vapid_check(request: HttpRequest):
    """Verify VAPID configuration is properly set up."""
    from core_system.services.notifications import verify_vapid_configuration
    
    guard = require_role(request, role=["Treasurer", "Auditor", "President"])
    if guard is not None:
        return guard
    
    try:
        vapid_config = verify_vapid_configuration()
        return JsonResponse({"ok": True, "vapid": vapid_config})
    except Exception as e:
        logger.error("Error in VAPID check: %s", e)
        return JsonResponse({"ok": False, "error": str(e)}, status=500)


@require_POST
@csrf_exempt
def validate_subscription(request: HttpRequest):
    """Validate if a push subscription is still active and valid."""
    recipient_type = (request.body and json.loads(request.body).get("recipient_type") or "officer").strip().lower()
    
    if recipient_type == "member":
        from core_system.member_views import _get_member_from_session
        member, err = _get_member_from_session(request)
        if not member:
            return JsonResponse({"ok": False, "error": "Not authenticated or no member session."}, status=401)
        
        try:
            body = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({"ok": False, "error": "Invalid JSON."}, status=400)
        
        endpoint = body.get("endpoint", "").strip()
        
        if not endpoint:
            return JsonResponse({"ok": False, "error": "Missing endpoint."}, status=400)
        
        # Check if subscription exists for this member
        subscription = PushSubscription.objects.filter(
            member_id_FK=member,
            endpoint=endpoint
        ).first()
        
        if subscription:
            return JsonResponse({"ok": True, "valid": True})
        else:
            return JsonResponse({"ok": True, "valid": False})
    
    else:
        # Handle officer session
        guard = require_role(request, role=None)
        if guard is not None:
            return guard
        
        officer = _current_officer(request)
        if officer is None:
            return JsonResponse({"ok": False, "error": "Not authenticated."}, status=401)
        
        try:
            body = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({"ok": False, "error": "Invalid JSON."}, status=400)
        
        endpoint = body.get("endpoint", "").strip()
        
        if not endpoint:
            return JsonResponse({"ok": False, "error": "Missing endpoint."}, status=400)
        
        # Check if subscription exists for this officer
        subscription = PushSubscription.objects.filter(
            officer_id_FK=officer,
            endpoint=endpoint
        ).first()
        
        if subscription:
            return JsonResponse({"ok": True, "valid": True})
        else:
            return JsonResponse({"ok": True, "valid": False})
