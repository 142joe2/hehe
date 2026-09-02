from __future__ import annotations

from datetime import date

from django.utils import timezone

from core_system.constants.status_constants import Status
from core_system.models import (
    AidTrackingPost,
    Contribution,
    Department,
    Member,
    MembershipFee,
    MonthlyDues,
    SystemSetting,
)


def _get_grace_period_days(default: int = 15) -> int:
    try:
        setting = SystemSetting.objects.get(setting_key="grace_period_days")
        return int(setting.setting_value)
    except (SystemSetting.DoesNotExist, ValueError, TypeError):
        return default


def active_members_qs():
    return Member.objects.exclude(membership_status__iexact="retired")


def _get_paid_members_for_period(year: int, month: int) -> set[int]:
    month_str = f"{year}-{month:02d}"
    dues_ids = set(
        MonthlyDues.objects.filter(
            month_covered=month_str,
            payment_status__in=Status.ALL_AUDITOR_VERIFIED,
        ).values_list("member_id_FK", flat=True)
    )
    fee_ids = set(
        MembershipFee.objects.filter(
            payment_status__in=Status.ALL_AUDITOR_VERIFIED,
        ).values_list("member_id_FK", flat=True)
    )
    return dues_ids | fee_ids


def dues_compliance_summary(year: int | None = None, month: int | None = None):
    today = timezone.localdate()
    year = year or today.year
    month = month or today.month

    paid_member_ids = _get_paid_members_for_period(year, month)
    departments = Department.objects.filter(is_active=True).order_by("name")
    results = []

    for dept in departments:
        dept_members = active_members_qs().filter(
            department_id_FK=dept,
        )
        total = dept_members.count()
        if total == 0:
            continue
        paid_count = dept_members.filter(
            member_id_PK__in=paid_member_ids,
        ).count()
        unpaid_count = total - paid_count

        results.append({
            "department_id": dept.department_id_PK,
            "department_name": dept.name,
            "total_members": total,
            "paid_count": paid_count,
            "unpaid_count": unpaid_count,
            "percentage": round(paid_count / total * 100, 1) if total else 0.0,
        })

    return results


def member_dues_status(member, year: int | None = None, month: int | None = None):
    today = timezone.localdate()
    year = year or today.year
    month = month or today.month

    if member.membership_status and member.membership_status.lower() == "retired":
        return "exempt"

    month_str = f"{year}-{month:02d}"
    has_dues = MonthlyDues.objects.filter(
        member_id_FK=member,
        month_covered=month_str,
        payment_status__in=Status.ALL_AUDITOR_VERIFIED,
    ).exists()
    has_fee = MembershipFee.objects.filter(
        member_id_FK=member,
        payment_status__in=Status.ALL_AUDITOR_VERIFIED,
    ).exists()

    if has_dues or has_fee:
        return "paid"

    due_date = date(year, month, 1)
    if today > due_date:
        return "overdue"
    return "unpaid"


def contribution_compliance_summary(post_id: int):
    try:
        post = AidTrackingPost.objects.get(post_id_PK=post_id)
    except AidTrackingPost.DoesNotExist:
        return []

    departments = Department.objects.filter(is_active=True).order_by("name")
    contribs = Contribution.objects.filter(aid_tracking_post_id_FK=post).select_related(
        "member_id_FK__department_id_FK"
    )
    contrib_by_dept: dict[int, dict] = {}

    for c in contribs:
        dept = c.member_id_FK.department_id_FK
        if not dept:
            continue
        if dept.department_id_PK not in contrib_by_dept:
            contrib_by_dept[dept.department_id_PK] = {
                "department_id": dept.department_id_PK,
                "department_name": dept.name,
                "total_members": 0,
                "paid_count": 0,
                "unpaid_count": 0,
                "skipped_count": 0,
            }
        row = contrib_by_dept[dept.department_id_PK]
        row["total_members"] += 1
        if c.status in ("PAID", "RECORDED", "PENDING_VERIFICATION"):
            row["paid_count"] += 1
        elif c.status == "SKIPPED":
            row["skipped_count"] += 1
        else:
            row["unpaid_count"] += 1

    for row in contrib_by_dept.values():
        total = row["total_members"]
        row["percentage"] = round(row["paid_count"] / total * 100, 1) if total else 0.0

    return list(contrib_by_dept.values())


def member_contribution_status(member, post_id: int) -> str:
    try:
        contrib = Contribution.objects.get(
            aid_tracking_post_id_FK=post_id,
            member_id_FK=member,
        )
        return contrib.status.lower()
    except Contribution.DoesNotExist:
        return "unpaid"


def dues_overdue_bucket(member, year: int | None = None, month: int | None = None) -> str | None:
    today = timezone.localdate()
    year = year or today.year
    month = month or today.month

    if member.membership_status and member.membership_status.lower() == "retired":
        return None

    status = member_dues_status(member, year, month)
    if status == "paid" or status == "exempt":
        return None

    due_date = date(year, month, 1)
    if today <= due_date:
        return None

    days = (today - due_date).days

    if days <= 1:
        return "1d"
    elif days <= 3:
        return "3d"
    elif days <= 5:
        return "5d"
    elif days <= 7:
        return "7d"
    else:
        return "15d+"
