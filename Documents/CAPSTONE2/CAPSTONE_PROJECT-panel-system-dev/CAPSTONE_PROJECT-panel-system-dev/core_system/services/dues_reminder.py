"""Monthly dues reminder engine.

Reads reminder configuration from SystemSetting and sends dashboard
notifications (and emails) to members whose current-month dues are
overdue at each configured interval.
"""
from __future__ import annotations

import json
import logging
from datetime import date

from django.db.models import Q
from django.utils import timezone

from core_system.models import Member, MonthlyDues, Notification, SystemSetting
from core_system.services.compliance import dues_overdue_bucket
from core_system.services.email_service import send_html_email

logger = logging.getLogger(__name__)

DEFAULT_INTERVALS = [1, 3, 5, 7, 15]
DEFAULT_CHANNELS = {"1": "email", "3": "email", "5": "sms", "7": "sms", "15": "email+sms"}
DEFAULT_MESSAGE = (
    "Your monthly dues for {month_label} are overdue. "
    "Please settle your payment as soon as possible."
)
NOTIFICATION_TYPE = "Monthly Dues Reminder"


def _load_setting(key: str, default):
    try:
        setting = SystemSetting.objects.get(setting_key=key)
        return json.loads(setting.setting_value)
    except (SystemSetting.DoesNotExist, json.JSONDecodeError, TypeError, ValueError):
        return default


def _month_label(year: int, month: int) -> str:
    return date(year, month, 1).strftime("%B %Y")


def run_dues_reminders(dry_run: bool = False) -> dict:
    """Evaluate overdue members and issue reminders at each interval.

    Returns a summary dict for reporting.
    """
    today = timezone.localdate()
    intervals = _load_setting("reminder_intervals", DEFAULT_INTERVALS)
    channels = _load_setting("reminder_channels", DEFAULT_CHANNELS)
    templates = _load_setting("reminder_message_templates", {})
    if not isinstance(intervals, list):
        intervals = DEFAULT_INTERVALS
    if not isinstance(channels, dict):
        channels = DEFAULT_CHANNELS
    if not isinstance(templates, dict):
        templates = {}

    month_label = _month_label(today.year, today.month)
    month_start = date(today.year, today.month, 1)

    # Reminders already sent this month for each (member, interval) bucket.
    sent_keys = set(
        Notification.objects.filter(
            recipient_type="member",
            notification_type=NOTIFICATION_TYPE,
            sent_at__year=today.year,
            sent_at__month=today.month,
        ).values_list("recipient_id", "overdue_bucket")
    )

    members = Member.objects.filter(
        ~Q(membership_status__iexact="Retired")
    ).order_by("member_id_PK")

    sent_count = 0
    for member in members:
        days_overdue = (today - month_start).days
        bucket = dues_overdue_bucket(member, today.year, today.month)
        if bucket is None:
            continue

        for interval in sorted(int(i) for i in intervals if str(i).isdigit()):
            if days_overdue < interval:
                continue
            bucket_key = f"{interval}d"
            if (member.member_id_PK, bucket_key) in sent_keys:
                continue

            template = templates.get(str(interval)) or DEFAULT_MESSAGE
            message = template.format(
                member_name=member.full_name,
                month=month_label,
                month_label=month_label,
                days_overdue=days_overdue,
                interval=interval,
            )
            channel = channels.get(str(interval), "email")

            if dry_run:
                sent_keys.add((member.member_id_PK, bucket_key))
                sent_count += 1
                logger.info(
                    "[DRY RUN] Reminder %s (%dd) for %s (ID=%s, channel=%s)",
                    month_label,
                    interval,
                    member.full_name,
                    member.member_id_PK,
                    channel,
                )
                continue

            Notification.objects.create(
                recipient_type="member",
                recipient_id=member.member_id_PK,
                recipient_name=member.full_name,
                recipient_contact=member.email or "",
                notification_type=NOTIFICATION_TYPE,
                message=message,
                category="dues",
                delivery_status="sent",
                overdue_bucket=bucket_key,
                channel=channel,
                sent_at=timezone.now(),
                sender_name="ISU CAUFA",
                sender_role="System",
            )
            sent_keys.add((member.member_id_PK, bucket_key))
            sent_count += 1

            if "email" in channel and member.email:
                try:
                    send_html_email(
                        subject=f"Monthly Dues Reminder - {month_label}",
                        recipient_list=[member.email],
                        html_template="emails/dues_reminder.html",
                        context={
                            "member_name": member.full_name,
                            "month_label": month_label,
                            "days_overdue": days_overdue,
                            "interval": interval,
                            "message": message,
                        },
                    )
                except Exception as exc:  # noqa: BLE001
                    logger.warning("Failed to send dues reminder email to %s: %s", member.full_name, exc)

    return {
        "dry_run": dry_run,
        "year": today.year,
        "month": today.month,
        "month_label": month_label,
        "reminders_sent": sent_count,
    }
