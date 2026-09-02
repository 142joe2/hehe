from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.db.models import Sum, Q
from django.views.decorators.cache import never_cache

from core_system.guards import require_officer_session, require_role
from core_system.models import (
    AidTrackingPost,
    Contribution,
    FundTransaction,
    Member,
    MembershipFee,
    OfficerUser,
    MonthlyDues,
    TransactionArchive,
    TransactionVerification,
    SystemSetting,
)
from core_system.constants.policy_constants import get_expected_dues_amount
from core_system.constants.status_constants import Status

import logging
logger = logging.getLogger(__name__)


@never_cache
def hx_cash_flow_summary(request: HttpRequest):
    """Legacy — redirects to fund balance endpoint."""
    guard = require_officer_session(request)
    if guard:
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

    return render(request, "htmx/fund_balance_fragment.html", {
        "balance": balance,
        "safety_threshold": float(threshold.setting_value),
        "available": balance - float(threshold.setting_value),
        "month_in": 0,
        "month_out": 0,
    })


TREASURER_MODULE_WHITELIST = {
    "dashboard-overview", "view-member-profile", "view-fee-payment",
    "view-returned-entries", "view-otc-payment", "view-salary-deduction",
    "view-monthly-dues-returned", "view-dues-tracking", "view-medical-aid",
    "view-death-aid", "view-medical-aid-returned", "view-death-aid-returned",
    "treasurer-aid-tracking-posts", "treasurer-aid-history", "view-reports",
    "view-payroll-batches",
}

AUDITOR_MODULE_WHITELIST = {
    "dashboard-overview", "audit-members-payments", "Membership-Fee-Audit",
    "audit-aid-requests", "audit-comprehensive-aid-collection",
    "audit-aid-history", "view-audit-ledger", "view-reports-compiler",
    "audit-payroll-batches",
}

PRESIDENT_MODULE_WHITELIST = {
    "dashboard-overview", "presidential-payments", "presidential-aid-requests",
    "president-finish-approvals", "view-executive-ledger", "view-reports-compiler",
    "approve-payroll-batches",
}


@never_cache
def hx_treasurer_module(request: HttpRequest, module_name: str):
    guard = require_role(request, role="treasurer")
    if guard:
        return guard

    if module_name not in TREASURER_MODULE_WHITELIST:
        return HttpResponse(status=404)

    officer_id = request.session.get("officer_id")
    officer_full_name = ""
    officer_role = "treasurer"
    if officer_id is not None:
        try:
            officer = OfficerUser.objects.get(user_id_PK=int(officer_id))
            officer_full_name = getattr(officer, "full_name", "") or ""
            officer_role = getattr(officer, "role", None) or officer_role
        except Exception:
            pass

    context = {
        "officer_full_name": officer_full_name,
        "officer_role": officer_role,
        "expected_dues_default_amount": get_expected_dues_amount(),
        "access_token": request.session.get("access_token", ""),
        "returned_entries_count": TransactionVerification.objects.filter(
            table_name="membership_fee",
            verification_status__in=[Status.RETURNED_REVISION, Status.REJECTED],
        ).count(),
        "monthly_dues_returned_count": TransactionVerification.objects.filter(
            table_name="monthly_dues",
            verification_status__in=[Status.RETURNED_REVISION, Status.REJECTED],
        ).count(),
        "medical_aid_returned_count": TransactionVerification.objects.filter(
            table_name="medical_aid",
            verification_status__in=[Status.RETURNED_REVISION, Status.REJECTED],
        ).count(),
        "death_aid_returned_count": TransactionVerification.objects.filter(
            table_name="death_aid",
            verification_status__in=[Status.RETURNED_REVISION, Status.REJECTED],
        ).count(),
        "active_aid_posts_count": AidTrackingPost.objects.filter(
            is_active=True,
        ).count(),
    }

    if not officer_full_name.strip():
        context["officer_full_name"] = context["officer_role"]

    template = f"htmx/treasurer/{module_name}.html"
    return render(request, template, context)


@never_cache
def hx_auditor_module(request: HttpRequest, module_name: str):
    guard = require_role(request, role="auditor")
    if guard:
        return guard

    if module_name not in AUDITOR_MODULE_WHITELIST:
        return HttpResponse(status=404)

    officer_id = request.session.get("officer_id")
    officer_full_name = ""
    officer_role = "auditor"
    if officer_id is not None:
        try:
            officer = OfficerUser.objects.get(user_id_PK=int(officer_id))
            officer_full_name = getattr(officer, "full_name", "") or ""
            officer_role = getattr(officer, "role", None) or officer_role
        except Exception:
            pass

    context = {
        "officer_full_name": officer_full_name,
        "officer_role": officer_role,
        "access_token": request.session.get("access_token", ""),
    }

    if not officer_full_name.strip():
        context["officer_full_name"] = context["officer_role"]

    template = f"htmx/auditor/{module_name}.html"
    return render(request, template, context)




@never_cache
def hx_president_module(request: HttpRequest, module_name: str):
    guard = require_role(request, role="president")
    if guard:
        return guard

    if module_name not in PRESIDENT_MODULE_WHITELIST:
        return HttpResponse(status=404)

    officer_id = request.session.get("officer_id")
    officer_full_name = ""
    officer_role = "president"
    if officer_id is not None:
        try:
            officer = OfficerUser.objects.get(user_id_PK=int(officer_id))
            officer_full_name = getattr(officer, "full_name", "") or ""
            officer_role = getattr(officer, "role", None) or officer_role
        except Exception:
            pass

    context = {
        "officer_full_name": officer_full_name,
        "officer_role": officer_role,
        "access_token": request.session.get("access_token", ""),
    }

    if not officer_full_name.strip():
        context["officer_full_name"] = context["officer_role"]

    template = f"htmx/president/{module_name}.html"
    return render(request, template, context)
