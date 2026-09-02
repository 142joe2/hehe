# =========================================================================
# MIGRATION STATUS — All views moved to dedicated files:
#   - President views   → president_views.py
#   - Treasurer views   → treasurer_views.py
#   - Auditor views     → auditor_views.py
# This file now only re-exports logout_view + shared fund ledger views.
# =========================================================================
from __future__ import annotations

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from django.db.models import Q, Sum, Prefetch
from django.http import HttpRequest, JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone
from django.views.decorators.http import require_GET

from django.shortcuts import render
from core_system.auth_utils import sha256_hex
from core_system.auth_views import _workspace_redirect
from core_system.constants.policy_constants import get_membership_fee_amount, get_monthly_dues_amount
from core_system.constants.status_constants import Status
from core_system.guards import require_officer_session, require_role
from core_system.models import (
    Claimant,
    Contribution,
    DeathAid,
    FundTransaction,
    MedicalAid,
    Member,
    MembershipFee,
    MonthlyDues,
    Notification,
    OfficerUser,
    PayrollBatch,
    PayrollDeduction,
    SystemSetting,
)
from core_system.logout_view import logout_view

MEMBERSHIP_FEE_SUBMITTED_STATUSES = {"Paid", "Full Payment", "Partial", "Pending"}

logout_view = logout_view


def _ensure_default_superadmin_accounts():
    superadmin_defaults = {
        "full_name": "Superadmin Admin Von",
        "password_hash": sha256_hex("adminvon123"),
        "role": "Superadmin",
        "account_status": "Active",
        "mfa_enabled": False,
        "mfa_secret": None,
        "email": "adminvon@caufa.local",
    }

    president_defaults = {
        "full_name": "President Account",
        "password_hash": sha256_hex("adminvon123"),
        "role": "President",
        "account_status": "Active",
        "mfa_enabled": False,
        "mfa_secret": None,
        "email": "president@caufa.local",
    }

    system_backfill_defaults = {
        "full_name": "System Backfill",
        "password_hash": sha256_hex("adminvon123"),
        "role": "System",
        "account_status": "Inactive",
        "mfa_enabled": False,
        "mfa_secret": None,
        "email": "",
    }

    def _resolve(role, username, defaults):
        # Prefer the canonical username account.
        account = OfficerUser.objects.filter(username=username).first()
        if account is not None:
            return account
        # Fall back to any existing account of the same role so that renaming
        # an account's username never spawns a duplicate default on the next load.
        account = OfficerUser.objects.filter(role__iexact=role).order_by("user_id_PK").first()
        if account is not None:
            return account
        return OfficerUser.objects.create(**defaults)

    superadmin = _resolve("Superadmin", "adminvon", superadmin_defaults)
    president = _resolve("President", "president", president_defaults)
    system_backfill = _resolve("System", "system_backfill", system_backfill_defaults)

    return superadmin, president, system_backfill


def _build_superadmin_dashboard_context(superadmin: OfficerUser, president: OfficerUser, system_backfill: OfficerUser, form_feedback: dict | None = None, threshold_feedback: dict | None = None):
    # Get safety threshold settings
    safety_threshold = SystemSetting.objects.filter(setting_key="safety_threshold_amount").first()
    safety_threshold_enabled = SystemSetting.objects.filter(setting_key="safety_threshold_enabled").first()

    def _account_payload(account: OfficerUser):
        return {
            "full_name": account.full_name,
            "username": account.username,
            "role": account.role,
            "status": account.account_status,
            "email": account.email or "",
        }

    return {
        "superadmin_account": _account_payload(superadmin),
        "president_account": _account_payload(president),
        "system_backfill_account": _account_payload(system_backfill),
        "superadmin_id": superadmin.pk,
        "president_id": president.pk,
        "system_backfill_id": system_backfill.pk,
        "president_exists": president.pk is not None,
        "president_dashboard_url": "/president/",
        "form_feedback": form_feedback,
        "threshold_feedback": threshold_feedback,
        "safety_threshold": safety_threshold.setting_value if safety_threshold else "0.00",
        "safety_threshold_enabled": safety_threshold_enabled.setting_value if safety_threshold_enabled else "false",
    }


def _handle_superadmin_account_form(request: HttpRequest, account: OfficerUser, label: str) -> tuple[OfficerUser, dict]:
    full_name = request.POST.get("account_full_name", "").strip()
    username = request.POST.get("account_username", "").strip()
    password = request.POST.get("account_password", "").strip()
    email = request.POST.get("account_email", "").strip()
    account_status = request.POST.get("account_status", "Active").strip() or "Active"

    feedback = {"ok": False, "message": "", "level": "error"}

    if not full_name:
        feedback["message"] = f"{label} full name is required."
        return account, feedback
    if not username:
        feedback["message"] = f"{label} username is required."
        return account, feedback

    existing_username = OfficerUser.objects.filter(username=username).exclude(pk=account.pk).first()
    if existing_username is not None:
        feedback["message"] = "That username is already taken. Choose a different one."
        return account, feedback

    update_fields = ["full_name", "username", "email", "account_status", "updated_at"]

    account.full_name = full_name
    account.username = username
    account.email = email or None
    account.account_status = account_status
    account.updated_at = timezone.now()
    if password:
        account.password_hash = sha256_hex(password)
        update_fields.append("password_hash")

    account.save(update_fields=update_fields)

    feedback["ok"] = True
    feedback["message"] = f"{label} account has been saved successfully."
    feedback["level"] = "success"
    return account, feedback


def _handle_superadmin_safety_threshold_form(request: HttpRequest) -> dict:
    form_type = request.POST.get("form_type", "").strip()
    threshold_amount = request.POST.get("safety_threshold_amount", "0").strip()
    threshold_enabled = request.POST.get("safety_threshold_enabled", "false").strip()

    feedback = {"ok": False, "message": "", "level": "error"}

    if form_type != "safety_threshold":
        feedback["message"] = "Invalid form type."
        return feedback

    try:
        threshold_float = float(threshold_amount)
        if threshold_float < 0:
            feedback["message"] = "Safety threshold amount must be non-negative."
            return feedback
    except ValueError:
        feedback["message"] = "Invalid safety threshold amount."
        return feedback

    # Update or create safety threshold setting
    SystemSetting.objects.update_or_create(
        setting_key="safety_threshold_amount",
        defaults={"setting_value": str(threshold_float)}
    )
    SystemSetting.objects.update_or_create(
        setting_key="safety_threshold_enabled",
        defaults={"setting_value": threshold_enabled}
    )

    feedback["ok"] = True
    feedback["message"] = "Safety threshold settings have been saved successfully."
    feedback["level"] = "success"
    return feedback


def _handle_superadmin_toggle_account_status(request: HttpRequest, account: OfficerUser, label: str) -> tuple[OfficerUser, dict]:
    feedback = {"ok": False, "message": "", "level": "error"}

    new_status = "Inactive" if (account.account_status or "").lower() == "active" else "Active"
    account.account_status = new_status
    account.updated_at = timezone.now()
    account.save(update_fields=["account_status", "updated_at"])

    feedback["ok"] = True
    feedback["message"] = f"{label} account has been {new_status.lower()}d successfully."
    feedback["level"] = "success"
    return account, feedback


def superadmin_dashboard(request: HttpRequest):
    guard = require_role(request, role="Superadmin")
    if guard is not None:
        return guard

    superadmin, president, system_backfill = _ensure_default_superadmin_accounts()
    form_feedback = None
    threshold_feedback = None

    if request.method == "POST":
        form_type = request.POST.get("form_type", "").strip()
        account_key = request.POST.get("account_key", "").strip()
        label_by_key = {
            "superadmin": "Superadmin",
            "president": "President",
            "system_backfill": "System Backfill",
        }
        account_by_key = {
            "superadmin": superadmin,
            "president": president,
            "system_backfill": system_backfill,
        }

        if form_type == "safety_threshold":
            threshold_feedback = _handle_superadmin_safety_threshold_form(request)
        elif form_type == "toggle_account_status" and account_key in account_by_key:
            updated, form_feedback = _handle_superadmin_toggle_account_status(request, account_by_key[account_key], label_by_key[account_key])
            account_by_key[account_key] = updated
        elif form_type == "account_update" and account_key in account_by_key:
            updated, form_feedback = _handle_superadmin_account_form(request, account_by_key[account_key], label_by_key[account_key])
            account_by_key[account_key] = updated
        else:
            form_feedback = {"ok": False, "message": "Unknown form submission.", "level": "error"}

        superadmin, president, system_backfill = (
            account_by_key["superadmin"],
            account_by_key["president"],
            account_by_key["system_backfill"],
        )

    context = _build_superadmin_dashboard_context(superadmin, president, system_backfill, form_feedback, threshold_feedback)
    return render(request, "website/Superadmin/superadmin_dashboard.html", context)


@require_GET
def fund_ledger_list(request: HttpRequest):
    """Return paginated FundTransaction entries — visible to all roles."""
    guard = require_officer_session(request)
    if guard is not None:
        return guard

    page = int(request.GET.get("page", 1))
    per_page = int(request.GET.get("per_page", 50))
    direction = request.GET.get("direction", "")
    date_from = request.GET.get("date_from", "")
    date_to = request.GET.get("date_to", "")

    qs = FundTransaction.objects.select_related("recorded_by_user_id_FK").all()

    if direction in ("inflow", "outflow"):
        qs = qs.filter(direction=direction)
    if date_from:
        qs = qs.filter(recorded_at__gte=date_from)
    if date_to:
        qs = qs.filter(recorded_at__lte=date_to)

    total = qs.count()
    qs = qs.order_by("-recorded_at")

    offset = (page - 1) * per_page
    entries = qs[offset:offset + per_page]

    totals = FundTransaction.objects.aggregate(
        total_in=Sum("amount", filter=Q(direction="inflow")),
        total_out=Sum("amount", filter=Q(direction="outflow")),
    )
    total_in = float(totals["total_in"] or 0)
    total_out = float(totals["total_out"] or 0)
    balance = total_in - total_out

    items = []
    for e in entries:
        items.append({
            "id": e.transaction_id_PK,
            "direction": e.direction,
            "amount": float(e.amount),
            "source_type": e.source_type,
            "description": e.description,
            "reference_number": e.reference_number or "",
            "recorded_by": e.recorded_by_user_id_FK.full_name if e.recorded_by_user_id_FK else "",
            "recorded_at": e.recorded_at.isoformat() if e.recorded_at else "",
        })

    return JsonResponse({
        "ok": True,
        "items": items,
        "total": total,
        "page": page,
        "per_page": per_page,
        "total_pages": (total + per_page - 1) // per_page if per_page else 1,
        "summary": {
            "total_in": total_in,
            "total_out": total_out,
            "balance": balance,
        },
    })


@require_GET
def fund_balance_summary(request: HttpRequest):
    """Return current fund balance + safety threshold — visible to all roles."""
    guard = require_officer_session(request)
    if guard is not None:
        return guard

    totals = FundTransaction.objects.aggregate(
        total_in=Sum("amount", filter=Q(direction="inflow")),
        total_out=Sum("amount", filter=Q(direction="outflow")),
    )
    balance = float(totals["total_in"] or 0) - float(totals["total_out"] or 0)

    threshold, _ = SystemSetting.objects.get_or_create(
        setting_key="safety_threshold",
        defaults={"setting_value": "20000"},
    )
    safety_threshold = float(threshold.setting_value)

    # Monthly totals
    now = timezone.now()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    month_in = FundTransaction.objects.filter(
        direction="inflow", recorded_at__gte=month_start
    ).aggregate(total=Sum("amount"))["total"] or 0
    month_out = FundTransaction.objects.filter(
        direction="outflow", recorded_at__gte=month_start
    ).aggregate(total=Sum("amount"))["total"] or 0

    return JsonResponse({
        "ok": True,
        "balance": balance,
        "safety_threshold": safety_threshold,
        "available": balance - safety_threshold,
        "month_in": float(month_in),
        "month_out": float(month_out),
    })


@require_GET
def member_deductions_list(request: HttpRequest, member_id: int | None = None):
    """Return deduction history for a specific member — visible to all roles."""
    guard = require_officer_session(request)
    if guard is not None:
        return guard

    if member_id is None:
        member_id = request.GET.get("member_id", "")
        if not member_id:
            return JsonResponse({"ok": False, "error": "member_id required."}, status=400)

    try:
        member_id = int(member_id)
    except (TypeError, ValueError):
        return JsonResponse({"ok": False, "error": "member_id must be an integer."}, status=400)

    officer_role = (request.session.get("role") or "").strip().lower()
    is_member_role = officer_role in ("member", "member_user")
    if is_member_role:
        # Members may only read their own deduction history (IDOR guard).
        officer_id = request.session.get("officer_id")
        own_member = None
        if officer_id:
            own_member = Member.objects.filter(
                officer_user_id_FK=officer_id,
            ).first()
        if not own_member or own_member.member_id_PK != member_id:
            return JsonResponse({"ok": False, "error": "Forbidden: you can only view your own deductions."}, status=403)
        member = own_member
    else:
        member = get_object_or_404(Member, pk=member_id)

    deductions = PayrollDeduction.objects.filter(
        member_id_FK=member,
        batch_id_FK__status="Approved",
    ).select_related("batch_id_FK", "aid_tracking_post_id_FK").order_by("-batch_id_FK__created_at")

    items = []
    for d in deductions:
        batch = d.batch_id_FK
        aid_ref = ""
        if d.aid_tracking_post_id_FK:
            post = d.aid_tracking_post_id_FK
            aid_ref = f"{post.aid_type}#{post.source_id}" if post.source_id else post.aid_type
        items.append({
            "date": batch.president_approved_at.isoformat() if batch.president_approved_at else "",
            "payroll_period": batch.payroll_period,
            "category": d.category,
            "amount": float(d.amount),
            "fund_impact": d.fund_impact,
            "aid_reference": aid_ref,
            "month_covered": d.month_covered or "",
            "batch_id": batch.batch_id_PK,
            "description": _build_member_deduction_desc(d, batch),
        })

    total_deducted = sum(i["amount"] for i in items)

    return JsonResponse({
        "ok": True,
        "member_id": member.member_id_PK,
        "member_name": member.full_name,
        "deductions": items,
        "total_deducted": total_deducted,
        "count": len(items),
    })


def _build_member_deduction_desc(deduction: PayrollDeduction, batch: PayrollBatch) -> str:
    label = dict(PayrollDeduction.CATEGORY_CHOICES).get(deduction.category, deduction.category)
    period = f" ({deduction.month_covered})" if deduction.month_covered else ""
    return f"{label}{period} — {batch.payroll_period}"


@require_GET
def member_onboarding(request: HttpRequest):
    """Serve the member onboarding wizard directly (after first-login password change)."""
    guard = require_officer_session(request)
    if guard is not None:
        return guard

    officer_id = request.session.get("officer_id")
    if not officer_id:
        return redirect("login")

    officer = OfficerUser.objects.get(user_id_PK=officer_id)
    if officer.role != "Member":
        return redirect(_workspace_redirect(officer.role))

    member = Member.objects.filter(officer_user_id_FK=officer).first()
    if not member:
        return redirect(_workspace_redirect(officer.role))

    if member.setup_complete:
        return redirect("/member/")

    return render(request, "website/Member/member_onboarding.html", {
        "member_id": member.member_id_PK,
        "full_name": member.full_name,
        "member_type": member.member_type or "Member",
        "position": member.position or "Member",
        "department": member.department or "",
        "has_pin": bool(member.pin_code),
    })


@require_GET
def member_dashboard(request: HttpRequest):
    """Member dashboard page - visible when Member role logs in."""
    guard = require_officer_session(request)
    if guard is not None:
        return guard

    officer_id = request.session.get("officer_id")
    officer_full_name = ""
    officer_email = ""
    member_data = None
    member = None

    if officer_id:
        try:
            officer = OfficerUser.objects.get(user_id_PK=officer_id)
            officer_full_name = officer.full_name or ""
            officer_email = officer.email or ""
            member = Member.objects.filter(officer_user_id_FK=officer).first()
            if member and not member.setup_complete:
                return render(request, "website/Member/member_onboarding.html", {
                    "member_id": member.member_id_PK,
                    "full_name": member.full_name,
                    "member_type": member.member_type or "Member",
                    "position": member.position or "Member",
                    "department": member.department or "",
                    "has_pin": bool(member.pin_code),
                })
            if member:
                member_data = {
                    "member_id": member.member_id_PK,
                    "full_name": member.full_name,
                    "employee_id": member.employee_id or "",
                    "email": member.email or "",
                    "contact_number": member.contact_number or "",
                    "department": member.department or "",
                    "position": member.position or "",
                    "employment_status": member.employment_status,
                    "membership_status": member.membership_status,
                    "member_type": member.member_type,
                    "date_joined": member.date_joined.isoformat() if member.date_joined else "",
                    "profile_picture": member.profile_picture.url if member.profile_picture else "",
                    "has_pin": bool(member.pin_code),
                    "qr_code": member.qr_code.url if member.qr_code else "",
                    "emergency_contact": member.emergency_contact or "",
                    "emergency_number": member.emergency_number or "",
                }
        except OfficerUser.DoesNotExist:
            pass
    
    # --- Real data queries ---

    # Membership Fee status
    membership_fee_status = "Unpaid"
    membership_fee_amount = 0
    membership_fee_paid = False
    membership_fee_submitted = False
    membership_fee_reference = ""
    membership_fee_payment_date = ""
    membership_fee_method = ""
    if member:
        fee = MembershipFee.objects.filter(member_id_FK=member).order_by("-payment_date").first()
        if fee:
            membership_fee_status = fee.payment_status
            membership_fee_amount = float(fee.amount)
            membership_fee_paid = fee.payment_status in ("Paid", "Full Payment")
            membership_fee_submitted = fee.payment_status in MEMBERSHIP_FEE_SUBMITTED_STATUSES
            membership_fee_reference = fee.receipt_number or fee.deposit_reference or ""
            membership_fee_payment_date = fee.payment_date.strftime("%b %d, %Y") if fee.payment_date else ""
            membership_fee_method = fee.payment_method or ""
    if membership_fee_amount == 0:
        membership_fee_amount = get_membership_fee_amount()

    monthly_dues_amount = get_monthly_dues_amount()

    # Monthly Dues
    total_dues_paid = 0
    total_dues_pending = 0
    total_dues_unpaid = 0
    outstanding_balance = 0
    dues_records = []
    if member:
        all_dues = MonthlyDues.objects.filter(member_id_FK=member).order_by("-month_covered")
        total_dues_paid = float(all_dues.filter(payment_status__in=Status.ALL_AUDITOR_VERIFIED).aggregate(t=Sum("amount"))["t"] or 0)
        total_dues_pending = float(all_dues.filter(payment_status="Pending").aggregate(t=Sum("amount"))["t"] or 0)
        total_dues_unpaid = float(all_dues.filter(payment_status="Unpaid").aggregate(t=Sum("amount"))["t"] or 0)
        covered = set(
            all_dues.filter(
                payment_status__in=["Pending", "Paid", "Full Payment"],
            ).values_list("month_covered", flat=True)
        )
        joined = member.date_joined or (timezone.now().date() - timedelta(days=365))
        unpaid_count = 0
        year, month = joined.year, joined.month + 1
        if month > 12:
            year += 1
            month = 1
        today = timezone.now().date()
        while (year < today.year) or (year == today.year and month <= today.month):
            if f"{year}-{month:02d}" not in covered:
                unpaid_count += 1
            month += 1
            if month > 12:
                month = 1
                year += 1
        outstanding_balance = round(float(get_monthly_dues_amount()) * unpaid_count, 2)
        for d in all_dues:
            dues_records.append({
                "dues_id": d.dues_id_PK,
                "month_covered": d.month_covered,
                "amount": float(d.amount),
                "payment_status": d.payment_status,
                "payment_method": d.payment_method,
                "payment_date": d.payment_date.isoformat() if d.payment_date else "",
            })

    # Contributions
    total_contributions = 0
    contribution_records = []
    if member:
        medical_claim_ids = MedicalAid.objects.filter(member_id_FK=member).values_list("medical_aid_id_PK", flat=True)
        death_claim_ids = DeathAid.objects.filter(member_id_FK=member).values_list("death_aid_id_PK", flat=True)
        contribs = Contribution.objects.filter(member_id_FK=member).exclude(
            Q(aid_tracking_post_id_FK__source_type="medical_aid", aid_tracking_post_id_FK__source_id__in=medical_claim_ids)
            | Q(aid_tracking_post_id_FK__source_type="death_aid", aid_tracking_post_id_FK__source_id__in=death_claim_ids)
        ).select_related("aid_tracking_post_id_FK").order_by("-aid_tracking_post_id_FK__created_at")
        total_contributions = float(contribs.aggregate(t=Sum("paid_amount"))["t"] or 0)
        for c in contribs:
            post = c.aid_tracking_post_id_FK
            contribution_records.append({
                "contribution_id": c.contribution_id_PK,
                "aid_type": post.aid_type if post else "",
                "target_month": post.target_month if post else "",
                "expected_amount": float(c.expected_amount),
                "paid_amount": float(c.paid_amount),
                "payment_date": c.payment_date.isoformat() if c.payment_date else "",
                "status": c.status,
            })

    # Claims and Notifications
    claim_items = []
    medical_aid_records = []
    death_aid_records = []
    notifications = []
    medical_aid_count = 0
    death_aid_count = 0
    medical_aid_pending = 0
    medical_aid_approved = 0
    medical_aid_released = 0
    death_aid_pending = 0
    death_aid_approved = 0
    death_aid_released = 0

    if member:
        medical_aids = MedicalAid.objects.filter(member_id_FK=member).order_by("-request_date")
        for ma in medical_aids:
            record = {
                "claim_id": ma.medical_aid_id_PK,
                "claim_type": "Medical Aid",
                "status": ma.status,
                "description": f"{ma.hospital_name or 'Medical'} - ₱{ma.requested_amount or 0}",
                "date": ma.request_date.isoformat() if ma.request_date else "",
                "is_medical": True,
            }
            medical_aid_records.append(record)
            claim_items.append(record)
            medical_aid_count += 1
            if ma.status == 'Pending':
                medical_aid_pending += 1
            elif ma.status == 'Approved':
                medical_aid_approved += 1
            elif ma.status == 'Released':
                medical_aid_released += 1

        death_aids = DeathAid.objects.filter(member_id_FK=member).order_by("-claim_date")
        for da in death_aids:
            record = {
                "claim_id": da.death_aid_id_PK,
                "claim_type": "Death Aid",
                "status": da.status,
                "description": f"{da.deceased_name or 'Death'} - ₱{da.benefit_amount or 0}",
                "date": da.claim_date.isoformat() if da.claim_date else "",
                "is_medical": False,
            }
            death_aid_records.append(record)
            claim_items.append(record)
            death_aid_count += 1
            if da.status == 'Pending':
                death_aid_pending += 1
            elif da.status == 'Approved':
                death_aid_approved += 1
            elif da.status == 'Released':
                death_aid_released += 1
        
        notifications_qs = Notification.objects.filter(
            recipient_type='member',
            recipient_id=member.member_id_PK
        ).order_by("-sent_at")[:10]
        for n in notifications_qs:
            notifications.append({
                "notification_id_PK": n.notification_id_PK,
                "notification_type": n.notification_type,
                "message": n.message,
                "category": n.category,
                "sent_at": n.sent_at,
                "is_read": n.is_read,
                "sender_name": n.sender_name or "",
                "sender_role": n.sender_role or "",
                "receipt_number": n.receipt_number or "",
            })

    claim_items.sort(key=lambda x: x["date"], reverse=True)
    total_claims = medical_aid_count + death_aid_count

    # Finance summary
    total_financial_contributions = (membership_fee_amount if membership_fee_paid else 0) + total_dues_paid + total_contributions
    total_paid = (membership_fee_amount if membership_fee_paid else 0) + total_dues_paid
    pending_amount = total_dues_pending

    # Latest payment dates & method
    latest_payment_date = ""
    next_due_date = ""
    next_due_month = ""
    next_due_month_label = "Up to date"
    first_payment_method = ""
    if member:
        last_pmt = MonthlyDues.objects.filter(member_id_FK=member, payment_date__isnull=False).order_by("-payment_date").first()
        if last_pmt:
            first_payment_method = last_pmt.payment_method or ""
        if not first_payment_method:
            last_fee = MembershipFee.objects.filter(member_id_FK=member, payment_date__isnull=False).order_by("-payment_date").first()
            if last_fee:
                first_payment_method = last_fee.payment_method or ""
    if member:
        last_dues = MonthlyDues.objects.filter(
            member_id_FK=member, payment_date__isnull=False
        ).order_by("-payment_date").first()
        if last_dues and last_dues.payment_date:
            latest_payment_date = last_dues.payment_date.isoformat()
        
        today = date.today()
        next_m = today.replace(day=1) + timedelta(days=32)
        next_m = next_m.replace(day=1)
        next_month_str = next_m.strftime("%Y-%m")
        
        has_next_due = not MonthlyDues.objects.filter(
            member_id_FK=member, month_covered=next_month_str
        ).exists()
        
        if has_next_due:
            # Assuming dues are for the first of the month.
            next_due_date = next_m.strftime("%b %d, %Y")
            next_due_month = next_month_str
            next_due_month_label = next_m.strftime("%B %Y")


    # Payment history (combined)
    payment_history = []
    if member:
        fees = MembershipFee.objects.filter(member_id_FK=member, payment_date__isnull=False).order_by("-payment_date")[:10]
        for f in fees:
            payment_history.append({
                "type": "Membership Fee",
                "amount": float(f.amount),
                "method": f.payment_method,
                "status": f.payment_status,
                "date": f.payment_date.isoformat() if f.payment_date else "",
                "reference": f.receipt_number or "",
            })
        dues = MonthlyDues.objects.filter(member_id_FK=member, payment_date__isnull=False).order_by("-payment_date")[:10]
        for d in dues:
            payment_history.append({
                "type": f"Dues ({d.month_covered})",
                "amount": float(d.amount),
                "method": d.payment_method,
                "status": d.payment_status,
                "date": d.payment_date.isoformat() if d.payment_date else "",
                "reference": d.receipt_number or "",
                "treasurer_status": d.treasurer_status,
                "auditor_status": d.auditor_status,
                "president_status": d.president_status,
            })
        payment_history.sort(key=lambda x: x["date"], reverse=True)

    # Compute member_since_date (fallback chain)
    member_since_date = ""
    member_since_label = ""
    if member:
        if member.date_joined:
            member_since_date = member.date_joined.isoformat()
            member_since_label = member.date_joined.strftime("%b %Y")
        else:
            earliest = None
            first_fee = MembershipFee.objects.filter(member_id_FK=member, payment_date__isnull=False).order_by("payment_date").first()
            if first_fee and first_fee.payment_date:
                earliest = first_fee.payment_date
            
            first_dues = MonthlyDues.objects.filter(member_id_FK=member, payment_date__isnull=False).order_by("payment_date").first()
            if first_dues and first_dues.payment_date:
                if earliest is None or first_dues.payment_date < earliest:
                    earliest = first_dues.payment_date
            
            if earliest:
                member_since_date = earliest.isoformat()
                member_since_label = earliest.strftime("%b %Y")
            else:
                member_since_label = "N/A"

    # Authorized representative
    rep_data = None
    if member:
        rep = Claimant.objects.filter(member_id_FK=member).first()
        if rep:
            rep_data = {
                "full_name": rep.full_name,
                "contact_number": rep.contact_number or "",
                "relationship": rep.relationship_to_member,
            }

    context = {
        "officer_full_name": officer_full_name,
        "officer_email": officer_email,
        "member_data": member_data,
        "access_token": request.session.get("access_token", ""),
        "membership_fee_status": membership_fee_status,
        "membership_fee_amount": membership_fee_amount,
        "membership_fee_paid": membership_fee_paid,
        "membership_fee_submitted": membership_fee_submitted,
        "membership_fee_reference": membership_fee_reference,
        "membership_fee_payment_date": membership_fee_payment_date,
        "membership_fee_method": membership_fee_method,
        "monthly_dues_amount": monthly_dues_amount,
        "next_due_month": next_due_month,
        "next_due_month_label": next_due_month_label,
        "total_dues_paid": total_dues_paid,
        "total_dues_pending": total_dues_pending,
        "total_dues_unpaid": total_dues_unpaid,
        "outstanding_balance": outstanding_balance,
        "total_contributions": total_contributions,
        "total_financial_contributions": total_financial_contributions,
        "total_paid": total_paid,
        "pending_amount": pending_amount,
        "next_due_date": next_due_date,
        "latest_payment_date": latest_payment_date,
        "first_payment_method": first_payment_method,
        "total_claims": total_claims,
        "dues_records": dues_records,
        "contribution_records": contribution_records,
        "medical_aid_records": medical_aid_records,
        "death_aid_records": death_aid_records,
        "notifications": notifications,
        "payment_history": payment_history,
        "rep_data": rep_data,
        "member_since_date": member_since_date,
        "member_since_label": member_since_label,
        "medical_aid_pending": medical_aid_pending,
        "medical_aid_approved": medical_aid_approved,
        "medical_aid_released": medical_aid_released,
        "death_aid_pending": death_aid_pending,
        "death_aid_approved": death_aid_approved,
        "death_aid_released": death_aid_released,
        "claim_items": claim_items,
        "total_claims": total_claims,
        "medical_aid_count": medical_aid_count,
        "death_aid_count": death_aid_count,
        "membership_fee_paid": membership_fee_paid,
        "is_member": member is not None,
    }

    return render(request, "website/Member/member_dashboard.html", context)
