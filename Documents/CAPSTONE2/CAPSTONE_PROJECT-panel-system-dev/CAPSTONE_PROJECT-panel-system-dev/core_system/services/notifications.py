"""Reusable notification service.

`notify_member` / `notify_officer` do three things in one call:

  1. Persist a Notification row (the permanent in-app history behind the bell).
  2. Send a Web Push to every device the recipient has subscribed.
  3. Broadcast a WebSocket event to the recipient's live dashboard group so the
     notification count / bell dot updates instantly (no manual refresh).
  4. Send an Email notification to the recipient's email address.

Web Push is best-effort: missing VAPID keys or a dead subscription never raise
and never break the caller's request.
"""
from __future__ import annotations

import json
import logging
import re
import time

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone

logger = logging.getLogger(__name__)

NOTIFICATION_CHANNEL_PUSH = "push"

# Retry configuration for failed push notifications
MAX_PUSH_RETRIES = 1  # Changed to 1 to prevent duplicate sends
PUSH_RETRY_DELAY_SECONDS = 0  # No delay since we're not retrying


def _abs_url(path: str) -> str:
    """Return an absolute URL for push payloads.

    Relative paths (e.g. /member/dashboard, /static/img/...png) are resolved
    against settings.BASE_URL instead of the service-worker registration origin,
    so notifications always point at the production domain (never a stale ngrok
    tunnel the device was subscribed under while testing).
    """
    if not path:
        return settings.BASE_URL.rstrip("/") + "/"
    if "://" in path:
        return path
    return settings.BASE_URL.rstrip("/") + "/" + path.lstrip("/")


def _broadcast_ws(group_name: str, payload: dict) -> None:
    try:
        async_to_sync(get_channel_layer().group_send)(group_name, payload)
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("WS broadcast to %s failed: %s", group_name, exc)


def _send_push_subs(subs, notification_type: str, message: str, url: str) -> None:
    """Send a Web Push payload to a queryset of PushSubscription rows with retry logic."""
    # VAPID Configuration Verification
    logger.info("=== PUSH NOTIFICATION START ===")
    logger.info("Notification Type: %s", notification_type)
    logger.info("Message: %s", message[:100] if message else "")
    logger.info("URL: %s", url)
    
    if not settings.VAPID_PRIVATE_KEY or not settings.VAPID_PUBLIC_KEY:
        logger.warning("VAPID keys not configured - PRIVATE_KEY: %s, PUBLIC_KEY: %s", 
                      bool(settings.VAPID_PRIVATE_KEY), bool(settings.VAPID_PUBLIC_KEY))
        logger.warning("Skipping push notifications due to missing VAPID keys")
        logger.info("=== PUSH NOTIFICATION END (SKIPPED) ===")
        return
    
    logger.info("VAPID keys configured - Push notifications enabled")
    
    try:
        from pywebpush import webpush
        logger.info("pywebpush library available")
    except Exception as exc:
        logger.warning("pywebpush unavailable: %s", exc)
        logger.warning("Skipping push notifications due to missing pywebpush library")
        logger.info("=== PUSH NOTIFICATION END (SKIPPED) ===")
        return

    if not subs.exists():
        logger.info("No push subscriptions found in database - skipping push notifications")
        logger.info("=== PUSH NOTIFICATION END (NO SUBSCRIPTIONS) ===")
        return

    logger.info("Found %d push subscriptions to attempt", subs.count())
    
    # Log subscription details for debugging
    for sub in subs:
        logger.info("Subscription ID: %s, Endpoint: %s, Member ID: %s, Officer ID: %s",
                   sub.subscription_id_PK, sub.endpoint[:50] + "...",
                   sub.member_id_FK_id, sub.officer_id_FK_id)

    payload = json.dumps({
        "title": notification_type,
        "body": message,
        "url": _abs_url(url or "/"),
        "icon": _abs_url("/static/img/isu_caufa_official_192.png"),
        "badge": _abs_url("/static/img/isu_caufa_official_badge.png"),
    })
    logger.info("Push payload prepared: %s", payload[:200])

    success_count = 0
    failure_count = 0
    retry_count = 0
    
    for sub in subs:
        logger.info("--- Attempting push to subscription %s ---", sub.subscription_id_PK)
        
        if sub.origin and "ngrok" in sub.origin.lower():
            logger.warning("Skipping subscription %s registered under transient origin %s", 
                          sub.subscription_id_PK, sub.origin)
            continue
        
        # Retry logic for each subscription
        for attempt in range(MAX_PUSH_RETRIES):
            try:
                logger.info("Attempt %d/%d for subscription %s", attempt + 1, MAX_PUSH_RETRIES, sub.subscription_id_PK)
                
                webpush(
                    subscription_info={
                        "endpoint": sub.endpoint,
                        "keys": {"p256dh": sub.p256dh_key, "auth": sub.auth_key},
                    },
                    data=payload,
                    vapid_private_key=settings.VAPID_PRIVATE_KEY,
                    vapid_claims={
                        "sub": "mailto:admin@caufa.local",
                    },
                    timeout=10,
                )
                
                success_count += 1
                logger.info("✓ SUCCESS: Push notification sent to subscription %s on attempt %d", 
                           sub.subscription_id_PK, attempt + 1)
                break  # Success - stop retrying this subscription, move to the next
                
            except Exception as exc:
                error_str = str(exc)
                logger.error("✗ FAILED: Attempt %d/%d for subscription %s: %s", 
                           attempt + 1, MAX_PUSH_RETRIES, sub.subscription_id_PK, error_str)
                
                # If this is not the last attempt, wait before retry
                if attempt < MAX_PUSH_RETRIES - 1:
                    retry_count += 1
                    logger.info("Waiting %d seconds before retry...", PUSH_RETRY_DELAY_SECONDS)
                    time.sleep(PUSH_RETRY_DELAY_SECONDS)
                else:
                    # All retries failed
                    failure_count += 1
                    logger.error("All %d retries failed for subscription %s", MAX_PUSH_RETRIES, sub.subscription_id_PK)
                    
                    # 410 Gone means subscription expired - delete it
                    if "410" in error_str or "Gone" in error_str:
                        logger.info("Subscription %s expired (410 Gone) - deleting from database", sub.subscription_id_PK)
                        try:
                            sub.delete()
                            logger.info("✓ Successfully deleted expired subscription %s", sub.subscription_id_PK)
                        except Exception as delete_exc:
                            logger.warning("✗ Failed to delete expired subscription %s: %s", 
                                         sub.subscription_id_PK, delete_exc)
                    elif "404" in error_str or "Not Found" in error_str:
                        logger.warning("Subscription %s not found (404) - endpoint may be invalid", sub.subscription_id_PK)
                    elif "403" in error_str or "Forbidden" in error_str:
                        logger.warning("Subscription %s forbidden (403) - VAPID keys may be invalid", sub.subscription_id_PK)
                    continue  # All retries failed - move on to the next subscription
    
    logger.info("=== PUSH NOTIFICATION SUMMARY ===")
    logger.info("Total subscriptions: %d", subs.count())
    logger.info("Successful deliveries: %d", success_count)
    logger.info("Failed deliveries: %d", failure_count)
    logger.info("Total retries attempted: %d", retry_count)
    logger.info("=== PUSH NOTIFICATION END ===")


def check_subscription_health():
    """Check the health of all push subscriptions in the database."""
    from core_system.models import PushSubscription
    
    logger.info("=== SUBSCRIPTION HEALTH CHECK ===")
    
    try:
        total_subs = PushSubscription.objects.count()
        logger.info("Total subscriptions in database: %d", total_subs)
        
        if total_subs == 0:
            logger.info("No subscriptions found in database")
            return {"total": 0, "active": 0, "expired": 0, "details": []}
        
        member_subs = PushSubscription.objects.filter(member_id_FK__isnull=False).count()
        officer_subs = PushSubscription.objects.filter(officer_id_FK__isnull=False).count()
        
        logger.info("Member subscriptions: %d", member_subs)
        logger.info("Officer subscriptions: %d", officer_subs)
        
        # Check for recently created subscriptions (last 30 days)
        from django.utils import timezone
        from datetime import timedelta
        thirty_days_ago = timezone.now() - timedelta(days=30)
        recent_subs = PushSubscription.objects.filter(created_at__gte=thirty_days_ago).count()
        
        logger.info("Recent subscriptions (last 30 days): %d", recent_subs)
        
        # Check for old subscriptions (older than 90 days)
        ninety_days_ago = timezone.now() - timedelta(days=90)
        old_subs = PushSubscription.objects.filter(created_at__lt=ninety_days_ago).count()
        
        logger.info("Old subscriptions (older than 90 days): %d", old_subs)
        
        health_report = {
            "total": total_subs,
            "member_subs": member_subs,
            "officer_subs": officer_subs,
            "recent_subs": recent_subs,
            "old_subs": old_subs,
            "vapid_configured": bool(settings.VAPID_PRIVATE_KEY and settings.VAPID_PUBLIC_KEY),
        }
        
        logger.info("Subscription Health Report: %s", health_report)
        logger.info("=== SUBSCRIPTION HEALTH CHECK END ===")
        
        return health_report
        
    except Exception as e:
        logger.error("Error during subscription health check: %s", e)
        logger.info("=== SUBSCRIPTION HEALTH CHECK END (ERROR) ===")
        return {"error": str(e)}


def verify_vapid_configuration():
    """Verify VAPID configuration is properly set up."""
    logger.info("=== VAPID CONFIGURATION VERIFICATION ===")
    
    vapid_config = {
        "private_key_configured": bool(settings.VAPID_PRIVATE_KEY),
        "public_key_configured": bool(settings.VAPID_PUBLIC_KEY),
        "private_key_length": len(settings.VAPID_PRIVATE_KEY) if settings.VAPID_PRIVATE_KEY else 0,
        "public_key_length": len(settings.VAPID_PUBLIC_KEY) if settings.VAPID_PUBLIC_KEY else 0,
    }
    
    logger.info("VAPID Private Key Configured: %s", vapid_config["private_key_configured"])
    logger.info("VAPID Public Key Configured: %s", vapid_config["public_key_configured"])
    
    if settings.VAPID_PRIVATE_KEY:
        logger.info("VAPID Private Key Length: %d characters", vapid_config["private_key_length"])
    if settings.VAPID_PUBLIC_KEY:
        logger.info("VAPID Public Key Length: %d characters", vapid_config["public_key_length"])
    
    # Check if pywebpush is available
    try:
        from pywebpush import webpush
        logger.info("pywebpush library: AVAILABLE")
        vapid_config["pywebpush_available"] = True
    except Exception as exc:
        logger.warning("pywebpush library: NOT AVAILABLE - %s", exc)
        vapid_config["pywebpush_available"] = False
    
    # Overall status
    vapid_config["status"] = "OK" if (
        vapid_config["private_key_configured"] and 
        vapid_config["public_key_configured"] and 
        vapid_config["pywebpush_available"]
    ) else "MISSING_REQUIREMENTS"
    
    logger.info("VAPID Configuration Status: %s", vapid_config["status"])
    logger.info("=== VAPID CONFIGURATION VERIFICATION END ===")
    
    return vapid_config


def notify(
    *,
    recipient_type: str,
    recipient_id: int,
    notification_type: str,
    message: str,
    recipient_name: str = "",
    recipient_contact: str = "",
    category: str | None = None,
    url: str = "/",
    ws_group: str | None = None,
    ws_payload: dict | None = None,
    send_push: bool = True,
    sender_name: str = "",
    sender_role: str = "",
    receipt_number: str = "",
    extra_context: dict = None,
    create_notification: bool = True,
    send_email: bool = True,
) -> None:
    """Persist a notification, send Web Push, and broadcast to a WS group."""
    from core_system.models import Notification, PushSubscription

    logger.info("Creating notification for %s %s: type=%s, message=%s", 
               recipient_type, recipient_id, notification_type, message[:50])

    if create_notification:
        notification = Notification.objects.create(
            recipient_type=recipient_type,
            recipient_id=recipient_id,
            recipient_name=recipient_name,
            recipient_contact=recipient_contact,
            notification_type=notification_type,
            message=message,
            delivery_status="Sent",
            category=category,
            channel=NOTIFICATION_CHANNEL_PUSH,
            sender_name=sender_name,
            sender_role=sender_role,
            receipt_number=receipt_number,
        )
        logger.info("Notification created with ID: %s", notification.notification_id_PK)

    if send_push:
        subs = PushSubscription.objects.none()
        if recipient_type == "member":
            subs = PushSubscription.objects.filter(member_id_FK_id=recipient_id)
        elif recipient_type == "officer":
            subs = PushSubscription.objects.filter(officer_id_FK_id=recipient_id)
        
        logger.info("Attempting to send push notifications to %s %s: found %d subscriptions", 
                   recipient_type, recipient_id, subs.count())
        _send_push_subs(subs, notification_type, message, url)

    # Send email notification using HTML template
    if send_email and recipient_contact and '@' in recipient_contact:
        try:
            logger.info("Sending email notification to %s: %s", recipient_contact, notification_type)
            # Use HTML email service for consistent branding
            from core_system.services.email_service import send_html_email
            
            # Map notification types to email templates
            template_map = {
                "Payment Approved": "emails/monthly_dues_approved.html",
                "Payment Rejected": "emails/finance_item_returned.html",
                "Payment Returned": "emails/finance_item_returned.html",
                "Aid Contribution Required": "emails/aid_bulk_contribution_notice.html",
                "Aid Approved – Not Included in Contribution": "emails/aid_processing_notice.html",
                "Claim Approved": "emails/claim_approved.html",
                "Claim Completed": "emails/claim_completed.html",
                "Aid Released": "emails/aid_released.html",
                "Claim Update": "emails/claim_update.html",
                "Claim Submitted": "emails/claim_submitted.html",
                "Monthly Dues Reminder": "emails/dues_reminder.html",
                "Payment Reminder": "emails/payment_reminder.html",
                "exemption_request": "emails/exemption_request.html",
                "exemption_response": "emails/exemption_response.html",
                "membership_approved": "emails/membership_approved.html",
                "Attendance Completed": "emails/certificate_notification.html",
                "Announcement": "emails/announcement_notification.html",
            }
            
            # Check if there's a template for this notification type
            html_template = template_map.get(notification_type)
            
            if html_template:
                # Use HTML template with full branding
                template_context = {
                    "member_name": recipient_name,
                    "notification_type": notification_type,
                    "message": message,
                    "sender_name": sender_name,
                    "sender_role": sender_role,
                    "receipt_number": receipt_number,
                }
                
                # Merge with provided context if available
                if extra_context:
                    template_context.update(extra_context)
                # Parse month_covered and amount from message if it's a payment approval
                if notification_type == "Payment Approved":
                    import re
                    # Try multiple patterns for month extraction
                    month_match = re.search(r'for (\d{4}-\d{2})', message)
                    if not month_match:
                        month_match = re.search(r'(\d{4}-\d{2})', message)
                    
                    # Try multiple patterns for amount extraction
                    amount_match = re.search(r'₱[\d,]+\.?\d*', message)
                    if not amount_match:
                        amount_match = re.search(r'\([\s₱]*([\d,]+\.?\d*)\)', message)
                    
                    # Check if this is a membership fee payment (no month covered)
                    is_membership_fee = "membership fee" in message.lower()
                    
                    if month_match and not is_membership_fee:
                        from datetime import datetime as dt
                        month_str = month_match.group(1)
                        try:
                            month_date = dt.strptime(month_str, "%Y-%m")
                            template_context["month_covered"] = month_date.strftime("%B %Y")
                        except:
                            template_context["month_covered"] = month_str
                    else:
                        template_context["month_covered"] = "N/A" if is_membership_fee else "N/A"
                    
                    if amount_match:
                        amount_str = amount_match.group(1) if amount_match.lastindex else amount_match.group(0)
                        template_context["amount"] = amount_str.replace('₱', '').replace('(', '').replace(')', '').strip()
                    else:
                        template_context["amount"] = "0.00"
                    
                    template_context["payment_method"] = "Direct Encoding" if "directly" in message.lower() else "Online Banking"
                    template_context["receipt_number"] = receipt_number or "N/A"
                    template_context["approval_date"] = timezone.now().strftime("%B %d, %Y")
                
                # Parse claim-related notification data
                elif notification_type in ["Claim Approved", "Claim Completed", "Aid Released", "Claim Update", "Claim Submitted"]:
                    import re
                    # Extract aid type (Medical Aid or Death Aid)
                    aid_type_match = re.search(r'(Medical Aid|Death Aid)', message)
                    if aid_type_match:
                        template_context["aid_type"] = aid_type_match.group(1)
                    else:
                        template_context["aid_type"] = "Aid"
                    
                    # Extract payout amount for Claim Approved
                    if notification_type == "Claim Approved":
                        amount_match = re.search(r'₱[\d,]+\.?\d*', message)
                        if amount_match:
                            template_context["payout_amount"] = amount_match.group(0).replace('₱', '')
                        else:
                            template_context["payout_amount"] = "0.00"
                        template_context["approval_date"] = timezone.now().strftime("%B %d, %Y")
                    
                    # Set dates for other claim types
                    if notification_type == "Claim Completed":
                        template_context["completion_date"] = timezone.now().strftime("%B %d, %Y")
                    elif notification_type == "Aid Released":
                        template_context["release_date"] = timezone.now().strftime("%B %d, %Y")
                    elif notification_type == "Claim Update":
                        template_context["update_message"] = message
                        template_context["update_date"] = timezone.now().strftime("%B %d, %Y")
                    elif notification_type == "Claim Submitted":
                        template_context["submission_date"] = timezone.now().strftime("%B %d, %Y")
                
                # Parse attendance completion notification data
                elif notification_type == "Attendance Completed":
                    import re
                    # Extract event title from message if not already provided
                    if not template_context.get("event_title"):
                        event_match = re.search(r'event [\'"]([^\'"]+)[\'"]', message)
                        if event_match:
                            template_context["event_title"] = event_match.group(1)
                        else:
                            template_context["event_title"] = "Event"
                    
                    # Check if certificate_number was provided in extra_context (for "Processing" status)
                    if not template_context.get("certificate_number"):
                        template_context["certificate_number"] = "TBD"
                    
                    # Set default values for certificate_notification.html template
                    if not template_context.get("event_venue"):
                        template_context["event_venue"] = "ISU CAUFA Campus"
                    if not template_context.get("has_pdf_attachment"):
                        template_context["has_pdf_attachment"] = False
                    if not template_context.get("dashboard_url"):
                        template_context["dashboard_url"] = "/member/dashboard"
                    
                    # Set default dates if not provided
                    if not template_context.get("event_date"):
                        template_context["event_date"] = timezone.now().strftime("%B %d, %Y")
                    if not template_context.get("issue_date"):
                        template_context["issue_date"] = timezone.now().strftime("%B %d, %Y")
                
                # Parse announcement notification data
                elif notification_type == "Announcement":
                    import re
                    # Extract announcement title from message if not already provided
                    if not template_context.get("announcement_title"):
                        title_match = re.search(r'New announcement: ([^.]+)', message)
                        if title_match:
                            template_context["announcement_title"] = title_match.group(1).strip()
                        else:
                            template_context["announcement_title"] = "New Announcement"
                    
                    # Set default values if not provided
                    if not template_context.get("announcement_category"):
                        template_context["announcement_category"] = "General"
                    if not template_context.get("announcement_description"):
                        template_context["announcement_description"] = message
                    if not template_context.get("posted_date"):
                        template_context["posted_date"] = timezone.now().strftime("%B %d, %Y")
                    if not template_context.get("expiry_date"):
                        template_context["expiry_date"] = None
                
                # Parse monthly dues reminder notification data
                elif notification_type == "Monthly Dues Reminder":
                    import re
                    # Extract month covered
                    month_match = re.search(r'for\s+([A-Za-z]+\s+\d{4})', message, re.IGNORECASE)
                    if not month_match:
                        month_match = re.search(r'([A-Za-z]+\s+\d{4})', message)
                    if month_match:
                        template_context["month_label"] = month_match.group(1)
                    else:
                        template_context["month_label"] = "N/A"
                    template_context["days_overdue"] = "0"  # Default, can be enhanced with regex
                    template_context["message"] = message
                
                # Parse payment reminder notification data
                elif notification_type == "Payment Reminder":
                    import re
                    # Extract aid type and target month
                    aid_type_match = re.search(r'(Medical Aid|Death Aid)', message)
                    if aid_type_match:
                        template_context["payment_type"] = f"{aid_type_match.group(1)} Contribution"
                    else:
                        template_context["payment_type"] = "Aid Contribution"
                    
                    # Extract amount
                    amount_match = re.search(r'₱[\d,]+\.?\d*', message)
                    if amount_match:
                        template_context["amount"] = amount_match.group(0).replace('₱', '')
                    else:
                        template_context["amount"] = "0.00"
                    
                    # Extract target month
                    month_match = re.search(r'target month:?\s*([A-Za-z]+\s+\d{4})', message, re.IGNORECASE)
                    if not month_match:
                        month_match = re.search(r'([A-Za-z]+\s+\d{4})', message)
                    if month_match:
                        template_context["target_month"] = month_match.group(1)
                    else:
                        template_context["target_month"] = "N/A"
                
                # Parse exemption request notification data
                elif notification_type == "exemption_request":
                    import re
                    # Extract month covered
                    month_match = re.search(r'for\s+([A-Za-z]+\s+\d{4})', message, re.IGNORECASE)
                    if not month_match:
                        month_match = re.search(r'([A-Za-z]+\s+\d{4})', message)
                    if month_match:
                        template_context["month_covered"] = month_match.group(1)
                    else:
                        template_context["month_covered"] = "N/A"
                    template_context["request_date"] = timezone.now().strftime("%B %d, %Y")
                
                # Parse exemption response notification data
                elif notification_type == "exemption_response":
                    import re
                    # Extract month covered
                    month_match = re.search(r'for\s+([A-Za-z]+\s+\d{4})', message, re.IGNORECASE)
                    if not month_match:
                        month_match = re.search(r'([A-Za-z]+\s+\d{4})', message)
                    if month_match:
                        template_context["month_covered"] = month_match.group(1)
                    else:
                        template_context["month_covered"] = "N/A"
                    
                    # Extract status (Approved/Rejected)
                    if "approved" in message.lower():
                        template_context["status"] = "Approved"
                    elif "rejected" in message.lower() or "denied" in message.lower():
                        template_context["status"] = "Rejected"
                    else:
                        template_context["status"] = "Reviewed"
                    
                    template_context["response_date"] = timezone.now().strftime("%B %d, %Y")
                    template_context["remarks"] = message  # Full message as remarks
                
                # Parse membership approved notification data
                elif notification_type == "membership_approved":
                    template_context["approval_date"] = timezone.now().strftime("%B %d, %Y")
                
                send_html_email(
                    subject=f"ISU CAUFA: {notification_type}",
                    recipient_list=[recipient_contact],
                    html_template=html_template,
                    context=template_context,
                )
            else:
                # Fallback to plain text for notification types without templates
                send_mail(
                    subject=f"ISU CAUFA: {notification_type}",
                    message=message,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[recipient_contact],
                    fail_silently=True,
                )
            logger.info("Email sent successfully to %s for notification: %s", recipient_contact, notification_type)
        except Exception as e:
            logger.error("Failed to send email to %s: %s", recipient_contact, e)

    if ws_group:
        _broadcast_ws(
            ws_group,
            ws_payload
            or {
                "type": "notification_created",
                "notification": {
                    "type": notification_type,
                    "message": message,
                    "category": category or "general",
                },
            },
        )


def notify_member(
    member,
    *,
    notification_type: str,
    message: str,
    category: str | None = None,
    url: str = "/member/",
    send_push: bool = True,
    sender_name: str = "",
    sender_role: str = "",
    receipt_number: str = "",
    extra_context: dict = None,
    create_notification: bool = True,
    send_email: bool = True,
) -> None:
    """Notify a Member instance (in-app + phone push + live bell dot + email)."""
    if member is None:
        logger.warning("notify_member called with None member")
        return
    notify(
        recipient_type="member",
        recipient_id=member.member_id_PK,
        notification_type=notification_type,
        message=message,
        recipient_name=member.full_name or "",
        recipient_contact=member.email or member.contact_number or "",
        category=category,
        url=url,
        ws_group=f"member_{member.member_id_PK}",
        ws_payload={
            "type": "notification_created",
            "notification": {
                "type": notification_type,
                "message": message,
                "category": category or "general",
                "sender_name": sender_name,
                "sender_role": sender_role,
                "receipt_number": receipt_number,
            },
        },
        send_push=send_push,
        sender_name=sender_name,
        sender_role=sender_role,
        receipt_number=receipt_number,
        extra_context=extra_context,
        create_notification=create_notification,
        send_email=send_email,
    )


def notify_officer(
    officer,
    *,
    notification_type: str,
    message: str,
    category: str | None = None,
    url: str = "/",
    send_push: bool = True,
) -> None:
    """Notify an OfficerUser instance (in-app + phone push)."""
    if officer is None:
        return
    notify(
        recipient_type="officer",
        recipient_id=officer.user_id_PK,
        notification_type=notification_type,
        message=message,
        recipient_name=officer.full_name or "",
        recipient_contact=getattr(officer, "email", "") or "",
        category=category,
        url=url,
        send_push=send_push,
    )
