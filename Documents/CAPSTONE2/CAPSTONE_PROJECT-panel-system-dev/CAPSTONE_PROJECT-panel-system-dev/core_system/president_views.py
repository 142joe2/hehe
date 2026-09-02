import hashlib
import json
import logging
import os
import secrets
import threading
import time
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List

from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.db import IntegrityError, transaction
from django.db.models import Sum, Count, Q, F
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import render, get_object_or_404
from django.views.decorators.http import require_GET, require_POST, require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from django.contrib.contenttypes.models import ContentType
from django.conf import settings

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

logger = logging.getLogger(__name__)

from core_system.guards import check_zero_trust, require_role
from core_system.constants.status_constants import Status
from core_system.services.oversight_reports import STAGE_MAP, MONTH_NAMES, DEATH_CATEGORY_LABELS
from core_system.models import (
    AidTrackingPost,
    BackupJob,
    BylawsFile,
    Department,
    Contribution,
    DeathAid,
    FinancialDocumentArchive,
    FundTransaction,
    GlobalAuditTrail,
    MedicalAid,
    Member,
    MemberRegistrationRequest,
    MembershipFee,
    MonthlyDues,
    OfficerUser,
    PayrollBatch,
    PayrollDeduction,
    SalaryDeductionExemption,
    SupportingProof,
    SystemSetting,
    TransactionArchive,
    TransactionVerification,
    MemberLedger,
    Document,
    DocumentPin,
    DocumentActivity,
    Category,
)
from core_system.services.backup_service import (
    list_backup_jobs,
    trigger_manual_backup,
    restore_backup_job,
)
from core_system.constants.status_constants import (
    RegistrationStatus,
    Status,
    can_president_act,
    is_approved,
    is_rejected,
)
from core_system.constants.policy_constants import (
    get_death_aid_amount,
    get_membership_fee_amount,
    get_monthly_dues_amount,
    get_contribution_amount_for_aid,
    is_exempt_from_dues_and_aid,
    POLICY,
    _get_setting_override,
    _POLICY_CONSTANT_KEYS,
    _POLICY_OVERRIDE_PREFIX,
)
from core_system.shared_view_utils import (
    MODEL_MAP,
    _audit_evidence_filename,
    _compute_row_signature,
    _get_auditor_verification,
    _get_proof_url,
    _link_proof_to_record,
    _officer_to_json,
    _record_audit_trail,
    _record_bulk_audit_trail,
    _log_sensitive_read,
    _payment_item_to_json,
    archive_transaction,
    route_back_to_treasurer,
    _broadcast_pending_counts,
    _broadcast_to_group,
    resolve_officer_from_session,
)
from core_system.services.notifications import notify_member
from core_system.services.compliance import (
    dues_compliance_summary,
    active_members_qs,
)
from core_system.services.email_service import (
    process_email_queue,
    queue_email,
    send_aid_emails,
    send_html_email,
    send_registration_rejected_email,
)
from core_system.auth_utils import hash_password
from core_system.services.oversight_reports import build_report, report_to_pdf, report_to_xlsx


def permission_denied_view(request, exception=None):
    return render(request, "errors/403.html", status=403)


@require_GET
def audit_trail_api(request: HttpRequest, table_name: str, record_id: int):
    allowed_roles = {"Treasurer", "Auditor", "President"}
    stored_role = (request.session.get("role") or "").strip()
    if stored_role not in allowed_roles:
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied("Forbidden for this role.")

    entries = GlobalAuditTrail.objects.filter(
        table_name=table_name,
        record_id=int(record_id),
    ).order_by("-timestamp")

    limit = int(request.GET.get("limit", 200))
    offset = int(request.GET.get("offset", 0))
    if limit > 200:
        limit = 200
    total = entries.count()
    entries = entries[offset : offset + limit]

    rows = []
    for entry in entries:
        rows.append(
            {
                "trail_id": entry.trail_id,
                "action": entry.action,
                "actor_type": entry.actor_type,
                "actor_id": entry.actor_id,
                "actor_name": entry.actor_name,
                "old_values": entry.old_values,
                "new_values": entry.new_values,
                "notes": entry.notes,
                "ip_address": str(entry.ip_address) if entry.ip_address else None,
                "timestamp": entry.timestamp.isoformat() if entry.timestamp else None,
            }
        )

    return JsonResponse(
        {
            "ok": True,
            "table_name": table_name,
            "record_id": record_id,
            "total": total,
            "entries": rows,
        }
    )


# ==========================================================================
# PRESIDENT WORKSPACE VIEWS
# ==========================================================================

OFFICER_DEPARTMENT_CODES = {
    "CED": "CED",
    "CCSICT": "CCSICT",
    "IAT": "IAT",
    "CCJE": "CCJE",
    "SAS": "SAS",
    "CBM": "CBM",
    "PS": "PS",
}

def _resolve_officer_department(department_id):
    if department_id in (None, "", 0, "0"):
        return None
    if str(department_id).isdigit():
        department = Department.objects.filter(department_id_PK=int(department_id)).first()
        if department:
            return department
    code = str(department_id).strip().upper()
    if not code:
        return None
    department = Department.objects.filter(code__iexact=code).first()
    if department:
        return department
    if code in OFFICER_DEPARTMENT_CODES:
        return Department.objects.create(code=code, name=OFFICER_DEPARTMENT_CODES[code], is_active=True)
    return None


def president_dashboard(request):
    guard = require_role(request, role="President")
    if guard is not None:
        return guard

    officer_full_name = ""
    officer_role = "President"

    stored_officer_id = request.session.get("officer_id")
    if stored_officer_id is not None:
        try:
            officer = OfficerUser.objects.get(user_id_PK=int(stored_officer_id))
            officer_full_name = getattr(officer, "full_name", "") or ""
            officer_role = getattr(officer, "role", None) or officer_role
        except Exception:
            pass

    context = {
        "officer_full_name": officer_full_name,
        "officer_role": officer_role,
        "access_token": request.session.get("access_token", ""),
        "departments": Department.objects.filter(is_active=True).order_by("name"),
    }

    if not officer_full_name.strip():
        context["officer_full_name"] = context["officer_role"]

    return render(request, "website/President/president_dashboard.html", context)


def systembackup_dashboard(request):
    guard = require_role(request, role=["President", "System"])
    if guard is not None:
        return guard

    officer_full_name = ""
    officer_role = "System Backup"

    stored_officer_id = request.session.get("officer_id")
    if stored_officer_id is not None:
        try:
            officer = OfficerUser.objects.get(user_id_PK=int(stored_officer_id))
            officer_full_name = getattr(officer, "full_name", "") or ""
            officer_role = getattr(officer, "role", None) or officer_role
        except Exception:
            pass

    context = {
        "officer_name": officer_full_name,
        "officer_role": officer_role,
        "access_token": request.session.get("access_token", ""),
    }

    if not officer_full_name.strip():
        context["officer_name"] = "System Backup"

    return render(request, "website/SystemBackup/systembackup_dashboard.html", context)


def _load_pending_dues_record(v):
    """Load monthly dues record data for presidential queue."""
    payment_record = (
        MonthlyDues.objects.filter(dues_id_PK=v.record_id)
        .select_related("member_id_FK", "recorded_by_user_id_FK")
        .first()
    )
    if not payment_record:
        return None, None, None

    p_member = payment_record.member_id_FK
    member_data = {
        "member_name": p_member.full_name,
        "employee_id": p_member.employee_id,
        "department": p_member.department,
        "membership_status": p_member.membership_status,
        "contact_info": p_member.contact_number,
    }
    method = (payment_record.payment_method or "").strip().lower()
    is_salary = method == "salary deduction"

    payment_details = {
        "reference_code": payment_record.receipt_number
        or payment_record.deduction_batch_reference
        or "—",
        "covered_period": payment_record.month_covered,
        "amount_paid": float(payment_record.amount),
        "expected": get_monthly_dues_amount(),
        "payment_method": payment_record.payment_method,
        "encoder_name": (
            payment_record.recorded_by_user_id_FK.full_name
            if payment_record.recorded_by_user_id_FK
            else "System"
        ),
        "type": "monthly_dues_salary" if is_salary else "monthly_dues_otc",
    }

    if is_salary:
        approved_fields = {
            "membership_type": "Monthly Dues (Salary Deduction)",
            "membership_ref": payment_record.remittance_reference or payment_record.receipt_number or "",
            "membership_month": payment_record.month_covered or "",
            "membership_amount": float(payment_record.amount),
            "otc_month": "—", "otc_amount": 0, "otc_ref": "—",
            "salary_month": payment_record.month_covered,
            "salary_amount": float(payment_record.amount),
            "salary_ref": payment_record.remittance_reference or payment_record.receipt_number or "",
        }
    else:
        approved_fields = {
            "membership_type": "Monthly Dues (OTC)",
            "membership_ref": payment_record.receipt_number or "",
            "membership_month": payment_record.month_covered or "",
            "membership_amount": float(payment_record.amount),
            "salary_month": "—", "salary_amount": 0, "salary_ref": "—",
            "otc_month": payment_record.month_covered,
            "otc_amount": float(payment_record.amount),
            "otc_ref": payment_record.receipt_number or "",
        }

    return member_data, payment_details, approved_fields


def _load_pending_fee_record(v):
    """Load membership fee record data for presidential queue."""
    payment_record = (
        MembershipFee.objects.filter(fee_id_PK=v.record_id)
        .select_related("member_id_FK", "recorded_by_user_id_FK")
        .first()
    )
    if not payment_record:
        return None, None, None

    p_member = payment_record.member_id_FK
    member_data = {
        "member_name": p_member.full_name,
        "employee_id": p_member.employee_id,
        "department": p_member.department,
        "membership_status": p_member.membership_status,
        "contact_info": p_member.contact_number,
    }
    payment_details = {
        "reference_code": payment_record.receipt_number
        or payment_record.deposit_reference
        or "—",
        "covered_period": "One-Time Fee",
        "amount_paid": float(payment_record.amount),
        "expected": get_membership_fee_amount(),
        "payment_method": payment_record.payment_method,
        "encoder_name": (
            payment_record.recorded_by_user_id_FK.full_name
            if payment_record.recorded_by_user_id_FK
            else "System"
        ),
        "type": "membership_fee",
    }
    approved_fields = {
        "membership_type": "OTC Membership Fee",
        "membership_ref": payment_record.receipt_number or payment_record.deposit_reference or "",
        "membership_month": "One-Time Fee",
        "membership_amount": float(payment_record.amount),
        "otc_month": "—", "otc_amount": 0, "otc_ref": "—",
        "salary_month": "—", "salary_amount": 0, "salary_ref": "—",
    }

    return member_data, payment_details, approved_fields


def _build_auditor_info(v):
    """Build auditor verification info for presidential queue item."""
    apv = _get_auditor_verification(str(v.table_name).lower(), v.record_id)
    if apv:
        return {
            "auditorName": apv.auditor_id_FK.full_name if apv.auditor_id_FK_id else "—",
            "auditorDate": (
                apv.verified_at.strftime("%Y-%m-%d %H:%M:%S")
                if getattr(apv, "verified_at", None)
                else (v.verified_at.strftime("%Y-%m-%d %H:%M:%S") if v.verified_at else "—")
            ),
            "auditorEvidence": _audit_evidence_filename(apv.evidence_file_path) if apv.evidence_file_path else "—",
            "auditorRemarks": (
                apv.auditor_remarks.strip()
                if apv.auditor_remarks and str(apv.auditor_remarks).strip()
                else "—"
            ),
        }
    return {
        "auditorName": v.auditor_id_FK.full_name if v.auditor_id_FK_id else "—",
        "auditorDate": v.verified_at.strftime("%Y-%m-%d %H:%M:%S") if v.verified_at else "—",
        "auditorEvidence": "—",
        "auditorRemarks": "—",
    }


@require_GET
def get_pending_presidential_payments(request):
    guard = require_role(request, role="President")
    if guard is not None:
        return guard
    verifications = TransactionVerification.objects.filter(
        table_name__in=["membership_fee", "monthly_dues"],
        verification_status="Auditor Verified",
        auditor_id_FK__isnull=False,
        president_id_FK__isnull=True,
    ).select_related("auditor_id_FK")

    # Optimize: Fetch all audit logs in a single query instead of N+1 queries
    record_ids = [(v.table_name, v.record_id) for v in verifications]
    all_logs = {}
    if record_ids:
        all_logs_qs = GlobalAuditTrail.objects.filter(
            table_name__in=[t[0] for t in record_ids],
            record_id__in=[t[1] for t in record_ids],
            action__in=["VERIFIED", "RETURNED", "CORRECTION_REQUIRED", "REJECTED", "RESUBMITTED", "CREATED"],
        ).order_by("timestamp")
        
        for log in all_logs_qs:
            key = (log.table_name, log.record_id)
            if key not in all_logs:
                all_logs[key] = []
            all_logs[key].append(log)

    data = []
    for v in verifications:
        tn = str(v.table_name).lower()

        if tn == "monthly_dues":
            member_data, payment_details, approved_fields = _load_pending_dues_record(v)
        else:
            member_data, payment_details, approved_fields = _load_pending_fee_record(v)

        if not member_data:
            continue

        # Use pre-fetched logs instead of separate query
        logs = all_logs.get((v.table_name, v.record_id), [])

        timeline_data = [
            {
                "timestamp": log.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                "role": log.actor_type or "System",
                "user": log.actor_name or "System Log",
                "action": log.action.title().replace("_", " "),
                "notes": log.notes or "",
                "old_values": log.old_values,
                "new_values": log.new_values,
            }
            for log in logs
        ]

        auditor_info = _build_auditor_info(v)

        record_payload = {
            "id": v.verification_id,
            **auditor_info,
            "timeline": timeline_data,
            "returned_reason": v.returned_reason or "",
            "return_count": v.return_count or 0,
        }
        record_payload.update(member_data)
        record_payload.update(payment_details)
        record_payload.update(approved_fields)

        data.append(record_payload)

    return JsonResponse({"success": True, "payments": data}, safe=False)


@require_GET
def president_auditor_approved_payments_queue(request: HttpRequest):
    guard = require_role(request, role="President")
    if guard is not None:
        return guard

    approved_verifications = TransactionVerification.objects.filter(
        table_name__in=["membership_fee", "monthly_dues"],
        verification_status="Auditor Verified",
        auditor_id_FK__isnull=False,
        president_id_FK__isnull=True,
    ).select_related()

    items: List[Dict[str, Any]] = []

    for tv in approved_verifications:
        if str(tv.table_name).lower() == "membership_fee":
            fee = (
                MembershipFee.objects.select_related("member_id_FK", "recorded_by_user_id_FK")
                .filter(fee_id_PK=tv.record_id)
                .first()
            )
            if not fee:
                continue
            items.append(_payment_item_to_json("membership_fee", fee))
        elif str(tv.table_name).lower() == "monthly_dues":
            dues = (
                MonthlyDues.objects.select_related("member_id_FK", "recorded_by_user_id_FK")
                .filter(dues_id_PK=tv.record_id)
                .first()
            )
            if not dues:
                continue
            items.append(_payment_item_to_json("monthly_dues", dues))

    items.sort(key=lambda x: x.get("entity_id", 0), reverse=True)
    return JsonResponse({"ok": True, "payments": items})


@require_GET
def _build_treasurer_original(record):
    if record is None:
        return {"member": None}
    if isinstance(record, MembershipFee):
        ref = record.receipt_number or ""
    else:
        ref = record.receipt_number or record.remittance_reference or ""
    return {
        "memberName": record.member_id_FK.full_name,
        "employeeId": record.member_id_FK.employee_id or "",
        "department": record.member_id_FK.department or "",
        "status": record.member_id_FK.membership_status or "",
        "contact": record.member_id_FK.contact_number or "",
        "covered": record.month_covered or "",
        "expected": str(record.amount),
        "method": record.payment_method or "",
        "ref": ref,
        "encoder": getattr(record.recorded_by_user_id_FK, "full_name", "") or "",
    }


def president_auditor_approved_payment_detail(request: HttpRequest, entity_id: int):
    guard = require_role(request, role="President")
    if guard is not None:
        return guard

    fee = MembershipFee.objects.select_related("member_id_FK", "recorded_by_user_id_FK").filter(fee_id_PK=entity_id).first()
    dues = MonthlyDues.objects.select_related("member_id_FK", "recorded_by_user_id_FK").filter(dues_id_PK=entity_id).first()

    tv = TransactionVerification.objects.filter(
        table_name__in=["membership_fee", "monthly_dues"],
        record_id=entity_id,
        verification_status="Auditor Verified",
        president_id_FK__isnull=True,
    ).order_by("-approved_at", "-verified_at").first()

    if not tv or (not fee and not dues):
        return JsonResponse({"ok": False, "error": "Approved payment not found."}, status=404)

    approved_membership = _payment_item_to_json("membership_fee", fee) if fee else None
    approved_otc_dues = None
    approved_salary_dues = None
    if dues:
        method = (dues.payment_method or "").lower()
        if method == "salary deduction":
            approved_salary_dues = _payment_item_to_json("monthly_dues", dues)
        else:
            approved_otc_dues = _payment_item_to_json("monthly_dues", dues)

    auditor_name = tv.auditor_id_FK.full_name if tv.auditor_id_FK_id else ""
    auditor_date = (tv.verified_at.isoformat() if tv.verified_at else "")

    evidence_filename = ""
    archive = FinancialDocumentArchive.objects.filter(
        related_record_id=entity_id,
        document_type="auditor_finding",
        related_module=tv.table_name.upper(),
    ).order_by("-uploaded_at").first()
    if archive and archive.file_path:
        evidence_filename = archive.file_path.split("/")[-1]

    return JsonResponse({
        "ok": True,
        "item": {
            "id": str(entity_id),
            "table_name": tv.table_name,
            "auditorName": auditor_name,
            "auditorDate": auditor_date,
            "auditorEvidence": evidence_filename or "",
            "auditorRemarks": "—",
            "returned_reason": tv.returned_reason or "",
            "return_count": tv.return_count or 0,
        },
        "approvedMembership": approved_membership,
        "approvedOtcDues": approved_otc_dues,
        "approvedSalaryDues": approved_salary_dues,
        "treasurerOriginal": _build_treasurer_original(fee or dues),
        "timeline": [],
    })


@require_POST
@transaction.atomic
def president_approve_monthly_dues(request: HttpRequest):
    """President approves or rejects a monthly dues payment."""
    guard = require_role(request, role="President")
    if guard is not None:
        return guard
    # ZT check removed during transition

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"ok": False, "error": "Invalid JSON"}, status=400)

    dues_id = data.get("dues_id")
    action = data.get("action")  # "approve" or "reject"
    remarks = data.get("remarks", "")

    if not dues_id or action not in ["approve", "reject"]:
        return JsonResponse({"ok": False, "error": "Missing required fields: dues_id, action"}, status=400)

    dues = get_object_or_404(MonthlyDues.objects.select_for_update(), dues_id_PK=dues_id)
    officer_id = request.session.get("officer_id")
    officer = OfficerUser.objects.get(user_id_PK=officer_id)

    # State check: only allow approval if the record is in a pending president state (S6).
    if action == "approve" and dues.president_status not in ("Pending President Approval", "Pending"):
        return JsonResponse(
            {"ok": False, "error": "This payment is not in a state that can be approved by the President."},
            status=409,
        )

    if action == "approve":
        # Update MonthlyDues approval fields
        dues.president_status = "President Approved"
        dues.president_id_FK = officer
        dues.president_remarks = remarks
        dues.president_approved_at = timezone.now()
        dues.payment_status = "Full Payment"
        dues.treasurer_status = dues.treasurer_status or "Treasurer Verified"
        if dues.treasurer_status == "Pending Treasurer Review":
            dues.treasurer_status = "Treasurer Verified"
        dues.save()

        # Create FundTransaction (inflow) — idempotent per dues record.
        if not FundTransaction.objects.filter(
            source_type="monthly_dues",
            source_id=dues.dues_id_PK,
        ).exists():
            FundTransaction.objects.create(
                direction="inflow",
                amount=dues.amount,
                source_type="monthly_dues",
                source_id=dues.dues_id_PK,
                description=f"Monthly Dues - {dues.member_id_FK.full_name} ({dues.month_covered})",
                reference_number=dues.receipt_number,
                recorded_by_user_id_FK=officer,
            )

        # Calculate and update MemberLedger — idempotent per dues record so the
        # ledger entry is written exactly once (at final approval), never doubled
        # when a president re-approves or when two approval endpoints race (C3).
        if not MemberLedger.objects.filter(
            reference_type="MonthlyDues",
            reference_id=dues.dues_id_PK,
        ).exists():
            last_ledger = MemberLedger.objects.filter(
                member_id_FK=dues.member_id_FK
            ).order_by("-recorded_at").first()
            balance_after = last_ledger.balance_after if last_ledger else Decimal("0.00")
            balance_after += dues.amount

            MemberLedger.objects.create(
                member_id_FK=dues.member_id_FK,
                transaction_type="monthly_dues",
                amount=dues.amount,
                direction="credit",
                balance_after=balance_after,
                reference_id=dues.dues_id_PK,
                reference_type="MonthlyDues",
                description=f"Monthly Dues Payment - {dues.month_covered}",
                recorded_by_user_id_FK=officer,
            )

        # Update TransactionVerification
        tv = TransactionVerification.objects.filter(
            table_name="monthly_dues",
            record_id=dues_id
        ).first()
        if tv:
            tv.verification_status = "President Approved"
            tv.president_id_FK = officer
            tv.save()

        # If this is salary deduction payment, remove any exemption for this month
        if dues.payment_method == "Salary Deduction":
            deleted_count, _ = SalaryDeductionExemption.objects.filter(
                member_id_FK=dues.member_id_FK,
                month_covered=dues.month_covered
            ).delete()
            logger.info("Removed %d salary deduction exemption(s) for member %s month %s", deleted_count, dues.member_id_FK.full_name, dues.month_covered)

        # Log audit trail
        _record_audit_trail(
            table="monthly_dues",
            record_id=dues_id,
            action="President Approved",
            actor=officer,
            new={"member": dues.member_id_FK, "month_covered": str(dues.month_covered), "amount": str(dues.amount)},
            ip=request.META.get("REMOTE_ADDR"),
            notes=remarks,
        )

        # Notify member using notification service for consistent HTML email handling
        try:
            from core_system.services.notifications import notify_member
            notify_member(
                dues.member_id_FK,
                notification_type="Payment Approved",
                message=f"Your monthly dues payment for {dues.month_covered} (₱{dues.amount}) has been approved. Thank you for your contribution.",
                category="payment",
                sender_name=officer.full_name if officer else "President",
                sender_role="President",
                receipt_number=dues.receipt_number or "",
            )
        except Exception as e:
            logger.warning("Failed to send payment approval notification to member %s: %s", dues.member_id_FK.member_id_PK, e)

        return JsonResponse({
            "ok": True,
            "message": "Monthly dues payment approved successfully.",
        })
    else:
        # Reject: route the payment back to the Treasurer queue (non-terminal).
        route_back_to_treasurer(
            "monthly_dues",
            dues_id,
            officer,
            remarks,
            request,
            member=dues.member_id_FK,
            extra_updates={
                "president_status": "President Rejected",
                "president_id_FK": officer,
                "president_remarks": remarks,
                "president_approved_at": timezone.now(),
            },
            details=f"Your monthly dues payment for {dues.month_covered} was returned for revision by the President.",
        )

        return JsonResponse({
            "ok": True,
            "message": "Monthly dues payment returned to the Treasurer for revision.",
        })


@require_GET
def president_pending_contributions(request: HttpRequest):
    guard = require_role(request, role="President")
    if guard is not None:
        return guard

    verifications = TransactionVerification.objects.filter(
        table_name="contribution",
        target_category="aid_contribution",
        verification_status="Auditor Verified",
        auditor_id_FK__isnull=False,
        president_id_FK__isnull=True,
    ).select_related("auditor_id_FK").order_by("verification_id")

    items = []
    for v in verifications:
        contrib = Contribution.objects.filter(
            contribution_id_PK=v.record_id
        ).select_related("member_id_FK", "aid_tracking_post_id_FK").first()
        if not contrib:
            continue

        member = contrib.member_id_FK
        post = contrib.aid_tracking_post_id_FK
        member_name = member.full_name if member else "Unknown"

        logs = GlobalAuditTrail.objects.filter(
            table_name="contribution",
            record_id=v.record_id,
            action__in=["VERIFIED", "RETURNED", "CORRECTION_REQUIRED", "REJECTED", "RESUBMITTED", "CREATED"],
        ).order_by("timestamp")

        timeline = [
            {
                "timestamp": log.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                "role": log.actor_type or "System",
                "user": log.actor_name or "System Log",
                "action": log.action.title().replace("_", " "),
                "notes": log.notes or "",
                "old_values": log.old_values,
                "new_values": log.new_values,
            }
            for log in logs
        ]

        aid_type_label = post.aid_type if post else "—"
        source_type_label = {
            "medical_aid": "Medical Aid",
            "death_aid": "Death Aid",
        }.get(post.source_type if post else "", "—")

        items.append({
            "verification_id": v.verification_id,
            "record_id": contrib.contribution_id_PK,
            "member_name": member_name,
            "member_id": member.member_id_PK if member else None,
            "expected_amount": float(contrib.expected_amount),
            "paid_amount": float(contrib.paid_amount),
            "payment_date": str(contrib.payment_date) if contrib.payment_date else "—",
            "status": contrib.status,
            "aid_type": aid_type_label,
            "source_type": source_type_label,
            "post_id": post.post_id_PK if post else None,
            "auditor_name": v.auditor_id_FK.full_name if v.auditor_id_FK_id else "—",
            "auditor_remarks": v.auditor_remarks or "",
            "verified_at": v.verified_at.strftime("%Y-%m-%d %H:%M:%S") if v.verified_at else "—",
            "returned_reason": v.returned_reason or "",
            "return_count": v.return_count or 0,
            "timeline": timeline,
        })

    return JsonResponse({"success": True, "contributions": items}, safe=False)


@require_http_methods(["POST"])
def submit_presidential_contribution_decision(request):
    guard = require_role(request, role="President")
    if guard is not None:
        return guard
    # ZT check removed during transition
    try:
        body = json.loads(request.body)
        target_id = body.get("target_id")
        decision = body.get("decision")
        remarks = body.get("remarks", "")

        stored_officer_id = request.session.get("officer_id")
        if stored_officer_id is None:
            return JsonResponse({"success": False, "message": "Officer session missing."}, status=401)
        officer = get_object_or_404(OfficerUser, user_id_PK=int(stored_officer_id))
        verification = get_object_or_404(TransactionVerification, verification_id=target_id)

        if not can_president_act(verification.verification_status):
            return JsonResponse({"success": False, "message": "Transaction is not in a state that can be acted upon by the President."}, status=400)

        if decision == "Approved":
            verification.verification_status = "Approved"
            verification.approved_at = timezone.now()
            action_str = "Presidential Executive Approval Completed"
        elif decision == "Rejected":
            verification.verification_status = "Rejected"
            if not remarks:
                return JsonResponse({"success": False, "message": "Remarks are mandatory for rejections."}, status=400)
            action_str = "Flagged Deficient by Executive Order"
        else:
            return JsonResponse({"success": False, "message": "Invalid decision route."}, status=400)

        verification.president_id_FK = officer
        verification.save()

        if verification.verification_status == "Approved":
            archive = archive_transaction(verification.table_name, verification.record_id, officer)
            if archive:
                FundTransaction.objects.create(
                    direction="inflow",
                    amount=archive.amount,
                    source_type="aid_contribution",
                    source_id=verification.record_id,
                    description=f"Aid contribution — {archive.member_name}",
                    recorded_by_user_id_FK=officer,
                )

        _record_audit_trail(
            table=verification.table_name,
            record_id=verification.record_id,
            action="APPROVED" if verification.verification_status == "Approved" else "REJECTED",
            actor=officer,
            notes=remarks or None,
            ip=request.META.get("REMOTE_ADDR"),
        )

        _broadcast_pending_counts()
        return JsonResponse({"success": True, "message": f"Contribution verification {verification.verification_status}."})
    except Exception as e:
        return JsonResponse({"success": False, "message": str(e)}, status=500)


@require_GET
def president_auditor_approved_aids_queue(request: HttpRequest):
    guard = require_role(request, role="President")
    if guard is not None:
        return guard

    medicals = MedicalAid.objects.select_related(
        "member_id_FK",
        "auditor_verified_by_user_id_FK",
        "treasurer_validated_by_user_id_FK",
    ).filter(
        status="Auditor Verified",
        president_decided_by_user_id_FK__isnull=True,
    ).order_by("-medical_aid_id_PK")

    deaths = DeathAid.objects.select_related(
        "member_id_FK",
        "claimant_id_FK",
        "treasurer_validated_by_user_id_FK",
        "auditor_verified_by_user_id_FK",
    ).filter(
        status="Auditor Verified",
        president_decided_by_user_id_FK__isnull=True,
    ).order_by("-death_aid_id_PK")

    items: List[Dict[str, Any]] = []
    pres_med_record_ids = []

    for m in medicals:
        pres_med_record_ids.append(m.medical_aid_id_PK)
        member = m.member_id_FK
        tv = TransactionVerification.objects.filter(
            table_name="medical_aid",
            record_id=m.medical_aid_id_PK,
        ).order_by("-verified_at").first()

        auditor_name = "—"
        auditor_date = "—"
        auditor_evidence = "—"
        auditor_remarks = "—"
        if tv:
            auditor_name = tv.auditor_id_FK.full_name if tv.auditor_id_FK_id else "—"
            auditor_date = tv.verified_at.strftime("%Y-%m-%d %H:%M:%S") if tv.verified_at else "—"
            auditor_evidence = tv.evidence_file_path.split("/")[-1] if tv.evidence_file_path else "—"
            auditor_remarks = (tv.auditor_remarks or "").strip() or "—"

        audit_logs = GlobalAuditTrail.objects.filter(
            table_name="medical_aid",
            record_id=m.medical_aid_id_PK,
        ).filter(
            action__in=["VERIFIED", "RETURNED", "RESUBMITTED", "CREATED"],
        ).order_by("timestamp")

        timeline = [
            {
                "timestamp": log.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                "role": log.actor_type or "System",
                "user": log.actor_name or "System Log",
                "action": log.action.title().replace("_", " "),
                "notes": log.notes or "",
                "old_values": log.old_values,
                "new_values": log.new_values,
            }
            for log in audit_logs
        ]

        if not timeline and tv:
            timeline = [{"timestamp": auditor_date, "role": "Auditor", "user": auditor_name, "action": "Verified", "notes": auditor_remarks, "old_values": None, "new_values": None}]

        req_amount = float(m.validated_aid_amount or m.requested_amount or 0)
        bill_amount = float(m.hospital_bill_amount or 0)
        member_name = member.full_name if member else ""
        reason_text = (m.reason_for_request or "").strip()
        if not reason_text:
            _status_fallback = (m.document_status or m.policy_record_status or "").strip()
            if _status_fallback.casefold() not in ("pending", "pending review"):
                reason_text = _status_fallback
        active_non_retired = Member.objects.exclude(membership_status__iexact="Retired")
        if member is not None:
            active_contributors = active_non_retired.exclude(member_id_PK=member.member_id_PK)
        else:
            active_contributors = active_non_retired
        medical_contrib = float(get_contribution_amount_for_aid("medical_aid"))
        contributor_count = active_contributors.count()
        expected_payout = round(medical_contrib * contributor_count, 2)

        items.append(
            {
                "id": "medical-" + str(m.medical_aid_id_PK),
                "entity_id": int(m.medical_aid_id_PK),
                "aid_type": "medical_aid",
                "type": "Medical Aid Request",
                "request_date": str(m.request_date),
                "medical_case": reason_text,
                "requested_amount": req_amount,
                "hospital": m.hospital_name or member_name,
                "hospital_date": str(m.hospital_date or m.admission_date or m.discharge_date) if (m.hospital_date or m.admission_date or m.discharge_date) else "",
                "admission_date": str(m.admission_date) if m.admission_date else "",
                "discharge_date": str(m.discharge_date) if m.discharge_date else "",
                "total_hospital_bill": bill_amount,
                "validated_aid_amount": float(m.validated_aid_amount or 0),
                "date": str(m.request_date),
                "reqAmount": req_amount,
                "bill": bill_amount,
                "contribution_per_member": medical_contrib,
                "active_member_count": contributor_count,
                "expected_payout": expected_payout,
                "reason": reason_text,
                "validation": m.document_status or m.policy_record_status or "",
                "memberName": member_name,
                "member": {
                    "member_id": member.member_id_PK if member else None,
                    "member_name": member_name,
                    "employee_id": member.employee_id or "" if member else "",
                    "department": member.department or "" if member else "",
                    "position": member.position or "" if member else "",
                    "contact": getattr(member, "contact_number", None) or "" if member else "",
                    "email": getattr(member, "email", None) or "" if member else "",
                },
                "auditorName": auditor_name,
                "auditorDate": auditor_date,
                "auditorEvidence": auditor_evidence,
                "auditorRemarks": auditor_remarks,
                "returned_reason": tv.returned_reason if tv else "",
                "return_count": tv.return_count if tv else 0,
                "timeline": timeline,
            }
        )

    for d in deaths:
        member = d.member_id_FK
        claimant = d.claimant_id_FK
        tv = TransactionVerification.objects.filter(
            table_name="death_aid",
            record_id=d.death_aid_id_PK,
        ).order_by("-verified_at").first()

        auditor_name = "—"
        auditor_date = "—"
        auditor_evidence = "—"
        auditor_remarks = "—"
        if tv:
            auditor_name = tv.auditor_id_FK.full_name if tv.auditor_id_FK_id else "—"
            auditor_date = tv.verified_at.strftime("%Y-%m-%d %H:%M:%S") if tv.verified_at else "—"
            auditor_evidence = tv.evidence_file_path.split("/")[-1] if tv.evidence_file_path else "—"
            auditor_remarks = (tv.auditor_remarks or "").strip() or "—"

        audit_logs = GlobalAuditTrail.objects.filter(
            table_name="death_aid",
            record_id=d.death_aid_id_PK,
        ).filter(
            action__in=["VERIFIED", "RETURNED", "RESUBMITTED", "CREATED"],
        ).order_by("timestamp")

        timeline = [
            {
                "timestamp": log.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                "role": log.actor_type or "System",
                "user": log.actor_name or "System Log",
                "action": log.action.title().replace("_", " "),
                "notes": log.notes or "",
                "old_values": log.old_values,
                "new_values": log.new_values,
            }
            for log in audit_logs
        ]

        if not timeline and tv:
            timeline = [{"timestamp": auditor_date, "role": "Auditor", "user": auditor_name, "action": "Verified", "notes": auditor_remarks, "old_values": None, "new_values": None}]

        benefit_amount = float(d.benefit_amount or 0)
        member_name = member.full_name if member else ""
        _claimant_contact = ""
        if claimant and claimant.contact_number:
            _claimant_contact = claimant.contact_number
        elif member and getattr(member, "contact_number", None):
            _claimant_contact = member.contact_number
        elif member and getattr(member, "contact", None):
            _claimant_contact = member.contact
        active_non_retired = Member.objects.exclude(membership_status__iexact="Retired")
        if member is not None:
            active_contributors = active_non_retired.exclude(member_id_PK=member.member_id_PK)
        else:
            active_contributors = active_non_retired
        contributor_count = active_contributors.count()
        death_expected_payout = round(benefit_amount * contributor_count, 2)

        items.append(
            {
                "id": "death-" + str(d.death_aid_id_PK),
                "entity_id": int(d.death_aid_id_PK),
                "aid_type": "death_aid",
                "type": "Death Aid Claim",
                "claim_date": str(d.claim_date),
                "deceased_name": d.deceased_name,
                "relationship_to_member": d.relationship_to_member,
                "relationshipGroup": d.relationship_group,
                "claim_type": d.claim_type,
                "claimant_name": claimant.full_name if claimant else "",
                "claimant_contact": _claimant_contact,
                "bill_amount": float(d.bill_amount) if d.bill_amount else 0,
                "benefit_amount": benefit_amount,
                "date_of_death": str(d.date_of_death) if d.date_of_death else "",
                "date": str(d.claim_date),
                "deceased": d.deceased_name,
                "relationship": d.relationship_to_member,
                "relationshipGroup": d.relationship_group,
                "claimType": d.claim_type,
                "claimantName": claimant.full_name if claimant else "",
                "claimantContact": _claimant_contact,
                "benefit": benefit_amount,
                "contribution_per_member": benefit_amount,
                "active_member_count": contributor_count,
                "expected_payout": death_expected_payout,
                "dateOfDeath": str(d.date_of_death) if d.date_of_death else "",
                "deathDate": str(d.date_of_death) if d.date_of_death else "",
                "memberName": member_name,
                "member": {
                    "member_id": member.member_id_PK if member else None,
                    "member_name": member_name,
                    "employee_id": member.employee_id or "" if member else "",
                    "department": member.department or "" if member else "",
                    "position": member.position or "" if member else "",
                },
                "auditorName": auditor_name,
                "auditorDate": auditor_date,
                "auditorEvidence": auditor_evidence,
                "auditorRemarks": auditor_remarks,
                "returned_reason": tv.returned_reason if tv else "",
                "return_count": tv.return_count if tv else 0,
                "timeline": timeline,
            }
        )

    if pres_med_record_ids:
        _log_sensitive_read(request, "medical_aid", pres_med_record_ids, "President viewed auditor-approved medical aid queue")

    return JsonResponse({"success": True, "aids": items})


@require_http_methods(["POST"])
def submit_presidential_decision(request):
    guard = require_role(request, role="President")
    if guard is not None:
        return guard
    # ZT check removed during transition
    try:
        body = json.loads(request.body)
        target_id = body.get("target_id")
        decision = body.get("decision")
        remarks = body.get("remarks", "")

        stored_officer_id = request.session.get("officer_id")
        if stored_officer_id is None:
            return JsonResponse(
                {"success": False, "message": "Officer session missing."}, status=401
            )
        officer = get_object_or_404(OfficerUser, user_id_PK=int(stored_officer_id))
        verification = get_object_or_404(
            TransactionVerification, verification_id=target_id
        )

        if not can_president_act(verification.verification_status):
            return JsonResponse(
                {"success": False, "message": "Transaction is not in a state that can be acted upon by the President."},
                status=400,
            )

        if decision == "Approved":
            verification.verification_status = "Approved"
            verification.approved_at = timezone.now()
            action_str = "Presidential Executive Approval Completed"
        elif decision == "Rejected":
            if not remarks:
                return JsonResponse(
                    {
                        "success": False,
                        "message": "Remarks are mandatory for rejections.",
                    },
                    status=400,
                )
            route_back_to_treasurer(
                verification.table_name,
                verification.record_id,
                officer,
                remarks,
                request,
                details="Your payment/claim was returned for revision by the President.",
            )
            _broadcast_pending_counts()
            return JsonResponse(
                {
                    "success": True,
                    "message": "Transaction returned to the Treasurer for revision.",
                }
            )
        else:
            return JsonResponse(
                {"success": False, "message": "Invalid decision route."}, status=400
            )

        verification.president_id_FK = officer
        verification.save()

        if verification.verification_status == "Approved":
            archive = archive_transaction(
                verification.table_name,
                verification.record_id,
                officer,
            )
            if archive and verification.table_name in ("membership_fee", "monthly_dues"):
                # Create FundTransaction (inflow) — idempotent per finance record (C3).
                if not FundTransaction.objects.filter(
                    source_type=verification.table_name,
                    source_id=verification.record_id,
                ).exists():
                    FundTransaction.objects.create(
                        direction="inflow",
                        amount=archive.amount,
                        source_type=verification.table_name,
                        source_id=verification.record_id,
                        description=f"{archive.member_name} ({dict(FundTransaction.SOURCE_TYPES).get(verification.table_name, verification.table_name)})",
                        recorded_by_user_id_FK=officer,
                    )

                # Update MonthlyDues approval fields if applicable
                if verification.table_name == "monthly_dues":
                    dues = MonthlyDues.objects.filter(dues_id_PK=verification.record_id).first()
                    if dues:
                        dues.president_status = "President Approved"
                        dues.president_id_FK = officer
                        dues.president_approved_at = timezone.now()
                        dues.payment_status = "Full Payment"
                        dues.treasurer_status = dues.treasurer_status or "Treasurer Verified"
                        if dues.treasurer_status == "Pending Treasurer Review":
                            dues.treasurer_status = "Treasurer Verified"
                        dues.save()

                        # Create MemberLedger entry — idempotent per dues record (C3)
                        if not MemberLedger.objects.filter(
                            reference_type="MonthlyDues",
                            reference_id=dues.dues_id_PK,
                        ).exists():
                            last_ledger = MemberLedger.objects.filter(
                                member_id_FK=dues.member_id_FK
                            ).order_by("-recorded_at").first()
                            balance_after = last_ledger.balance_after if last_ledger else Decimal("0.00")
                            balance_after += dues.amount

                            MemberLedger.objects.create(
                                member_id_FK=dues.member_id_FK,
                                transaction_type="monthly_dues",
                                amount=dues.amount,
                                direction="credit",
                                balance_after=balance_after,
                                reference_id=dues.dues_id_PK,
                                reference_type="MonthlyDues",
                                description=f"Monthly Dues Payment - {dues.month_covered}",
                                recorded_by_user_id_FK=officer,
                            )

                        notify_member(
                            dues.member_id_FK,
                            notification_type="Payment Approved",
                            message=f"Your monthly dues payment for {dues.month_covered} (₱{dues.amount}) has been approved. Thank you for your contribution.",
                            category="payment",
                            sender_name=officer.full_name if officer else "President",
                            sender_role="President",
                            receipt_number=dues.receipt_number or "",
                        )

                        # If this is salary deduction payment, remove any exemption for this month
                        if dues.payment_method == "Salary Deduction":
                            deleted_count, _ = SalaryDeductionExemption.objects.filter(
                                member_id_FK=dues.member_id_FK,
                                month_covered=dues.month_covered
                            ).delete()
                            logger.info("Removed %d salary deduction exemption(s) for member %s month %s", deleted_count, dues.member_id_FK.full_name, dues.month_covered)

                # Walk-in registration: create OfficerUser for members without one
                if verification.table_name == "membership_fee":
                    fee = MembershipFee.objects.filter(fee_id_PK=verification.record_id).select_related("member_id_FK").first()
                    if fee and fee.member_id_FK and not fee.member_id_FK.officer_user_id_FK:
                        member = fee.member_id_FK
                        officer_user, created = OfficerUser.objects.get_or_create(
                            username=member.employee_id or f"member-{member.member_id_PK}",
                            defaults={
                                "full_name": member.full_name,
                                "password_hash": hash_password(member.employee_id or str(member.member_id_PK)),
                                "role": "Member",
                                "email": member.email or "",
                                "account_status": "Active",
                            },
                        )
                        if created:
                            member.officer_user_id_FK = officer_user
                            member.save(update_fields=["officer_user_id_FK"])
                            try:
                                if member.email:
                                    from core_system.services.email_service import send_html_email

                                    send_html_email(
                                        subject="Welcome to ISU CAUFA – Membership Approved!",
                                        recipient_list=[member.email],
                                        html_template="emails/member_added.html",
                                        context={
                                            "full_name": member.full_name,
                                            "employee_id": member.employee_id or "N/A",
                                            "date_joined": member.date_joined.strftime("%B %d, %Y") if member.date_joined else str(timezone.now().date()),
                                            "department": member.department or "",
                                            "monthly_dues_amount": get_monthly_dues_amount(),
                                            "membership_fee_amount": get_membership_fee_amount(),
                                            "officer_contact": "",
                                        },
                                    )
                            except Exception:
                                logger.exception("Failed to enqueue welcome email for walk-in member %s", member.full_name)
                            
                            # Create notification for member about membership approval
                            try:
                                notify_member(
                                    member,
                                    notification_type="Membership Approved",
                                    message="Welcome to ISU CAUFA! Your membership has been approved. You can now access all member benefits and services.",
                                    category="membership",
                                    sender_name=officer.full_name if officer else "President",
                                    sender_role="President",
                                )
                            except Exception as e:
                                logger.warning("Failed to send membership approval notification to member %s: %s", member.member_id_PK, e)

                    # Create MemberLedger entry for Membership Fee — idempotent
                    # per fee record so re-approving a walk-in fee cannot double-credit.
                    if fee and fee.member_id_FK:
                        if not MemberLedger.objects.filter(
                            reference_type="MembershipFee",
                            reference_id=fee.fee_id_PK,
                        ).exists():
                            last_ledger = MemberLedger.objects.filter(
                                member_id_FK=fee.member_id_FK
                            ).order_by("-recorded_at").first()
                            balance_after = last_ledger.balance_after if last_ledger else Decimal("0.00")
                            balance_after += fee.amount

                            MemberLedger.objects.create(
                                member_id_FK=fee.member_id_FK,
                                transaction_type="membership_fee",
                                amount=fee.amount,
                                direction="credit",
                                balance_after=balance_after,
                                reference_id=fee.fee_id_PK,
                                reference_type="MembershipFee",
                                description=f"Membership Fee Payment",
                                recorded_by_user_id_FK=officer,
                            )

                    # Notify member
                    if fee and fee.member_id_FK:
                        notify_member(
                            fee.member_id_FK,
                            notification_type="Payment Approved",
                            message="Your membership fee payment has been approved by the President. Welcome to ISU CAUFA!",
                            category="payment",
                            sender_name=officer.full_name if officer else "President",
                            sender_role="President",
                            receipt_number=fee.receipt_number or "",
                        )

        _record_audit_trail(
            table=verification.table_name,
            record_id=verification.record_id,
            action=(
                "APPROVED"
                if verification.verification_status == "Approved"
                else "REJECTED"
            ),
            actor=officer,
            notes=remarks or None,
            ip=request.META.get("REMOTE_ADDR"),
        )

        _broadcast_pending_counts()
        return JsonResponse(
            {
                "success": True,
                "message": f"Transaction status updated to {verification.verification_status}.",
            }
        )
    except Exception as e:
        return JsonResponse({"success": False, "message": str(e)}, status=500)


@require_http_methods(["POST"])
@transaction.atomic
def submit_presidential_aid_decision(request):
    guard = require_role(request, role="President")
    if guard is not None:
        return guard
    # ZT check removed during transition
    try:
        body = json.loads(request.body)
        target_id = (body.get("target_id") or "").strip()
        decision = (body.get("decision") or "").strip()
        approved_amount = body.get("approved_amount")
        remarks = (body.get("remarks") or "").strip()

        if not target_id:
            return JsonResponse(
                {"success": False, "message": "Missing target_id."},
                status=400,
            )

        if decision not in {"Approved", "Rejected"}:
            return JsonResponse(
                {
                    "success": False,
                    "message": "Invalid decision value. Use Approved or Rejected.",
                },
                status=400,
            )

        try:
            approved_amount = float(approved_amount)
        except (TypeError, ValueError):
            return JsonResponse(
                {"success": False, "message": "Approved amount must be a number."},
                status=400,
            )

        if approved_amount <= 0:
            return JsonResponse(
                {
                    "success": False,
                    "message": "Approved amount must be greater than zero.",
                },
                status=400,
            )

        if decision == "Rejected" and not remarks:
            return JsonResponse(
                {"success": False, "message": "Remarks are mandatory for rejections."},
                status=400,
            )

        stored_officer_id = request.session.get("officer_id")
        if stored_officer_id is None:
            return JsonResponse(
                {"success": False, "message": "Officer session missing."},
                status=401,
            )
        officer = get_object_or_404(OfficerUser, user_id_PK=int(stored_officer_id))

        table_name = None
        record = None

        if target_id.startswith("medical-"):
            record_id = int(target_id.replace("medical-", ""))
            record = get_object_or_404(MedicalAid, medical_aid_id_PK=record_id)
            table_name = "medical_aid"
        elif target_id.startswith("death-"):
            record_id = int(target_id.replace("death-", ""))
            record = get_object_or_404(DeathAid, death_aid_id_PK=record_id)
            table_name = "death_aid"
        else:
            return JsonResponse(
                {"success": False, "message": "Invalid target_id format."},
                status=400,
            )

        # Status gate: only allow acting on records in an auditor-verified state (S7).
        if record.status not in ("Auditor Verified", "Pending Auditor Verification", "Pending"):
            return JsonResponse(
                {
                    "success": False,
                    "message": "Aid request is not in a state that can be acted upon by the President.",
                },
                status=409,
            )

        # Active contributors determine the total payout = approved per-member
        # contribution x member count (excludes retired members and the requester).
        active_contributors = Member.objects.exclude(
            membership_status__iexact="Retired",
        )
        requester_member = None
        if record is not None and hasattr(record, "member_id_FK") and record.member_id_FK:
            requester_member = record.member_id_FK
            active_contributors = active_contributors.exclude(
                member_id_PK=requester_member.member_id_PK
            )
        contributor_count = active_contributors.count()

        payout_total = (
            Decimal(str(approved_amount)) * Decimal(str(contributor_count))
            if decision == "Approved"
            else approved_amount
        )

        if table_name == "medical_aid" and decision == "Approved":
            # Note: for Treasurer-created medical aids `requested_amount` is 0
            # or the ₱100 per-member benefit, so the hospital bill is the only
            # reliable ceiling for the total payout.
            hospital_bill = float(record.hospital_bill_amount or 0)
            if payout_total > hospital_bill:
                return JsonResponse(
                    {
                        "success": False,
                        "message": f"Total approved payout (₱{payout_total:,.2f}) cannot exceed the hospital bill amount (₱{hospital_bill:,.2f}).",
                    },
                    status=400,
                )

        record.president_decided_by_user_id_FK = officer
        record.president_decision = decision
        record.status = decision
        extra_fields = ["president_decided_by_user_id_FK", "president_decision", "status"]
        if table_name == "medical_aid" and decision == "Approved" and approved_amount:
            record.validated_aid_amount = payout_total
            extra_fields.append("validated_aid_amount")
        if table_name == "death_aid" and decision == "Approved" and approved_amount:
            record.benefit_amount = payout_total
            extra_fields.append("benefit_amount")
        record.save(update_fields=extra_fields)

        # Send notification to member about President approval
        if decision == "Approved" and record.member_id_FK:
            try:
                from core_system.services.notifications import notify_member
                aid_label = "Medical Aid" if table_name == "medical_aid" else "Death Aid"
                notify_member(
                    record.member_id_FK,
                    notification_type="Claim Approved",
                    message=f"Your {aid_label} claim has been approved by the President (total payout ₱{payout_total:,.2f}). The Treasurer will now release the funds.",
                    category="claim",
                    sender_name=officer.full_name if officer else "President",
                    sender_role="President",
                )
            except Exception as e:
                logger.warning("Failed to send President approval notification to member %s: %s", record.member_id_FK.member_id_PK, e)

        if decision == "Approved":
            archive = archive_transaction(
                table_name,
                record.pk,
                officer,
            )

            relationship = ""
            if table_name == "death_aid":
                relationship = getattr(record, "relationship_to_member", "")

            active_members_for_post = active_contributors
            member_count = contributor_count

            # System-controlled contribution amount — never derived from the approved amount.
            per_member_amount = Decimal(str(get_contribution_amount_for_aid(table_name, relationship)))
            if per_member_amount <= 0:
                return JsonResponse(
                    {
                        "success": False,
                        "message": f"Could not determine a valid contribution amount for {table_name}.",
                    },
                    status=400,
                )
            total_expected = per_member_amount * Decimal(str(member_count))

            post = AidTrackingPost.objects.create(
                archive_id_FK=archive,
                aid_type=table_name,
                target_month=timezone.now().strftime("%Y-%m"),
                total_expected=total_expected,
                total_collected=0,
                status="tracking",
                source_type=table_name,
                source_id=record.pk,
                created_by_user_id_FK=officer,
            )

            contribution_rows = [
                Contribution(
                    aid_tracking_post_id_FK=post,
                    member_id_FK=member,
                    expected_amount=per_member_amount,
                    paid_amount=0,
                    status="NOT_PAID",
                )
                for member in active_members_for_post
            ]

            # The requesting member is not included in contributing to this aid case.
            if requester_member is not None:
                contribution_rows.append(
                    Contribution(
                        aid_tracking_post_id_FK=post,
                        member_id_FK=requester_member,
                        expected_amount=per_member_amount,
                        paid_amount=0,
                        status=Contribution.STATUS_EXCLUDED_REQUESTER,
                        notes="Requesting member is not included in contributing to this aid case.",
                    )
                )

            Contribution.objects.bulk_create(contribution_rows)

            transaction.on_commit(
                lambda r=record, tn=table_name, pm=per_member_amount: send_aid_emails(r, tn, pm)
            )

        else:
            route_back_to_treasurer(
                table_name,
                record.pk,
                officer,
                remarks,
                request,
                member=getattr(record, "member_id_FK", None),
                details=f"Your {table_name.replace('_', ' ')} request was returned for revision by the President.",
            )
            _broadcast_to_group("treasurer_dashboard", {"type": "data_changed", "section": "aids"})
            _broadcast_pending_counts()
            return JsonResponse(
                {"success": True, "message": "Aid request returned to the Treasurer for revision."}
            )

        TransactionVerification.objects.filter(
            table_name=table_name,
            record_id=record.pk,
        ).update(
            verification_status=decision,
            president_id_FK=officer,
            approved_at=timezone.now(),
        )

        try:
            notify_member(
                record.member_id_FK,
                notification_type="Claim Approved",
                message=f"Your {'Medical Aid' if table_name == 'medical_aid' else 'Death Aid'} claim has been approved by the President (₱{approved_amount:,.2f}).",
                category="claim",
                sender_name=officer.full_name if officer else "President",
                sender_role="President",
            )
        except Exception:
            logger.exception("President aid approval notification failed")

        _record_audit_trail(
            table=table_name,
            record_id=record.pk,
            action="APPROVED" if decision == "Approved" else "REJECTED",
            actor=officer,
            new={
                "president_decision": decision,
                "approved_amount": approved_amount,
                "action": f"Presidential {decision}",
            },
            notes=remarks or (f"Presidential {decision}" if decision == "Rejected" else None),
            ip=request.META.get("REMOTE_ADDR"),
        )

        transaction.on_commit(lambda: _broadcast_to_group(
            "treasurer_dashboard", {"type": "data_changed", "section": "aids"}
        ))
        transaction.on_commit(_broadcast_pending_counts)
        if decision == "Approved":
            payload = {
                "type": "aid_post_created",
                "post_id": post.post_id_PK,
                "member_name": record.member_id_FK.full_name
                if hasattr(record, "member_id_FK") and record.member_id_FK
                else "",
                "aid_type": table_name,
                "total_expected": float(total_expected),
                "target_month": post.target_month,
            }
            transaction.on_commit(lambda: async_to_sync(get_channel_layer().group_send)("auditor_dashboard", payload))
            transaction.on_commit(lambda: async_to_sync(get_channel_layer().group_send)("treasurer_dashboard", payload))

        return JsonResponse(
            {
                "success": True,
                "message": f"Aid request {decision.lower()} recorded successfully.",
            }
        )
    except Exception as e:
        return JsonResponse({"success": False, "message": str(e)}, status=500)


@require_POST
@transaction.atomic
def submit_presidential_decision_batch(request):
    guard = require_role(request, role="President")
    if guard is not None:
        return guard
    # ZT check removed during transition
    try:
        body = json.loads(request.body)
        ids = body.get("ids", [])
        decision = (body.get("decision") or "").strip()
        remarks = (body.get("remarks") or "").strip()

        if not ids or not isinstance(ids, list):
            return JsonResponse({"success": False, "message": "ids must be a non-empty array."}, status=400)
        if decision not in {"Approved", "Rejected"}:
            return JsonResponse({"success": False, "message": "Invalid decision. Use Approved or Rejected."}, status=400)
        if decision == "Rejected" and not remarks:
            return JsonResponse({"success": False, "message": "Remarks are mandatory for rejections."}, status=400)

        stored_officer_id = request.session.get("officer_id")
        if stored_officer_id is None:
            return JsonResponse({"success": False, "message": "Officer session missing."}, status=401)
        officer = get_object_or_404(OfficerUser, user_id_PK=int(stored_officer_id))

        verifications = TransactionVerification.objects.select_for_update().filter(
            verification_id__in=ids,
        )
        existing_map = {v.verification_id: v for v in verifications}

        processed = 0
        skipped = 0
        audit_entries = []
        fund_transactions = []
        ip_address = request.META.get("REMOTE_ADDR")
        for vid in ids:
            v = existing_map.get(vid)
            if v is None:
                skipped += 1
                continue
            if not can_president_act(v.verification_status):
                skipped += 1
                continue

            if decision == Status.APPROVED:
                v.verification_status = Status.APPROVED
                v.approved_at = timezone.now()
                action_str = "APPROVED"
            else:
                route_back_to_treasurer(
                    v.table_name,
                    v.record_id,
                    officer,
                    remarks,
                    request,
                )
                v.verification_status = Status.RETURNED_REVISION
                v.returned_reason = remarks
                action_str = "RETURNED"

            v.president_id_FK = officer
            if decision == Status.APPROVED:
                v.save()
            else:
                v.save(update_fields=["verification_status", "returned_reason", "president_id_FK"])

            if decision == "Approved":
                archive = archive_transaction(v.table_name, v.record_id, officer)
                if archive and v.table_name in ("membership_fee", "monthly_dues"):
                    # Idempotent: skip if a FundTransaction already exists for this record (C3).
                    if not FundTransaction.objects.filter(
                        source_type=v.table_name,
                        source_id=v.record_id,
                    ).exists():
                        fund_transactions.append(
                            FundTransaction(
                                direction="inflow",
                                amount=archive.amount,
                                source_type=v.table_name,
                                source_id=v.record_id,
                                description=f"{archive.member_name} ({dict(FundTransaction.SOURCE_TYPES).get(v.table_name, v.table_name)})",
                                recorded_by_user_id_FK=officer,
                            )
                        )

                # B4: Also update the MonthlyDues record and create ledger entry for batch approval.
                if v.table_name == "monthly_dues":
                    dues = MonthlyDues.objects.filter(dues_id_PK=v.record_id).first()
                    if dues:
                        dues.president_status = "President Approved"
                        dues.president_id_FK = officer
                        dues.president_approved_at = timezone.now()
                        dues.payment_status = "Full Payment"
                        dues.treasurer_status = dues.treasurer_status or "Treasurer Verified"
                        if dues.treasurer_status == "Pending Treasurer Review":
                            dues.treasurer_status = "Treasurer Verified"
                        dues.save()

                        # Idempotent MemberLedger write — one entry per dues record.
                        if not MemberLedger.objects.filter(
                            reference_type="MonthlyDues",
                            reference_id=dues.dues_id_PK,
                        ).exists():
                            last_ledger = MemberLedger.objects.filter(
                                member_id_FK=dues.member_id_FK
                            ).order_by("-recorded_at").first()
                            balance_after = last_ledger.balance_after if last_ledger else Decimal("0.00")
                            balance_after += dues.amount

                        MemberLedger.objects.create(
                            member_id_FK=dues.member_id_FK,
                            transaction_type="monthly_dues",
                            amount=dues.amount,
                            direction="credit",
                            balance_after=balance_after,
                            reference_id=dues.dues_id_PK,
                            reference_type="MonthlyDues",
                            description=f"Monthly Dues Payment - {dues.month_covered}",
                            recorded_by_user_id_FK=officer,
                        )

                        # Notify member using notification service for consistent HTML email handling
                        try:
                            from core_system.services.notifications import notify_member
                            notify_member(
                                dues.member_id_FK,
                                notification_type="Payment Approved",
                                message=f"Your monthly dues payment for {dues.month_covered} (₱{dues.amount}) has been approved. Thank you for your contribution.",
                                category="payment",
                                sender_name=officer.full_name if officer else "President",
                                sender_role="President",
                                receipt_number=dues.receipt_number or "",
                            )
                        except Exception as e:
                            logger.warning("Failed to send payment approval notification to member %s: %s", dues.member_id_FK.member_id_PK, e)

                        # If this is salary deduction payment, remove any exemption for this month
                        if dues.payment_method == "Salary Deduction":
                            deleted_count, _ = SalaryDeductionExemption.objects.filter(
                                member_id_FK=dues.member_id_FK,
                                month_covered=dues.month_covered
                            ).delete()
                            logger.info("Removed %d salary deduction exemption(s) for member %s month %s", deleted_count, dues.member_id_FK.full_name, dues.month_covered)
                elif v.table_name == "membership_fee":
                    fee = MembershipFee.objects.filter(fee_id_PK=v.record_id).first()
                    if fee and fee.member_id_FK:
                        # Idempotent MemberLedger write — one entry per fee record (C3).
                        if not MemberLedger.objects.filter(
                            reference_type="MembershipFee",
                            reference_id=fee.fee_id_PK,
                        ).exists():
                            last_ledger = MemberLedger.objects.filter(
                                member_id_FK=fee.member_id_FK
                            ).order_by("-recorded_at").first()
                            balance_after = last_ledger.balance_after if last_ledger else Decimal("0.00")
                            balance_after += fee.amount

                            MemberLedger.objects.create(
                                member_id_FK=fee.member_id_FK,
                                transaction_type="membership_fee",
                                amount=fee.amount,
                                direction="credit",
                                balance_after=balance_after,
                                reference_id=fee.fee_id_PK,
                                reference_type="MembershipFee",
                                description=f"Membership Fee Payment",
                                recorded_by_user_id_FK=officer,
                            )

            audit_entries.append({
                "table": v.table_name,
                "record_id": v.record_id,
                "action": action_str,
                "ip": ip_address,
                "notes": remarks.strip() if remarks else None,
            })
            processed += 1

        if audit_entries:
            _record_bulk_audit_trail(audit_entries, actor=officer)

        if fund_transactions:
            FundTransaction.objects.bulk_create(fund_transactions)

        _broadcast_pending_counts()
        return JsonResponse({
            "success": True,
            "processed": processed,
            "skipped": skipped,
            "message": f"Processed {processed} entr{processed == 1 and 'y' or 'ies'} ({skipped} skipped).",
        })
    except Exception as e:
        return JsonResponse({"success": False, "message": str(e)}, status=500)


@require_POST
@transaction.atomic
def submit_presidential_aid_decision_batch(request):
    guard = require_role(request, role="President")
    if guard is not None:
        return guard
    # ZT check removed during transition
    try:
        body = json.loads(request.body)
        ids = body.get("ids", [])
        decision = (body.get("decision") or "").strip()
        remarks = (body.get("remarks") or "").strip()

        if not ids or not isinstance(ids, list):
            return JsonResponse({"success": False, "message": "ids must be a non-empty array."}, status=400)
        if decision not in {"Approved", "Rejected"}:
            return JsonResponse({"success": False, "message": "Invalid decision. Use Approved or Rejected."}, status=400)
        if decision == "Rejected" and not remarks:
            return JsonResponse({"success": False, "message": "Remarks are mandatory for rejections."}, status=400)

        stored_officer_id = request.session.get("officer_id")
        if stored_officer_id is None:
            return JsonResponse({"success": False, "message": "Officer session missing."}, status=401)
        officer = get_object_or_404(OfficerUser, user_id_PK=int(stored_officer_id))

        table_record_pairs = []
        for raw_id in ids:
            if not isinstance(raw_id, str):
                return JsonResponse({"success": False, "message": "Invalid id format."}, status=400)
            if raw_id.startswith("medical-"):
                table_name = "medical_aid"
                record_id = raw_id.replace("medical-", "")
            elif raw_id.startswith("death-"):
                table_name = "death_aid"
                record_id = raw_id.replace("death-", "")
            else:
                return JsonResponse({"success": False, "message": f"Invalid id format: {raw_id}"}, status=400)
            try:
                table_record_pairs.append((table_name, int(record_id)))
            except ValueError:
                return JsonResponse({"success": False, "message": f"Invalid record id in: {raw_id}"}, status=400)

        from collections import defaultdict
        from itertools import chain
        table_ids = defaultdict(list)
        for tn, rid in table_record_pairs:
            table_ids[tn].append(rid)

        verifications = TransactionVerification.objects.select_for_update().filter(
            table_name__in=list(table_ids.keys()),
            record_id__in=set(chain.from_iterable(table_ids.values())),
        )
        existing_map = {}
        for tv in verifications:
            key = (tv.table_name, tv.record_id)
            existing_map[key] = tv

        active_members = Member.objects.exclude(
            membership_status__iexact="Retired",
        )
        active_members_count = active_members.count()

        processed = 0
        skipped = 0
        audit_entries = []
        ip_address = request.META.get("REMOTE_ADDR")
        for tn, rid in table_record_pairs:
            v = existing_map.get((tn, rid))
            if v is None:
                skipped += 1
                continue
            if not can_president_act(v.verification_status):
                skipped += 1
                continue

            canonical_decision = Status.APPROVED if is_approved(decision) else Status.RETURNED_REVISION

            record = None
            if v.table_name == "medical_aid":
                record = MedicalAid.objects.filter(medical_aid_id_PK=v.record_id).first()
            elif v.table_name == "death_aid":
                record = DeathAid.objects.filter(death_aid_id_PK=v.record_id).first()

            if record is not None:
                record.president_decided_by_user_id_FK = officer
                record.president_decision = decision
                record.status = canonical_decision
                record.save(update_fields=[
                    "president_decided_by_user_id_FK",
                    "president_decision",
                    "status",
                ])

            v.verification_status = canonical_decision
            if is_approved(decision):
                v.approved_at = timezone.now()
            else:
                route_back_to_treasurer(
                    v.table_name,
                    v.record_id,
                    officer,
                    remarks,
                    request,
                    member=getattr(record, "member_id_FK", None) if record is not None else None,
                    details=f"Your {v.table_name.replace('_', ' ')} request was returned for revision by the President.",
                )
                v.returned_reason = remarks

            v.president_id_FK = officer
            v.save(update_fields=["verification_status", "approved_at", "president_id_FK", "returned_reason"])

            if is_approved(decision):
                archive = archive_transaction(v.table_name, v.record_id, officer)

                if archive is not None:
                    relationship = ""
                    if v.table_name == "death_aid" and record is not None:
                        relationship = getattr(record, "relationship_to_member", "")

                    requester_member = None
                    if record is not None and hasattr(record, "member_id_FK") and record.member_id_FK:
                        requester_member = record.member_id_FK
                        active_members_for_post = active_members.exclude(member_id_PK=requester_member.member_id_PK)
                    else:
                        active_members_for_post = active_members
                    active_members_count_for_post = active_members_for_post.count()

                    per_member_amount = get_contribution_amount_for_aid(v.table_name, relationship)
                    if per_member_amount <= 0:
                        skipped += 1
                        continue
                    total_expected = active_members_count_for_post * per_member_amount

                    if AidTrackingPost.objects.filter(
                        source_type=v.table_name,
                        source_id=v.record_id,
                    ).exists():
                        skipped += 1
                        continue

                    post = AidTrackingPost.objects.create(
                        archive_id_FK=archive,
                        aid_type=v.table_name,
                        target_month=timezone.now().strftime("%Y-%m"),
                        total_expected=total_expected,
                        total_collected=0,
                        source_type=v.table_name,
                        source_id=v.record_id,
                        created_by_user_id_FK=officer,
                    )

                    contribution_rows = [
                        Contribution(
                            aid_tracking_post_id_FK=post,
                            member_id_FK=member,
                            expected_amount=per_member_amount,
                            paid_amount=0,
                            status="NOT_PAID",
                        )
                        for member in active_members_for_post
                    ]

                    # The requesting member is not included in contributing to this aid case.
                    if requester_member is not None:
                        contribution_rows.append(
                            Contribution(
                                aid_tracking_post_id_FK=post,
                                member_id_FK=requester_member,
                                expected_amount=per_member_amount,
                                paid_amount=0,
                                status=Contribution.STATUS_EXCLUDED_REQUESTER,
                                notes="Requesting member is not included in contributing to this aid case.",
                            )
                        )

                    Contribution.objects.bulk_create(contribution_rows)

                    transaction.on_commit(
                        lambda r=record, tn=v.table_name, pm=per_member_amount: send_aid_emails(r, tn, pm)
                    )

                    member_name = record.member_id_FK.full_name if record is not None and hasattr(record, "member_id_FK") and record.member_id_FK else ""
                    payload = {
                        "type": "aid_post_created",
                        "post_id": post.post_id_PK,
                        "member_name": member_name,
                        "aid_type": v.table_name,
                        "total_expected": float(total_expected),
                        "target_month": post.target_month,
                    }
                    _broadcast_to_group("auditor_dashboard", payload)
                    _broadcast_to_group("treasurer_dashboard", payload)

            audit_entries.append({
                "table": v.table_name,
                "record_id": v.record_id,
                "action": "APPROVED" if decision == "Approved" else "REJECTED",
                "ip": ip_address,
                "notes": remarks.strip() if remarks else None,
            })
            processed += 1

        if audit_entries:
            _record_bulk_audit_trail(audit_entries, actor=officer)

        _broadcast_pending_counts()
        _broadcast_to_group("treasurer_dashboard", {"type": "data_changed", "section": "aids"})
        return JsonResponse({
            "success": True,
            "processed": processed,
            "skipped": skipped,
            "message": f"Processed {processed} entr{processed == 1 and 'y' or 'ies'} ({skipped} skipped).",
        })
    except Exception as e:
        return JsonResponse({"success": False, "message": str(e)}, status=500)


@require_GET
def president_kpi_counts(request: HttpRequest):
    guard = require_role(request, role="President")
    if guard is not None:
        return guard

    verified_dues_count = TransactionVerification.objects.filter(
        table_name__in=["membership_fee", "monthly_dues"],
        verification_status="Auditor Verified",
        auditor_id_FK__isnull=False,
        president_id_FK__isnull=True,
    ).count()

    active_claim_statuses = (Status.ALL_PENDING | Status.ALL_AUDITOR_VERIFIED) - {Status.RELEASED, Status.COMPLETED}
    medical_pending = MedicalAid.objects.filter(
        status__in=active_claim_statuses,
        president_decided_by_user_id_FK__isnull=True,
    ).count()
    death_pending = DeathAid.objects.filter(
        status__in=active_claim_statuses,
        president_decided_by_user_id_FK__isnull=True,
    ).count()
    verified_claims_count = medical_pending + death_pending

    verified_contributions_count = TransactionVerification.objects.filter(
        table_name="contribution",
        target_category="aid_contribution",
        verification_status="Auditor Verified",
        auditor_id_FK__isnull=False,
        president_id_FK__isnull=True,
    ).count()

    payment_decisions = TransactionVerification.objects.filter(
        president_id_FK__isnull=False,
    ).count()
    aid_decisions = MedicalAid.objects.filter(
        president_decided_by_user_id_FK__isnull=False,
    ).count() + DeathAid.objects.filter(
        president_decided_by_user_id_FK__isnull=False,
    ).count()
    contribution_decisions = TransactionVerification.objects.filter(
        table_name="contribution",
        president_id_FK__isnull=False,
    ).count()
    total_approvals_count = payment_decisions + aid_decisions + contribution_decisions

    today = timezone.localdate()
    month_key = f"{today.year}-{today.month:02d}"
    active_members = Member.objects.exclude(membership_status__iexact="retired")
    paid_member_ids = set(MonthlyDues.objects.filter(
        month_covered=month_key,
        payment_status__in=list(Status.ALL_AUDITOR_VERIFIED),
    ).values_list("member_id_FK_id", flat=True))
    paid_member_ids.update(MembershipFee.objects.filter(
        payment_status__in=list(Status.ALL_AUDITOR_VERIFIED),
    ).values_list("member_id_FK_id", flat=True))
    dept_rows = (
        active_members.filter(department__isnull=False).exclude(department="")
        .values("department")
        .annotate(
            total_members=Count("member_id_PK"),
            paid_count=Count("member_id_PK", filter=Q(member_id_PK__in=paid_member_ids)),
        )
    )
    dept_summary = [
        {
            "department_name": r["department"],
            "total_members": r["total_members"],
            "paid_count": r["paid_count"],
            "unpaid_count": r["total_members"] - r["paid_count"],
            "percentage": round(r["paid_count"] / r["total_members"] * 100, 1) if r["total_members"] else 0.0,
        }
        for r in dept_rows
    ]
    total_active = sum(d["total_members"] for d in dept_summary)
    total_paid = sum(d["paid_count"] for d in dept_summary)
    total_unpaid = sum(d["unpaid_count"] for d in dept_summary)
    overall_pct = round(total_paid / total_active * 100, 1) if total_active else 0.0
    low_depts = [
        {"name": d["department_name"], "pct": d["percentage"]}
        for d in dept_summary if d["percentage"] < 70
    ]
    sorted_depts = sorted(dept_summary, key=lambda d: d["percentage"], reverse=True)
    top_depts = [{"name": d["department_name"], "pct": d["percentage"]} for d in sorted_depts[:3]]
    bottom_depts = [{"name": d["department_name"], "pct": d["percentage"]} for d in sorted_depts[-3:]] if len(sorted_depts) >= 3 else []

    return JsonResponse({
        "ok": True,
        "verified_dues_count": verified_dues_count,
        "verified_claims_count": verified_claims_count,
        "verified_contributions_count": verified_contributions_count,
        "total_approvals_count": total_approvals_count,
        "total_active_members": total_active,
        "overall_compliance_percentage": overall_pct,
        "total_paid": total_paid,
        "total_unpaid": total_unpaid,
        "departments_below_threshold": low_depts,
        "top_performing_departments": top_depts,
        "bottom_performing_departments": bottom_depts,
    })


# ============================================================================
# PRESIDENT: VISUALIZATION DATA ENDPOINTS
# ============================================================================

# ==========================================================================
# PRESIDENT OVERVIEW — one-shot aggregator for the executive dashboard
# (mockup president-app.html parity — everything computed from real records)
# ==========================================================================

@require_GET
def president_overview(request: HttpRequest):
    guard = require_role(request, role="President")
    if guard is not None:
        return guard

    today = timezone.localdate()
    year, month = today.year, today.month
    month_label = f"{MONTH_NAMES[month - 1]} {year}"

    # ---------------- Fund aggregates (whole ledger) ----------------
    totals = FundTransaction.objects.aggregate(
        total_in=Sum("amount", filter=Q(direction="inflow")),
        total_out=Sum("amount", filter=Q(direction="outflow")),
    )
    total_in = float(totals["total_in"] or 0)
    total_out = float(totals["total_out"] or 0)
    fund_balance = total_in - total_out
    opening_balance = fund_balance - total_in + total_out

    # Year-to-date collections (monthly dues inflows this year)
    ytd_collections = float(
        FundTransaction.objects.filter(
            direction="inflow",
            source_type="monthly_dues",
            recorded_at__year=year,
        ).aggregate(s=Sum("amount"))["s"] or 0
    )

    # ---------------- Monthly series (12 months of `year`) ----------------
    inflow_map: Dict[int, float] = {}
    outflow_map: Dict[int, float] = {}
    collection_map: Dict[int, float] = {}
    yearly_collections: Dict[int, float] = {}

    for ft in FundTransaction.objects.filter(
        Q(recorded_at__year=year) | Q(source_type="monthly_dues", direction="inflow")
    ).iterator():
        mth = ft.recorded_at.month
        amount = float(ft.amount)
        if ft.recorded_at.year == year:
            if ft.direction == "inflow":
                inflow_map[mth] = inflow_map.get(mth, 0) + amount
            else:
                outflow_map[mth] = outflow_map.get(mth, 0) + amount
        if ft.direction == "inflow" and ft.source_type == "monthly_dues":
            yr = ft.recorded_at.year
            yearly_collections[yr] = yearly_collections.get(yr, 0) + amount
            if ft.recorded_at.year == year:
                collection_map[mth] = collection_map.get(mth, 0) + amount

    months = []
    inflow_series = []
    outflow_series = []
    collection_series = []
    balance_series = []
    running = opening_balance
    for mth in range(1, 13):
        months.append(f"{year}-{mth:02d}")
        inflow_series.append(round(inflow_map.get(mth, 0), 2))
        outflow_series.append(round(outflow_map.get(mth, 0), 2))
        collection_series.append(round(collection_map.get(mth, 0), 2))
        running += inflow_map.get(mth, 0) - outflow_map.get(mth, 0)
        balance_series.append(round(running, 2))

    yearly_list = [
        {"year": yr, "total": round(yearly_collections[yr], 2)}
        for yr in sorted(yearly_collections)
    ][-6:]

    # ---------------- Monthly fund summary (breakdowns) ----------------
    month_tx = FundTransaction.objects.filter(
        recorded_at__year=year, recorded_at__month=month,
    )
    month_in = float(
        month_tx.filter(direction="inflow").aggregate(s=Sum("amount"))["s"] or 0
    )
    month_out = float(
        month_tx.filter(direction="outflow").aggregate(s=Sum("amount"))["s"] or 0
    )
    month_opening = fund_balance - month_in + month_out

    inflow_breakdown = {"Monthly Dues": 0.0, "Membership Fees": 0.0, "Aid Contributions": 0.0, "Other": 0.0}
    outflow_breakdown = {"Medical Aid": 0.0, "Death Aid": 0.0, "Other": 0.0}
    inflow_labels = {"monthly_dues": "Monthly Dues", "membership_fee": "Membership Fees", "contribution": "Aid Contributions"}
    outflow_labels = {"medical_aid": "Medical Aid", "death_aid": "Death Aid"}
    for ft in month_tx:
        amount = float(ft.amount)
        if ft.direction == "inflow":
            key = inflow_labels.get(ft.source_type, "Other")
            inflow_breakdown[key] = inflow_breakdown.get(key, 0) + amount
        else:
            key = outflow_labels.get(ft.source_type, "Other")
            outflow_breakdown[key] = outflow_breakdown.get(key, 0) + amount

    # ---------------- Dues compliance + departments ----------------
    # Members carry their department as a CharField (not the Department FK),
    # so group by Member.department — same convention as the compliance heatmap.
    month_key = f"{year}-{month:02d}"
    active_members = Member.objects.exclude(membership_status__iexact="retired")

    dues_rows = list(
        MonthlyDues.objects.filter(month_covered=month_key).select_related("member_id_FK")
    )
    paid_member_ids = set()
    pending_member_ids = set()
    for d in dues_rows:
        if d.payment_status in list(Status.ALL_AUDITOR_VERIFIED):
            paid_member_ids.add(d.member_id_FK_id)
        elif d.payment_status in list(Status.ALL_PENDING):
            pending_member_ids.add(d.member_id_FK_id)
    # Members who paid via a one-time verified MembershipFee count as paid too
    for fee in MembershipFee.objects.filter(payment_status__in=list(Status.ALL_AUDITOR_VERIFIED)):
        paid_member_ids.add(fee.member_id_FK_id)

    dept_names = sorted(
        active_members.filter(department__isnull=False)
        .exclude(department="")
        .values_list("department", flat=True)
        .distinct()
    )
    members_by_dept: Dict[str, list] = {}
    for m in active_members.filter(department__isnull=False).exclude(department=""):
        members_by_dept.setdefault(m.department, []).append(m)

    departments = []
    for dept in dept_names:
        dept_members = members_by_dept.get(dept, [])
        total = len(dept_members)
        paid = sum(1 for m in dept_members if m.member_id_PK in paid_member_ids)
        pending_ct = sum(1 for m in dept_members if m.member_id_PK in pending_member_ids and m.member_id_PK not in paid_member_ids)
        unpaid_ct = max(0, total - paid - pending_ct)
        pct = round(paid / total * 100, 1) if total else 0.0
        if pct >= 90:
            band = {"cls": "excellent", "label": "Excellent"}
        elif pct >= 75:
            band = {"cls": "good", "label": "Good"}
        elif pct >= 50:
            band = {"cls": "attention", "label": "Needs Attention"}
        else:
            band = {"cls": "critical", "label": "Immediate Follow-up"}
        departments.append({
            "name": dept,
            "members": total,
            "paid": paid,
            "pending": pending_ct,
            "unpaid": unpaid_ct,
            "compliance": pct,
            "band": band,
        })
    departments.sort(key=lambda x: x["compliance"], reverse=True)

    total_members = sum(d["members"] for d in departments)
    total_paid = sum(d["paid"] for d in departments)
    overall_pct = round(total_paid / total_members * 100, 1) if total_members else 0.0

    # ---------------- Action queues ----------------
    active_claim_statuses = (Status.ALL_PENDING | Status.ALL_AUDITOR_VERIFIED) - {
        Status.RELEASED, Status.COMPLETED,
    }

    verified_dues = TransactionVerification.objects.filter(
        table_name__in=["membership_fee", "monthly_dues"],
        verification_status="Auditor Verified",
        auditor_id_FK__isnull=False,
        president_id_FK__isnull=True,
    ).count()
    verified_claims = (
        MedicalAid.objects.filter(
            status__in=active_claim_statuses, president_decided_by_user_id_FK__isnull=True,
        ).count()
        + DeathAid.objects.filter(
            status__in=active_claim_statuses, president_decided_by_user_id_FK__isnull=True,
        ).count()
    )
    verified_contributions = TransactionVerification.objects.filter(
        table_name="contribution",
        target_category="aid_contribution",
        verification_status="Auditor Verified",
        auditor_id_FK__isnull=False,
        president_id_FK__isnull=True,
    ).count()
    pending_registrations = MemberRegistrationRequest.objects.filter(
        status=RegistrationStatus.AUDITOR_VERIFIED,
    ).count()
    ready_for_release = AidTrackingPost.objects.filter(
        is_active=True, finish_status="pending_release",
    ).count()

    pending_release_amount = float(
        Contribution.objects.filter(
            aid_tracking_post_id_FK__finish_status="pending_release",
            aid_tracking_post_id_FK__is_active=True,
        ).aggregate(s=Sum("paid_amount"))["s"] or 0
    )

    action_center = {
        "payments": verified_dues,
        "claims": verified_claims,
        "contributions": verified_contributions,
        "registrations": pending_registrations,
        "releases": ready_for_release,
    }
    action_center["total"] = (
        action_center["payments"] + action_center["claims"]
        + action_center["contributions"] + action_center["registrations"]
    )

    # ---------------- Pending approvals table rows ----------------
    pending_rows = []
    for v in TransactionVerification.objects.filter(
        table_name__in=["membership_fee", "monthly_dues"],
        verification_status="Auditor Verified",
        auditor_id_FK__isnull=False,
        president_id_FK__isnull=True,
    ).order_by("verification_id"):
        if str(v.table_name).lower() == "monthly_dues":
            rec = MonthlyDues.objects.filter(dues_id_PK=v.record_id).select_related("member_id_FK").first()
            rtype = "Monthly Dues"
        else:
            rec = MembershipFee.objects.filter(fee_id_PK=v.record_id).select_related("member_id_FK").first()
            rtype = "Membership Fee"
        if not rec:
            continue
        pending_rows.append({
            "ref": rec.receipt_number or rec.remittance_reference or f"{str(v.table_name).upper()[:4]}-{v.record_id}",
            "type": rtype,
            "from": rec.member_id_FK.full_name,
            "amount": float(rec.amount),
            "submitted": rec.payment_date.strftime("%b %d, %Y") if getattr(rec, "payment_date", None) else "",
            "view": "presidential-payments",
        })

    for m in MedicalAid.objects.filter(
        status="Auditor Verified", president_decided_by_user_id_FK__isnull=True,
    ).select_related("member_id_FK").order_by("-medical_aid_id_PK"):
        pending_rows.append({
            "ref": f"MA-{m.medical_aid_id_PK}",
            "type": "Medical Aid",
            "from": m.member_id_FK.full_name,
            "amount": float(m.validated_aid_amount or m.requested_amount or 0),
            "submitted": m.request_date.strftime("%b %d, %Y") if m.request_date else "",
            "view": "presidential-aid-requests",
        })

    for da in DeathAid.objects.filter(
        status="Auditor Verified", president_decided_by_user_id_FK__isnull=True,
    ).select_related("member_id_FK").order_by("-death_aid_id_PK"):
        cat = DEATH_CATEGORY_LABELS.get(da.relationship_group, "Death Aid")
        pending_rows.append({
            "ref": f"DA-{da.death_aid_id_PK}",
            "type": f"Death Aid — {cat}",
            "from": da.member_id_FK.full_name,
            "amount": float(da.benefit_amount or 0),
            "submitted": da.claim_date.strftime("%b %d, %Y") if da.claim_date else "",
            "view": "presidential-aid-requests",
        })

    for rr in MemberRegistrationRequest.objects.filter(
        status=RegistrationStatus.AUDITOR_VERIFIED,
    ).order_by("-updated_at"):
        pending_rows.append({
            "ref": f"REG-{rr.request_id_PK}",
            "type": "Registration",
            "from": rr.full_name,
            "amount": float(rr.amount or 0),
            "submitted": rr.updated_at.strftime("%b %d, %Y %I:%M %p") if rr.updated_at else "",
            "view": "president-registration-requests",
        })

    for v in TransactionVerification.objects.filter(
        table_name="contribution",
        target_category="aid_contribution",
        verification_status="Auditor Verified",
        auditor_id_FK__isnull=False,
        president_id_FK__isnull=True,
    ).order_by("verification_id"):
        contrib = Contribution.objects.filter(
            contribution_id_PK=v.record_id,
        ).select_related("member_id_FK", "aid_tracking_post_id_FK").first()
        if not contrib:
            continue
        pending_rows.append({
            "ref": f"POST-{contrib.aid_tracking_post_id_FK.post_id_PK}" if contrib.aid_tracking_post_id_FK else f"CP-{v.record_id}",
            "type": "Contribution Post",
            "from": contrib.member_id_FK.full_name if contrib.member_id_FK else "—",
            "amount": float(contrib.paid_amount),
            "submitted": "—",
            "view": "president-finish-approvals",
        })

    # ---------------- Aid summary ----------------
    released_statuses = set(Status.ALL_FINAL) | {"Released", "Completed"}

    def _aid_bucket(rows, amount_key):
        out = {"pending": 0, "approved": 0, "released": 0, "total_amount": 0.0}
        for r in rows:
            st = (r.get("status") or "").strip()
            amt = float(r.get(amount_key) or 0)
            if st in set(Status.ALL_PENDING):
                out["pending"] += 1
            elif st in set(Status.ALL_AUDITOR_VERIFIED):
                out["approved"] += 1
            elif st in released_statuses:
                out["released"] += 1
            else:
                out["pending"] += 1
            out["total_amount"] += amt
        return out

    med_rows = [
        {"status": r.get("status"), "amount": r.get("validated_aid_amount") or r.get("reqAmount") or 0}
        for r in MedicalAid.objects.values("status", "validated_aid_amount", "requested_amount")
    ]
    med_rows = [
        {"status": r["status"], "amount": r["amount"] if r["amount"] not in (None, "") else 0}
        for r in med_rows
    ]
    death_rows = [
        {"status": r["status"], "amount": r["benefit_amount"] or 0}
        for r in DeathAid.objects.values("status", "benefit_amount")
    ]

    aid_requests_count = MedicalAid.objects.count() + DeathAid.objects.count()

    # ---------------- Recent presidential activity ----------------
    activity_qs = GlobalAuditTrail.objects.filter(
        actor_type__icontains="President",
    ).order_by("-timestamp")[:8]
    recent_activity = []
    table_type_map = {
        "monthly_dues": "Monthly Dues",
        "membership_fee": "Membership Fee",
        "medical_aid": "Medical Aid",
        "death_aid": "Death Aid",
        "contribution": "Contribution Post",
        "member_registration_request": "Registration",
    }
    ref_prefix = {
        "monthly_dues": "DUES", "membership_fee": "MF", "medical_aid": "MA",
        "death_aid": "DA", "contribution": "CP", "member_registration_request": "REG",
    }
    for log in activity_qs:
        tlabel = table_type_map.get(str(log.table_name).lower(), str(log.table_name).replace("_", " ").title())
        ref = f"{ref_prefix.get(str(log.table_name).lower(), 'REC')}-{log.record_id}"
        action_label = str(log.action).title().replace("_", " ")
        if "final" in str(log.action).lower():
            action_label = "Final Approval"
        recent_activity.append({
            "type": tlabel,
            "ref": ref,
            "action": action_label,
            "time": log.timestamp.strftime("%B %d, %Y — %I:%M %p") if log.timestamp else "",
        })

    # ---------------- Notifications ----------------
    notifications = []
    if pending_rows:
        by_view = {}
        for r in pending_rows:
            if r["view"] not in by_view:
                by_view[r["view"]] = r
        first_payment = by_view.get("presidential-payments")
        first_aid = by_view.get("presidential-aid-requests")
        first_reg = by_view.get("president-registration-requests")
        first_contrib = by_view.get("president-finish-approvals")
        if first_payment:
            notifications.append({"cls": "blue", "icon": "fa-file-invoice-dollar", "title": f"{first_payment['type']} — {first_payment['from']}", "sub": "Awaiting final approval", "time": first_payment["submitted"] or "Today", "view": first_payment["view"]})
        if first_aid:
            notifications.append({"cls": "amber", "icon": "fa-file-medical-alt", "title": f"{first_aid['ref']} — {first_aid['type']}", "sub": "Aid request awaiting approval", "time": first_aid["submitted"] or "Today", "view": first_aid["view"]})
        if first_contrib:
            notifications.append({"cls": "green", "icon": "fa-check-double", "title": f"{first_contrib['ref']} ready for finish approval", "sub": "Contribution post final approval", "time": "This week", "view": first_contrib["view"]})
        if first_reg:
            notifications.append({"cls": "purple", "icon": "fa-user-plus", "title": f"{first_reg['ref']} — {first_reg['from']}", "sub": "Registration awaiting final approval", "time": first_reg["submitted"] or "Today", "view": first_reg["view"]})

    # ---------------- Death aid categories (policy constants) ----------------
    death_categories = [
        {"name": "Member", "amount": get_death_aid_amount("member")},
        {"name": "Husband/Wife of Member", "amount": get_death_aid_amount("spouse")},
        {"name": "Parents and Children", "amount": get_death_aid_amount("parent")},
        {"name": "Brother/Sister (Full Blood)", "amount": get_death_aid_amount("full-blood brother")},
    ]

    return JsonResponse({
        "ok": True,
        "month_label": month_label,
        "strip": {
            "total_funds": round(fund_balance, 2),
            "total_collections": round(ytd_collections, 2),
            "total_aid_released": round(total_out, 2),
            "pending_release_amount": round(pending_release_amount, 2),
            "pending_approvals": action_center["total"],
            "compliance_pct": overall_pct,
        },
        "kpis": {
            "total_members": total_members,
            "total_collections": round(ytd_collections, 2),
            "pending_approvals": action_center["total"],
            "aid_requests": aid_requests_count,
            "pending_audits": pending_registrations,
            "fund_balance": round(fund_balance, 2),
        },
        "fund_position": {
            "opening": round(month_opening, 2),
            "inflows": round(month_in, 2),
            "outflows": round(month_out, 2),
            "balance": round(fund_balance, 2),
            "net": round(month_in - month_out, 2),
            "growth": round((month_in - month_out) / month_opening * 100, 1) if month_opening else 0.0,
            "has_ledger": month_tx.exists(),
        },
        "action_center": action_center,
        "collection_trend": {"months": months, "collected": collection_series, "yearly": yearly_list},
        "inflow_outflow": {"months": months, "inflows": inflow_series, "outflows": outflow_series},
        "dues_status": {
            "month": month_key, "total": total_members,
            "paid": total_paid, "pending": sum(d["pending"] for d in departments),
            "unpaid": sum(d["unpaid"] for d in departments),
        },
        "aid_summary": {"medical": _aid_bucket(med_rows, "amount"), "death": _aid_bucket(death_rows, "amount")},
        "death_categories": death_categories,
        "recent_activity": recent_activity,
        "departments": departments,
        "fund_balance_series": {"months": months, "balances": balance_series},
        "fund_summary": {
            "opening": round(month_opening, 2),
            "inflows": round(month_in, 2),
            "outflows": round(month_out, 2),
            "balance": round(fund_balance, 2),
            "inflow_breakdown": inflow_breakdown,
            "outflow_breakdown": outflow_breakdown,
            "has_ledger": month_tx.exists(),
        },
        "pending_rows": pending_rows,
        "notifications": notifications,
    })


@require_GET
def president_dashboard_financial_overview(request: HttpRequest):
    """Financial overview: Fund Balance, Inflow, Outflow, Net Movement."""
    guard = require_role(request, role="President")
    if guard is not None:
        return guard

    totals = FundTransaction.objects.aggregate(
        total_in=Sum("amount", filter=Q(direction="inflow")),
        total_out=Sum("amount", filter=Q(direction="outflow")),
    )
    total_in = float(totals["total_in"] or 0)
    total_out = float(totals["total_out"] or 0)
    fund_balance = total_in - total_out

    return JsonResponse({
        "ok": True,
        "fund_balance": fund_balance,
        "total_inflow": total_in,
        "total_outflow": total_out,
        "net_movement": fund_balance,
    })


@require_GET
def president_dashboard_fund_movement(request: HttpRequest):
    """Fund movement trend over the last 12 months."""
    guard = require_role(request, role="President")
    if guard is not None:
        return guard

    year = timezone.now().year

    inflow_map = {}
    outflow_map = {}

    for ft in FundTransaction.objects.filter(recorded_at__year=year).iterator():
        m = ft.recorded_at.month
        amount = float(ft.amount)
        if ft.direction == "inflow":
            inflow_map[m] = inflow_map.get(m, 0) + amount
        else:
            outflow_map[m] = outflow_map.get(m, 0) + amount

    months = []
    inflow_data = []
    outflow_data = []
    net_data = []

    for m in range(1, 13):
        month_name = timezone.datetime(year, m, 1).strftime("%b %Y")
        months.append(month_name)
        inflow = inflow_map.get(m, 0)
        outflow = outflow_map.get(m, 0)
        inflow_data.append(inflow)
        outflow_data.append(outflow)
        net_data.append(inflow - outflow)

    return JsonResponse({
        "ok": True,
        "months": months,
        "inflow": inflow_data,
        "outflow": outflow_data,
        "net": net_data,
    })


@require_GET
def president_dashboard_membership_overview(request: HttpRequest):
    """Members by college/department."""
    guard = require_role(request, role="President")
    if guard is not None:
        return guard

    dept_data = Member.objects.exclude(
        Q(department__isnull=True) | Q(department="") | Q(membership_status__iexact="retired")
    ).values("department").annotate(count=Count("member_id_PK")).order_by("-count")

    result = [
        {"department": d["department"], "count": d["count"]}
        for d in dept_data
    ]

    return JsonResponse({
        "ok": True,
        "departments": result,
    })


@require_GET
def president_dashboard_dues_compliance(request: HttpRequest):
    """Simplified monthly dues compliance for executive overview."""
    guard = require_role(request, role="President")
    if guard is not None:
        return guard

    current_month = timezone.now().strftime("%Y-%m")
    dues = MonthlyDues.objects.filter(month_covered=current_month)

    paid_statuses = list(Status.ALL_AUDITOR_VERIFIED)
    pending_statuses = list(Status.ALL_PENDING)

    paid = dues.filter(payment_status__in=paid_statuses).count()
    pending = dues.filter(payment_status__in=pending_statuses).count()
    unpaid = dues.exclude(payment_status__in=paid_statuses + pending_statuses).count()

    total = paid + pending + unpaid

    return JsonResponse({
        "ok": True,
        "month": current_month,
        "paid": paid,
        "pending": pending,
        "unpaid": unpaid,
        "total": total,
        "paid_percentage": round(paid / total * 100, 1) if total else 0,
        "pending_percentage": round(pending / total * 100, 1) if total else 0,
        "unpaid_percentage": round(unpaid / total * 100, 1) if total else 0,
    })


@require_GET
def president_dashboard_aid_overview(request: HttpRequest):
    """Aid activity: Requests, Approved, Released."""
    guard = require_role(request, role="President")
    if guard is not None:
        return guard

    # Medical Aid
    medical_requests = MedicalAid.objects.count()
    medical_approved = MedicalAid.objects.filter(status__in=["Auditor Verified", "President Approved", "Released"]).count()
    medical_released = MedicalAid.objects.filter(status="Released").count()

    # Death Aid
    death_requests = DeathAid.objects.count()
    death_approved = DeathAid.objects.filter(status__in=["Auditor Verified", "President Approved", "Released"]).count()
    death_released = DeathAid.objects.filter(status="Released").count()

    return JsonResponse({
        "ok": True,
        "medical_aid": {
            "requests": medical_requests,
            "approved": medical_approved,
            "released": medical_released,
        },
        "death_aid": {
            "requests": death_requests,
            "approved": death_approved,
            "released": death_released,
        },
    })


@require_GET
def president_dashboard_contribution_progress(request: HttpRequest):
    """Active aid contribution progress for currently active aid posts."""
    guard = require_role(request, role="President")
    if guard is not None:
        return guard

    active_posts = AidTrackingPost.objects.filter(is_active=True).select_related("archive_id_FK")

    posts_data = []
    for post in active_posts:
        expected = float(post.total_expected or 0)
        collected = float(post.total_collected or 0)
        remaining = expected - collected
        percentage = round(collected / expected * 100, 1) if expected else 0

        posts_data.append({
            "post_id": post.post_id_PK,
            "aid_type": post.aid_type,
            "target_month": post.target_month,
            "expected": expected,
            "collected": collected,
            "remaining": remaining,
            "percentage": percentage,
            "status": post.status,
        })

    return JsonResponse({
        "ok": True,
        "posts": posts_data,
    })


@require_GET
def president_dashboard_approval_pipeline(request: HttpRequest):
    """Approval pipeline: shows flow from submission through Treasurer -> Auditor -> President."""
    guard = require_role(request, role="President")
    if guard is not None:
        return guard

    # Registration pipeline
    reg_submitted = MemberRegistrationRequest.objects.filter(status__in=["Pending", "Pending Treasurer Review"]).count()
    reg_treasurer = MemberRegistrationRequest.objects.filter(status="Pending Auditor Verification").count()
    reg_auditor = MemberRegistrationRequest.objects.filter(status="Auditor Verified").count()
    reg_president = MemberRegistrationRequest.objects.filter(status="President Approved").count()
    reg_approved = MemberRegistrationRequest.objects.filter(status="Approved").count()

    # Medical Aid pipeline
    med_submitted = MedicalAid.objects.filter(status__in=["Pending", "Pending Treasurer Review"]).count()
    med_treasurer = MedicalAid.objects.filter(status="Pending Auditor Verification").count()
    med_auditor = MedicalAid.objects.filter(status="Auditor Verified").count()
    med_president = MedicalAid.objects.filter(status="President Approved").count()
    med_approved = MedicalAid.objects.filter(status__in=["President Approved", "Released"]).count()

    # Death Aid pipeline
    death_submitted = DeathAid.objects.filter(status__in=["Pending", "Pending Treasurer Review"]).count()
    death_treasurer = DeathAid.objects.filter(status="Pending Auditor Verification").count()
    death_auditor = DeathAid.objects.filter(status="Auditor Verified").count()
    death_president = DeathAid.objects.filter(status="President Approved").count()
    death_approved = DeathAid.objects.filter(status__in=["President Approved", "Released"]).count()

    return JsonResponse({
        "ok": True,
        "registration": {
            "submitted": reg_submitted,
            "treasurer": reg_treasurer,
            "auditor": reg_auditor,
            "president": reg_president,
            "approved": reg_approved,
        },
        "medical_aid": {
            "submitted": med_submitted,
            "treasurer": med_treasurer,
            "auditor": med_auditor,
            "president": med_president,
            "approved": med_approved,
        },
        "death_aid": {
            "submitted": death_submitted,
            "treasurer": death_treasurer,
            "auditor": death_auditor,
            "president": death_president,
            "approved": death_approved,
        },
    })


@require_GET
def president_dashboard_oversight_attention(request: HttpRequest):
    """Oversight attention panel for the President."""
    guard = require_role(request, role="President")
    if guard is not None:
        return guard

    # Claims awaiting action (at President level)
    claims_awaiting = MedicalAid.objects.filter(
        status__in=["Auditor Verified", "President Approved"]
    ).count() + DeathAid.objects.filter(
        status__in=["Auditor Verified", "President Approved"]
    ).count()

    # Unpaid members
    current_month = timezone.now().strftime("%Y-%m")
    unpaid_members = MonthlyDues.objects.filter(
        month_covered=current_month
    ).exclude(payment_status__in=["Full Payment", "Partial", "Advance", "Pending", "Pending Verification"]).count()

    # Registrations awaiting approval
    reg_awaiting = MemberRegistrationRequest.objects.filter(
        status__in=["Auditor Verified", "President Approved"]
    ).count()

    # Contributions incomplete
    contributions_incomplete = AidTrackingPost.objects.filter(
        is_active=True
    ).exclude(
        Q(total_collected__gte=F("total_expected")) | Q(status="closed")
    ).count()

    # Transactions ready for release
    ready_for_release = AidTrackingPost.objects.filter(
        is_active=True,
        finish_status="pending_release"
    ).count()

    return JsonResponse({
        "ok": True,
        "claims_awaiting_action": claims_awaiting,
        "unpaid_members": unpaid_members,
        "registrations_awaiting_approval": reg_awaiting,
        "contributions_incomplete": contributions_incomplete,
        "transactions_ready_for_release": ready_for_release,
    })


# ============================================================================
# PRESIDENT: AID TRACKING POST FINISH APPROVAL
# ============================================================================


@require_GET
def president_pending_finish_requests(request: HttpRequest):
    guard = require_role(request, role="President")
    if guard is not None:
        return guard

    posts = AidTrackingPost.objects.filter(
        finish_status__in=["pending_approval", "pending_president"], is_active=True
    ).select_related(
        "archive_id_FK",
        "archive_id_FK__member_id_FK",
        "created_by_user_id_FK",
    ).all()

    items = []
    for post in posts:
        archive = post.archive_id_FK
        member = archive.member_id_FK if archive else None
        aid_label = "Medical Aid" if post.aid_type == "medical_aid" else "Death Aid"
        collection_rate = 0
        if post.total_expected > 0:
            collection_rate = round(float(post.total_collected) / float(post.total_expected) * 100, 1)
        
        # Exclude EXCLUDED_REQUESTER from count
        total = Contribution.objects.filter(aid_tracking_post_id_FK=post).exclude(status="EXCLUDED_REQUESTER").count()
        paid = Contribution.objects.filter(aid_tracking_post_id_FK=post, status__in=["PAID", "RECORDED", "PENDING_VERIFICATION"]).count()

        items.append({
            "post_id": post.post_id_PK,
            "aid_type": post.aid_type,
            "aid_label": aid_label,
            "member_name": archive.member_name if archive else "",
            "member_id": member.member_id_PK if member else None,
            "target_month": post.target_month,
            "total_expected": str(post.total_expected),
            "total_collected": str(post.total_collected),
            "collection_rate": collection_rate,
            "skip_remaining": post.finish_skip_remaining,
            "paid_count": paid,
            "total_count": total,
            "status": archive.status if archive else "",
            "amount": str(archive.amount) if archive else "0",
            "created_by": post.created_by_user_id_FK.full_name if post.created_by_user_id_FK else "",
            "created_at": post.created_at.isoformat() if post.created_at else "",
            "verified_by_auditor": post.finish_status == "pending_president",
            "has_deduction_sheet": bool(post.deduction_sheet),
            "deduction_batch_reference": post.deduction_batch_reference or "",
            "deduction_payroll_period": post.deduction_payroll_period or "",
            "has_remittance": bool(post.deduction_remitted_amount is not None),
            "deduction_remitted_amount": str(post.deduction_remitted_amount) if post.deduction_remitted_amount is not None else None,
            "deduction_remittance_reference": post.deduction_remittance_reference or "",
            "deduction_remitted_date": post.deduction_remitted_date.isoformat() if post.deduction_remitted_date else None,
        })

    return JsonResponse({"ok": True, "posts": items})


@require_GET
def president_finish_request_details(request: HttpRequest):
    guard = require_role(request, role="President")
    if guard is not None:
        return guard

    post_id = request.GET.get("post_id", "").strip()
    if not post_id:
        return JsonResponse({"ok": False, "error": "post_id required."}, status=400)

    try:
        post = AidTrackingPost.objects.get(post_id_PK=int(post_id))
    except (ValueError, AidTrackingPost.DoesNotExist):
        return JsonResponse({"ok": False, "error": "Post not found."}, status=404)

    contributions = Contribution.objects.filter(
        aid_tracking_post_id_FK=post
    ).exclude(status="EXCLUDED_REQUESTER").select_related("member_id_FK").order_by("member_id_FK__full_name")

    details = []
    total_paid = 0
    paid_count = 0
    for c in contributions:
        member_name = c.member_id_FK.full_name if c.member_id_FK else "Unknown"
        paid = float(c.paid_amount) if c.paid_amount else 0
        expected = float(c.expected_amount) if c.expected_amount else 0
        if c.status in ("PAID", "RECORDED", "PENDING_VERIFICATION"):
            total_paid += paid
            paid_count += 1
        details.append({
            "member_name": member_name,
            "expected_amount": expected,
            "paid_amount": paid,
            "status": c.status,
            "payment_date": c.payment_date.isoformat() if c.payment_date else None,
        })

    return JsonResponse({
        "ok": True,
        "post_id": post.post_id_PK,
        "aid_type": post.aid_type,
        "target_month": post.target_month,
        "total_expected": float(post.total_expected),
        "total_paid": round(total_paid, 2),
        "paid_count": paid_count,
        "total_count": contributions.count(),
        "details": details,
    })


@require_POST
@transaction.atomic
def president_approve_aid_post_finish(request: HttpRequest):
    guard = require_role(request, role="President")
    if guard is not None:
        return guard
    # ZT check removed during transition

    president_id = request.session.get("officer_id")
    if president_id is None:
        return JsonResponse({"ok": False, "error": "Session missing."}, status=401)
    try:
        president = OfficerUser.objects.get(user_id_PK=int(president_id))
    except OfficerUser.DoesNotExist:
        return JsonResponse({"ok": False, "error": "Officer not found."}, status=404)

    post_id = (request.POST.get("post_id") or "").strip()
    if not post_id:
        return JsonResponse({"ok": False, "error": "Missing post_id."}, status=400)

    try:
        post = AidTrackingPost.objects.get(
            post_id_PK=int(post_id), is_active=True,
            finish_status__in=["pending_approval", "pending_president"],
        )
    except (ValueError, AidTrackingPost.DoesNotExist):
        return JsonResponse({"ok": False, "error": "Pending finish request not found."}, status=404)

    if post.finish_skip_remaining and not post.finish_paid_with_funds:
        Contribution.objects.filter(
            aid_tracking_post_id_FK=post,
            status="NOT_PAID",
        ).update(
            status="SKIPPED",
            is_manually_overridden=True,
            paid_amount=0,
        )
        totals = Contribution.objects.filter(aid_tracking_post_id_FK=post).aggregate(
            total_collected=Sum("paid_amount"),
        )
        post.total_collected = totals["total_collected"] or 0

    was_auditor_verified = post.finish_status == "pending_president"

    archive = post.archive_id_FK
    member_name = archive.member_name if archive else ""

    if was_auditor_verified:
        pending_ids = list(
            Contribution.objects.filter(
                aid_tracking_post_id_FK=post,
                status__in=["PENDING_VERIFICATION", "RECORDED"],
            ).values_list("contribution_id_PK", flat=True)
        )
        if pending_ids:
            Contribution.objects.filter(contribution_id_PK__in=pending_ids).update(status="PAID")
            totals = Contribution.objects.filter(aid_tracking_post_id_FK=post).aggregate(
                total_collected=Sum("paid_amount"),
            )
            post.total_collected = totals["total_collected"] or 0

        if post.finish_paid_with_funds:
            # Cycle 2 (finish_cycle >= 2) is the repayment phase: the fund was already
            # disbursed in cycle 1, so approving here closes the post. Deciding by
            # finish_cycle (instead of whether any PAID contributions exist) ensures a
            # cycle-1 post always routes to release, even if some member payments were
            # recorded before the Treasurer chose "Paid with Funds".
            if post.finish_cycle >= 2:
                # Second cycle — repayments have been collected, close the post
                # (inflow was already recorded at Auditor verify time)
                post.finish_status = "approved"
                post.is_active = False
                post.save(update_fields=["finish_status", "is_active", "total_collected"])

                if archive is not None:
                    if archive.transaction_type == "death_aid":
                        DeathAid.objects.filter(death_aid_id_PK=archive.record_id).update(status="Released")
                    elif archive.transaction_type == "medical_aid":
                        MedicalAid.objects.filter(medical_aid_id_PK=archive.record_id).update(status="Released")

                _record_audit_trail(
                    table="AID_TRACKING_POST",
                    record_id=post.post_id_PK,
                    action="REPAYMENT_APPROVED",
                    actor=president,
                    new={
                        "finish_status": "approved",
                        "is_active": False,
                        "total_collected": float(post.total_collected),
                    },
                    ip=request.META.get("REMOTE_ADDR"),
                    notes="President approved repayment — post closed.",
                )

                channel_layer = get_channel_layer()
                async_to_sync(channel_layer.group_send)("treasurer_dashboard", {
                    "type": "aid_post_finished", "post_id": post.post_id_PK, "member_name": member_name,
                })
                async_to_sync(channel_layer.group_send)("auditor_dashboard", {
                    "type": "data_changed", "section": "aids",
                })
                async_to_sync(channel_layer.group_send)("president_dashboard", {
                    "type": "data_changed", "section": "aids",
                })

                try:
                    notify_member(
                        archive.member_id_FK,
                        notification_type="Claim Released",
                        message="Your claim repayment has been approved and the aid post is now closed.",
                        category="claim",
                        sender_name=president.full_name if president else "President",
                        sender_role="President",
                    )
                except Exception:
                    logger.exception("President repayment-approval notification failed")

                return JsonResponse({"ok": True, "message": "Repayment approved. Aid post closed."})

        # First cycle (paid-with-funds, no repayments yet) or normal pay: route to release
        post.finish_status = "pending_release"
        post.save(update_fields=["finish_status", "total_collected"])

        _record_audit_trail(
            table="AID_TRACKING_POST",
            record_id=post.post_id_PK,
            action="FINISH_APPROVED",
            actor=president,
            new={
                "finish_status": "pending_release",
                "deduction_batch_reference": post.deduction_batch_reference or "",
                "deduction_payroll_period": post.deduction_payroll_period or "",
            },
            ip=request.META.get("REMOTE_ADDR"),
            notes=f"Finish approved (pending release) — deduction ref {post.deduction_batch_reference}, period {post.deduction_payroll_period}" if post.deduction_batch_reference else "Finish approved (pending release)",
        )

        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)("treasurer_dashboard", {
            "type": "aid_post_release_pending",
            "post_id": post.post_id_PK,
            "member_name": member_name,
        })
        async_to_sync(channel_layer.group_send)("auditor_dashboard", {
            "type": "data_changed", "section": "aids",
        })
        async_to_sync(channel_layer.group_send)("president_dashboard", {
            "type": "data_changed", "section": "aids",
        })

        try:
            notify_member(
                archive.member_id_FK,
                notification_type="Claim Approved",
                message="Your claim has been approved by the President. The Treasurer will now release the funds.",
                category="claim",
                sender_name=president.full_name if president else "President",
                sender_role="President",
            )
        except Exception:
            logger.exception("President finish-approval notification failed")

        return JsonResponse({"ok": True, "message": "Finish approved. The Treasurer must now release the funds to close this post."})
    else:
        post.finish_status = "approved"
        post.is_active = False
        post.save(update_fields=["finish_status", "is_active", "total_collected"])

        if archive is not None:
            if archive.transaction_type == "death_aid":
                DeathAid.objects.filter(death_aid_id_PK=archive.record_id).update(status="Released")
            elif archive.transaction_type == "medical_aid":
                MedicalAid.objects.filter(medical_aid_id_PK=archive.record_id).update(status="Released")

        _record_audit_trail(
            table="AID_TRACKING_POST",
            record_id=post.post_id_PK,
            action="FINISH_APPROVED",
            actor=president,
            new={
                "finish_status": "approved",
                "is_active": False,
                "deduction_batch_reference": post.deduction_batch_reference or "",
                "deduction_payroll_period": post.deduction_payroll_period or "",
            },
            ip=request.META.get("REMOTE_ADDR"),
            notes=f"Finish approved — deduction ref {post.deduction_batch_reference}, period {post.deduction_payroll_period}" if post.deduction_batch_reference else "Finish approved",
        )

        channel_layer = get_channel_layer()
        payload = {
            "type": "aid_post_finished",
            "post_id": post.post_id_PK,
            "member_name": member_name,
        }
        async_to_sync(channel_layer.group_send)("treasurer_dashboard", payload)
        async_to_sync(channel_layer.group_send)("auditor_dashboard", payload)
        async_to_sync(channel_layer.group_send)("president_dashboard", payload)

        try:
            notify_member(
                archive.member_id_FK.pk,
                notification_type="Claim Approved",
                message="Your claim has been approved by the President and the aid post has been finalized.",
                category="claim",
                sender_name=president.full_name if president else "President",
                sender_role="President",
            )
        except Exception:
            logger.exception("President finish-approval notification failed")

        return JsonResponse({"ok": True, "message": "Finish request approved. Post moved to history."})


@require_POST
@transaction.atomic
def president_reject_aid_post_finish(request: HttpRequest):
    guard = require_role(request, role="President")
    if guard is not None:
        return guard
    # ZT check removed during transition

    president_id = request.session.get("officer_id")
    if president_id is None:
        return JsonResponse({"ok": False, "error": "Session missing."}, status=401)
    try:
        president = OfficerUser.objects.get(user_id_PK=int(president_id))
    except OfficerUser.DoesNotExist:
        return JsonResponse({"ok": False, "error": "Officer not found."}, status=404)

    post_id = (request.POST.get("post_id") or "").strip()
    remarks = (request.POST.get("remarks") or "").strip()

    if not post_id:
        return JsonResponse({"ok": False, "error": "Missing post_id."}, status=400)

    try:
        post = AidTrackingPost.objects.get(
            post_id_PK=int(post_id), is_active=True,
            finish_status__in=["pending_approval", "pending_president"],
        )
    except (ValueError, AidTrackingPost.DoesNotExist):
        return JsonResponse({"ok": False, "error": "Pending finish request not found."}, status=404)

    post.finish_status = "rejected"
    post.save(update_fields=["finish_status"])

    _record_audit_trail(
        table="AID_TRACKING_POST",
        record_id=post.post_id_PK,
        action="FINISH_REJECTED",
        actor=president,
        new={"finish_status": "rejected"},
        notes=remarks,
        ip=request.META.get("REMOTE_ADDR"),
    )

    archive = post.archive_id_FK
    member_name = archive.member_name if archive else ""
    channel_layer = get_channel_layer()
    payload = {
        "type": "aid_post_finish_rejected",
        "post_id": post.post_id_PK,
        "member_name": member_name,
        "remarks": remarks,
    }
    async_to_sync(channel_layer.group_send)("treasurer_dashboard", payload)
    async_to_sync(channel_layer.group_send)("auditor_dashboard", payload)
    async_to_sync(channel_layer.group_send)("president_dashboard", payload)

    return JsonResponse({"ok": True, "message": "Finish request rejected. Post returned to active state."})


# ==========================================================================
# PAYROLL BATCH APPROVAL (PRESIDENT)
# ==========================================================================


@require_GET
def president_pending_payroll_batches(request: HttpRequest):
    """List auditor-verified PayrollBatches pending presidential approval."""
    guard = require_role(request, role="President")
    if guard is not None:
        return guard

    batches = PayrollBatch.objects.filter(
        status="Auditor Verified",
    ).select_related(
        "recorded_by_user_id_FK",
        "auditor_verified_by_user_id_FK",
    ).order_by("-created_at")

    fund_balance = float(FundTransaction.get_balance())
    safety_threshold = float(SystemSetting.objects.get_or_create(
        setting_key="safety_threshold", defaults={"setting_value": "20000"}
    )[0].setting_value)

    items = []
    for b in batches:
        fund_impact = PayrollDeduction.objects.filter(
            batch_id_FK=b, fund_impact="inflow"
        ).aggregate(total=Sum("amount"))["total"] or 0
        projected = fund_balance + float(fund_impact)

        items.append({
            "batch_id": b.batch_id_PK,
            "payroll_period": b.payroll_period,
            "total_amount": float(b.total_amount),
            "member_count": b.member_count,
            "fund_impact": float(fund_impact),
            "projected_balance": projected,
            "notes": b.notes or "",
            "recorded_by": b.recorded_by_user_id_FK.full_name if b.recorded_by_user_id_FK else "",
            "verified_by": b.auditor_verified_by_user_id_FK.full_name if b.auditor_verified_by_user_id_FK else "",
            "created_at": b.created_at.isoformat() if b.created_at else "",
        })

    return JsonResponse({
        "ok": True,
        "batches": items,
        "fund_balance": fund_balance,
        "safety_threshold": safety_threshold,
    })


@require_GET
def president_payroll_batch_detail(request: HttpRequest, batch_id: int):
    """View a PayrollBatch with fund balance context."""
    guard = require_role(request, role="President")
    if guard is not None:
        return guard

    batch = get_object_or_404(PayrollBatch, pk=batch_id)
    deductions = PayrollDeduction.objects.filter(batch_id_FK=batch).select_related("member_id_FK")

    fund_balance = float(FundTransaction.get_balance())
    fund_impact = deductions.filter(fund_impact="inflow").aggregate(
        total=Sum("amount")
    )["total"] or 0
    projected = fund_balance + float(fund_impact)
    safety_threshold = float(SystemSetting.objects.get_or_create(
        setting_key="safety_threshold", defaults={"setting_value": "20000"}
    )[0].setting_value)

    ded_list = []
    for d in deductions:
        ded_list.append({
            "deduction_id": d.deduction_id_PK,
            "member_id": d.member_id_FK.member_id_PK,
            "member_name": d.member_id_FK.full_name,
            "amount": float(d.amount),
            "category": d.category,
            "fund_impact": d.fund_impact,
            "month_covered": d.month_covered or "",
        })

    return JsonResponse({
        "ok": True,
        "batch": {
            "batch_id": batch.batch_id_PK,
            "payroll_period": batch.payroll_period,
            "total_amount": float(batch.total_amount),
            "member_count": batch.member_count,
            "hardcopy_reference": batch.hardcopy_reference or "",
            "notes": batch.notes or "",
            "status": batch.status,
            "recorded_by": batch.recorded_by_user_id_FK.full_name if batch.recorded_by_user_id_FK else "",
            "verified_by": batch.auditor_verified_by_user_id_FK.full_name if batch.auditor_verified_by_user_id_FK else "",
            "auditor_remarks": batch.auditor_remarks or "",
            "created_at": batch.created_at.isoformat() if batch.created_at else "",
        },
        "deductions": ded_list,
        "fund_balance": fund_balance,
        "fund_impact": float(fund_impact),
        "projected_balance": projected,
        "safety_threshold": safety_threshold,
        "is_safe": projected >= safety_threshold,
    })


@require_POST
@transaction.atomic
def president_approve_payroll_batch(request: HttpRequest, batch_id: int):
    """Approve a PayrollBatch — creates FundTransaction entries and archives."""
    guard = require_role(request, role="President")
    if guard is not None:
        return guard
    # ZT check removed during transition

    batch = get_object_or_404(PayrollBatch, pk=batch_id, status="Auditor Verified")

    stored_officer_id = request.session.get("officer_id")
    try:
        president = OfficerUser.objects.get(user_id_PK=int(stored_officer_id))
    except (ValueError, OfficerUser.DoesNotExist):
        return JsonResponse({"ok": False, "error": "Officer not found."}, status=404)

    try:
        data = json.loads(request.body)
    except Exception:
        data = {}

    remarks = data.get("remarks", "")

    # Approve the batch
    batch.status = "Approved"
    batch.president_approved_by_user_id_FK = president
    batch.president_approved_at = timezone.now()
    batch.president_remarks = remarks
    batch.save(update_fields=[
        "status", "president_approved_by_user_id_FK",
        "president_approved_at", "president_remarks",
    ])

    # Create FundTransaction for each deduction with fund_impact="inflow"
    inflow_deductions = PayrollDeduction.objects.filter(
        batch_id_FK=batch, fund_impact="inflow"
    ).select_related("member_id_FK")

    ft_count = 0
    for d in inflow_deductions:
        description = _build_payroll_deduction_description(d)
        FundTransaction.objects.create(
            direction="inflow",
            amount=d.amount,
            source_type="payroll_batch",
            source_id=batch.pk,
            description=description,
            reference_number=batch.hardcopy_reference or "",
            recorded_by_user_id_FK=president,
        )
        ft_count += 1

        # If aid contribution, update the Contribution record for tracking
        if d.category == "aid_contribution" and d.aid_tracking_post_id_FK:
            Contribution.objects.update_or_create(
                aid_tracking_post_id_FK=d.aid_tracking_post_id_FK,
                member_id_FK=d.member_id_FK,
                defaults={
                    "paid_amount": d.amount,
                    "payment_date": timezone.now().date(),
                    "status": "PAID",
                    "updated_by_user_id_FK": president,
                },
            )

    # Archive the batch
    archive_transaction(table_name="payroll_batch", pk=batch.pk, officer=president)

    fund_balance = float(FundTransaction.get_balance())

    _record_audit_trail(
        table="PAYROLL_BATCH",
        record_id=batch.pk,
        action="APPROVED",
        actor=president,
        new={
            "status": "Approved",
            "total_amount": float(batch.total_amount),
            "fund_impact_count": ft_count,
            "remarks": remarks,
        },
        ip=request.META.get("REMOTE_ADDR"),
    )

    _broadcast_pending_counts()
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)("treasurer_dashboard", {
        "type": "dashboard_refresh", "section": "payroll_batches",
    })
    async_to_sync(channel_layer.group_send)("president_dashboard", {
        "type": "dashboard_refresh", "section": "all",
    })

    return JsonResponse({
        "ok": True,
        "message": "Payroll batch approved.",
        "fund_balance": fund_balance,
        "fund_transactions_created": ft_count,
    })


@require_POST
@transaction.atomic
def president_reject_payroll_batch(request: HttpRequest, batch_id: int):
    """Reject a PayrollBatch."""
    guard = require_role(request, role="President")
    if guard is not None:
        return guard
    # ZT check removed during transition

    batch = get_object_or_404(PayrollBatch, pk=batch_id, status="Auditor Verified")

    stored_officer_id = request.session.get("officer_id")
    try:
        president = OfficerUser.objects.get(user_id_PK=int(stored_officer_id))
    except (ValueError, OfficerUser.DoesNotExist):
        return JsonResponse({"ok": False, "error": "Officer not found."}, status=404)

    try:
        data = json.loads(request.body)
    except Exception:
        data = {}

    reason = data.get("reason", "")
    batch.status = "Rejected"
    batch.president_approved_by_user_id_FK = president
    batch.president_remarks = reason
    batch.save(update_fields=["status", "president_approved_by_user_id_FK", "president_remarks"])

    _record_audit_trail(
        table="PAYROLL_BATCH",
        record_id=batch.pk,
        action="REJECTED",
        actor=president,
        new={"status": "Rejected", "reason": reason},
        ip=request.META.get("REMOTE_ADDR"),
    )

    _broadcast_pending_counts()

    return JsonResponse({"ok": True, "message": "Payroll batch rejected."})


def _build_payroll_deduction_description(deduction: PayrollDeduction) -> str:
    """Build a human-readable description for a PayrollDeduction FundTransaction."""
    member = deduction.member_id_FK
    member_name = member.full_name if member else "Unknown"
    if deduction.category == "monthly_dues":
        period = deduction.month_covered or ""
        return f"Monthly dues {period} — {member_name}"
    elif deduction.category == "membership_fee":
        return f"Membership fee — {member_name}"
    elif deduction.category == "aid_contribution":
        post_ref = ""
        if deduction.aid_tracking_post_id_FK:
            post = deduction.aid_tracking_post_id_FK
            post_ref = f" ({post.aid_type}#{post.source_id})"
        return f"Aid contribution{post_ref} — {member_name}"
    return f"Deduction — {member_name}"


# ==========================================================================
# BYLAWS CONSTANTS MANAGEMENT
# ==========================================================================


def _resolve_president(request: HttpRequest):
    stored_officer_id = request.session.get("officer_id")
    if stored_officer_id is None:
        return None
    try:
        return OfficerUser.objects.get(user_id_PK=int(stored_officer_id))
    except Exception:
        return None


def _parse_iso_date(value: Any):
    raw_value = (value or "").strip() if isinstance(value, str) else value
    if not raw_value:
        return None
    try:
        return datetime.fromisoformat(str(raw_value)).date()
    except (TypeError, ValueError):
        return None


def _extract_request_data(request: HttpRequest) -> Dict[str, Any]:
    if request.content_type and "json" in request.content_type.lower():
        try:
            return json.loads(request.body.decode("utf-8") or "{}")
        except (UnicodeDecodeError, json.JSONDecodeError):
            return {}
    if request.body:
        try:
            return json.loads(request.body.decode("utf-8") or "{}")
        except (UnicodeDecodeError, json.JSONDecodeError):
            pass
    return request.POST.dict()


@require_GET
def president_officers_list(request: HttpRequest):
    guard = require_role(request, role="President")
    if guard is not None:
        return guard

    officers = (
        OfficerUser.objects.select_related("department_id_FK")
        .exclude(role__iexact="Member")
        .exclude(role__iexact="System")
        .exclude(role__iexact="Superadmin")
        .order_by("-created_at", "full_name")
    )
    return JsonResponse({"ok": True, "officers": [_officer_to_json(officer) for officer in officers]})


@require_POST
@transaction.atomic
def president_officers_create(request: HttpRequest):
    guard = require_role(request, role="President")
    if guard is not None:
        return guard

    payload = _extract_request_data(request)
    full_name = (payload.get("full_name") or payload.get("name") or "").strip()
    username = (payload.get("username") or "").strip()
    password = (payload.get("password") or "").strip()
    email = (payload.get("email") or "").strip() or None
    role = (payload.get("role") or "Officer").strip()
    account_status = (payload.get("account_status") or "Active").strip() or "Active"
    term_start = _parse_iso_date(payload.get("term_start"))
    term_end = _parse_iso_date(payload.get("term_end"))
    department_id = payload.get("department_id") or payload.get("department") or None

    if not full_name:
        return JsonResponse({"ok": False, "error": "Full name is required."}, status=400)
    if not username:
        return JsonResponse({"ok": False, "error": "Username is required."}, status=400)
    if not password:
        return JsonResponse({"ok": False, "error": "Password is required."}, status=400)

    if OfficerUser.objects.filter(username=username).exists():
        return JsonResponse({"ok": False, "error": "Username already exists."}, status=409)
    if email and OfficerUser.objects.filter(email__iexact=email).exists():
        return JsonResponse({"ok": False, "error": "Email already exists."}, status=409)

    department = None
    if department_id not in (None, "", 0, "0"):
        department = _resolve_officer_department(department_id)
        if department is None:
            return JsonResponse({"ok": False, "error": "Selected department was not found."}, status=400)

    officer = OfficerUser.objects.create(
        full_name=full_name,
        username=username,
        password_hash=hash_password(password),
        role=role,
        email=email,
        department_id_FK=department,
        account_status=account_status,
        term_start=term_start,
        term_end=term_end,
        must_change_password=True,
    )

    president = _resolve_president(request)
    _record_audit_trail(
        table="officer_user",
        record_id=officer.user_id_PK,
        action="CREATED",
        actor=president,
        new=_officer_to_json(officer),
        ip=request.META.get("REMOTE_ADDR"),
        notes=f"Created officer account for {officer.full_name}",
    )

    return JsonResponse({"ok": True, "officer": _officer_to_json(officer)})


@require_POST
@transaction.atomic
def president_officers_update(request: HttpRequest, officer_id: int):
    guard = require_role(request, role="President")
    if guard is not None:
        return guard

    officer = get_object_or_404(OfficerUser.objects.select_related("department_id_FK"), pk=officer_id)
    payload = _extract_request_data(request)

    username = (payload.get("username") or officer.username).strip()
    full_name = (payload.get("full_name") or officer.full_name).strip()
    role = (payload.get("role") or officer.role).strip()
    email = (payload.get("email") or getattr(officer, "email", "") or "").strip() or None
    account_status = (payload.get("account_status") or officer.account_status).strip()
    term_start = _parse_iso_date(payload.get("term_start")) if payload.get("term_start") not in (None, "") else officer.term_start
    term_end = _parse_iso_date(payload.get("term_end")) if payload.get("term_end") not in (None, "") else officer.term_end
    password = (payload.get("password") or "").strip()
    department_id = payload.get("department_id") or payload.get("department")

    if not username:
        return JsonResponse({"ok": False, "error": "Username is required."}, status=400)
    if not full_name:
        return JsonResponse({"ok": False, "error": "Full name is required."}, status=400)

    if OfficerUser.objects.exclude(pk=officer.pk).filter(username=username).exists():
        return JsonResponse({"ok": False, "error": "Username already exists."}, status=409)
    if email and OfficerUser.objects.exclude(pk=officer.pk).filter(email__iexact=email).exists():
        return JsonResponse({"ok": False, "error": "Email already exists."}, status=409)

    department = officer.department_id_FK
    if department_id not in (None, "", 0, "0"):
        department = _resolve_officer_department(department_id)
        if department is None:
            return JsonResponse({"ok": False, "error": "Selected department was not found."}, status=400)
    elif department_id in ("", None):
        department = None if payload.get("clear_department") else department

    officer.full_name = full_name
    officer.username = username
    officer.role = role
    officer.email = email
    officer.account_status = account_status
    officer.term_start = term_start
    officer.term_end = term_end
    officer.department_id_FK = department
    if password:
        officer.password_hash = hash_password(password)

    update_fields = [
        "full_name",
        "username",
        "role",
        "email",
        "account_status",
        "term_start",
        "term_end",
        "department_id_FK",
        "updated_at",
    ]
    if password:
        update_fields.append("password_hash")
    officer.save(update_fields=update_fields)

    president = _resolve_president(request)
    _record_audit_trail(
        table="officer_user",
        record_id=officer.user_id_PK,
        action="UPDATED",
        actor=president,
        new=_officer_to_json(officer),
        ip=request.META.get("REMOTE_ADDR"),
        notes=f"Updated officer account for {officer.full_name}",
    )

    return JsonResponse({"ok": True, "officer": _officer_to_json(officer)})


@require_POST
@transaction.atomic
def president_officers_reset_password(request: HttpRequest, officer_id: int):
    guard = require_role(request, role="President")
    if guard is not None:
        return guard

    officer = get_object_or_404(OfficerUser, pk=officer_id)
    temp_password = secrets.token_urlsafe(10)
    officer.password_hash = hash_password(temp_password)
    officer.must_change_password = True
    officer.save(update_fields=["password_hash", "must_change_password", "updated_at"])

    president = _resolve_president(request)
    _record_audit_trail(
        table="officer_user",
        record_id=officer.user_id_PK,
        action="PASSWORD_RESET",
        actor=president,
        new={"username": officer.username, "temp_password_generated": True},
        ip=request.META.get("REMOTE_ADDR"),
        notes=f"Reset password for {officer.full_name}",
    )

    return JsonResponse({"ok": True, "temp_password": temp_password, "officer": _officer_to_json(officer)})


@require_POST
@transaction.atomic
def president_officers_deactivate(request: HttpRequest, officer_id: int):
    guard = require_role(request, role="President")
    if guard is not None:
        return guard
    # ZT check removed during transition

    officer = get_object_or_404(OfficerUser, pk=officer_id)
    officer.account_status = "Inactive"
    officer.save(update_fields=["account_status", "updated_at"])

    president = _resolve_president(request)
    _record_audit_trail(
        table="officer_user",
        record_id=officer.user_id_PK,
        action="DEACTIVATED",
        actor=president,
        new=_officer_to_json(officer),
        ip=request.META.get("REMOTE_ADDR"),
        notes=f"Deactivated officer account for {officer.full_name}",
    )

    return JsonResponse({"ok": True, "officer": _officer_to_json(officer)})


@require_GET
def president_profile(request: HttpRequest):
    guard = require_role(request, role="President")
    if guard is not None:
        return guard

    officer = resolve_officer_from_session(request)
    if officer is None:
        return JsonResponse({"ok": False, "error": "Officer session missing."}, status=401)

    return JsonResponse({"ok": True, "officer": _officer_to_json(officer)})


@require_POST
@transaction.atomic
def president_profile_update(request: HttpRequest):
    guard = require_role(request, role="President")
    if guard is not None:
        return guard

    officer = resolve_officer_from_session(request)
    if officer is None:
        return JsonResponse({"ok": False, "error": "Officer session missing."}, status=401)

    payload = _extract_request_data(request)
    full_name = (payload.get("full_name") or officer.full_name).strip()
    username = (payload.get("username") or officer.username).strip()
    password = (payload.get("password") or "").strip()

    if not full_name:
        return JsonResponse({"ok": False, "error": "Full name is required."}, status=400)
    if not username:
        return JsonResponse({"ok": False, "error": "Username is required."}, status=400)

    if OfficerUser.objects.exclude(pk=officer.pk).filter(username=username).exists():
        return JsonResponse({"ok": False, "error": "Username already exists."}, status=409)

    officer.full_name = full_name
    officer.username = username
    if password:
        officer.password_hash = hash_password(password)

    update_fields = ["full_name", "username", "updated_at"]
    if password:
        update_fields.append("password_hash")
    officer.save(update_fields=update_fields)

    _record_audit_trail(
        table="officer_user",
        record_id=officer.user_id_PK,
        action="PROFILE_UPDATED",
        actor=officer,
        new=_officer_to_json(officer),
        ip=request.META.get("REMOTE_ADDR"),
        notes="Updated own officer profile",
    )

    return JsonResponse({"ok": True, "officer": _officer_to_json(officer)})


@require_POST
@transaction.atomic
def president_officer_self_enroll(request: HttpRequest):
    guard = require_role(request, role="President")
    if guard is not None:
        return guard

    president = resolve_officer_from_session(request)
    if president is None:
        return JsonResponse({"ok": False, "error": "Officer session missing."}, status=401)

    payload = _extract_request_data(request)
    employee_id = (payload.get("employee_id") or payload.get("prof_id") or "").strip()
    department_id = payload.get("department_id") or payload.get("prof_dept") or None
    department_name = (payload.get("department_name") or payload.get("department") or "").strip()
    position = (payload.get("position") or payload.get("prof_pos") or president.role or "Officer").strip()
    contact_number = (payload.get("contact_number") or payload.get("prof_contact") or "").strip() or None
    email = (payload.get("email") or payload.get("prof_email") or "").strip() or None

    if not employee_id:
        return JsonResponse({"ok": False, "error": "Employee ID is required."}, status=400)

    if Member.objects.filter(employee_id=employee_id).exists():
        return JsonResponse({"ok": False, "error": "Employee ID is already registered."}, status=409)
    if Member.objects.filter(officer_user_id_FK=president).exists():
        return JsonResponse({"ok": False, "error": "This officer is already linked to a member profile."}, status=409)

    department = president.department_id_FK
    if department_id not in (None, "", 0, "0"):
        department = Department.objects.filter(department_id_PK=int(department_id)).first() or department
    elif department_name:
        department = Department.objects.filter(name__iexact=department_name).first() or department

    normalized_position = position.title()
    role_value = normalized_position if normalized_position in {"Secretary", "Treasurer", "Auditor", "President"} else (president.role or "Officer")

    officer_update_fields = ["role", "email", "department_id_FK", "account_status", "updated_at"]
    if not president.password_hash or president.password_hash == "unused":
        president.password_hash = hash_password(president.username)
        officer_update_fields.append("password_hash")

    president.role = role_value
    president.email = email or president.email
    president.department_id_FK = department
    president.account_status = "Active"
    president.save(update_fields=officer_update_fields)

    member = Member.objects.create(
        full_name=president.full_name,
        employee_id=employee_id,
        officer_user_id_FK=president,
        department=department.name if department else department_name or None,
        department_id_FK=department,
        position=position,
        contact_number=contact_number,
        email=email,
        employment_status="Active",
        membership_status="Pending",
        member_type="Member",
        date_joined=timezone.now().date(),
    )

    fee = MembershipFee.objects.create(
        member_id_FK=member,
        amount=str(get_membership_fee_amount()),
        payment_method="Pending",
        payment_status="Pending",
        payment_date=timezone.now().date(),
        receipt_number=f"OFFICER-SELF-{int(timezone.now().timestamp())}",
        recorded_by_user_id_FK=president,
    )
    TransactionVerification.objects.create(
        table_name="membership_fee",
        record_id=fee.fee_id_PK,
        verification_status="Pending",
    )

    _record_audit_trail(
        table="member",
        record_id=member.member_id_PK,
        action="CREATED",
        actor=president,
        new={
            "member_id": member.member_id_PK,
            "full_name": member.full_name,
            "employee_id": member.employee_id,
            "department": member.department or "",
            "position": member.position or "",
            "member_type": member.member_type,
            "officer_user_id": president.user_id_PK,
        },
        ip=request.META.get("REMOTE_ADDR"),
        notes="Officer self-enrolled as member",
    )

    _record_audit_trail(
        table="membership_fee",
        record_id=fee.fee_id_PK,
        action="CREATED",
        actor=president,
        new={
            "member_id": member.member_id_PK,
            "amount": str(fee.amount),
            "payment_status": fee.payment_status,
            "receipt_number": fee.receipt_number,
        },
        ip=request.META.get("REMOTE_ADDR"),
        notes="Auto-generated membership fee for officer self-enrollment",
    )

    _broadcast_to_group("treasurer_dashboard", {"type": "data_changed", "section": "members"})

    return JsonResponse({
        "ok": True,
        "member": {
            "member_id": member.member_id_PK,
            "employee_id": member.employee_id,
            "full_name": member.full_name,
        },
        "officer": {
            "username": president.username,
            "role": president.role,
            "default_password": president.username,
        },
    })


@require_GET
def get_policy_constants(request: HttpRequest):
    guard = require_role(request, role="President")
    if guard is not None:
        return guard

    president = _resolve_president(request)

    defaults = {
        "membership_fee": float(POLICY.membership_fee),
        "monthly_dues": float(POLICY.monthly_dues),
        "accidental_sickness_aid_threshold": float(POLICY.accidental_sickness_aid_threshold),
        "accidental_sickness_aid_benefit": float(POLICY.accidental_sickness_aid_benefit),
        "death_aid_member": float(POLICY.death_aid_member),
        "death_aid_spouse": float(POLICY.death_aid_spouse),
        "death_aid_parent_child": float(POLICY.death_aid_parent_child),
        "death_aid_full_blood_sibling": float(POLICY.death_aid_full_blood_sibling),
    }

    overrides = {}
    for key in defaults:
        raw = _get_setting_override(key)
        if raw is not None:
            try:
                overrides[key] = float(raw)
            except (TypeError, ValueError):
                overrides[key] = defaults[key]
        else:
            overrides[key] = defaults[key]

    _record_audit_trail(
        table="policy_constants",
        record_id=0,
        action="READ",
        actor=president,
        ip=request.META.get("REMOTE_ADDR"),
        notes="Retrieved policy constants snapshot",
    )

    return JsonResponse({
        "ok": True,
        "constants": overrides,
        "defaults": defaults,
    })


@require_POST
@transaction.atomic
def update_policy_constant(request: HttpRequest):
    guard = require_role(request, role="President")
    if guard is not None:
        return guard
    # ZT check removed during transition

    president = _resolve_president(request)
    if president is None:
        return JsonResponse({"ok": False, "error": "Officer session missing."}, status=401)

    try:
        data = json.loads(request.body)
    except Exception:
        return JsonResponse({"ok": False, "error": "Invalid JSON body."}, status=400)

    key = (data.get("key") or "").strip()
    value_raw = data.get("value")

    allowed_keys = {k for k, _, _ in _POLICY_CONSTANT_KEYS}
    if key not in allowed_keys:
        return JsonResponse({"ok": False, "error": f"Unknown constant key: {key}"}, status=400)

    try:
        new_value = float(value_raw)
    except (TypeError, ValueError):
        return JsonResponse({"ok": False, "error": "Value must be a number."}, status=400)

    if new_value < 0:
        return JsonResponse({"ok": False, "error": "Value cannot be negative."}, status=400)

    old_value = None
    setting_key = f"{_POLICY_OVERRIDE_PREFIX}{key}"
    row, _ = SystemSetting.objects.get_or_create(
        setting_key=setting_key,
        defaults={"setting_value": str(new_value)},
    )
    old_value = row.setting_value
    row.setting_value = str(new_value)
    row.save(update_fields=["setting_value", "updated_at"])

    _record_audit_trail(
        table="policy_constants",
        record_id=0,
        action="UPDATED",
        actor=president,
        old={"key": key, "value": old_value},
        new={"key": key, "value": str(new_value)},
        ip=request.META.get("REMOTE_ADDR"),
        notes=f"Updated policy constant {key}",
    )

    return JsonResponse({
        "ok": True,
        "message": f"Constant {key} updated to ₱{new_value:,.2f}",
        "key": key,
        "value": new_value,
    })


@require_GET
def bylaws_files_api(request: HttpRequest):
    guard = require_role(request, role="President")
    if guard is not None:
        return guard

    president = _resolve_president(request)
    files = BylawsFile.objects.all().order_by("-uploaded_at")

    data = []
    for f in files:
        data.append({
            "document_id": f.bylaws_file_id,
            "document_type": f.document_type,
            "file_name": f.file_name,
            "file_type": f.file_type,
            "uploaded_at": f.uploaded_at.strftime("%Y-%m-%d %H:%M:%S") if f.uploaded_at else None,
            "uploaded_by": f.uploaded_by_user_id_FK.full_name if f.uploaded_by_user_id_FK else "System",
            "verification_status": f.verification_status,
            "is_public_visible": f.is_public_visible,
        })

    _record_audit_trail(
        table="bylaws_documents",
        record_id=0,
        action="READ",
        actor=president,
        ip=request.META.get("REMOTE_ADDR"),
        notes="Listed bylaws document archive",
    )

    return JsonResponse({"ok": True, "files": data})


@require_POST
@transaction.atomic
def upload_bylaws_file(request: HttpRequest):
    guard = require_role(request, role="President")
    if guard is not None:
        return guard

    president = _resolve_president(request)
    if president is None:
        return JsonResponse({"ok": False, "error": "Officer session missing."}, status=401)

    uploaded_file = request.FILES.get("bylaws_file")
    if not uploaded_file:
        return JsonResponse({"ok": False, "error": "No file uploaded."}, status=400)

    allowed_types = {"application/pdf", "text/plain", "application/msword",
                     "application/vnd.openxmlformats-officedocument.wordprocessingml.document"}
    if uploaded_file.content_type not in allowed_types:
        return JsonResponse({"ok": False, "error": f"Unsupported file type: {uploaded_file.content_type}"}, status=400)

    allowed_doc_types = {"Constitution", "By-Laws", "Other", "Public Documents"}
    document_type = (request.POST.get("document_type") or "By-Laws").strip()
    if document_type not in allowed_doc_types:
        document_type = "By-Laws"

    is_public_visible = request.POST.get("is_public_visible") in ("1", "true", "True", "on")

    max_size = 10 * 1024 * 1024
    if uploaded_file.size > max_size:
        return JsonResponse({"ok": False, "error": "File size exceeds 10MB limit."}, status=400)

    file_bytes = uploaded_file.read()
    file_hash = ""
    try:
        hasher = hashlib.sha256()
        hasher.update(file_bytes)
        file_hash = hasher.hexdigest()
    except Exception:
        file_hash = ""

    doc = BylawsFile.objects.create(
        document_type=document_type,
        file_name=uploaded_file.name,
        file_type=uploaded_file.content_type or "",
        file_data=file_bytes,
        file_size=uploaded_file.size or 0,
        file_hash=file_hash or "",
        verification_status="Active",
        is_public_visible=is_public_visible,
        uploaded_by_user_id_FK=president,
    )

    _record_audit_trail(
        table="bylaws_documents",
        record_id=doc.bylaws_file_id,
        action="UPLOADED",
        actor=president,
        new={
            "document_type": doc.document_type,
            "file_name": uploaded_file.name,
            "file_type": uploaded_file.content_type,
            "file_size": uploaded_file.size,
            "file_hash": file_hash,
        },
        ip=request.META.get("REMOTE_ADDR"),
        notes=f"Uploaded bylaws file: {uploaded_file.name}",
    )

    return JsonResponse({
        "ok": True,
        "message": f"Bylaws file '{uploaded_file.name}' uploaded successfully.",
        "document_id": doc.bylaws_file_id,
        "file_name": uploaded_file.name,
    })


@require_POST
@transaction.atomic
def delete_bylaws_file(request: HttpRequest, document_id: int):
    guard = require_role(request, role="President")
    if guard is not None:
        return guard
    # ZT check removed during transition

    president = _resolve_president(request)
    if president is None:
        return JsonResponse({"ok": False, "error": "Officer session missing."}, status=401)

    doc = get_object_or_404(BylawsFile, pk=document_id)
    old_values = {
        "file_name": doc.file_name,
        "file_type": doc.file_type,
        "verification_status": doc.verification_status,
    }

    doc.delete()

    _record_audit_trail(
        table="bylaws_documents",
        record_id=document_id,
        action="DELETED",
        actor=president,
        old=old_values,
        ip=request.META.get("REMOTE_ADDR"),
        notes=f"Deleted bylaws file: {old_values.get('file_name')}",
    )

    return JsonResponse({"ok": True, "message": "Bylaws file deleted successfully."})


@require_POST
@transaction.atomic
def toggle_bylaws_visibility(request: HttpRequest, document_id: int):
    guard = require_role(request, role="President")
    if guard is not None:
        return guard

    president = _resolve_president(request)
    if president is None:
        return JsonResponse({"ok": False, "error": "Officer session missing."}, status=401)

    doc = get_object_or_404(BylawsFile, pk=document_id)
    doc.is_public_visible = not doc.is_public_visible
    doc.save(update_fields=["is_public_visible"])

    _record_audit_trail(
        table="bylaws_documents",
        record_id=doc.bylaws_file_id,
        action="VISIBILITY_TOGGLED",
        actor=president,
        new={"is_public_visible": doc.is_public_visible},
        old={"is_public_visible": not doc.is_public_visible},
        ip=request.META.get("REMOTE_ADDR"),
        notes=f"Toggled public visibility for bylaws file: {doc.file_name}",
    )

    return JsonResponse({
        "ok": True,
        "is_public_visible": doc.is_public_visible,
        "message": "Visibility updated.",
    })


@require_GET
def president_backups_list(request: HttpRequest):
    guard = require_role(request, role=["President", "System"])
    if guard is not None:
        return guard
    # ZT check removed during transition

    limit = request.GET.get("limit", 50)
    jobs = list_backup_jobs(limit=limit)
    return JsonResponse({
        "ok": True,
        "jobs": [
            {
                "job_id": j.job_id,
                "backup_type": j.backup_type,
                "backup_status": j.backup_status,
                "created_at": j.created_at.isoformat() if j.created_at else None,
                "db_dump_path": j.db_dump_path,
                "media_archive_path": j.media_archive_path,
            }
            for j in jobs
        ],
    })


@require_POST
@transaction.atomic
def president_backups_manual(request: HttpRequest):
    guard = require_role(request, role=["President", "System"])
    if guard is not None:
        return guard
    # ZT check removed during transition

    officer = _resolve_officer(request)
    if officer is None:
        return JsonResponse({"ok": False, "error": "Officer session missing."}, status=401)

    try:
        jobs = trigger_manual_backup()
        _record_audit_trail(
            table="backup_job",
            record_id=0,
            action="BACKUP_MANUAL",
            actor=officer,
            ip=request.META.get("REMOTE_ADDR"),
            notes=f"Manual backup triggered ({', '.join(j.backup_type for j in jobs)})",
        )
        return JsonResponse({
            "ok": True,
            "jobs": [
                {
                    "job_id": j.job_id,
                    "backup_type": j.backup_type,
                    "backup_status": j.backup_status,
                    "created_at": j.created_at.isoformat() if j.created_at else None,
                }
                for j in jobs
            ],
        })
    except Exception as e:
        logger.exception("Manual backup failed")
        return JsonResponse({"ok": False, "error": str(e)}, status=500)


@require_POST
@transaction.atomic
def president_backups_restore(request: HttpRequest, job_id: int):
    guard = require_role(request, role=["President", "System"])
    if guard is not None:
        return guard
    # ZT check removed during transition

    officer = _resolve_officer(request)
    if officer is None:
        return JsonResponse({"ok": False, "error": "Officer session missing."}, status=401)

    result = restore_backup_job(
        job_id=job_id,
        actor_officer=officer,
        ip=request.META.get("REMOTE_ADDR"),
    )

    _record_audit_trail(
        table="backup_job",
        record_id=job_id,
        action="BACKUP_RESTORE",
        actor=officer,
        ip=request.META.get("REMOTE_ADDR"),
        notes=f"Restore attempted for backup job {job_id}: {'succeeded' if result.get('ok') else 'failed - ' + result.get('error', '')}",
    )

    if not result.get("ok"):
        return JsonResponse(result, status=500)
    return JsonResponse(result)


@require_GET
def president_audit_logs(request: HttpRequest):
    guard = require_role(request, role="President")
    if guard is not None:
        return guard

    limit = int(request.GET.get("limit", 50))
    offset = int(request.GET.get("offset", 0))
    action_filter = request.GET.get("action", "")
    table_filter = request.GET.get("table", "")
    actor_filter = request.GET.get("actor", "")
    role_filter = request.GET.get("role", "")

    qs = GlobalAuditTrail.objects.all().order_by("-timestamp")

    if action_filter:
        qs = qs.filter(action__icontains=action_filter)
    if table_filter:
        qs = qs.filter(table_name__icontains=table_filter)
    if actor_filter:
        qs = qs.filter(actor_name__icontains=actor_filter)
    if role_filter:
        qs = qs.filter(actor_type__icontains=role_filter)

    total = qs.count()
    logs = list(qs[offset:offset + limit])

    return JsonResponse({
        "ok": True,
        "logs": [
            {
                "trail_id": log.trail_id,
                "table_name": log.table_name,
                "record_id": log.record_id,
                "action": log.action,
                "actor_name": log.actor_name,
                "actor_type": log.actor_type,
                "actor_id": log.actor_id,
                "ip_address": str(log.ip_address) if log.ip_address else None,
                "device_info": log.device_info,
                "notes": log.notes,
                "timestamp": log.timestamp.isoformat() if log.timestamp else None,
                "old_values": log.old_values,
                "new_values": log.new_values,
            }
            for log in logs
        ],
        "total": total,
        "offset": offset,
        "limit": limit,
    })


# ==========================================================================
# PRESIDENT REGISTRATION APPROVAL — Final step for registration requests
# ==========================================================================


@require_GET
def president_registration_requests_list(request: HttpRequest):
    """List registration requests awaiting president approval (Auditor Verified)."""
    guard = require_role(request, role="President")
    if guard is not None:
        return guard

    requests_qs = MemberRegistrationRequest.objects.filter(
        status=RegistrationStatus.AUDITOR_VERIFIED,
    ).select_related(
        "processed_by_user_id_FK",
        "treasurer_verified_by_user_id_FK",
        "auditor_verified_by_user_id_FK",
    ).order_by("-updated_at")

    rows = []
    for req in requests_qs:
        rows.append({
            "id": req.request_id_PK,
            "full_name": req.full_name,
            "employee_id": req.employee_id,
            "email": req.email or "",
            "department_name": req.department or "",
            "position": req.position or "",
            "membership_category": req.membership_category,
            "payment_amount": float(req.amount) if req.amount else 0,
            "payment_method": req.payment_method,
            "receipt_number": req.receipt_number,
            "reference_number": req.reference_number or "",
            "payment_date": str(req.payment_date) if req.payment_date else "",
            "status": req.status,
            "created_at": req.submitted_at.isoformat() if req.submitted_at else "",
            "treasurer_verified_by_name": getattr(req.treasurer_verified_by_user_id_FK, "full_name", "") if req.treasurer_verified_by_user_id_FK else "",
            "auditor_verified_by_name": getattr(req.auditor_verified_by_user_id_FK, "full_name", "") if req.auditor_verified_by_user_id_FK else "",
            "proof_url": _get_proof_url(MemberRegistrationRequest, req.request_id_PK) or "",
        })

    return JsonResponse({"ok": True, "requests": rows})


@require_POST
@transaction.atomic
def president_approve_registration_request(request: HttpRequest, request_id: int):
    """President approves registration request — creates Member, OfficerUser, MembershipFee, FundTransaction."""
    guard = require_role(request, role="President")
    if guard is not None:
        return guard
    # ZT check removed during transition

    officer = resolve_officer_from_session(request)
    if officer is None:
        return JsonResponse({"ok": False, "error": "Unable to resolve officer session."}, status=401)

    request_row = get_object_or_404(MemberRegistrationRequest.objects.select_for_update(), request_id_PK=request_id)
    action = (request.POST.get("action") or "").strip().lower()
    reason = (request.POST.get("reason") or "").strip()

    if action not in {"approve", "reject"}:
        return JsonResponse({"ok": False, "error": "Invalid action specified."}, status=400)

    if request_row.status != RegistrationStatus.AUDITOR_VERIFIED:
        return JsonResponse(
            {"ok": False, "error": "This registration request is not awaiting president approval."},
            status=400,
        )

    if action == "reject":
        if not reason:
            return JsonResponse({"ok": False, "error": "Reason is required for rejecting a request."}, status=400)
        request_row.status = RegistrationStatus.REJECTED
        request_row.returned_reason = reason
        request_row.president_approved_by_user_id_FK = officer
        request_row.save()

        _record_audit_trail(
            table="member_registration_request",
            record_id=request_row.request_id_PK,
            action="REJECTED",
            actor=officer,
            ip=request.META.get("REMOTE_ADDR"),
            notes=f"President rejected registration request for {request_row.full_name}: {reason}",
        )

        try:
            send_registration_rejected_email(request_row.email, request_row.full_name, reason=reason)
        except Exception:
            logger.exception("Failed to send rejection email for %s", request_row.full_name)

        return JsonResponse({"ok": True, "status": request_row.status})

    if Member.objects.filter(employee_id__iexact=request_row.employee_id).exists():
        return JsonResponse({"ok": False, "error": "A member with this Employee ID already exists."}, status=409)

    membership_status = request_row.membership_category or "Permanent"
    payment_date = request_row.payment_date or timezone.now().date()
    try:
        fee_amount = float(request_row.amount)
    except (TypeError, ValueError):
        return JsonResponse({"ok": False, "error": "Invalid payment amount."}, status=400)

    expected_amount = float(get_membership_fee_amount())
    payment_status = "Full Payment" if fee_amount >= expected_amount else "Partial"
    now = timezone.now()

    member_obj = None
    fee = None

    try:
        with transaction.atomic():
            member_obj = Member.objects.create(
                full_name=request_row.full_name,
                employee_id=request_row.employee_id,
                department=request_row.department,
                position=request_row.position,
                contact_number="",
                email=request_row.email,
                employment_status="Active",
                membership_status=membership_status,
                member_type="Member",
                date_joined=now.date(),
            )

            # Generate a new secure password for the approved member
            from core_system.services.email_service import generate_secure_password
            generated_password = generate_secure_password()
            
            officer_user = OfficerUser.objects.create(
                full_name=request_row.full_name,
                username=request_row.employee_id,
                password_hash=hash_password(generated_password),
                role="Member",
                email=request_row.email,
                account_status="Active",
                must_change_password=True,
            )

            member_obj.officer_user_id_FK = officer_user
            member_obj.save(update_fields=["officer_user_id_FK"])

            fee = MembershipFee.objects.create(
                member_id_FK=member_obj,
                receipt_number=request_row.receipt_number,
                amount=fee_amount,
                payment_date=payment_date,
                payment_method=request_row.payment_method,
                payment_status=payment_status,
                deposit_reference=request_row.reference_number or None,
                recorded_by_user_id_FK=officer,
            )

            TransactionVerification.objects.create(
                table_name="membership_fee",
                record_id=fee.fee_id_PK,
                verification_status="Approved",
                auditor_id_FK=officer,
                president_id_FK=officer,
                verified_at=now,
                approved_at=now,
                auditor_remarks="Auto-approved via registration final approval",
            )

            FundTransaction.objects.create(
                direction="inflow",
                amount=fee_amount,
                source_type="membership_fee",
                source_id=fee.fee_id_PK,
                description=f"{request_row.full_name} - Membership Fee (registration)",
                reference_number=request_row.receipt_number,
                recorded_by_user_id_FK=officer,
            )

            # Mirror the FundTransaction above into MemberLedger so every
            # financial event is recorded in both ledgers in sync (C3).
            if not MemberLedger.objects.filter(
                reference_type="MembershipFee",
                reference_id=fee.fee_id_PK,
            ).exists():
                MemberLedger.objects.create(
                    member_id_FK=member_obj,
                    transaction_type="membership_fee",
                    amount=fee.amount,
                    direction="credit",
                    balance_after=(fee.amount),
                    reference_id=fee.fee_id_PK,
                    reference_type="MembershipFee",
                    description="Membership Fee Payment",
                    recorded_by_user_id_FK=officer,
                )

            proof = SupportingProof.objects.filter(
                content_type=ContentType.objects.get_for_model(MemberRegistrationRequest),
                object_id=request_row.request_id_PK,
            ).order_by("-uploaded_at").first()
            if proof:
                copy_proof = SupportingProof(
                    content_type=ContentType.objects.get_for_model(fee),
                    object_id=fee.fee_id_PK,
                    file=proof.file,
                    file_name=proof.file_name,
                    file_type=proof.file_type,
                    file_sha256=proof.file_sha256,
                    uploaded_by=officer,
                )
                copy_proof.row_signature = _compute_row_signature(proof.file_sha256, fee.fee_id_PK)
                copy_proof.save()

            request_row.status = RegistrationStatus.PRESIDENT_APPROVED
            request_row.president_approved_by_user_id_FK = officer
            request_row.save()

        _record_audit_trail(
            table="member_registration_request",
            record_id=request_row.request_id_PK,
            action="PRESIDENT_APPROVED",
            actor=officer,
            new={
                "member_id": member_obj.member_id_PK,
                "officer_user_id": officer_user.user_id_PK,
                "fee_id": fee.fee_id_PK,
                "status": RegistrationStatus.PRESIDENT_APPROVED,
            },
            ip=request.META.get("REMOTE_ADDR"),
            notes=f"President approved registration for {request_row.full_name}. Member/OfficerUser/MembershipFee created.",
        )

        recipient_email = request_row.email or member_obj.email
        if recipient_email:
            try:
                send_html_email(
                    subject="Welcome to ISU CAUFA – Membership Approved!",
                    recipient_list=[recipient_email],
                    html_template="emails/member_added.html",
                    context={
                        "full_name": member_obj.full_name,
                        "employee_id": member_obj.employee_id or "N/A",
                        "date_joined": member_obj.date_joined.strftime("%B %d, %Y") if member_obj.date_joined else str(now.date()),
                        "department": member_obj.department or "",
                        "monthly_dues_amount": get_monthly_dues_amount(),
                        "membership_fee_amount": get_membership_fee_amount(),
                        "officer_contact": "",
                        "generated_password": generated_password,
                    },
                )
                logger.info("Welcome email sent to %s <%s>", request_row.full_name, recipient_email)
            except Exception:
                logger.exception("Failed to send welcome email for %s", request_row.full_name)
        else:
            logger.warning("No email address for %s — welcome email not sent", request_row.full_name)

        notify_member(
            member_obj,
            notification_type="membership_approved",
            message=f"Your ISU CAUFA membership registration has been approved. Welcome aboard, {member_obj.full_name}!",
            category="general",
            url="/member/",
            send_push=True,
            sender_name=officer.full_name,
            sender_role="President",
            send_email=False,
        )

        _broadcast_pending_counts()
        _broadcast_to_group("treasurer_dashboard", {"type": "data_changed", "section": "members"})

        return JsonResponse({
            "ok": True,
            "member_id": member_obj.member_id_PK,
            "fee_id": fee.fee_id_PK,
            "status": request_row.status,
        })

    except IntegrityError as ex:
        logger.exception("Integrity error while approving registration request %s", request_id)
        return JsonResponse({"ok": False, "error": "This registration request has already been processed or the account already exists."}, status=409)
    except Exception as ex:
        return JsonResponse({"ok": False, "error": f"Failed to create member account: {str(ex)}"}, status=500)

# ==========================================================================
# OVERSIGHT REPORTS ENDPOINTS
# ==========================================================================

@require_GET
def oversight_members_by_college(request: HttpRequest):
    """Generate Members by College report with filtering."""
    guard = require_role(request, role=["President", "Auditor", "Treasurer"])
    if guard is not None:
        return guard

    report, legacy = build_report(request, "members_by_college")
    return JsonResponse({"ok": True, **legacy, "report": report})

@require_GET
def oversight_paid_unpaid_summary(request: HttpRequest):
    """Generate Paid/Unpaid Summary report."""
    guard = require_role(request, role=["President", "Auditor", "Treasurer"])
    if guard is not None:
        return guard

    report, legacy = build_report(request, "paid_unpaid_summary")
    return JsonResponse({"ok": True, **legacy, "report": report})

@require_GET
def oversight_pending_claims(request: HttpRequest):
    """Generate Pending Claims report."""
    guard = require_role(request, role=["President", "Auditor", "Treasurer"])
    if guard is not None:
        return guard

    report, legacy = build_report(request, "pending_claims")
    return JsonResponse({"ok": True, **legacy, "report": report})

@require_GET
def oversight_membership_summary(request: HttpRequest):
    """Generate Membership Summary report with statistics and trends."""
    guard = require_role(request, role=["President", "Auditor", "Treasurer"])
    if guard is not None:
        return guard

    report, legacy = build_report(request, "membership_summary")
    return JsonResponse({"ok": True, **legacy, "report": report})

@require_GET
def oversight_membership_status(request: HttpRequest):
    """Generate Membership Status report."""
    guard = require_role(request, role=["President", "Auditor", "Treasurer"])
    if guard is not None:
        return guard

    report, legacy = build_report(request, "membership_status")
    return JsonResponse({"ok": True, **legacy, "report": report})

@require_GET
def oversight_monthly_dues_summary(request: HttpRequest):
    """Generate Monthly Dues Summary with financial view."""
    guard = require_role(request, role=["President", "Auditor", "Treasurer"])
    if guard is not None:
        return guard

    report, legacy = build_report(request, "monthly_dues_summary")
    return JsonResponse({"ok": True, **legacy, "report": report})

@require_GET
def oversight_contributions_summary(request: HttpRequest):
    """Generate Contributions Summary for aid cases."""
    guard = require_role(request, role=["President", "Auditor", "Treasurer"])
    if guard is not None:
        return guard

    report, legacy = build_report(request, "contributions_summary")
    return JsonResponse({"ok": True, **legacy, "report": report})

@require_GET
def oversight_fund_summary(request: HttpRequest):
    """Generate Fund Summary with financial position."""
    guard = require_role(request, role=["President", "Auditor", "Treasurer"])
    if guard is not None:
        return guard

    report, legacy = build_report(request, "fund_summary")
    return JsonResponse({"ok": True, **legacy, "report": report})

@require_GET
def oversight_medical_aid(request: HttpRequest):
    """Generate Medical Aid report with case status."""
    guard = require_role(request, role=["President", "Auditor", "Treasurer"])
    if guard is not None:
        return guard

    report, legacy = build_report(request, "medical_aid")
    return JsonResponse({"ok": True, **legacy, "report": report})

@require_GET
def oversight_death_aid(request: HttpRequest):
    """Generate Death Aid report with beneficiary categories."""
    guard = require_role(request, role=["President", "Auditor", "Treasurer"])
    if guard is not None:
        return guard

    report, legacy = build_report(request, "death_aid")
    return JsonResponse({"ok": True, **legacy, "report": report})

@require_GET
def oversight_approved_claims(request: HttpRequest):
    """Generate Approved Claims report with approval chain."""
    guard = require_role(request, role=["President", "Auditor", "Treasurer"])
    if guard is not None:
        return guard

    report, legacy = build_report(request, "approved_claims")
    return JsonResponse({"ok": True, **legacy, "report": report})

@require_GET
def oversight_released_claims(request: HttpRequest):
    """Generate Released Claims report with release history."""
    guard = require_role(request, role=["President", "Auditor", "Treasurer"])
    if guard is not None:
        return guard

    report, legacy = build_report(request, "released_claims")
    return JsonResponse({"ok": True, **legacy, "report": report})


@require_GET
def oversight_export_report(request: HttpRequest):
    """Export an oversight report as XLSX or PDF using the same builders."""
    guard = require_role(request, role=["President", "Auditor", "Treasurer"])
    if guard is not None:
        return guard

    report_key = request.GET.get("report_key", "").strip()
    fmt = request.GET.get("format", "xlsx").strip().lower()

    report, _ = build_report(request, report_key)
    if report is None:
        return JsonResponse({"ok": False, "error": "Unknown report key."}, status=400)

    filename = f"{report_key}_{timezone.now().strftime('%Y%m%d_%H%M%S')}"

    if fmt == "pdf":
        payload = report_to_pdf(report)
        response = HttpResponse(payload, content_type="application/pdf")
        response["Content-Disposition"] = f'attachment; filename="{filename}.pdf"'
        return response

    wb = report_to_xlsx(report)
    response = HttpResponse(
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = f'attachment; filename="{filename}.xlsx"'
    wb.save(response)
    return response

@require_GET
def oversight_summary(request: HttpRequest):
    """Generate comprehensive oversight summary for executive dashboard."""
    try:
        guard = require_role(request, role=["President", "Auditor", "Treasurer"])
        if guard is not None:
            return guard
    except Exception as e:
        return JsonResponse({"ok": False, "error": f"Role check failed: {str(e)}"}, status=403)

    try:
        # Get filter parameters
        period = request.GET.get("period", "current_month")  # current_month, previous_month, current_year, custom
        college = request.GET.get("college", "")
        custom_start = request.GET.get("custom_start", "")
        custom_end = request.GET.get("custom_end", "")

        now = timezone.now()
        current_month = now.strftime("%m")
        current_year = now.strftime("%Y")

        # Determine date range based on period filter
        if period == "current_month":
            start_date = now.replace(day=1).date()
            end_date = now.date()
            month_key = f"{current_year}-{current_month}"
            display_period = f"{now.strftime('%B')} {current_year}"
        elif period == "previous_month":
            if current_month == "01":
                prev_month = "12"
                prev_year = str(int(current_year) - 1)
            else:
                prev_month = str(int(current_month) - 1).zfill(2)
                prev_year = current_year
            start_date = datetime(int(prev_year), int(prev_month), 1).date()
            end_date = datetime(int(prev_year), int(prev_month), 28).date()  # Simplified
            month_key = f"{prev_year}-{prev_month}"
            display_period = f"{MONTH_NAMES[int(prev_month) - 1]} {prev_year}"
        elif period == "current_year":
            start_date = now.replace(month=1, day=1).date()
            end_date = now.date()
            month_key = None  # Annual view
            display_period = f"{current_year}"
        elif period == "custom" and custom_start and custom_end:
            start_date = datetime.strptime(custom_start, "%Y-%m-%d").date()
            end_date = datetime.strptime(custom_end, "%Y-%m-%d").date()
            month_key = None
            display_period = f"{custom_start} to {custom_end}"
        else:
            # Default to current month
            start_date = now.replace(day=1).date()
            end_date = now.date()
            month_key = f"{current_year}-{current_month}"
            display_period = f"{now.strftime('%B')} {current_year}"

        # Get member statistics
        members = Member.objects.exclude(membership_status__iexact="retired")
        if college:
            members = members.filter(department__iexact=college)

        total_members = members.count()
        active_members = members.filter(membership_status__in=['Permanent', 'Temporary']).count()

        # Valid departments list (ONLY these 7 departments)
        VALID_DEPARTMENTS = [
            "CCSICT",  # College of Computing Studies, Information and Communication Technology
            "IAT",     # Institute of Agricultural Technology
            "PS",      # Polytechnic School
            "CED",     # COLLEGE OF EDUCATION
            "SAS",     # School of Arts and Sciences
            "CBM",     # (Don't touch - already good)
            "CCJE"     # College of Criminal Justice Education
        ]

        # Get members by college for horizontal bar chart (only valid departments)
        members_by_college = []
        for dept in members.values("department").annotate(count=Count("member_id_PK")).order_by("-count"):
            if dept["department"] and dept["department"] in VALID_DEPARTMENTS:
                members_by_college.append({
                    "college": dept["department"],
                    "count": dept["count"]
                })

        # Get payment statistics for selected period
        if month_key:
            dues = MonthlyDues.objects.filter(month_covered=month_key)
        else:
            # For annual or custom ranges, filter by date range
            dues = MonthlyDues.objects.filter(payment_date__range=[start_date, end_date])

        if college:
            dues = dues.filter(member_id_FK__department__iexact=college)

        paid_count = dues.filter(payment_status__in=Status.ALL_AUDITOR_VERIFIED).count()
        unpaid_count = dues.exclude(payment_status__in=Status.ALL_AUDITOR_VERIFIED | Status.ALL_PENDING).count()
        pending_count = dues.filter(payment_status__in=Status.ALL_PENDING).count()

        # Monthly dues payment status for donut chart
        payment_status_breakdown = {
            "paid": paid_count,
            "pending": pending_count,
            "unpaid": unpaid_count
        }

        # Monthly dues trend for line chart (last 6 months)
        dues_trend = []
        for i in range(6):
            trend_date = now - timedelta(days=30 * i)
            trend_month_key = trend_date.strftime("%Y-%m")
            trend_dues = MonthlyDues.objects.filter(month_covered=trend_month_key)
            if college:
                trend_dues = trend_dues.filter(member_id_FK__department__iexact=college)
            trend_paid = trend_dues.filter(payment_status__in=Status.ALL_AUDITOR_VERIFIED).count()
            trend_collected = trend_dues.filter(payment_status__in=Status.ALL_AUDITOR_VERIFIED).aggregate(
                total=Sum("amount")
            )["total"] or 0
            dues_trend.append({
                "month": trend_date.strftime("%b"),
                "month_key": trend_month_key,
                "paid_members": trend_paid,
                "collected_amount": float(trend_collected)
            })
        dues_trend.reverse()  # Show oldest to newest

        # Payment compliance by college for bar chart (only valid departments)
        compliance_by_college = []
        for dept in members.values("department").distinct():
            dept_name = dept["department"]
            if dept_name and dept_name in VALID_DEPARTMENTS:
                dept_members = members.filter(department=dept_name)
                dept_total = dept_members.count()
                if dept_total > 0:
                    dept_paid = MonthlyDues.objects.filter(
                        member_id_FK__in=dept_members,
                        month_covered=month_key if month_key else "",
                        payment_status__in=Status.ALL_AUDITOR_VERIFIED
                    ).count()
                    compliance_rate = round((dept_paid / dept_total * 100), 2)
                    compliance_by_college.append({
                        "college": dept_name,
                        "total": dept_total,
                        "paid": dept_paid,
                        "compliance": compliance_rate
                    })

        # Financial movement for bar chart
        fund_start_date = start_date
        fund_end_date = end_date
        if period == "current_year":
            fund_start_date = now.replace(month=1, day=1).date()
            fund_end_date = now.date()
        elif period == "previous_month":
            fund_start_date = start_date
            fund_end_date = end_date
        else:
            fund_start_date = start_date
            fund_end_date = end_date

        fund_transactions = FundTransaction.objects.filter(
            recorded_at__date__range=[fund_start_date, fund_end_date]
        ).order_by("recorded_at")

        contributions_inflow = fund_transactions.filter(
            description__icontains="contribution", direction="inflow"
        ).aggregate(total=Sum("amount"))["total"] or 0

        medical_aid_outflow = fund_transactions.filter(
            description__icontains="medical", direction="outflow"
        ).aggregate(total=Sum("amount"))["total"] or 0

        death_aid_outflow = fund_transactions.filter(
            description__icontains="death", direction="outflow"
        ).aggregate(total=Sum("amount"))["total"] or 0

        dues_inflow = fund_transactions.filter(
            description__icontains="dues", direction="inflow"
        ).aggregate(total=Sum("amount"))["total"] or 0

        other_inflow = fund_transactions.filter(
            direction="inflow"
        ).exclude(
            description__icontains="contribution"
        ).exclude(
            description__icontains="dues"
        ).aggregate(total=Sum("amount"))["total"] or 0

        financial_movement = {
            "contributions_in": float(contributions_inflow),
            "medical_aid_out": float(medical_aid_outflow),
            "death_aid_out": float(death_aid_outflow),
            "dues_in": float(dues_inflow),
            "other_in": float(other_inflow),
            "total_in": float(contributions_inflow + dues_inflow + other_inflow),
            "total_out": float(medical_aid_outflow + death_aid_outflow)
        }

        # Fund balance trend (last 6 months)
        fund_balance_trend = []
        running_balance = 0
        for i in range(6):
            trend_date = now - timedelta(days=30 * i)
            month_start = trend_date.replace(day=1)
            # Get last day of month
            if trend_date.month == 12:
                month_end = trend_date.replace(year=trend_date.year + 1, month=1, day=1) - timedelta(days=1)
            else:
                month_end = trend_date.replace(month=trend_date.month + 1, day=1) - timedelta(days=1)

            month_inflow = FundTransaction.objects.filter(
                recorded_at__date__range=[month_start, month_end],
                direction="inflow"
            ).aggregate(total=Sum("amount"))["total"] or 0

            month_outflow = FundTransaction.objects.filter(
                recorded_at__date__range=[month_start, month_end],
                direction="outflow"
            ).aggregate(total=Sum("amount"))["total"] or 0

            running_balance += float(month_inflow) - float(month_outflow)

            fund_balance_trend.append({
                "month": trend_date.strftime("%b"),
                "balance": running_balance
            })
        fund_balance_trend.reverse()

        # Medical aid and death aid statistics
        medical_claims = MedicalAid.objects.all()
        death_claims = DeathAid.objects.all()

        if college:
            medical_claims = medical_claims.filter(member_id_FK__department__iexact=college)
            death_claims = death_claims.filter(member_id_FK__department__iexact=college)

        # Apply date filters if not using month_key
        if not month_key:
            medical_claims = medical_claims.filter(request_date__range=[start_date, end_date])
            death_claims = death_claims.filter(claim_date__range=[start_date, end_date])

        outstanding_claim_statuses = (Status.ALL_PENDING | Status.ALL_AUDITOR_VERIFIED) - {Status.RELEASED, Status.COMPLETED}
        pending_medical = medical_claims.filter(status__in=outstanding_claim_statuses).count()
        approved_medical = medical_claims.filter(status__in=Status.ALL_AUDITOR_VERIFIED).count()
        released_medical = medical_claims.filter(status__in=[Status.RELEASED, Status.COMPLETED]).count()

        pending_death = death_claims.filter(status__in=outstanding_claim_statuses).count()
        approved_death = death_claims.filter(status__in=Status.ALL_AUDITOR_VERIFIED).count()
        released_death = death_claims.filter(status__in=[Status.RELEASED, Status.COMPLETED]).count()

        # Aid activity for grouped bar chart
        aid_activity = []
        for i in range(6):
            trend_date = now - timedelta(days=30 * i)
            month_start = trend_date.replace(day=1)
            if trend_date.month == 12:
                month_end = trend_date.replace(year=trend_date.year + 1, month=1, day=1) - timedelta(days=1)
            else:
                month_end = trend_date.replace(month=trend_date.month + 1, day=1) - timedelta(days=1)

            month_medical = MedicalAid.objects.filter(
                request_date__range=[month_start, month_end]
            ).count()
            month_death = DeathAid.objects.filter(
                claim_date__range=[month_start, month_end]
            ).count()

            aid_activity.append({
                "month": trend_date.strftime("%b"),
                "medical": month_medical,
                "death": month_death
            })
        aid_activity.reverse()

        # Claim approval pipeline for funnel
        pipeline_stages = {
            "submitted": medical_claims.filter(status="Submitted").count() + death_claims.filter(status="Submitted").count(),
            "treasurer_review": medical_claims.filter(status="Pending Treasurer Review").count() + death_claims.filter(status="Pending Treasurer Review").count(),
            "auditor_review": medical_claims.filter(status="Pending Auditor Review").count() + death_claims.filter(status="Pending Auditor Review").count(),
            "president_review": medical_claims.filter(status="Pending President Approval").count() + death_claims.filter(status="Pending President Approval").count(),
            "approved": approved_medical + approved_death,
            "released": released_medical + released_death
        }

        # Contribution statistics
        contributions = Contribution.objects.all()
        if college:
            contributions = contributions.filter(member_id_FK__department__iexact=college)

        if not month_key:
            contributions = contributions.filter(payment_date__range=[start_date, end_date])

        pending_contributions = contributions.filter(status="PENDING_VERIFICATION").count()
        paid_contributions = contributions.filter(status="PAID").count()

        total_expected = contributions.aggregate(total=Sum("expected_amount"))["total"] or 0
        total_paid = contributions.aggregate(total=Sum("paid_amount"))["total"] or 0

        contribution_progress = {
            "expected": float(total_expected),
            "collected": float(total_paid),
            "remaining": float(total_expected - total_paid),
            "percentage": round((total_paid / total_expected * 100) if total_expected > 0 else 0, 2)
        }

        # Current fund balance
        current_balance = FundTransaction.get_balance()

        # Activity trend (overall system activity)
        activity_trend = []
        for i in range(6):
            trend_date = now - timedelta(days=30 * i)
            month_start = trend_date.replace(day=1)
            # Get last day of month
            if trend_date.month == 12:
                month_end = trend_date.replace(year=trend_date.year + 1, month=1, day=1) - timedelta(days=1)
            else:
                month_end = trend_date.replace(month=trend_date.month + 1, day=1) - timedelta(days=1)

            month_activities = 0
            month_activities += MonthlyDues.objects.filter(
                payment_date__range=[month_start, month_end]
            ).count()
            month_activities += MedicalAid.objects.filter(
                request_date__range=[month_start, month_end]
            ).count()
            month_activities += DeathAid.objects.filter(
                claim_date__range=[month_start, month_end]
            ).count()
            month_activities += Contribution.objects.filter(
                payment_date__range=[month_start, month_end]
            ).count()

            activity_trend.append({
                "month": trend_date.strftime("%b"),
                "activities": month_activities
            })
        activity_trend.reverse()

        # Recent activity timeline
        recent_activities = []
        recent_medical = medical_claims.order_by("-request_date")[:5]
        recent_death = death_claims.order_by("-claim_date")[:5]
        recent_contributions = contributions.order_by("-payment_date")[:5]

        for claim in recent_medical:
            recent_activities.append({
                "type": "Medical Aid",
                "description": f"Medical Aid #{claim.medical_aid_id_PK}",
                "status": claim.status,
                "amount": float(claim.requested_amount) if claim.requested_amount else 0,
                "date": claim.request_date.strftime("%Y-%m-%d %H:%M") if claim.request_date else "N/A",
                "icon": "medkit"
            })

        for claim in recent_death:
            recent_activities.append({
                "type": "Death Aid",
                "description": f"Death Aid #{claim.death_aid_id_PK}",
                "status": claim.status,
                "amount": float(claim.benefit_amount) if claim.benefit_amount else 0,
                "date": claim.claim_date.strftime("%Y-%m-%d %H:%M") if claim.claim_date else "N/A",
                "icon": "heart"
            })

        for contrib in recent_contributions:
            recent_activities.append({
                "type": "Contribution",
                "description": f"Contribution for Aid",
                "status": contrib.status,
                "amount": float(contrib.paid_amount) if contrib.paid_amount else 0,
                "date": contrib.payment_date.strftime("%Y-%m-%d %H:%M") if contrib.payment_date else "N/A",
                "icon": "hand-holding-usd"
            })

        # Sort by date and take latest 10
        recent_activities.sort(key=lambda x: x["date"] if x["date"] != "N/A" else "1970-01-01", reverse=True)
        recent_activities = recent_activities[:10]

        # Attention required items
        attention_required = []

        # Aid requests awaiting treasurer review
        treasurer_review_count = pipeline_stages["treasurer_review"]
        if treasurer_review_count > 0:
            attention_required.append({
                "level": "high",
                "message": f"{treasurer_review_count} Aid Requests awaiting Treasurer Review",
                "icon": "exclamation-circle",
                "action": "aid-requests"
            })

        # Contributions not fully collected
        if contribution_progress["remaining"] > 0:
            attention_required.append({
                "level": "medium",
                "message": f"Contributions not yet fully collected (₱{contribution_progress['remaining']:,.2f} remaining)",
                "icon": "clock",
                "action": "contributions"
            })

        # Overdue payments (unpaid from current month)
        if unpaid_count > 0:
            attention_required.append({
                "level": "medium",
                "message": f"{unpaid_count} members with unpaid monthly dues",
                "icon": "money-bill",
                "action": "payments"
            })

        # Low compliance colleges
        low_compliance = [c for c in compliance_by_college if c["compliance"] < 70]
        if low_compliance:
            attention_required.append({
                "level": "low",
                "message": f"{len(low_compliance)} colleges with payment compliance below 70%",
                "icon": "chart-line",
                "action": "compliance"
            })

        # Calculate overall compliance rate
        compliance_rate = round((paid_count / total_members * 100) if total_members > 0 else 0, 2)

        return JsonResponse({
            "ok": True,
            "summary": {
                "members": {
                    "total": total_members,
                    "active": active_members,
                    "inactive": total_members - active_members,
                    "by_college": members_by_college
                },
                "payments": {
                    "paid": paid_count,
                    "unpaid": unpaid_count,
                    "pending": pending_count,
                    "compliance_rate": compliance_rate,
                    "status_breakdown": payment_status_breakdown,
                    "dues_trend": dues_trend,
                    "compliance_by_college": compliance_by_college
                },
                "claims": {
                    "pending_medical": pending_medical,
                    "pending_death": pending_death,
                    "approved_medical": approved_medical,
                    "approved_death": approved_death,
                    "released_medical": released_medical,
                    "released_death": released_death,
                    "total_pending": pending_medical + pending_death,
                    "total_approved": approved_medical + approved_death,
                    "total_released": released_medical + released_death,
                    "aid_activity": aid_activity,
                    "pipeline_stages": pipeline_stages
                },
                "contributions": {
                    "pending": pending_contributions,
                    "paid": paid_contributions,
                    "progress": contribution_progress
                },
                "funds": {
                    "current_balance": float(current_balance),
                    "financial_movement": financial_movement,
                    "balance_trend": fund_balance_trend
                },
                "activity": {
                    "trend": activity_trend,
                    "recent": recent_activities
                },
                "attention_required": attention_required,
                "period": {
                    "type": period,
                    "display": display_period,
                    "month": current_month,
                    "year": current_year,
                    "month_name": now.strftime("%B"),
                    "start_date": start_date.strftime("%Y-%m-%d"),
                    "end_date": end_date.strftime("%Y-%m-%d")
                },
            }
        })

    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        return JsonResponse({
            "ok": False,
            "error": str(e),
            "traceback": error_trace
        }, status=500)

    # Get filter parameters
    period = request.GET.get("period", "current_month")  # current_month, previous_month, current_year, custom
    college = request.GET.get("college", "")
    custom_start = request.GET.get("custom_start", "")
    custom_end = request.GET.get("custom_end", "")

    now = timezone.now()
    current_month = now.strftime("%m")
    current_year = now.strftime("%Y")
    
    # Determine date range based on period filter
    if period == "current_month":
        start_date = now.replace(day=1).date()
        end_date = now.date()
        month_key = f"{current_year}-{current_month}"
        display_period = f"{now.strftime('%B')} {current_year}"
    elif period == "previous_month":
        if current_month == "01":
            prev_month = "12"
            prev_year = str(int(current_year) - 1)
        else:
            prev_month = str(int(current_month) - 1).zfill(2)
            prev_year = current_year
        start_date = datetime(int(prev_year), int(prev_month), 1).date()
        end_date = datetime(int(prev_year), int(prev_month), 28).date()  # Simplified
        month_key = f"{prev_year}-{prev_month}"
        display_period = f"{MONTH_NAMES[int(prev_month) - 1]} {prev_year}"
    elif period == "current_year":
        start_date = now.replace(month=1, day=1).date()
        end_date = now.date()
        month_key = None  # Annual view
        display_period = f"{current_year}"
    elif period == "custom" and custom_start and custom_end:
        start_date = datetime.strptime(custom_start, "%Y-%m-%d").date()
        end_date = datetime.strptime(custom_end, "%Y-%m-%d").date()
        month_key = None
        display_period = f"{custom_start} to {custom_end}"
    else:
        # Default to current month
        start_date = now.replace(day=1).date()
        end_date = now.date()
        month_key = f"{current_year}-{current_month}"
        display_period = f"{now.strftime('%B')} {current_year}"

    # Get member statistics
    members = Member.objects.exclude(membership_status__iexact="retired")
    if college:
        members = members.filter(department__iexact=college)
    
    total_members = members.count()
    active_members = members.filter(membership_status__in=['Permanent', 'Temporary']).count()
    
    # Get members by college for horizontal bar chart
    members_by_college = []
    for dept in members.values("department").annotate(count=Count("member_id_PK")).order_by("-count"):
        if dept["department"]:
            members_by_college.append({
                "college": dept["department"],
                "count": dept["count"]
            })
    
    # Get payment statistics for selected period
    if month_key:
        dues = MonthlyDues.objects.filter(month_covered=month_key)
    else:
        # For annual or custom ranges, filter by date range
        dues = MonthlyDues.objects.filter(payment_date__range=[start_date, end_date])
    
    if college:
        dues = dues.filter(member_id_FK__department__iexact=college)
    
    paid_count = dues.filter(payment_status__in=Status.ALL_AUDITOR_VERIFIED).count()
    unpaid_count = dues.exclude(payment_status__in=Status.ALL_AUDITOR_VERIFIED | Status.ALL_PENDING).count()
    pending_count = dues.filter(payment_status__in=Status.ALL_PENDING).count()
    
    # Monthly dues payment status for donut chart
    payment_status_breakdown = {
        "paid": paid_count,
        "pending": pending_count,
        "unpaid": unpaid_count
    }
    
    # Monthly dues trend for line chart (last 6 months)
    dues_trend = []
    for i in range(6):
        trend_date = now - timedelta(days=30 * i)
        trend_month_key = trend_date.strftime("%Y-%m")
        trend_dues = MonthlyDues.objects.filter(month_covered=trend_month_key)
        if college:
            trend_dues = trend_dues.filter(member_id_FK__department__iexact=college)
        trend_paid = trend_dues.filter(payment_status__in=Status.ALL_AUDITOR_VERIFIED).count()
        trend_collected = trend_dues.filter(payment_status__in=Status.ALL_AUDITOR_VERIFIED).aggregate(
            total=Sum("amount")
        )["total"] or 0
        dues_trend.append({
            "month": trend_date.strftime("%b"),
            "month_key": trend_month_key,
            "paid_members": trend_paid,
            "collected_amount": float(trend_collected)
        })
    dues_trend.reverse()  # Show oldest to newest
    
    # Payment compliance by college for bar chart
    compliance_by_college = []
    for dept in members.values("department").distinct():
        dept_name = dept["department"]
        if dept_name:
            dept_members = members.filter(department=dept_name)
            dept_total = dept_members.count()
            if month_key:
                dept_dues = MonthlyDues.objects.filter(month_covered=month_key, member_id_FK__department=dept_name)
            else:
                dept_dues = MonthlyDues.objects.filter(
                    payment_date__range=[start_date, end_date],
                    member_id_FK__department=dept_name
                )
            dept_paid = dept_dues.filter(payment_status__in=Status.ALL_AUDITOR_VERIFIED).count()
            compliance_rate = round((dept_paid / dept_total * 100) if dept_total > 0 else 0, 2)
            compliance_by_college.append({
                "college": dept_name,
                "compliance": compliance_rate,
                "total": dept_total,
                "paid": dept_paid
            })
    
    # Get claims statistics with detailed breakdown
    medical_claims = MedicalAid.objects.all()
    death_claims = DeathAid.objects.all()
    
    if college:
        medical_claims = medical_claims.filter(member_id_FK__department__iexact=college)
        death_claims = death_claims.filter(member_id_FK__department__iexact=college)
    
    # Filter by date range if not current month view
    if not month_key:
        medical_claims = medical_claims.filter(request_date__range=[start_date, end_date])
        death_claims = death_claims.filter(claim_date__range=[start_date, end_date])
    
    outstanding_claim_statuses = (Status.ALL_PENDING | Status.ALL_AUDITOR_VERIFIED) - {Status.RELEASED, Status.COMPLETED}
    pending_medical = medical_claims.filter(status__in=outstanding_claim_statuses).count()
    pending_death = death_claims.filter(status__in=outstanding_claim_statuses).count()
    approved_medical = medical_claims.filter(status__in=Status.ALL_AUDITOR_VERIFIED).count()
    approved_death = death_claims.filter(status__in=Status.ALL_AUDITOR_VERIFIED).count()
    released_medical = medical_claims.filter(status__in=[Status.RELEASED, Status.COMPLETED]).count()
    released_death = death_claims.filter(status__in=[Status.RELEASED, Status.COMPLETED]).count()
    
    # Medical vs Death aid activity for grouped bar chart
    aid_activity = {
        "medical": {
            "requests": medical_claims.count(),
            "approved": approved_medical,
            "released": released_medical
        },
        "death": {
            "requests": death_claims.count(),
            "approved": approved_death,
            "released": released_death
        }
    }
    
    # Claim approval pipeline for funnel visualization
    pipeline_stages = {
        "treasurer_review": 0,
        "auditor_verification": 0,
        "president_approval": 0,
        "released": 0
    }
    
    for claim in medical_claims:
        stage = STAGE_MAP.get(claim.status, "Unknown")
        if stage == "Treasurer Review":
            pipeline_stages["treasurer_review"] += 1
        elif stage == "Auditor Verification":
            pipeline_stages["auditor_verification"] += 1
        elif stage == "President Approval":
            pipeline_stages["president_approval"] += 1
        elif stage == "Released":
            pipeline_stages["released"] += 1
    
    for claim in death_claims:
        stage = STAGE_MAP.get(claim.status, "Unknown")
        if stage == "Treasurer Review":
            pipeline_stages["treasurer_review"] += 1
        elif stage == "Auditor Verification":
            pipeline_stages["auditor_verification"] += 1
        elif stage == "President Approval":
            pipeline_stages["president_approval"] += 1
        elif stage == "Released":
            pipeline_stages["released"] += 1
    
    # Get contributions statistics
    contributions = Contribution.objects.all()
    if college:
        contributions = contributions.filter(aid_tracking_post_id_FK__source_type__in=["medical_aid", "death_aid"])
        # Need to filter by member department through the aid tracking post
        medical_post_ids = AidTrackingPost.objects.filter(
            source_type="medical_aid",
            source_id__in=medical_claims.values_list("medical_aid_id_PK", flat=True)
        ).values_list("post_id_PK", flat=True)
        death_post_ids = AidTrackingPost.objects.filter(
            source_type="death_aid", 
            source_id__in=death_claims.values_list("death_aid_id_PK", flat=True)
        ).values_list("post_id_PK", flat=True)
        contributions = contributions.filter(aid_tracking_post_id_FK_id__in=list(medical_post_ids) + list(death_post_ids))
    
    pending_contributions = contributions.filter(status__in=["NOT_PAID", "PENDING_VERIFICATION"]).count()
    paid_contributions = contributions.filter(status="PAID").count()
    
    # Contribution collection progress
    total_expected = contributions.aggregate(total=Sum("expected_amount"))["total"] or 0
    total_collected = contributions.aggregate(total=Sum("paid_amount"))["total"] or 0
    contribution_progress = {
        "expected": float(total_expected),
        "collected": float(total_collected),
        "remaining": float(total_expected - total_collected),
        "percentage": round((total_collected / total_expected * 100) if total_expected > 0 else 0, 2)
    }
    
    # Fund movement and balance trend
    int_year = int(current_year)
    if period == "current_year":
        fund_start_date = now.replace(month=1, day=1)
        fund_end_date = now
    elif period == "custom":
        fund_start_date = start_date
        fund_end_date = end_date
    else:
        fund_start_date = now.replace(day=1)
        fund_end_date = now
    
    fund_transactions = FundTransaction.objects.filter(
        recorded_at__date__range=[fund_start_date, fund_end_date]
    ).order_by("recorded_at")
    
    contributions_inflow = fund_transactions.filter(
        description__icontains="contribution", direction="inflow"
    ).aggregate(total=Sum("amount"))["total"] or 0
    
    medical_aid_outflow = fund_transactions.filter(
        description__icontains="medical", direction="outflow"
    ).aggregate(total=Sum("amount"))["total"] or 0
    
    death_aid_outflow = fund_transactions.filter(
        description__icontains="death", direction="outflow"
    ).aggregate(total=Sum("amount"))["total"] or 0
    
    other_inflow = fund_transactions.filter(
        direction="inflow"
    ).exclude(description__icontains="contribution").aggregate(total=Sum("amount"))["total"] or 0
    
    releases_outflow = fund_transactions.filter(
        direction="outflow"
    ).exclude(description__icontains="medical").exclude(description__icontains="death").aggregate(total=Sum("amount"))["total"] or 0
    
    financial_movement = {
        "contributions": float(contributions_inflow),
        "medical_aid": float(medical_aid_outflow),
        "death_aid": float(death_aid_outflow),
        "other_inflow": float(other_inflow),
        "releases": float(releases_outflow)
    }
    
    # Fund balance trend (last 6 months)
    fund_balance_trend = []
    running_balance = 0
    for i in range(6):
        trend_date = now - timedelta(days=30 * i)
        month_start = trend_date.replace(day=1)
        # Get last day of month
        if trend_date.month == 12:
            month_end = trend_date.replace(year=trend_date.year + 1, month=1, day=1) - timedelta(days=1)
        else:
            month_end = trend_date.replace(month=trend_date.month + 1, day=1) - timedelta(days=1)
        
        month_inflow = FundTransaction.objects.filter(
            recorded_at__date__range=[month_start, month_end],
            direction="inflow"
        ).aggregate(total=Sum("amount"))["total"] or 0
        
        month_outflow = FundTransaction.objects.filter(
            recorded_at__date__range=[month_start, month_end],
            direction="outflow"
        ).aggregate(total=Sum("amount"))["total"] or 0
        
        running_balance += float(month_inflow) - float(month_outflow)
        
        fund_balance_trend.append({
            "month": trend_date.strftime("%b"),
            "balance": running_balance
        })
    fund_balance_trend.reverse()
    
    # Current fund balance
    current_balance = fund_transactions.aggregate(
        balance=Sum("amount", filter=Q(direction="inflow")) - Sum("amount", filter=Q(direction="outflow"))
    )["balance"] or 0
    
    # Activity trend (overall system activity)
    activity_trend = []
    for i in range(6):
        trend_date = now - timedelta(days=30 * i)
        month_start = trend_date.replace(day=1)
        # Get last day of month
        if trend_date.month == 12:
            month_end = trend_date.replace(year=trend_date.year + 1, month=1, day=1) - timedelta(days=1)
        else:
            month_end = trend_date.replace(month=trend_date.month + 1, day=1) - timedelta(days=1)
        
        month_activities = 0
        month_activities += MonthlyDues.objects.filter(
            payment_date__range=[month_start, month_end]
        ).count()
        month_activities += MedicalAid.objects.filter(
            request_date__range=[month_start, month_end]
        ).count()
        month_activities += DeathAid.objects.filter(
            claim_date__date__range=[month_start, month_end]
        ).count()
        month_activities += Contribution.objects.filter(
            payment_date__range=[month_start, month_end]
        ).count()
        
        activity_trend.append({
            "month": trend_date.strftime("%b"),
            "activities": month_activities
        })
    activity_trend.reverse()
    
    # Recent activity timeline
    recent_activities = []
    recent_medical = medical_claims.order_by("-request_date")[:5]
    recent_death = death_claims.order_by("-claim_date")[:5]
    recent_contributions = contributions.order_by("-payment_date")[:5]
    
    for claim in recent_medical:
        recent_activities.append({
            "type": "Medical Aid",
            "description": f"Medical Aid #{claim.medical_aid_id_PK}",
            "status": claim.status,
            "amount": float(claim.requested_amount) if claim.requested_amount else 0,
            "date": claim.request_date.strftime("%Y-%m-%d %H:%M") if claim.request_date else "N/A",
            "icon": "medkit"
        })
    
    for claim in recent_death:
        recent_activities.append({
            "type": "Death Aid",
            "description": f"Death Aid #{claim.death_aid_id_PK}",
            "status": claim.status,
            "amount": float(claim.benefit_amount) if claim.benefit_amount else 0,
            "date": claim.claim_date.strftime("%Y-%m-%d %H:%M") if claim.claim_date else "N/A",
            "icon": "heart"
        })
    
    for contrib in recent_contributions:
        recent_activities.append({
            "type": "Contribution",
            "description": f"Contribution for Aid",
            "status": contrib.status,
            "amount": float(contrib.paid_amount) if contrib.paid_amount else 0,
            "date": contrib.payment_date.strftime("%Y-%m-%d %H:%M") if contrib.payment_date else "N/A",
            "icon": "hand-holding-usd"
        })
    
    # Sort by date and take latest 10
    recent_activities.sort(key=lambda x: x["date"] if x["date"] != "N/A" else "1970-01-01", reverse=True)
    recent_activities = recent_activities[:10]
    
    # Attention required items
    attention_required = []
    
    # Aid requests awaiting treasurer review
    treasurer_review_count = pipeline_stages["treasurer_review"]
    if treasurer_review_count > 0:
        attention_required.append({
            "level": "high",
            "message": f"{treasurer_review_count} Aid Requests awaiting Treasurer Review",
            "icon": "exclamation-circle",
            "action": "aid-requests"
        })
    
    # Contributions not fully collected
    if contribution_progress["remaining"] > 0:
        attention_required.append({
            "level": "medium",
            "message": f"Contributions not yet fully collected (₱{contribution_progress['remaining']:,.2f} remaining)",
            "icon": "clock",
            "action": "contributions"
        })
    
    # Overdue payments (unpaid from current month)
    if unpaid_count > 0:
        attention_required.append({
            "level": "medium",
            "message": f"{unpaid_count} members with unpaid monthly dues",
            "icon": "money-bill",
            "action": "payments"
        })
    
    # Low compliance colleges
    low_compliance = [c for c in compliance_by_college if c["compliance"] < 70]
    if low_compliance:
        attention_required.append({
            "level": "low",
            "message": f"{len(low_compliance)} colleges with payment compliance below 70%",
            "icon": "chart-line",
            "action": "compliance"
        })
    
    # Calculate overall compliance rate
    compliance_rate = round((paid_count / total_members * 100) if total_members > 0 else 0, 2)

    return JsonResponse({
        "ok": True,
        "summary": {
            "members": {
                "total": total_members,
                "active": active_members,
                "inactive": total_members - active_members,
                "by_college": members_by_college
            },
            "payments": {
                "paid": paid_count,
                "unpaid": unpaid_count,
                "pending": pending_count,
                "compliance_rate": compliance_rate,
                "status_breakdown": payment_status_breakdown,
                "dues_trend": dues_trend,
                "compliance_by_college": compliance_by_college
            },
            "claims": {
                "pending_medical": pending_medical,
                "pending_death": pending_death,
                "approved_medical": approved_medical,
                "approved_death": approved_death,
                "released_medical": released_medical,
                "released_death": released_death,
                "total_pending": pending_medical + pending_death,
                "total_approved": approved_medical + approved_death,
                "total_released": released_medical + released_death,
                "aid_activity": aid_activity,
                "pipeline_stages": pipeline_stages
            },
            "contributions": {
                "pending": pending_contributions,
                "paid": paid_contributions,
                "progress": contribution_progress
            },
            "funds": {
                "current_balance": float(current_balance),
                "financial_movement": financial_movement,
                "balance_trend": fund_balance_trend
            },
            "activity": {
                "trend": activity_trend,
                "recent": recent_activities
            },
            "attention_required": attention_required,
            "period": {
                "type": period,
                "display": display_period,
                "month": current_month,
                "year": current_year,
                "month_name": now.strftime("%B"),
                "start_date": start_date.strftime("%Y-%m-%d"),
                "end_date": end_date.strftime("%Y-%m-%d")
            },
            "filters": {
                "college": college or "All",
                "period": period
            }
        },
        "generated_at": now.strftime("%Y-%m-%d %H:%M:%S")
    })

@require_POST
def oversight_custom_report(request: HttpRequest):
    """Generate custom report based on advanced multi-filtering."""
    guard = require_role(request, role=["President", "Auditor", "Treasurer"])
    if guard is not None:
        return guard

    try:
        import json
        filters = json.loads(request.body)
    except:
        return JsonResponse({"ok": False, "error": "Invalid filter data"}, status=400)

    # Build base query
    members = Member.objects.exclude(membership_status__iexact="retired")
    
    # Apply profile filters
    if filters.get("profile", {}).get("department"):
        members = members.filter(department__iexact=filters["profile"]["department"])
    if filters.get("profile", {}).get("membership_status"):
        members = members.filter(membership_status__iexact=filters["profile"]["membership_status"])
    if filters.get("profile", {}).get("employment_status"):
        members = members.filter(employment_status__iexact=filters["profile"]["employment_status"])
    
    # Collect results
    results = []
    for member in members:
        # Get payment status
        payment_status = "N/A"
        payment_color = "#666"
        
        # Check date range filter
        date_from = filters.get("date", {}).get("from")
        date_to = filters.get("date", {}).get("to")
        
        # Apply date filtering if specified
        if date_from or date_to:
            if date_from and member.date_joined and member.date_joined < timezone.datetime.strptime(date_from, "%Y-%m-%d").date():
                continue
            if date_to and member.date_joined and member.date_joined > timezone.datetime.strptime(date_to, "%Y-%m-%d").date():
                continue
        
        # Get claims info
        claims_info = "None"
        claims_color = "#666"
        
        # Get release info
        release_info = "None"
        release_color = "#666"
        
        # Determine status color
        if member.membership_status in ["Permanent", "Temporary"]:
            status_color = "#28a745"
        elif member.membership_status == "Retired":
            status_color = "#dc3545"
        else:
            status_color = "#666"
        
        results.append({
            "id": member.employee_id or "N/A",
            "name": member.full_name,
            "department": member.department or "N/A",
            "status": member.membership_status or "N/A",
            "status_color": status_color,
            "payment": payment_status,
            "payment_color": payment_color,
            "claims": claims_info,
            "release": release_info,
            "release_color": release_color
        })
    
    return JsonResponse({
        "ok": True,
        "filters": filters,
        "summary": {
            "total": len(results),
            "active": len([m for m in results if m["status"] in ["Permanent", "Temporary"]]),
            "retired": len([m for m in results if m["status"] == "Retired"]),
        },
        "results": results
    })


# ============================================================================
# PRESIDENT DOCUMENT REPOSITORY API ENDPOINTS
# ============================================================================

def _resolve_document_uploader_fallbacks(document_ids: list[int]) -> dict[int, str]:
    """Return fallback uploader names from document activity when the uploader FK is missing."""
    if not document_ids:
        return {}

    uploader_names: dict[int, str] = {}
    activities = DocumentActivity.objects.filter(
        document_id_FK__in=document_ids,
    ).order_by('-timestamp').values('document_id_FK', 'officer_name')

    for activity in activities:
        doc_id = activity['document_id_FK']
        if doc_id not in uploader_names and activity.get('officer_name'):
            uploader_names[doc_id] = activity['officer_name']

    return uploader_names


@require_GET
def president_documents_list(request: HttpRequest):
    """
    Get documents list with filters for President
    Only shows documents uploaded by President role
    """
    guard = require_role(request, role=["President"])
    if guard is not None:
        return guard

    document_type = request.GET.get('document_type')
    category = request.GET.get('category')
    year = request.GET.get('year')
    keyword = request.GET.get('keyword')
    search = request.GET.get('search')
    status_filter = request.GET.get('status')
    filetype_filter = request.GET.get('file_type')
    page = int(request.GET.get('page', 1))
    page_size = int(request.GET.get('page_size', 10))
    
    # Filter to only show documents uploaded by President role
    queryset = Document.objects.select_related('uploaded_by_user_id_FK').filter(
        uploaded_by_user_id_FK__role='President'
    )
    
    if document_type:
        queryset = queryset.filter(document_type=document_type)
    
    if category:
        queryset = queryset.filter(category__icontains=category)
    
    if year:
        queryset = queryset.filter(uploaded_at__year=year)
    
    if keyword:
        queryset = queryset.filter(keywords__icontains=keyword)
    
    if search:
        queryset = queryset.filter(
            Q(title__icontains=search) |
            Q(document_type__icontains=search) |
            Q(category__icontains=search) |
            Q(description__icontains=search) |
            Q(keywords__icontains=search) |
            Q(tags__icontains=search)
        )
    
    if status_filter:
        if status_filter == 'Active':
            queryset = queryset.filter(is_archived=False)
        elif status_filter == 'Archived':
            queryset = queryset.filter(is_archived=True)
    
    if filetype_filter:
        queryset = queryset.filter(file_type__icontains=filetype_filter)
    
    officer_id = request.session.get("officer_id")
    pinned_ids = set()
    if officer_id:
        pinned_ids = set(DocumentPin.objects.filter(officer_id_FK=officer_id).values_list('document_id_FK', flat=True))
    
    total = queryset.count()
    start = (page - 1) * page_size
    end = start + page_size
    page_docs = list(queryset.order_by('-uploaded_at')[start:end])
    missing_doc_ids = [doc.document_id_PK for doc in page_docs if not doc.uploaded_by_user_id_FK]
    uploader_fallbacks = _resolve_document_uploader_fallbacks(missing_doc_ids)

    documents = []
    for doc in page_docs:
        status = 'Active'
        if doc.is_archived:
            status = 'Archived'

        try:
            uploaded_by_name = doc.uploaded_by_user_id_FK.full_name if doc.uploaded_by_user_id_FK else None
        except (OfficerUser.DoesNotExist, AttributeError):
            uploaded_by_name = None

        if not uploaded_by_name:
            uploaded_by_name = uploader_fallbacks.get(doc.document_id_PK)

        documents.append({
            'document_id': doc.document_id_PK,
            'title': doc.title,
            'description': doc.description,
            'document_type': doc.document_type,
            'category': doc.category or doc.document_type,
            'keywords': doc.keywords,
            'tags': doc.tags,
            'file_name': doc.file_name,
            'file_size': doc.file_size,
            'file_type': doc.file_type,
            'version': doc.version,
            'uploaded_by': uploaded_by_name or 'Unknown',
            'uploaded_at': timezone.localtime(doc.uploaded_at).strftime('%Y-%m-%d %I:%M %p'),
            'retention_period': doc.retention_period.strftime('%Y-%m-%d') if doc.retention_period else None,
            'is_archived': doc.is_archived,
            'status': status,
            'is_pinned': doc.document_id_PK in pinned_ids,
            'is_public_visible': doc.is_public_visible,
        })
    
    return JsonResponse({
        'ok': True,
        'documents': documents,
        'total': total,
        'page': page,
        'page_size': page_size,
        'total_pages': max(1, (total + page_size - 1) // page_size)
    })


@require_GET
def president_document_stats(request: HttpRequest):
    guard = require_role(request, role=["President"])
    if guard is not None:
        return guard
    try:
        # Only count documents uploaded by President role
        president_docs = Document.objects.filter(uploaded_by_user_id_FK__role='President')
        total = president_docs.count()
        active = president_docs.filter(is_archived=False).count()
        archived = president_docs.filter(is_archived=True).count()
        files = president_docs.exclude(file_size__isnull=True).values_list('file_size', flat=True)
        total_size = sum(files) if files else 0
        size_mb = round(total_size / (1024 * 1024), 1)
        return JsonResponse({
            'ok': True, 'total': total, 'active': active,
            'archived': archived, 'draft': 0, 'storage_mb': size_mb,
        })
    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=500)


@require_GET
def president_document_activity(request: HttpRequest):
    guard = require_role(request, role=["President"])
    if guard is not None:
        return guard
    try:
        # Only show activity for documents uploaded by President role
        activities = DocumentActivity.objects.select_related('document_id_FK').filter(
            document_id_FK__uploaded_by_user_id_FK__role='President'
        )[:15]
        items = []
        for a in activities:
            items.append({
                'action': a.action,
                'officer_name': a.officer_name,
                'details': a.details,
                'timestamp': timezone.localtime(a.timestamp).strftime('%b %d, %Y %I:%M %p') if a.timestamp else '',
                'doc_title': a.document_id_FK.title if a.document_id_FK else '',
            })
        return JsonResponse({'ok': True, 'activities': items})
    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=500)


@require_POST
@csrf_exempt
def president_document_upload(request: HttpRequest):
    """
    Upload a document for President
    """
    guard = require_role(request, role=["President"])
    if guard is not None:
        return guard

    try:
        officer_id = request.session.get("officer_id")
        officer = OfficerUser.objects.get(user_id_PK=officer_id) if officer_id else None
        
        title = request.POST.get('title')
        description = request.POST.get('description', '')
        document_type = request.POST.get('document_type')
        category = (request.POST.get('category', '') or '')[:100]
        keywords = (request.POST.get('keywords', '') or '')[:500]
        tags = (request.POST.get('tags', '') or '')[:500]
        is_public_visible = request.POST.get('is_public_visible') in ("1", "true", "True", "on")
        
        file = request.FILES.get('file')
        if not file:
            return JsonResponse({
                'ok': False,
                'error': 'No file uploaded'
            }, status=400)
        
        upload_dir = os.path.join(settings.MEDIA_ROOT, 'documents')
        os.makedirs(upload_dir, exist_ok=True)
        
        file_path = os.path.join(upload_dir, file.name)
        with open(file_path, 'wb+') as destination:
            for chunk in file.chunks():
                destination.write(chunk)
        
        document = Document.objects.create(
            title=title,
            description=description,
            document_type=document_type,
            category=category or document_type,
            keywords=keywords,
            tags=tags,
            file_path=file_path,
            file_name=file.name,
            file_size=file.size,
            file_type=(file.content_type or 'application/octet-stream')[:50],
            is_public_visible=is_public_visible,
            uploaded_by_user_id_FK=officer
        )

        DocumentActivity.objects.create(
            document_id_FK=document,
            action='uploaded',
            officer_id_FK=officer,
            officer_name=officer.full_name if officer else 'President',
            details=f'Uploaded {title}',
        )
        
        return JsonResponse({
            'ok': True,
            'message': 'Document uploaded successfully',
            'document_id': document.document_id_PK
        })
        
    except OfficerUser.DoesNotExist:
        return JsonResponse({
            'ok': False,
            'error': 'Officer not found'
        }, status=404)
    except Exception as e:
        return JsonResponse({
            'ok': False,
            'error': str(e)
        }, status=500)


@require_POST
@csrf_exempt
def president_document_replace(request: HttpRequest):
    guard = require_role(request, role=["President"])
    if guard is not None:
        return guard
    try:
        document_id = request.POST.get('document_id')
        file = request.FILES.get('file')
        if not document_id or not file:
            return JsonResponse({'ok': False, 'error': 'document_id and file required'}, status=400)

        old_doc = Document.objects.get(document_id_PK=document_id)
        officer_id = request.session.get("officer_id")
        officer = OfficerUser.objects.get(user_id_PK=officer_id) if officer_id else None

        old_doc.is_archived = True
        old_doc.save()

        old_version = float(old_doc.version) if old_doc.version else 1.0
        new_version = f'{old_version + 0.1:.1f}'

        upload_dir = os.path.join(settings.MEDIA_ROOT, 'documents')
        os.makedirs(upload_dir, exist_ok=True)
        file_path = os.path.join(upload_dir, file.name)
        with open(file_path, 'wb+') as dest:
            for chunk in file.chunks():
                dest.write(chunk)

        new_doc = Document.objects.create(
            title=old_doc.title,
            description=old_doc.description,
            document_type=old_doc.document_type,
            category=old_doc.category,
            keywords=old_doc.keywords,
            tags=old_doc.tags,
            file_path=file_path,
            file_name=file.name,
            file_size=file.size,
            file_type=(file.content_type or 'application/octet-stream')[:50],
            version=new_version,
            uploaded_by_user_id_FK=officer,
        )

        DocumentActivity.objects.create(
            document_id_FK=new_doc,
            action='replaced',
            officer_id_FK=officer,
            officer_name=officer.full_name if officer else 'President',
            details=f'Replaced version {old_doc.version} with {new_version}',
        )

        return JsonResponse({'ok': True, 'message': 'Document replaced', 'new_version': new_version, 'document_id': new_doc.document_id_PK})
    except Document.DoesNotExist:
        return JsonResponse({'ok': False, 'error': 'Document not found'}, status=404)
    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=500)


@require_POST
@csrf_exempt
def president_document_toggle_favorite(request: HttpRequest):
    guard = require_role(request, role=["President"])
    if guard is not None:
        return guard
    try:
        data = json.loads(request.body)
        document_id = data.get('document_id')
        officer_id = request.session.get("officer_id")
        if not document_id or not officer_id:
            return JsonResponse({'ok': False, 'error': 'document_id required'}, status=400)
        officer = OfficerUser.objects.get(user_id_PK=officer_id)
        doc = Document.objects.get(document_id_PK=document_id)
        pin = DocumentPin.objects.filter(document_id_FK=doc, officer_id_FK=officer).first()
        if pin:
            pin.delete()
            return JsonResponse({'ok': True, 'pinned': False})
        else:
            DocumentPin.objects.create(document_id_FK=doc, officer_id_FK=officer)
            return JsonResponse({'ok': True, 'pinned': True})
    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=500)


@require_POST
def president_document_toggle_public(request: HttpRequest):
    guard = require_role(request, role=["President"])
    if guard is not None:
        return guard
    try:
        data = json.loads(request.body)
        document_id = data.get('document_id')
        if not document_id:
            return JsonResponse({'ok': False, 'error': 'document_id required'}, status=400)
        doc = Document.objects.get(document_id_PK=document_id)
        doc.is_public_visible = not doc.is_public_visible
        doc.save(update_fields=['is_public_visible'])
        return JsonResponse({
            'ok': True,
            'is_public_visible': doc.is_public_visible,
            'message': 'Visibility updated.',
        })
    except Document.DoesNotExist:
        return JsonResponse({'ok': False, 'error': 'Document not found'}, status=404)
    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=500)


@require_GET
def president_document_preview(request: HttpRequest):
    guard = require_role(request, role=["President"])
    if guard is not None:
        return guard
    try:
        document_id = request.GET.get('document_id')
        if not document_id:
            return JsonResponse({'ok': False, 'error': 'document_id required'}, status=400)
        doc = Document.objects.get(document_id_PK=document_id)
        if not os.path.exists(doc.file_path):
            return JsonResponse({'ok': False, 'error': 'File not found on disk'}, status=404)
        with open(doc.file_path, 'rb') as f:
            content = f.read()
        content_type = doc.file_type or 'application/octet-stream'
        response = HttpResponse(content, content_type=content_type)
        response['Content-Disposition'] = f'inline; filename="{doc.file_name}"'
        response['X-Frame-Options'] = 'SAMEORIGIN'
        return response
    except Document.DoesNotExist:
        return JsonResponse({'ok': False, 'error': 'Document not found'}, status=404)
    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=500)


@require_GET
def president_document_download(request: HttpRequest):
    guard = require_role(request, role=["President"])
    if guard is not None:
        return guard
    try:
        document_id = request.GET.get('document_id')
        if not document_id:
            return JsonResponse({'ok': False, 'error': 'document_id required'}, status=400)
        doc = Document.objects.get(document_id_PK=document_id)
        if not os.path.exists(doc.file_path):
            return JsonResponse({'ok': False, 'error': 'File not found on disk'}, status=404)
        with open(doc.file_path, 'rb') as f:
            content = f.read()
        content_type = doc.file_type or 'application/octet-stream'
        response = HttpResponse(content, content_type=content_type)
        response['Content-Disposition'] = f'attachment; filename="{doc.file_name}"'
        return response
    except Document.DoesNotExist:
        return JsonResponse({'ok': False, 'error': 'Document not found'}, status=404)
    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=500)


@require_GET
def president_category_list(request: HttpRequest):
    guard = require_role(request, role=["President"])
    if guard is not None:
        return guard
    try:
        cats = Category.objects.filter(role='President').values('category_id_PK', 'name')
        return JsonResponse({'ok': True, 'categories': list(cats)})
    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=500)


@require_POST
@csrf_exempt
def president_category_create(request: HttpRequest):
    guard = require_role(request, role=["President"])
    if guard is not None:
        return guard
    try:
        data = json.loads(request.body)
        name = data.get('name', '').strip()
        if not name:
            return JsonResponse({'ok': False, 'error': 'Name is required'}, status=400)
        
        cat = Category.objects.create(name=name, role='President')
        return JsonResponse({'ok': True, 'category_id': cat.category_id_PK, 'name': cat.name})
    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=500)


@require_POST
@csrf_exempt
def president_category_rename(request: HttpRequest):
    guard = require_role(request, role=["President"])
    if guard is not None:
        return guard
    try:
        data = json.loads(request.body)
        category_id = data.get('category_id')
        name = data.get('name', '').strip()
        if not category_id or not name:
            return JsonResponse({'ok': False, 'error': 'category_id and name required'}, status=400)
        
        cat = Category.objects.get(category_id_PK=category_id, role='President')
        cat.name = name
        cat.save()
        return JsonResponse({'ok': True, 'name': cat.name})
    except Category.DoesNotExist:
        return JsonResponse({'ok': False, 'error': 'Category not found or not authorized'}, status=404)
    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=500)


@require_POST
@csrf_exempt
def president_category_delete(request: HttpRequest):
    guard = require_role(request, role=["President"])
    if guard is not None:
        return guard
    try:
        data = json.loads(request.body)
        category_id = data.get('category_id')
        if not category_id:
            return JsonResponse({'ok': False, 'error': 'category_id required'}, status=400)
        
        cat = Category.objects.get(category_id_PK=category_id, role='President')
        cat.delete()
        return JsonResponse({'ok': True, 'message': 'Category deleted'})
    except Category.DoesNotExist:
        return JsonResponse({'ok': False, 'error': 'Category not found or not authorized'}, status=404)
    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=500)

