from __future__ import annotations

import hashlib
import hmac
import json
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

from django.conf import settings

from django.contrib.contenttypes.models import ContentType
from django.core.files.storage import default_storage
from django.db import transaction
from django.db.models import Q, Sum, Max, Count
from django.db.models import ForeignKey
from django.http import HttpRequest, JsonResponse
from django.shortcuts import render, get_object_or_404
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from core_system.constants.status_constants import RegistrationStatus, Status, is_pending
from core_system.constants.policy_constants import get_medical_aid_contribution_amount
from core_system.guards import require_role, check_zero_trust
from core_system.services.email_service import (
    send_registration_status_update_email,
    send_registration_returned_email,
    send_registration_rejected_email,
)
from core_system.models import (
    AidTrackingPost,
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
    Notification,
    OfficerUser,
    PayrollBatch,
    PayrollDeduction,
    SupportingProof,
    TransactionVerification,
    MemberLedger,
)
from core_system.services.notifications import notify_member
from core_system.services.status_service import (
    MODEL_MAP as _SVC_MODEL_MAP,
    set_auditor_verified,
    set_returned_for_revision,
    set_president_decision,
)
from core_system.shared_view_utils import (
    MODEL_MAP,
    PAYMENT_SOURCE_LABELS,
    _broadcast_pending_counts,
    _broadcast_to_group,
    _get_proof_url,
    _log_sensitive_read,
    _payment_item_to_json,
    _payment_type_label,
    _record_audit_trail,
    _record_bulk_audit_trail,
    _serialize_for_audit,
    resolve_officer_from_session,
    route_back_to_treasurer,
)


def _serialize_record(instance) -> Dict[str, Any]:
    data = {}
    for field in instance._meta.fields:
        value = getattr(instance, field.name)
        if isinstance(field, ForeignKey) and value is not None:
            data[field.name] = value.pk
        else:
            if hasattr(value, "isoformat"):
                data[field.name] = value.isoformat()
            elif (
                hasattr(value, "to_eng_string") or type(value).__name__ == "Decimal"
            ):
                data[field.name] = str(value)
            else:
                data[field.name] = value
    return data


def _get_officer_from_session(request: HttpRequest) -> Optional[OfficerUser]:
    stored_officer_id = request.session.get("officer_id")
    if stored_officer_id is None:
        return None
    try:
        return OfficerUser.objects.get(user_id_PK=int(stored_officer_id))
    except Exception:
        return None


def _file_upload_to_archive(
    *,
    request: HttpRequest,
    related_module: str,
    related_record_id: int,
    document_type: str,
    uploaded_file,
    verification_status: str,
) -> FinancialDocumentArchive:
    officer = _get_officer_from_session(request)
    if officer is None:
        raise ValueError("Officer session missing")

    filename = uploaded_file.name
    stored_name = default_storage.save(
        f"evidence_uploads/{timezone.now().strftime('%Y%m%d')}_{filename}",
        uploaded_file,
    )

    file_hash = ""
    try:
        hasher = hashlib.sha256()
        data = uploaded_file.read()
        hasher.update(data)
        file_hash = hasher.hexdigest()
    except Exception:
        file_hash = ""

    return FinancialDocumentArchive.objects.create(
        related_module=related_module,
        related_record_id=related_record_id,
        document_type=document_type,
        file_path=stored_name,
        file_hash=file_hash or "",
        verification_status=verification_status,
        uploaded_by_user_id_FK=officer,
    )


def _create_placeholder_archive(
    *,
    request: HttpRequest,
    related_module: str,
    related_record_id: int,
    document_type: str,
    verification_status: str,
) -> FinancialDocumentArchive:
    officer = _get_officer_from_session(request)
    if officer is None:
        raise ValueError("Officer session missing")

    return FinancialDocumentArchive.objects.create(
        related_module=related_module,
        related_record_id=related_record_id,
        document_type=document_type,
        file_path="",
        file_hash="",
        verification_status=verification_status,
        uploaded_by_user_id_FK=officer,
    )


# ==========================================================================
# AUDITOR WORKSPACE VIEWS
# ==========================================================================
def auditor_dashboard(request):
    guard = require_role(request, role="Auditor")
    if guard is not None:
        return guard

    officer_full_name = ""
    officer_role = "Auditor"

    stored_officer_id = request.session.get("officer_id")
    officer_user_id = None
    if stored_officer_id is not None:
        try:
            officer = OfficerUser.objects.get(user_id_PK=int(stored_officer_id))
            officer_full_name = getattr(officer, "full_name", "") or ""
            officer_role = getattr(officer, "role", None) or officer_role
            officer_user_id = officer.user_id_PK
        except Exception:
            pass

    context = {
        "officer_full_name": officer_full_name,
        "officer_role": officer_role,
        "officer_user_id": officer_user_id,
        "access_token": request.session.get("access_token", ""),
    }

    if not officer_full_name.strip():
        context["officer_full_name"] = context["officer_role"]

    return render(request, "website/Auditor/auditor_dashboard.html", context)


@require_GET
def auditor_audit_trail_verify(request: HttpRequest, table_name: str = None, record_id: int = None):
    """
    Verify audit-log hash-chain integrity.

    If table_name and record_id are provided, verifies the chain for that specific record.
    Otherwise, verifies the global chain across all entries.

    Returns:
      {
        ok: true,
        table_name,
        record_id,
        total_entries,
        valid: bool,
        issues: [ ... ],
        entries: [ ... ],
      }
    """
    guard = require_role(request, role="Auditor")
    if guard is not None:
        return guard

    table_name = (table_name or "").strip()
    issues = []

    if table_name and record_id is not None:
        qs = (
            GlobalAuditTrail.objects.filter(
                table_name=table_name,
                record_id=int(record_id),
            )
            .order_by("timestamp", "trail_id")
        )
    else:
        qs = GlobalAuditTrail.objects.all().order_by("trail_id")

    entries = list(qs)
    total = len(entries)
    if total == 0:
        return JsonResponse(
            {
                "ok": True,
                "table_name": table_name or "ALL",
                "record_id": record_id,
                "total_entries": 0,
                "valid": True,
                "issues": [],
                "entries": [],
            }
        )

    expected_previous = "0" * 64
    for idx, entry in enumerate(entries):
        previous_hash = entry.previous_hash if getattr(entry, "previous_hash", None) else None
        prev_hash_effective = previous_hash or ("0" * 64)

        if prev_hash_effective != expected_previous:
            issues.append(
                {
                    "index": idx,
                    "trail_id": entry.trail_id,
                    "issue": "previous_hash_mismatch",
                    "expected": expected_previous,
                    "actual": prev_hash_effective,
                }
            )

        old_serialized = (
            entry.old_values
            if isinstance(entry.old_values, dict)
            else (json.loads(entry.old_values) if entry.old_values else None)
        )
        new_serialized = (
            entry.new_values
            if isinstance(entry.new_values, dict)
            else (json.loads(entry.new_values) if entry.new_values else None)
        )

        old_serialized = _serialize_for_audit(old_serialized) if old_serialized is not None else None
        new_serialized = _serialize_for_audit(new_serialized) if new_serialized is not None else None

        old_str = json.dumps(old_serialized, sort_keys=True) if old_serialized else ""
        new_str = json.dumps(new_serialized, sort_keys=True) if new_serialized else ""
        timestamp_str = entry.timestamp.isoformat() if entry.timestamp else ""

        chain_str = f"{expected_previous}:{entry.table_name}:{entry.record_id}:{entry.action}:{old_str}:{new_str}:{timestamp_str}"
        computed_entry_hash = hashlib.sha256(chain_str.encode()).hexdigest()

        expected_hmac = hmac.new(
            settings.SECRET_KEY.encode(),
            computed_entry_hash.encode(),
            hashlib.sha256,
        ).hexdigest()

        stored_entry_hash = getattr(entry, "entry_hash", None)
        stored_hmac = getattr(entry, "hmac_signature", None)

        if stored_entry_hash and stored_entry_hash != computed_entry_hash:
            issues.append(
                {
                    "index": idx,
                    "trail_id": entry.trail_id,
                    "issue": "entry_hash_mismatch",
                    "expected": computed_entry_hash,
                    "actual": stored_entry_hash,
                }
            )

        if stored_hmac and stored_hmac != expected_hmac:
            issues.append(
                {
                    "index": idx,
                    "trail_id": entry.trail_id,
                    "issue": "hmac_signature_mismatch",
                    "expected": expected_hmac,
                    "actual": stored_hmac,
                }
            )

        expected_previous = computed_entry_hash

    return JsonResponse(
        {
            "ok": True,
            "table_name": table_name or "ALL",
            "record_id": record_id,
            "total_entries": total,
            "valid": len(issues) == 0,
            "issues": issues,
            "entries": [
                {
                    "trail_id": e.trail_id,
                    "action": e.action,
                    "actor_name": e.actor_name,
                    "timestamp": e.timestamp.isoformat() if e.timestamp else "",
                    "old_values": _serialize_for_audit(
                        e.old_values if isinstance(e.old_values, dict)
                        else (json.loads(e.old_values) if e.old_values else None)
                    ),
                    "new_values": _serialize_for_audit(
                        e.new_values if isinstance(e.new_values, dict)
                        else (json.loads(e.new_values) if e.new_values else None)
                    ),
                    "entry_hash": e.entry_hash or "",
                    "hmac_signature": e.hmac_signature or "",
                }
                for e in entries
            ],
        }
    )


@require_GET
def auditor_pending_payments(request: HttpRequest):
    guard = require_role(request, role="Auditor")
    if guard is not None:
        return guard

    latest_verifications = TransactionVerification.objects.values(
        "table_name",
        "record_id",
    ).annotate(latest_id=Max("verification_id"))

    latest_ids = [item["latest_id"] for item in latest_verifications if item["latest_id"] is not None]

    # Build a lookup of latest pending verifications for payments only.
    # Show unclaimed entries for any auditor, plus entries routed back to the
    # requesting officer ("Send back to same auditor").
    officer = _get_officer_from_session(request)
    pending_verifications = TransactionVerification.objects.filter(
        verification_status__in=["Pending", "Pending Auditor Review"],
        verification_id__in=latest_ids,
    )
    if officer is not None:
        pending_verifications = pending_verifications.filter(
            Q(auditor_id_FK__isnull=True) | Q(auditor_id_FK=officer)
        )
    else:
        pending_verifications = pending_verifications.filter(auditor_id_FK__isnull=True)

    pending_fee_ids = set()
    pending_dues_ids = set()
    tv_map = {}

    for tv in pending_verifications:
        tn = str(tv.table_name).lower()
        if tn == "membership_fee":
            pending_fee_ids.add(tv.record_id)
            tv_map[("membership_fee", tv.record_id)] = tv
        elif tn == "monthly_dues":
            pending_dues_ids.add(tv.record_id)
            tv_map[("monthly_dues", tv.record_id)] = tv

    fees = MembershipFee.objects.select_related("member_id_FK", "recorded_by_user_id_FK").filter(
        fee_id_PK__in=pending_fee_ids
    ) if pending_fee_ids else []
    dues = MonthlyDues.objects.select_related("member_id_FK", "recorded_by_user_id_FK").filter(
        dues_id_PK__in=pending_dues_ids
    ) if pending_dues_ids else []

    items: List[Dict[str, Any]] = []

    for f in fees:
        item = _payment_item_to_json("membership_fee", f)
        tv = tv_map.get(("membership_fee", f.fee_id_PK))
        if tv:
            item["returned_by_auditor_id_FK"] = tv.returned_by_auditor_id_FK_id
            item["return_count"] = tv.return_count
            item["returned_reason"] = tv.returned_reason or ""
        items.append(item)

    for d in dues:
        item = _payment_item_to_json("monthly_dues", d)
        # Add approval status fields
        item["treasurer_status"] = d.treasurer_status
        item["auditor_status"] = d.auditor_status
        item["president_status"] = d.president_status
        tv = tv_map.get(("monthly_dues", d.dues_id_PK))
        if tv:
            item["returned_by_auditor_id_FK"] = tv.returned_by_auditor_id_FK_id
            item["return_count"] = tv.return_count
            item["returned_reason"] = tv.returned_reason or ""
        items.append(item)

    items.sort(key=lambda x: x.get("entity_id", 0), reverse=True)

    return JsonResponse({"ok": True, "payments": items})


@require_GET
def auditor_member_registry(request: HttpRequest):
    """Verified Registry — all members with current-month pay status
    (paid / pending / unpaid), last payment date, and per-member histories
    for the mockup member profile view."""
    guard = require_role(request, role="Auditor")
    if guard is not None:
        return guard

    current_month = timezone.now().strftime("%Y-%m")
    paid_statuses = list(Status.ALL_AUDITOR_VERIFIED)
    pending_statuses = list(Status.ALL_PENDING)

    members = Member.objects.select_related("department_id_FK").order_by("full_name")

    # Current-month dues status per member
    status_by_member: Dict[int, str] = {}
    for d in MonthlyDues.objects.filter(month_covered=current_month).only(
        "member_id_FK_id", "payment_status"
    ):
        mid = d.member_id_FK_id
        if mid not in status_by_member:
            status_by_member[mid] = str(d.payment_status)

    # Last payment date per member (dues + fees combined)
    last_pay: Dict[int, str] = {}
    for row in MonthlyDues.objects.exclude(payment_date=None).values(
        "member_id_FK_id"
    ).annotate(last_pay=Max("payment_date")):
        last_pay[row["member_id_FK_id"]] = str(row["last_pay"])
    for row in MembershipFee.objects.exclude(payment_date=None).values(
        "member_id_FK_id"
    ).annotate(last_pay=Max("payment_date")):
        mid = row["member_id_FK_id"]
        prev = last_pay.get(mid)
        cur = str(row["last_pay"])
        if prev is None or cur > prev:
            last_pay[mid] = cur

    # Payment history (dues + fees, latest 8 each), aid histories
    fees_by_member: Dict[int, List[Dict[str, Any]]] = {}
    for f in MembershipFee.objects.order_by("-payment_date", "-fee_id_PK").select_related(
        "member_id_FK"
    )[:400]:
        fees_by_member.setdefault(f.member_id_FK_id, []).append(
            {
                "date": str(f.payment_date) if f.payment_date else "",
                "amount": str(f.amount),
                "method": f.payment_method or "",
                "type": "Membership Fee",
                "ref": f.receipt_number or "",
            }
        )
    dues_hist: Dict[int, List[Dict[str, Any]]] = {}
    for d in MonthlyDues.objects.order_by("-payment_date", "-dues_id_PK").select_related(
        "member_id_FK"
    )[:400]:
        dues_hist.setdefault(d.member_id_FK_id, []).append(
            {
                "date": str(d.payment_date) if d.payment_date else "",
                "amount": str(d.amount),
                "method": d.payment_method or "",
                "type": "Monthly Dues",
                "ref": d.month_covered or "",
            }
        )
    med_by_member: Dict[int, List[Dict[str, Any]]] = {}
    for m in MedicalAid.objects.order_by("-request_date", "-medical_aid_id_PK")[:400]:
        med_by_member.setdefault(m.member_id_FK_id, []).append(
            {
                "date": str(m.request_date) if m.request_date else "",
                "amount": str(m.validated_aid_amount or m.requested_amount),
                "reason": m.reason_for_request or "",
                "status": str(m.status),
            }
        )
    death_by_member: Dict[int, List[Dict[str, Any]]] = {}
    for d in DeathAid.objects.order_by("-claim_date", "-death_aid_id_PK")[:400]:
        death_by_member.setdefault(d.member_id_FK_id, []).append(
            {
                "date": str(d.claim_date) if d.claim_date else "",
                "amount": str(d.benefit_amount),
                "reason": d.deceased_name or "",
                "status": str(d.status),
            }
        )

    items: List[Dict[str, Any]] = []
    for m in members:
        mid = m.member_id_PK
        ps = status_by_member.get(mid)
        if ps is None:
            pay_status = "unpaid"
        elif ps in paid_statuses:
            pay_status = "paid"
        elif ps in pending_statuses:
            pay_status = "pending"
        else:
            pay_status = "unpaid"

        history = (fees_by_member.get(mid, []) + dues_hist.get(mid, []))
        history.sort(key=lambda x: x["date"], reverse=True)

        items.append(
            {
                "member_id": mid,
                "employee_id": m.employee_id or ("M-" + str(mid)),
                "full_name": m.full_name,
                "department": m.department_id_FK.name if m.department_id_FK else (m.department or ""),
                "position": m.position or "",
                "membership_status": m.membership_status or "",
                "date_joined": str(m.date_joined) if m.date_joined else "—",
                "pay_status": pay_status,
                "last_payment": last_pay.get(mid, "—"),
                "payment_history": history[:8],
                "medical_aid_history": med_by_member.get(mid, []),
                "death_aid_history": death_by_member.get(mid, []),
            }
        )

    counts = {
        "paid": sum(1 for i in items if i["pay_status"] == "paid"),
        "pending": sum(1 for i in items if i["pay_status"] == "pending"),
        "unpaid": sum(1 for i in items if i["pay_status"] == "unpaid"),
        "total": len(items),
    }

    return JsonResponse({"ok": True, "month": current_month, "counts": counts, "members": items})


@require_GET
def auditor_pending_aids(request: HttpRequest):
    guard = require_role(request, role="Auditor")
    if guard is not None:
        return guard

    medicals = MedicalAid.objects.select_related(
        "member_id_FK",
        "auditor_verified_by_user_id_FK",
        "treasurer_validated_by_user_id_FK",
        "president_decided_by_user_id_FK",
    ).order_by("-medical_aid_id_PK")

    deaths = DeathAid.objects.select_related(
        "member_id_FK",
        "claimant_id_FK",
        "treasurer_validated_by_user_id_FK",
        "auditor_verified_by_user_id_FK",
        "president_decided_by_user_id_FK",
    ).order_by("-death_aid_id_PK")

    items: List[Dict[str, Any]] = []

    med_record_ids = []
    pending_med_ids = []
    for m in medicals:
        if str(m.status) in Status.ALL_PENDING:
            pending_med_ids.append(m.medical_aid_id_PK)
            member = m.member_id_FK
            med_record_ids.append(m.medical_aid_id_PK)
            items.append(
                {
                    "id": "medical-" + str(m.medical_aid_id_PK),
                    "entity_id": int(m.medical_aid_id_PK),
                    "aid_type": "medical_aid",
                    "type": "Medical Aid Request",
                    "request_date": str(m.request_date),
                    "medical_case": m.reason_for_request or "",
                    "requested_amount": str(m.requested_amount),
                    "hospital": m.hospital_name or (member.full_name if member else ""),
                    "hospital_date": str(m.hospital_date) if m.hospital_date else "",
                    "total_hospital_bill": str(m.hospital_bill_amount),
                    "validated_aid_amount": str(m.validated_aid_amount),
                    "assigned_amount": str(get_medical_aid_contribution_amount()),
                    "admission_date": m.admission_date.isoformat() if m.admission_date else "",
                    "discharge_date": m.discharge_date.isoformat() if m.discharge_date else "",
                    "date": str(m.request_date),
                    "reqAmount": str(m.validated_aid_amount or m.requested_amount),
                    "bill": str(m.hospital_bill_amount),
                    "reason": m.reason_for_request or "",
                    "member": {
                        "member_id": member.member_id_PK,
                        "member_name": member.full_name,
                        "employee_id": member.employee_id or "",
                        "department": member.department or "",
                        "position": member.position or "",
                        "contact": member.contact_number or "",
                        "email": member.email or "",
                    },
                }
            )

    pending_death_ids = []
    for d in deaths:
        if str(d.status) in Status.ALL_PENDING:
            pending_death_ids.append(d.death_aid_id_PK)
            member = d.member_id_FK
            claimant = d.claimant_id_FK
            items.append(
                {
                    "id": "death-" + str(d.death_aid_id_PK),
                    "entity_id": int(d.death_aid_id_PK),
                    "aid_type": "death_aid",
                    "type": "Death Aid Claim",
                    "claim_date": str(d.claim_date),
                    "deceased_name": d.deceased_name,
                    "relationship": d.relationship_to_member,
                    "relationshipGroup": d.relationship_group,
                    "claim_type": d.claim_type,
                    "claimant_name": claimant.full_name if claimant else "",
                    "claimant_contact": (claimant.contact_number if claimant and claimant.contact_number else (member.contact_number if member else "")),
                    "bill_amount": str(d.bill_amount) if d.bill_amount else "",
                    "benefit_amount": str(d.benefit_amount),
                    "assigned_amount": str(d.benefit_amount),
                    "date_of_death": str(d.date_of_death) if d.date_of_death else "",
                    "date": str(d.claim_date),
                    "deceased": d.deceased_name,
                    "claimType": d.claim_type,
                    "claimantName": claimant.full_name if claimant else "",
                    "claimantContact": (claimant.contact_number if claimant and claimant.contact_number else (member.contact_number if member else "")),
                    "benefit": str(d.benefit_amount),
                    "dateOfDeath": str(d.date_of_death) if d.date_of_death else "",
                    "member": {
                        "member_id": member.member_id_PK if member else None,
                        "member_name": member.full_name if member else "",
                        "employee_id": member.employee_id or "" if member else "",
                        "department": member.department or "" if member else "",
                        "position": member.position or "" if member else "",
                        "contact": member.contact_number or "" if member else "",
                    },
                }
            )

    if med_record_ids:
        _log_sensitive_read(request, "medical_aid", med_record_ids, "Auditor viewed pending medical aid list")

    blocked_ids = set()
    if pending_med_ids or pending_death_ids:
        tv_filters = []
        if pending_med_ids:
            tv_filters.append(("medical_aid", pending_med_ids))
        if pending_death_ids:
            tv_filters.append(("death_aid", pending_death_ids))
        q = Q()
        for tn, ids in tv_filters:
            q |= Q(table_name=tn, record_id__in=ids)
        tvs = TransactionVerification.objects.filter(q).exclude(
            verification_status__in=Status.ALL_PENDING
        ).values_list("table_name", "record_id")
        for tn, rid in tvs:
            blocked_ids.add((tn, rid))

    if blocked_ids:
        items = [
            it for it in items
            if (it["aid_type"], it["entity_id"]) not in blocked_ids
        ]

    return JsonResponse({"ok": True, "aids": items})


@require_POST
@transaction.atomic
def auditor_verify_payment(request: HttpRequest):
    guard = require_role(request, role="Auditor")
    if guard is not None:
        return guard
    guard = check_zero_trust(request, level="approve")
    if guard is not None:
        return guard

    officer = _get_officer_from_session(request)
    if officer is None:
        return JsonResponse({"ok": False, "error": "Officer session missing."}, status=401)

    target_id = (request.POST.get("pAuditID") or "").strip()
    remarks = (request.POST.get("pAuditRemarks") or "").strip()
    field_remarks = (request.POST.get("pAuditFieldRemarks") or "").strip()
    result = (request.POST.get("pAuditResult") or "").strip()

    if field_remarks:
        if remarks:
            remarks = remarks + "\n\n" + field_remarks
        else:
            remarks = field_remarks

    if not target_id:
        return JsonResponse({"ok": False, "error": "Missing pAuditID."}, status=400)

    is_verify = result == "Verified"
    if result not in {"Verified", "Returned"}:
        return JsonResponse({"ok": False, "error": "Invalid pAuditResult."}, status=400)

    entity = None
    related_module = None

    table_hint = None
    raw_id = target_id
    if ":" in target_id:
        parts = target_id.split(":", 1)
        table_hint = parts[0]
        raw_id = parts[1]

    try:
        as_int = int(raw_id)
    except ValueError:
        as_int = None

    fee = None
    dues = None
    if as_int is not None:
        if table_hint == "membership_fee":
            fee = MembershipFee.objects.filter(fee_id_PK=as_int).first()
        elif table_hint == "monthly_dues":
            dues = MonthlyDues.objects.filter(dues_id_PK=as_int).first()
        else:
            fee = MembershipFee.objects.filter(fee_id_PK=as_int).first()
            dues = MonthlyDues.objects.filter(dues_id_PK=as_int).first()

    if fee is not None and dues is not None and table_hint is None:
        return JsonResponse({"ok": False, "error": "Ambiguous payment identifier; please specify the source as membership_fee:<id> or monthly_dues:<id>."}, status=400)

    if fee is not None:
        entity_type = "MembershipFee"
        entity = fee
        related_module = "MEMBERSHIP_FEE"
        related_record_id = fee.fee_id_PK
    elif dues is not None:
        entity_type = "MonthlyDues"
        entity = dues
        related_module = "MONTHLY_DUES"
        related_record_id = dues.dues_id_PK
    else:
        return JsonResponse({"ok": False, "error": "Payment record not found."}, status=404)

    canonical_status = Status.AUDITOR_VERIFIED if is_verify else Status.RETURNED_REVISION

    if table_hint == "membership_fee" or isinstance(entity, MembershipFee):
        tv_table = "membership_fee"
    else:
        tv_table = "monthly_dues"

    tv_qs = TransactionVerification.objects.select_for_update().filter(
        table_name=tv_table,
        record_id=related_record_id,
    ).order_by("-verification_id")
    tv = tv_qs.first()

    if tv is not None and not is_pending(tv.verification_status):
        return JsonResponse(
            {"ok": False, "error": f"This record has already been acted upon (status: {tv.verification_status}) and cannot be re-verified."},
            status=400,
        )

    if tv is not None and tv.auditor_id_FK is not None and tv.auditor_id_FK != officer:
        return JsonResponse(
            {"ok": False, "error": "This record is assigned to another auditor and cannot be verified by you."},
            status=403,
        )

    uploaded = request.FILES.get("p_findings_file")

    if uploaded and getattr(uploaded, "size", 0) > 0:
        _file_upload_to_archive(
            request=request,
            related_module=related_module,
            related_record_id=related_record_id,
            document_type="auditor_finding",
            uploaded_file=uploaded,
            verification_status=canonical_status,
        )
    else:
        _create_placeholder_archive(
            request=request,
            related_module=related_module,
            related_record_id=related_record_id,
            document_type="auditor_finding",
            verification_status=canonical_status,
        )

    evidence_file_path = ""
    evidence_file_hash = ""

    if uploaded and getattr(uploaded, "size", 0) > 0:
        import os
        safe_name = os.path.basename(uploaded.name) or "evidence"
        evidence_file_path = default_storage.save(
            f"auditor_payment_evidence/{timezone.now().strftime('%Y%m%d')}_{safe_name}",
            uploaded,
        )

        try:
            hasher = hashlib.sha256()
            data = uploaded.read()
            hasher.update(data)
            evidence_file_hash = hasher.hexdigest()
        except Exception:
            evidence_file_hash = ""

    tv_update = {
        "verification_status": canonical_status,
        "auditor_id_FK": officer,
        "verified_at": timezone.now(),
        "auditor_remarks": remarks or "",
        "evidence_file_path": evidence_file_path,
        "evidence_file_hash": evidence_file_hash,
    }

    snapshot = None
    if not is_verify:
        snapshot = _serialize_record(entity)
        tv_update["returned_by_auditor_id_FK"] = officer
        tv_update["returned_reason"] = remarks or ""

    if tv is None:
        tv_update["table_name"] = tv_table
        tv_update["record_id"] = related_record_id
        TransactionVerification.objects.create(**tv_update)
    else:
        for fname, val in tv_update.items():
            setattr(tv, fname, val)
        tv.save()

    if not is_verify:
        from django.db.models import F
        TransactionVerification.objects.filter(
            table_name=tv_table,
            record_id=related_record_id,
        ).update(return_count=F("return_count") + 1)

    audit_action = "VERIFIED" if result == "Verified" else "RETURNED"
    audit_actor_type = getattr(officer, "role", "Auditor")

    _record_audit_trail(
        table=tv_table,
        record_id=related_record_id,
        action=audit_action,
        actor=officer,
        new=snapshot,
        ip=request.META.get("REMOTE_ADDR"),
        notes=remarks or None,
    )

    # Update MonthlyDues approval fields if this is a MonthlyDues record
    if isinstance(entity, MonthlyDues):
        if is_verify:
            entity.auditor_status = "Auditor Verified"
            entity.auditor_id_FK = officer
            entity.auditor_remarks = remarks or ""
            entity.auditor_approved_at = timezone.now()
            entity.president_status = "Pending President Approval"
            entity.save()

            notify_member(
                entity.member_id_FK,
                notification_type="Payment Approved",
                message=f"Your monthly dues payment for {entity.month_covered} (₱{entity.amount}) has been verified by the Auditor and forwarded to the President.",
                category="payment",
                sender_name=officer.full_name if officer else "Auditor",
                sender_role="Auditor",
                receipt_number=entity.receipt_number or "",
            )
        else:
            entity.auditor_status = "Returned for Revision"
            entity.auditor_id_FK = officer
            entity.auditor_remarks = remarks or ""
            entity.auditor_approved_at = timezone.now()
            entity.payment_status = "Returned"
            entity.save()

            notify_member(
                entity.member_id_FK,
                notification_type="Payment Returned",
                message=f"Your monthly dues payment for {entity.month_covered} was returned for revision. Reason: {remarks}",
                category="payment",
                sender_name=officer.full_name if officer else "Auditor",
                sender_role="Auditor",
            )
    elif isinstance(entity, MembershipFee):
        if is_verify:
            notify_member(
                entity.member_id_FK,
                notification_type="Payment Approved",
                message="Your membership fee payment has been verified by the Auditor and forwarded to the President.",
                category="payment",
                sender_name=officer.full_name if officer else "Auditor",
                sender_role="Auditor",
                receipt_number=entity.receipt_number or "",
            )
        else:
            notify_member(
                entity.member_id_FK,
                notification_type="Payment Returned",
                message=f"Your membership fee payment was returned for revision. Reason: {remarks}",
                category="payment",
                sender_name=officer.full_name if officer else "Auditor",
                sender_role="Auditor",
            )

    _broadcast_pending_counts()
    _broadcast_to_group("auditor_dashboard", {"type": "dashboard_refresh", "section": "all"})
    if not is_verify:
        _broadcast_to_group("treasurer_dashboard", {"type": "data_changed", "section": "returned_entries"})
    return JsonResponse({"ok": True})


@require_POST
@transaction.atomic
def auditor_verify_aid(request: HttpRequest):
    guard = require_role(request, role="Auditor")
    if guard is not None:
        return guard
    guard = check_zero_trust(request, level="approve")
    if guard is not None:
        return guard

    officer = _get_officer_from_session(request)
    if officer is None:
        return JsonResponse({"ok": False, "error": "Officer session missing."}, status=401)

    target_id = (request.POST.get("aAuditID") or "").strip()
    remarks = (request.POST.get("aAuditRemarks") or "").strip()
    result = (request.POST.get("aAuditResult") or "").strip()

    if not target_id:
        return JsonResponse({"ok": False, "error": "Missing aAuditID."}, status=400)

    if result not in {"Verified", "Returned"}:
        return JsonResponse({"ok": False, "error": "Invalid aAuditResult."}, status=400)
    is_verify = result == "Verified"

    table_hint = None
    raw_id = target_id
    if "-" in target_id:
        parts = target_id.split("-", 1)
        table_hint = parts[0]
        raw_id = parts[1]

    try:
        as_int = int(raw_id)
    except (ValueError, TypeError):
        as_int = None

    med = None
    dth = None
    if as_int is not None:
        if table_hint == "medical":
            med = MedicalAid.objects.filter(medical_aid_id_PK=as_int).first()
        elif table_hint == "death":
            dth = DeathAid.objects.filter(death_aid_id_PK=as_int).first()
        else:
            med = MedicalAid.objects.filter(medical_aid_id_PK=as_int).first()
            dth = DeathAid.objects.filter(death_aid_id_PK=as_int).first()

    entity = None
    if med is not None:
        entity_type = "MedicalAid"
        related_record_id = med.medical_aid_id_PK
        canonical_status = Status.AUDITOR_VERIFIED if is_verify else Status.RETURNED_REVISION
        entity = med
        med.status = canonical_status
        med.auditor_verified_by_user_id_FK = officer
        med.save(update_fields=["status", "auditor_verified_by_user_id_FK"])
        _broadcast_to_group("treasurer_dashboard", {"type": "data_changed", "section": "aids"})

    elif dth is not None:
        entity_type = "DeathAid"
        related_record_id = dth.death_aid_id_PK
        canonical_status = Status.AUDITOR_VERIFIED if is_verify else Status.RETURNED_REVISION
        entity = dth
        dth.status = canonical_status
        dth.auditor_verified_by_user_id_FK = officer
        dth.save(update_fields=["status", "auditor_verified_by_user_id_FK"])
        _broadcast_to_group("treasurer_dashboard", {"type": "data_changed", "section": "aids"})

    else:
        return JsonResponse({"ok": False, "error": "Aid record not found."}, status=404)

    aid_label = "Medical Aid" if entity_type == "MedicalAid" else "Death Aid"
    try:
        notify_member(
            entity.member_id_FK,
            notification_type="Claim Update",
            message=(
                f"Your {aid_label} claim has been verified by the Auditor and forwarded to the President."
                if is_verify
                else f"Your {aid_label} claim was returned for revision by the Auditor. Reason: {remarks}"
            ),
            category="claim",
            sender_name=officer.full_name if officer else "Auditor",
            sender_role="Auditor",
        )
    except Exception:
        logger.exception("Auditor aid verification notification failed")

    snapshot = None
    if not is_verify:
        snapshot = _serialize_record(entity)

    uploaded = request.FILES.get("a_findings_file")

    evidence_file_path = ""
    evidence_file_hash = ""

    if uploaded and getattr(uploaded, "size", 0) > 0:

        filename = uploaded.name
        evidence_file_path = default_storage.save(
            f"auditor_aid_evidence/{timezone.now().strftime('%Y%m%d')}_{filename}",
            uploaded,
        )

        try:
            hasher = hashlib.sha256()
            data = uploaded.read()
            hasher.update(data)
            evidence_file_hash = hasher.hexdigest()
        except Exception:
            evidence_file_hash = ""

    target_table = "medical_aid" if entity_type == "MedicalAid" else "death_aid"

    tv_defaults = {
        "verification_status": canonical_status,
        "auditor_id_FK": officer,
        "verified_at": timezone.now(),
        "auditor_remarks": remarks or "",
        "evidence_file_path": evidence_file_path,
        "evidence_file_hash": evidence_file_hash,
    }

    if not is_verify:
        tv_defaults["returned_by_auditor_id_FK"] = officer
        tv_defaults["returned_reason"] = remarks or ""

    TransactionVerification.objects.update_or_create(
        table_name=target_table,
        record_id=related_record_id,
        defaults=tv_defaults,
    )

    from django.db.models import F
    if not is_verify:
        TransactionVerification.objects.filter(
            table_name=target_table,
            record_id=related_record_id,
        ).update(return_count=F("return_count") + 1)

    audit_action = "VERIFIED" if is_verify else "RETURNED"
    _record_audit_trail(
        table=target_table,
        record_id=related_record_id,
        action=audit_action,
        actor=officer,
        new=snapshot,
        ip=request.META.get("REMOTE_ADDR"),
        notes=remarks or None,
    )

    _broadcast_pending_counts()
    _broadcast_to_group("auditor_dashboard", {"type": "dashboard_refresh", "section": "all"})
    return JsonResponse({"ok": True})


@require_GET
def auditor_pending_membership_fees(request: HttpRequest):
    guard = require_role(request, role="Auditor")
    if guard is not None:
        return guard

    all_fees = MembershipFee.objects.select_related("member_id_FK", "recorded_by_user_id_FK").exclude(
        receipt_number__startswith="REG-"
    ).all()
    items: List[Dict[str, Any]] = []
    tv_cache: Dict[int, TransactionVerification] = {}

    for f in all_fees:
        tv = tv_cache.get(f.fee_id_PK)
        if tv is None:
            tv = TransactionVerification.objects.filter(
                table_name="membership_fee",
                record_id=f.fee_id_PK,
            ).first()
            if tv:
                tv_cache[f.fee_id_PK] = tv

        if not tv or tv.verification_status != "Pending":
            continue

        member = f.member_id_FK
        encoder_name = ""
        if f.recorded_by_user_id_FK:
            encoder_name = getattr(f.recorded_by_user_id_FK, "full_name", "") or str(f.recorded_by_user_id_FK.user_id_PK)

        items.append({
                "fee_id": f.fee_id_PK,
                "ref": f.receipt_number or "",
                "member_id": member.member_id_PK if member else None,
                "member_name": member.full_name if member else "",
                "amount": str(f.amount),
                "payment_date": str(f.payment_date),
                "payment_status": f.payment_status,
                "deposit_reference": f.deposit_reference or "",
                "encoded_by": encoder_name,
                "returned_by_auditor_id_FK": tv.returned_by_auditor_id_FK_id if tv else None,
                "return_count": tv.return_count if tv else 0,
                "returned_reason": tv.returned_reason or "" if tv else "",
            })

    items.sort(key=lambda x: x["fee_id"], reverse=True)
    return JsonResponse({"ok": True, "fees": items})


@require_POST
@transaction.atomic
def auditor_verify_membership_fee(request: HttpRequest):
    data = request.POST.copy()
    for mf_key, p_key in [("mfAuditID", "pAuditID"), ("mfAuditRemarks", "pAuditRemarks"),
                          ("mfAuditFieldRemarks", "pAuditFieldRemarks"), ("mfAuditResult", "pAuditResult")]:
        if mf_key in data:
            data[p_key] = data[mf_key]
    request.POST = data
    return auditor_verify_payment(request)


@require_POST
@transaction.atomic
def auditor_verify_membership_fee_batch(request: HttpRequest):
    guard = require_role(request, role="Auditor")
    if guard is not None:
        return guard
    guard = check_zero_trust(request, level="approve")
    if guard is not None:
        return guard

    officer = _get_officer_from_session(request)
    if officer is None:
        return JsonResponse({"ok": False, "error": "Officer session missing."}, status=401)

    try:
        body_data = json.loads(request.body)
    except Exception:
        return JsonResponse({"ok": False, "error": "Invalid JSON body."}, status=400)

    ids = body_data.get("ids", [])
    result = (body_data.get("result") or "").strip()
    remarks = (body_data.get("remarks") or "").strip()

    if not ids or not isinstance(ids, list):
        return JsonResponse({"ok": False, "error": "ids must be a non-empty array."}, status=400)
    if result not in {"Verified", "Returned"}:
        return JsonResponse({"ok": False, "error": "Invalid result."}, status=400)

    items = [{"table_name": "membership_fee", "record_id": fid} for fid in ids]
    return _batch_verify_core(request, officer, items, result, remarks)


VALID_BATCH_TABLES = _SVC_MODEL_MAP.keys()


def _batch_verify_core(request, officer, items, result, remarks):
    if not items or not isinstance(items, list):
        return JsonResponse({"ok": False, "error": "items must be a non-empty array of {table_name, record_id}."}, status=400)
    if result not in {"Verified", "Returned"}:
        return JsonResponse({"ok": False, "error": "Invalid result."}, status=400)

    is_verify = result == "Verified"
    canonical_status = Status.AUDITOR_VERIFIED if is_verify else Status.RETURNED_REVISION
    audit_action = "VERIFIED" if is_verify else "RETURNED"

    seen = set()
    deduped = []
    for item in items:
        tn = (item.get("table_name") or "").strip()
        rid = item.get("record_id")
        if tn not in VALID_BATCH_TABLES:
            return JsonResponse({"ok": False, "error": f"Invalid table_name '{tn}'. Must be one of: {', '.join(sorted(VALID_BATCH_TABLES))}"}, status=400)
        if not isinstance(rid, int):
            return JsonResponse({"ok": False, "error": "record_id must be an integer."}, status=400)
        key = (tn, rid)
        if key not in seen:
            seen.add(key)
            deduped.append(key)

    verification_now = timezone.now()

    if is_verify and not (remarks or "").strip():
        auditor_name = getattr(officer, "full_name", "") or str(officer)
        remarks = f"Reviewed by {auditor_name}"

    from collections import defaultdict
    from itertools import chain
    table_ids = defaultdict(list)
    for tn, rid in deduped:
        table_ids[tn].append(rid)

    tvs_qs = TransactionVerification.objects.select_for_update().filter(
        table_name__in=list(table_ids.keys()),
        record_id__in=set(chain.from_iterable(table_ids.values())),
    )
    existing_tv_map = {(tv.table_name, tv.record_id): tv for tv in tvs_qs}

    processed = 0
    skipped = 0
    audit_entries = []

    for tn, rid in deduped:
        key = (tn, rid)
        tv = existing_tv_map.get(key)

        model_info = _SVC_MODEL_MAP.get(tn)

        if tv is not None and not is_pending(tv.verification_status):
            skipped += 1
        else:
            tv_defaults = {
                "verification_status": canonical_status,
                "auditor_id_FK": officer,
                "verified_at": verification_now,
                "auditor_remarks": remarks or "",
            }

            if not is_verify:
                tv_defaults["returned_by_auditor_id_FK"] = officer
                tv_defaults["returned_reason"] = remarks or ""

            if tv is None:
                tv_defaults["table_name"] = tn
                tv_defaults["record_id"] = rid
                TransactionVerification.objects.create(**tv_defaults)
            else:
                for field_name, val in tv_defaults.items():
                    setattr(tv, field_name, val)
                if not is_verify:
                    tv.return_count = (tv.return_count or 0) + 1
                tv.save()

            audit_entries.append({
                "table": tn,
                "record_id": rid,
                "action": audit_action,
                "ip": request.META.get("REMOTE_ADDR"),
                "notes": remarks or None,
            })
            processed += 1

        if model_info is not None:
            model_cls, pk_field, status_field = model_info
            model_cls.objects.filter(**{pk_field: rid}).update(**{status_field: canonical_status})

    if audit_entries:
        _record_bulk_audit_trail(audit_entries, actor=officer)

    _broadcast_pending_counts()
    _broadcast_to_group("auditor_dashboard", {"type": "dashboard_refresh", "section": "all"})
    _broadcast_to_group("treasurer_dashboard", {"type": "data_changed", "section": "aids"})
    return JsonResponse({"ok": True, "processed": processed, "skipped": skipped})


@require_POST
@transaction.atomic
def auditor_verify_batch(request: HttpRequest):
    guard = require_role(request, role="Auditor")
    if guard is not None:
        return guard
    guard = check_zero_trust(request, level="approve")
    if guard is not None:
        return guard

    officer = _get_officer_from_session(request)
    if officer is None:
        return JsonResponse({"ok": False, "error": "Officer session missing."}, status=401)

    try:
        body = json.loads(request.body)
    except Exception:
        return JsonResponse({"ok": False, "error": "Invalid JSON body."}, status=400)

    items = body.get("items", [])
    result = (body.get("result") or "").strip()
    remarks = (body.get("remarks") or "").strip()

    return _batch_verify_core(request, officer, items, result, remarks)


@require_POST
@transaction.atomic
def reject_transaction(request: HttpRequest):

    guard = require_role(request, role="Auditor")
    if guard is not None:
        return guard
    guard = check_zero_trust(request, level="approve")
    if guard is not None:
        return guard

    officer = _get_officer_from_session(request)
    if officer is None:
        return JsonResponse({"ok": False, "error": "Officer session missing."}, status=401)

    table_name = (request.POST.get("table_name") or "").strip()
    record_id = (request.POST.get("record_id") or "").strip()
    rejection_reason = (request.POST.get("rejection_reason") or "").strip()

    if table_name not in MODEL_MAP:
        return JsonResponse({"ok": False, "error": "Invalid table_name."}, status=400)
    if not record_id:
        return JsonResponse({"ok": False, "error": "Missing record_id."}, status=400)

    canonical_table = str(table_name).lower()
    Model = MODEL_MAP[canonical_table]
    try:
        record = Model.objects.get(pk=int(record_id))
    except (ValueError, Model.DoesNotExist):
        return JsonResponse({"ok": False, "error": "Record not found."}, status=404)

    tv_qs = TransactionVerification.objects.select_for_update().filter(
        table_name=canonical_table,
        record_id=int(record_id),
    )

    tv = tv_qs.first()
    if tv is not None and str(tv.verification_status) == "Returned for Revision":
        return JsonResponse({"ok": True}, status=200)

    route_back_to_treasurer(
        canonical_table,
        int(record_id),
        officer,
        rejection_reason,
        request,
        member=getattr(record, "member_id_FK", None),
        details="Your payment/claim was returned for revision by the Auditor.",
        tv_updates={
            "auditor_id_FK": officer,
            "auditor_remarks": rejection_reason or "",
            "returned_by_auditor_id_FK": officer,
        },
    )

    _broadcast_pending_counts()
    _broadcast_to_group("auditor_dashboard", {"type": "dashboard_refresh", "section": "all"})
    return JsonResponse({"ok": True})


@require_GET
def auditor_supporting_proof(request: HttpRequest, model_type: str, record_id: int):
    guard = require_role(request, role=["Auditor", "Treasurer", "President"])
    if guard is not None:
        return guard

    if model_type not in MODEL_MAP:
        return JsonResponse({"ok": False, "error": "Invalid model type."}, status=400)

    Model = MODEL_MAP[model_type]
    try:
        record = Model.objects.get(pk=record_id)
    except (ValueError, Model.DoesNotExist):
        return JsonResponse({"ok": False, "error": "Record not found."}, status=404)

    content_type = ContentType.objects.get_for_model(record)
    proof = SupportingProof.objects.filter(
        content_type=content_type,
        object_id=record.pk
    ).first()

    if not proof:
        return JsonResponse({"ok": True, "proof": None})

    file_url = proof.file.url if proof.file else None

    return JsonResponse({
        "ok": True,
        "proof": {
            "file_url": file_url,
            "file_type": proof.file_type,
            "file_name": proof.file_name
        }
    })


# ==========================================================================
# AID TRACKING POSTS — Auditor Dashboard
# ==========================================================================

@require_GET
def auditor_approved_aid_posts(request: HttpRequest):
    guard = require_role(request, role="Auditor")
    if guard is not None:
        return guard

    posts = AidTrackingPost.objects.filter(is_active=True).select_related(
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
            "finish_status": post.finish_status or "",
            "finish_paid_with_funds": post.finish_paid_with_funds,
            "status": archive.status if archive else "",
            "amount": str(archive.amount) if archive else "0",
            "created_at": post.created_at.isoformat() if post.created_at else "",
            "created_by": post.created_by_user_id_FK.full_name if post.created_by_user_id_FK else "",
        })

    return JsonResponse({"ok": True, "posts": items})


@require_GET
def auditor_aid_post_members(request: HttpRequest, post_id: int):
    guard = require_role(request, role="Auditor")
    if guard is not None:
        return guard

    try:
        post = AidTrackingPost.objects.select_related("archive_id_FK").get(
            post_id_PK=post_id
        )
    except AidTrackingPost.DoesNotExist:
        return JsonResponse({"ok": False, "error": "Post not found."}, status=404)

    contributions = Contribution.objects.filter(
        aid_tracking_post_id_FK=post,
    ).select_related("member_id_FK").order_by("member_id_FK__full_name")

    members_data = []
    for c in contributions:
        member = c.member_id_FK
        members_data.append({
            "contribution_id": c.contribution_id_PK,
            "member_id": member.member_id_PK,
            "member_name": member.full_name,
            "employee_id": member.employee_id or "",
            "department": member.department or "",
            "expected_amount": str(c.expected_amount),
            "paid_amount": str(c.paid_amount),
            "payment_date": str(c.payment_date) if c.payment_date else None,
            "status": c.status,
            "is_manually_overridden": c.is_manually_overridden,
            "notes": c.notes,
        })

    return JsonResponse({
        "ok": True,
        "post": {
            "post_id": post.post_id_PK,
            "aid_type": post.aid_type,
            "target_month": post.target_month,
            "total_expected": str(post.total_expected),
            "total_collected": str(post.total_collected),
        },
        "members": members_data,
    })


@require_POST
@transaction.atomic
def auditor_aid_post_member_pay(request: HttpRequest):
    guard = require_role(request, role="Auditor")
    if guard is not None:
        return guard
    guard = check_zero_trust(request, level="approve")
    if guard is not None:
        return guard

    officer = _get_officer_from_session(request)
    if officer is None:
        return JsonResponse({"ok": False, "error": "Session missing."}, status=401)

    contribution_id = (request.POST.get("contribution_id") or "").strip()
    if not contribution_id:
        return JsonResponse({"ok": False, "error": "Missing contribution_id."}, status=400)

    try:
        contribution = Contribution.objects.select_related(
            "aid_tracking_post_id_FK"
        ).get(contribution_id_PK=int(contribution_id))
    except (ValueError, Contribution.DoesNotExist):
        return JsonResponse({"ok": False, "error": "Contribution not found."}, status=404)

    contribution.paid_amount = contribution.expected_amount
    contribution.payment_date = timezone.now().date()
    contribution.status = "PAID"
    contribution.is_manually_overridden = False
    contribution.updated_by_user_id_FK = officer
    contribution.save()

    post = contribution.aid_tracking_post_id_FK
    totals = Contribution.objects.filter(aid_tracking_post_id_FK=post).aggregate(
        total_collected=Sum("paid_amount"),
    )
    post.total_collected = totals["total_collected"] or 0
    post.save(update_fields=["total_collected"])

    _record_audit_trail(
        table="contribution",
        record_id=contribution.contribution_id_PK,
        action="PAID",
        actor=officer,
        ip=request.META.get("REMOTE_ADDR"),
    )

    channel_layer = get_channel_layer()
    payload = {
        "type": "contribution_updated",
        "post_id": post.post_id_PK,
        "contribution_id": contribution.contribution_id_PK,
        "member_name": getattr(contribution.member_id_FK, "full_name", ""),
        "status": "PAID",
        "paid_amount": float(contribution.expected_amount),
    }
    async_to_sync(channel_layer.group_send)("auditor_dashboard", payload)
    async_to_sync(channel_layer.group_send)("treasurer_dashboard", payload)

    return JsonResponse({"ok": True, "status": "PAID"})


@require_POST
@transaction.atomic
def auditor_aid_post_member_skip(request: HttpRequest):
    guard = require_role(request, role="Auditor")
    if guard is not None:
        return guard
    guard = check_zero_trust(request, level="approve")
    if guard is not None:
        return guard

    officer = _get_officer_from_session(request)
    if officer is None:
        return JsonResponse({"ok": False, "error": "Session missing."}, status=401)

    contribution_id = (request.POST.get("contribution_id") or "").strip()
    notes = (request.POST.get("notes") or "").strip()

    if not contribution_id:
        return JsonResponse({"ok": False, "error": "Missing contribution_id."}, status=400)

    try:
        contribution = Contribution.objects.get(contribution_id_PK=int(contribution_id))
    except (ValueError, Contribution.DoesNotExist):
        return JsonResponse({"ok": False, "error": "Contribution not found."}, status=404)

    contribution.status = "SKIPPED"
    contribution.is_manually_overridden = True
    contribution.paid_amount = 0
    contribution.notes = notes or contribution.notes
    contribution.updated_by_user_id_FK = officer
    contribution.save()

    _record_audit_trail(
        table="contribution",
        record_id=contribution.contribution_id_PK,
        action="SKIPPED",
        actor=officer,
        ip=request.META.get("REMOTE_ADDR"),
        notes=notes or None,
    )

    channel_layer = get_channel_layer()
    payload = {
        "type": "contribution_updated",
        "post_id": contribution.aid_tracking_post_id_FK_id,
        "contribution_id": contribution.contribution_id_PK,
        "member_name": getattr(contribution.member_id_FK, "full_name", ""),
        "status": "SKIPPED",
        "paid_amount": 0,
    }
    async_to_sync(channel_layer.group_send)("auditor_dashboard", payload)
    async_to_sync(channel_layer.group_send)("treasurer_dashboard", payload)

    return JsonResponse({"ok": True, "status": "SKIPPED"})


@require_POST
@transaction.atomic
def auditor_aid_post_finish(request: HttpRequest):
    guard = require_role(request, role="Auditor")
    if guard is not None:
        return guard
    guard = check_zero_trust(request, level="approve")
    if guard is not None:
        return guard

    officer = _get_officer_from_session(request)
    if officer is None:
        return JsonResponse({"ok": False, "error": "Session missing."}, status=401)

    post_id = (request.POST.get("post_id") or "").strip()
    skip_remaining = (request.POST.get("skip_remaining") or "").strip().lower() == "true"

    if not post_id:
        return JsonResponse({"ok": False, "error": "Missing post_id."}, status=400)

    try:
        post = AidTrackingPost.objects.get(post_id_PK=int(post_id), is_active=True)
    except (ValueError, AidTrackingPost.DoesNotExist):
        return JsonResponse({"ok": False, "error": "Active post not found."}, status=404)

    if post.finish_status == "pending_approval":
        return JsonResponse({"ok": False, "error": "A finish request is already pending President approval."}, status=400)

    post.finish_status = "pending_approval"
    post.finish_skip_remaining = skip_remaining
    post.save(update_fields=["finish_status", "finish_skip_remaining"])

    _record_audit_trail(
        table="AID_TRACKING_POST",
        record_id=post.post_id_PK,
        action="FINISH_REQUESTED",
        actor=officer,
        new={"finish_status": "pending_approval", "finish_skip_remaining": skip_remaining},
        ip=request.META.get("REMOTE_ADDR"),
    )

    archive = post.archive_id_FK
    member_name = archive.member_name if archive else ""

    channel_layer = get_channel_layer()
    payload = {
        "type": "aid_post_finish_requested",
        "post_id": post.post_id_PK,
        "member_name": member_name,
    }
    async_to_sync(channel_layer.group_send)("auditor_dashboard", payload)
    async_to_sync(channel_layer.group_send)("treasurer_dashboard", payload)
    async_to_sync(channel_layer.group_send)("president_dashboard", payload)
    _broadcast_to_group("auditor_dashboard", {"type": "data_changed", "section": "aids"})

    return JsonResponse({"ok": True, "message": "Finish request submitted for President approval."})


@require_GET
def auditor_pending_finish_requests(request: HttpRequest):
    guard = require_role(request, role="Auditor")
    if guard is not None:
        return guard

    posts = AidTrackingPost.objects.filter(finish_status="pending_auditor").select_related(
        "archive_id_FK", "archive_id_FK__member_id_FK"
    )
    items = []
    for post in posts:
        archive = post.archive_id_FK
        total = Contribution.objects.filter(aid_tracking_post_id_FK=post).exclude(status="EXCLUDED_REQUESTER").count()
        paid = Contribution.objects.filter(aid_tracking_post_id_FK=post, status__in=["PAID", "RECORDED", "PENDING_VERIFICATION"]).count()
        items.append({
            "post_id": post.post_id_PK,
            "aid_type": post.aid_type,
            "aid_label": "Medical Aid" if post.aid_type == "medical_aid" else "Death Aid",
            "member_name": archive.member_name if archive else "",
            "target_month": post.target_month,
            "total_expected": float(post.total_expected),
            "total_collected": float(post.total_collected),
            "collection_rate": round((paid / total * 100) if total else 0, 1),
            "paid_count": paid,
            "total_count": total,
            "has_deduction_sheet": bool(post.deduction_sheet),
            "deduction_batch_reference": post.deduction_batch_reference or "",
            "deduction_payroll_period": post.deduction_payroll_period or "",
            "has_remittance": bool(post.deduction_remitted_amount is not None),
            "deduction_remitted_amount": str(post.deduction_remitted_amount) if post.deduction_remitted_amount is not None else None,
            "deduction_remittance_reference": post.deduction_remittance_reference or "",
            "deduction_remitted_date": post.deduction_remitted_date.isoformat() if post.deduction_remitted_date else None,
            "created_at": post.created_at.isoformat() if post.created_at else "",
        })
    return JsonResponse({"ok": True, "items": items})


@require_GET
def auditor_pending_counts(request: HttpRequest):
    """Lightweight pending counts for the auditor approval-desk navbar dots."""
    guard = require_role(request, role="Auditor")
    if guard is not None:
        return guard

    latest_verifications = TransactionVerification.objects.values(
        "table_name",
        "record_id",
    ).annotate(latest_id=Max("verification_id"))

    latest_ids = [item["latest_id"] for item in latest_verifications if item["latest_id"] is not None]

    payments = TransactionVerification.objects.filter(
        verification_status__in=["Pending", "Pending Auditor Review"],
        auditor_id_FK__isnull=True,
        verification_id__in=latest_ids,
        table_name__in=["membership_fee", "monthly_dues"],
    ).count()

    medical = MedicalAid.objects.filter(status__in=Status.ALL_PENDING).count()
    death = DeathAid.objects.filter(status__in=Status.ALL_PENDING).count()

    finish = AidTrackingPost.objects.filter(finish_status="pending_auditor").count()

    return JsonResponse({
        "ok": True,
        "payments": payments,
        "aids": medical + death,
        "finish": finish,
        "total": payments + medical + death + finish,
    })


@require_GET
def auditor_finish_request_details(request: HttpRequest):
    guard = require_role(request, role="Auditor")
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
def auditor_verify_post_finish(request: HttpRequest):
    guard = require_role(request, role="Auditor")
    if guard is not None:
        return guard
    guard = check_zero_trust(request, level="approve")
    if guard is not None:
        return guard

    officer = _get_officer_from_session(request)
    if officer is None:
        return JsonResponse({"ok": False, "error": "Session missing."}, status=401)

    post_id = (request.POST.get("post_id") or "").strip()
    decision = (request.POST.get("decision") or "").strip().lower()
    remarks = (request.POST.get("remarks") or "").strip()

    if not post_id or decision not in ("verified", "rejected"):
        return JsonResponse({"ok": False, "error": "Invalid request."}, status=400)

    try:
        post = AidTrackingPost.objects.get(post_id_PK=int(post_id), finish_status="pending_auditor")
    except (ValueError, AidTrackingPost.DoesNotExist):
        return JsonResponse({"ok": False, "error": "Post not found or not pending auditor."}, status=404)

    archive = post.archive_id_FK
    member_name = archive.member_name if archive else ""

    if decision == "verified" and not post.finish_paid_with_funds and not post.deduction_sheet:
        return JsonResponse({"ok": False, "error": "Deduction sheet has not been uploaded for this post. Treasurer must upload the salary deduction sheet before Auditor can verify."}, status=400)

    if decision == "rejected":
        post.finish_status = "rejected"
        post.save(update_fields=["finish_status"])

        _record_audit_trail(
            table="AID_TRACKING_POST",
            record_id=post.post_id_PK,
            action="FINISH_REJECTED",
            actor=officer,
            ip=request.META.get("REMOTE_ADDR"),
            notes=remarks or "Auditor rejected finish request",
        )

        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)("treasurer_dashboard", {
            "type": "aid_post_finish_rejected", "post_id": post.post_id_PK, "member_name": member_name,
        })

        try:
            notify_member(
                archive.member_id_FK,
                notification_type="Claim Update",
                message="Your claim finish request was rejected by the Auditor for revision.",
                category="claim",
                sender_name=officer.full_name if officer else "Auditor",
                sender_role="Auditor",
            )
        except Exception:
            logger.exception("Auditor finish-reject notification failed")

        return JsonResponse({"ok": True, "message": "Finish request rejected.", "status": "rejected"})

    post.finish_status = "pending_president"
    post.save(update_fields=["finish_status"])

    recorded_ids = list(
        Contribution.objects.filter(
            aid_tracking_post_id_FK=post,
            status="RECORDED",
        ).values_list("contribution_id_PK", flat=True)
    )
    pending_ids = list(
        Contribution.objects.filter(
            aid_tracking_post_id_FK=post,
            status="PENDING_VERIFICATION",
        ).values_list("contribution_id_PK", flat=True)
    )

    all_to_pay = recorded_ids + pending_ids
    inflow_count = 0

    if all_to_pay:
        Contribution.objects.filter(contribution_id_PK__in=all_to_pay).update(
            status="PAID",
            updated_by_user_id_FK=officer,
        )
        totals = Contribution.objects.filter(aid_tracking_post_id_FK=post).aggregate(
            total_collected=Sum("paid_amount"),
        )
        post.total_collected = totals["total_collected"] or 0
        post.save(update_fields=["total_collected"])

        if pending_ids:
            TransactionVerification.objects.filter(
                table_name="contribution",
                record_id__in=pending_ids,
            ).update(
                verification_status="Auditor Verified",
                auditor_id_FK=officer,
                verified_at=timezone.now(),
            )

        paid_contributions = Contribution.objects.filter(
            contribution_id_PK__in=all_to_pay,
        ).select_related("member_id_FK")

        fund_tx_batch = []
        for c in paid_contributions:
            fund_tx_batch.append(FundTransaction(
                direction="inflow",
                amount=c.paid_amount,
                source_type="contribution",
                source_id=c.contribution_id_PK,
                description=f"Aid contribution — {getattr(c.member_id_FK, 'full_name', '')} for {member_name}'s {'Medical Aid' if post.aid_type == 'medical_aid' else 'Death Aid'}",
                reference_number=f"AID-{post.post_id_PK}-C-{c.contribution_id_PK}",
                recorded_by_user_id_FK=officer,
            ))
            inflow_count += 1

        if fund_tx_batch:
            FundTransaction.objects.bulk_create(fund_tx_batch)

    _record_audit_trail(
        table="AID_TRACKING_POST",
        record_id=post.post_id_PK,
        action="FINISH_VERIFIED",
        actor=officer,
        new={
            "deduction_batch_reference": post.deduction_batch_reference or "",
            "deduction_payroll_period": post.deduction_payroll_period or "",
            "paid_count": len(all_to_pay),
            "inflow_count": inflow_count,
        },
        ip=request.META.get("REMOTE_ADDR"),
        notes=f"Auditor verified finish — ref {post.deduction_batch_reference}, period {post.deduction_payroll_period}. {remarks}" if remarks else f"Auditor verified finish — ref {post.deduction_batch_reference}, period {post.deduction_payroll_period}",
    )

    channel_layer = get_channel_layer()
    payload = {
        "type": "aid_post_finish_requested",
        "post_id": post.post_id_PK,
        "member_name": member_name,
        "stage": "president",
    }
    async_to_sync(channel_layer.group_send)("president_dashboard", payload)
    async_to_sync(channel_layer.group_send)("auditor_dashboard", payload)
    _broadcast_to_group("auditor_dashboard", {"type": "data_changed", "section": "aids"})

    try:
        notify_member(
            archive.member_id_FK,
            notification_type="Claim Update",
            message="Your claim has been verified by the Auditor and sent to the President for final approval.",
            category="claim",
            sender_name=officer.full_name if officer else "Auditor",
            sender_role="Auditor",
        )
    except Exception:
        logger.exception("Auditor finish-verify notification failed")

    return JsonResponse({"ok": True, "message": "Finish request verified and sent to President.", "status": "pending_president"})


@require_GET
def auditor_aid_post_history(request: HttpRequest):
    guard = require_role(request, role="Auditor")
    if guard is not None:
        return guard

    posts = AidTrackingPost.objects.filter(is_active=False).select_related(
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
            "status": archive.status if archive else "",
            "amount": str(archive.amount) if archive else "0",
            "created_at": post.created_at.isoformat() if post.created_at else "",
            "updated_at": post.updated_at.isoformat() if post.updated_at else "",
            "created_by": post.created_by_user_id_FK.full_name if post.created_by_user_id_FK else "",
        })

    return JsonResponse({"ok": True, "posts": items})


# ==========================================================================
# AUDITED LOGS — Official Audited Logs Registry
# ==========================================================================

TRANSACTION_TYPE_LABELS = {
    "membership_fee": "Membership Fee",
    "monthly_dues": "Monthly Dues",
    "medical_aid": "Medical Aid",
    "death_aid": "Death Aid",
    "contribution": "Aid Contribution",
}


@require_GET
def auditor_audited_logs(request: HttpRequest):
    guard = require_role(request, role="Auditor")
    if guard is not None:
        return guard

    from collections import defaultdict

    try:
        page = max(int(request.GET.get("page", 1)), 1)
    except (ValueError, TypeError):
        page = 1
    try:
        page_size = min(max(int(request.GET.get("page_size", 20)), 1), 100)
    except (ValueError, TypeError):
        page_size = 20

    base_qs = TransactionVerification.objects.exclude(
        verification_status="Pending Verification"
    ).exclude(
        verified_at__isnull=True
    )
    total_count = base_qs.count()
    total_pages = (total_count + page_size - 1) // page_size if total_count else 0

    if total_pages == 0:
        return JsonResponse({
            "ok": True,
            "logs": [],
            "page": 1,
            "page_size": page_size,
            "total_pages": 0,
            "total_count": 0,
            "has_prev": False,
            "has_next": False,
        })

    page = min(page, total_pages)
    start = (page - 1) * page_size
    qs = base_qs.select_related(
        "auditor_id_FK",
        "returned_by_auditor_id_FK",
        "president_id_FK",
    ).order_by("-verified_at")[start:start + page_size]

    table_ids = defaultdict(set)
    for tv in qs:
        table_ids[tv.table_name].add(tv.record_id)

    related_map = {}
    for tn, ids in table_ids.items():
        model_cls = MODEL_MAP.get(tn)
        if model_cls is None:
            continue
        pk_field = model_cls._meta.pk.name
        records = model_cls.objects.select_related("member_id_FK").filter(
            **{f"{pk_field}__in": list(ids)}
        )
        for r in records:
            related_map[(tn, getattr(r, pk_field))] = r

    items = []
    for tv in qs:
        key = (tv.table_name, tv.record_id)
        record = related_map.get(key)

        member_name = ""
        amount = ""
        if record:
            if hasattr(record, "member_id_FK") and record.member_id_FK:
                member_name = record.member_id_FK.full_name
            if hasattr(record, "amount"):
                amount = str(record.amount)
            elif hasattr(record, "requested_amount"):
                amount = str(record.requested_amount)
            elif hasattr(record, "benefit_amount"):
                amount = str(record.benefit_amount)
            elif hasattr(record, "paid_amount"):
                amount = str(record.paid_amount)
            elif hasattr(record, "expected_amount"):
                amount = str(record.expected_amount)

        items.append({
            "verification_id": tv.verification_id,
            "verified_at": tv.verified_at.isoformat() if tv.verified_at else "",
            "table_name": tv.table_name,
            "record_id": tv.record_id,
            "transaction_type": TRANSACTION_TYPE_LABELS.get(tv.table_name, tv.table_name),
            "member_name": member_name,
            "amount": amount,
            "result": tv.verification_status,
            "remarks": tv.auditor_remarks or "",
            "returned_reason": tv.returned_reason or "",
            "has_evidence": bool(tv.evidence_file_path),
            "evidence_file_path": tv.evidence_file_path or "",
            "auditor_name": tv.auditor_id_FK.full_name if tv.auditor_id_FK else "",
            "president_name": tv.president_id_FK.full_name if tv.president_id_FK else "",
            "approved_at": tv.approved_at.isoformat() if tv.approved_at else "",
            "return_count": tv.return_count or 0,
        })

    return JsonResponse({
        "ok": True,
        "logs": items,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
        "total_count": total_count,
        "has_prev": page > 1,
        "has_next": page < total_pages,
    })


# ==========================================================================
# PAYROLL BATCH VERIFICATION (AUDITOR)
# ==========================================================================


@require_GET
def auditor_pending_payroll_batches(request: HttpRequest):
    """List PayrollBatches pending auditor verification."""
    guard = require_role(request, role="Auditor")
    if guard is not None:
        return guard

    batches = PayrollBatch.objects.filter(
        status="Pending",
    ).select_related("recorded_by_user_id_FK").order_by("-created_at")

    items = []
    for b in batches:
        items.append({
            "batch_id": b.batch_id_PK,
            "payroll_period": b.payroll_period,
            "total_amount": float(b.total_amount),
            "member_count": b.member_count,
            "hardcopy_reference": b.hardcopy_reference or "",
            "notes": b.notes or "",
            "recorded_by": b.recorded_by_user_id_FK.full_name if b.recorded_by_user_id_FK else "",
            "recorded_at": b.created_at.isoformat() if b.created_at else "",
        })

    return JsonResponse({"ok": True, "batches": items})


@require_GET
def auditor_payroll_batch_detail(request: HttpRequest, batch_id: int):
    """View a PayrollBatch with all deductions (auditor version)."""
    guard = require_role(request, role="Auditor")
    if guard is not None:
        return guard

    batch = get_object_or_404(PayrollBatch, pk=batch_id)
    deductions = PayrollDeduction.objects.filter(batch_id_FK=batch).select_related("member_id_FK")

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
            "notes": d.notes or "",
        })

    proof = SupportingProof.objects.filter(
        content_type=ContentType.objects.get_for_model(PayrollBatch),
        object_id=batch.pk,
    )
    proof_files = [{
        "file_name": p.file_name,
        "url": p.file.url if p.file else "",
    } for p in proof]

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
            "created_at": batch.created_at.isoformat() if batch.created_at else "",
        },
        "deductions": ded_list,
        "supporting_files": proof_files,
    })


@require_POST
@transaction.atomic
def auditor_verify_payroll_batch(request: HttpRequest, batch_id: int):
    """Mark a PayrollBatch as Auditor Verified."""
    guard = require_role(request, role="Auditor")
    if guard is not None:
        return guard
    guard = check_zero_trust(request, level="approve")
    if guard is not None:
        return guard

    batch = get_object_or_404(PayrollBatch, pk=batch_id, status="Pending")

    stored_officer_id = request.session.get("officer_id")
    try:
        officer = OfficerUser.objects.get(user_id_PK=int(stored_officer_id))
    except (ValueError, OfficerUser.DoesNotExist):
        return JsonResponse({"ok": False, "error": "Officer not found."}, status=404)

    try:
        data = json.loads(request.body)
    except Exception:
        data = {}

    batch.status = "Auditor Verified"
    batch.auditor_verified_by_user_id_FK = officer
    batch.auditor_verified_at = timezone.now()
    batch.auditor_remarks = data.get("remarks", "")
    batch.save(update_fields=["status", "auditor_verified_by_user_id_FK", "auditor_verified_at", "auditor_remarks"])

    _record_audit_trail(
        table="PAYROLL_BATCH",
        record_id=batch.pk,
        action="VERIFIED",
        actor=officer,
        ip=request.META.get("REMOTE_ADDR"),
        new={"status": "Auditor Verified", "remarks": data.get("remarks", "")},
    )

    _broadcast_pending_counts()
    _broadcast_to_group("auditor_dashboard", {"type": "dashboard_refresh", "section": "all"})

    return JsonResponse({"ok": True, "message": "Payroll batch verified."})


@require_POST
@transaction.atomic
def auditor_reject_payroll_batch(request: HttpRequest, batch_id: int):
    """Return a PayrollBatch for revision."""
    guard = require_role(request, role="Auditor")
    if guard is not None:
        return guard
    guard = check_zero_trust(request, level="approve")
    if guard is not None:
        return guard

    batch = get_object_or_404(PayrollBatch, pk=batch_id, status="Pending")

    stored_officer_id = request.session.get("officer_id")
    try:
        officer = OfficerUser.objects.get(user_id_PK=int(stored_officer_id))
    except (ValueError, OfficerUser.DoesNotExist):
        return JsonResponse({"ok": False, "error": "Officer not found."}, status=404)

    try:
        data = json.loads(request.body)
    except Exception:
        data = {}

    reason = data.get("reason", "")
    if not reason:
        return JsonResponse({"ok": False, "error": "Reason is required for rejection."}, status=400)

    batch.status = "Returned for Revision"
    batch.returned_by_user_id_FK = officer
    batch.returned_reason = reason
    batch.save(update_fields=["status", "returned_by_user_id_FK", "returned_reason"])

    _record_audit_trail(
        table="PAYROLL_BATCH",
        record_id=batch.pk,
        action="RETURNED",
        actor=officer,
        ip=request.META.get("REMOTE_ADDR"),
        notes=reason,
        new={"status": "Returned for Revision", "reason": reason},
    )

    _broadcast_pending_counts()
    _broadcast_to_group("auditor_dashboard", {"type": "dashboard_refresh", "section": "all"})

    return JsonResponse({"ok": True, "message": "Payroll batch returned for revision."})


# ==========================================================================
# AUDITOR REGISTRATION REVIEW — Registration Requests
# ==========================================================================


@require_GET
def auditor_registration_requests_list(request: HttpRequest):
    """List registration requests awaiting auditor review (Treasurer Verified)."""
    guard = require_role(request, role="Auditor")
    if guard is not None:
        return guard

    requests_qs = MemberRegistrationRequest.objects.filter(
        status=RegistrationStatus.TREASURER_VERIFIED,
    ).select_related(
        "processed_by_user_id_FK", "treasurer_verified_by_user_id_FK"
    ).order_by("-submitted_at")

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
            "proof_url": _get_proof_url(MemberRegistrationRequest, req.request_id_PK) or "",
        })

    return JsonResponse({"ok": True, "requests": rows})


@require_POST
@transaction.atomic
def auditor_verify_registration_request(request: HttpRequest, request_id: int):
    """Auditor verifies or returns a registration request."""
    guard = require_role(request, role="Auditor")
    if guard is not None:
        return guard
    guard = check_zero_trust(request, level="approve")
    if guard is not None:
        return guard

    officer = resolve_officer_from_session(request)
    if officer is None:
        return JsonResponse({"ok": False, "error": "Unable to resolve officer session."}, status=401)

    request_row = get_object_or_404(MemberRegistrationRequest, request_id_PK=request_id)
    action = (request.POST.get("action") or "").strip().lower()
    reason = (request.POST.get("reason") or "").strip()

    if action not in {"verify", "return", "reject"}:
        return JsonResponse({"ok": False, "error": "Invalid action specified."}, status=400)

    if request_row.status != RegistrationStatus.TREASURER_VERIFIED:
        return JsonResponse(
            {"ok": False, "error": "This registration request is not awaiting auditor review."},
            status=400,
        )

    if action == "verify":
        request_row.status = RegistrationStatus.AUDITOR_VERIFIED
        request_row.auditor_verified_by_user_id_FK = officer
        request_row.save()

        _record_audit_trail(
            table="member_registration_request",
            record_id=request_row.request_id_PK,
            action="AUDITOR_VERIFIED",
            actor=officer,
            ip=request.META.get("REMOTE_ADDR"),
            notes=f"Auditor verified registration request for {request_row.full_name}",
        )

        _broadcast_pending_counts()

        try:
            send_registration_status_update_email(
                request_row.email,
                request_row.full_name,
                new_status="Auditor Verified",
                next_stage="President Approval",
            )
        except Exception:
            logger.exception("Failed to send status update email for %s", request_row.full_name)

        return JsonResponse({"ok": True, "status": request_row.status})

    if action in {"return", "reject"}:
        if not reason:
            return JsonResponse({"ok": False, "error": "Reason is required for returning or rejecting a request."}, status=400)

        request_row.status = (
            RegistrationStatus.RETURNED_FOR_REVISION if action == "return" else RegistrationStatus.REJECTED
        )
        request_row.returned_reason = reason
        request_row.auditor_verified_by_user_id_FK = officer
        request_row.save()

        try:
            if action == "return":
                send_registration_returned_email(
                    request_row.email,
                    request_row.full_name,
                    reason=reason,
                )
            else:
                send_registration_rejected_email(
                    request_row.email,
                    request_row.full_name,
                    reason=reason,
                )
        except Exception:
            logger.exception("Failed to send %s email for %s", action, request_row.full_name)

        return JsonResponse({"ok": True, "status": request_row.status})


# ─────────────────────────────────────────────────────────────────────────────
# Department Payment Compliance Heat Map (monitoring + reminders)
# ─────────────────────────────────────────────────────────────────────────────

_PAID_DUES_STATUSES = {"Paid", "Full Payment"}
_PENDING_DUES_STATUSES = {"Pending"}


def _heatmap_color(rate: float) -> str:
    if rate >= 90:
        return "green"
    if rate >= 75:
        return "yellow"
    if rate >= 50:
        return "orange"
    return "red"


def _heatmap_month_key(year: str, month: str) -> str:
    return f"{year}-{month:0>2}"


def _heatmap_member_status(member_id: int, dues_map: dict, pending_map: set) -> str:
    """Return 'paid' | 'advance' | 'pending' | 'unpaid' for a member in a month.

    ``dues_map`` maps member_id -> list of MonthlyDues rows that count as paid.
    ``pending_map`` holds member ids that have a Pending dues record for the month.
    A paid row whose ``is_advance`` is True means the covered month is satisfied by
    an early/advance payment, so the member is classified as 'advance'.
    """
    if member_id in dues_map:
        rows = dues_map[member_id]
        if any(getattr(d, "is_advance", False) for d in rows):
            return "advance"
        return "paid"
    if member_id in pending_map:
        return "pending"
    return "unpaid"


@require_GET
def auditor_payment_years(request: HttpRequest):
    """Get all years that have payment records for the heatmap year dropdown."""
    guard = require_role(request, role=["Auditor", "Treasurer", "President"])
    if guard is not None:
        return guard

    # Get unique years from MonthlyDues month_covered field
    # month_covered format is "YYYY-MM", so we extract the year part
    years = set()
    for due in MonthlyDues.objects.all():
        if due.month_covered:
            year = due.month_covered.split('-')[0]
            if year.isdigit() and len(year) == 4:
                years.add(int(year))
    
    # Convert to sorted list
    sorted_years = sorted(years) if years else [timezone.now().year]
    
    return JsonResponse({
        "ok": True,
        "years": sorted_years
    })


@require_GET
def auditor_compliance_heatmap(request: HttpRequest):
    """Department payment compliance heat map for a selected month.

    GET params:
      - month: 2-digit month (defaults to current month)
      - year: 4-digit year (defaults to current year)
      - payment_type: optional MonthlyDues.payment_method filter (never converts
        a member who paid through another method into 'unpaid')
      - payment_status: optional 'Paid' | 'Pending' | 'Advance' | 'Unpaid' filter
    """
    guard = require_role(request, role=["Auditor", "Treasurer", "President"])
    if guard is not None:
        return guard

    month = (request.GET.get("month") or "").strip()
    year = (request.GET.get("year") or "").strip()
    if not month.isdigit() or not (1 <= int(month) <= 12):
        month = timezone.now().strftime("%m")
    if not year.isdigit() or len(year) != 4:
        year = timezone.now().strftime("%Y")
    month = f"{int(month):02d}"

    payment_type = (request.GET.get("payment_type") or "").strip()
    status_filter = (request.GET.get("payment_status") or "").strip()

    month_key = _heatmap_month_key(year, month)

    active_members = Member.objects.exclude(membership_status__iexact="retired")

    # All dues for the selected month are loaded regardless of the payment-method
    # filter so that a member who paid through another method is NOT turned into an
    # "Unpaid" member -- the payment-status labels and compliance rate stay accurate.
    dues_rows = list(
        MonthlyDues.objects.filter(month_covered=month_key).select_related("member_id_FK")
    )

    paid_map = {}  # member_id -> list of paid dues rows
    pending_members = set()
    paid_by_type = set()  # member ids whose paid dues match the selected payment_type
    for d in dues_rows:
        if d.payment_status in _PAID_DUES_STATUSES:
            paid_map.setdefault(d.member_id_FK_id, []).append(d)
            if payment_type and d.payment_method == payment_type:
                paid_by_type.add(d.member_id_FK_id)
        elif d.payment_status in _PENDING_DUES_STATUSES:
            pending_members.add(d.member_id_FK_id)

    dept_names = sorted(
        active_members.filter(department__isnull=False)
        .exclude(department="")
        .values_list("department", flat=True)
        .distinct()
    )

    members_by_dept = {}
    for m in active_members.filter(department__isnull=False).exclude(department=""):
        members_by_dept.setdefault(m.department, []).append(m)

    departments = []
    analytics = {
        "total_departments": len(dept_names),
        "fully_compliant": 0,
        "needs_followup": 0,
        "total_paid_members": 0,
        "total_advance_members": 0,
        "total_pending_payments": 0,
        "total_unpaid_members": 0,
        "overall_compliance_rate": 0,
        "total_monthly_collections": 0,
    }
    grand_paid = 0
    grand_total = 0

    for dept in dept_names:
        dept_members = members_by_dept.get(dept, [])
        total = len(dept_members)
        paid = 0
        advance = 0
        pending = 0
        unpaid = 0
        collected = 0
        paid_other_method = 0

        for m in dept_members:
            st = _heatmap_member_status(m.member_id_PK, paid_map, pending_members)
            if status_filter and st != status_filter.lower():
                continue
            if st in ("paid", "advance"):
                paid += 1
                if st == "advance":
                    advance += 1
                if payment_type and m.member_id_PK not in paid_by_type:
                    paid_other_method += 1
                for d in paid_map.get(m.member_id_PK, []):
                    collected += float(d.amount)
            elif st == "pending":
                pending += 1
            else:
                unpaid += 1

        counted = paid + pending + unpaid
        if status_filter:
            rate = round((paid / counted * 100) if counted > 0 else 0, 1)
        else:
            rate = round((paid / total * 100) if total > 0 else 0, 1)

        departments.append({
            "department": dept,
            "total_members": total,
            "paid": paid,
            "advance": advance,
            "pending": pending,
            "unpaid": unpaid,
            "paid_other_method": paid_other_method,
            "compliance_rate": rate,
            "color": _heatmap_color(rate),
        })

        grand_paid += paid
        grand_total += total
        analytics["total_paid_members"] += paid
        analytics["total_advance_members"] += advance
        analytics["total_pending_payments"] += pending
        analytics["total_unpaid_members"] += unpaid
        analytics["total_monthly_collections"] += collected

        if rate >= 90:
            analytics["fully_compliant"] += 1
        else:
            analytics["needs_followup"] += 1

    if grand_total > 0:
        analytics["overall_compliance_rate"] = round(grand_paid / grand_total * 100, 1)

    return JsonResponse({
        "ok": True,
        "month": month_key,
        "analytics": analytics,
        "departments": departments,
    })


@require_GET
def auditor_department_detail(request: HttpRequest):
    """Member-level payment status within a single department for a month."""
    guard = require_role(request, role=["Auditor", "Treasurer", "President"])
    if guard is not None:
        return guard

    department = (request.GET.get("department") or "").strip()
    month = (request.GET.get("month") or "").strip()
    year = (request.GET.get("year") or "").strip()
    payment_method = (request.GET.get("payment_method") or "").strip()

    if not department:
        return JsonResponse({"ok": False, "error": "department query parameter required."}, status=400)
    if not month.isdigit() or not (1 <= int(month) <= 12):
        return JsonResponse({"ok": False, "error": "month query parameter required."}, status=400)
    if not year.isdigit() or len(year) != 4:
        # Tolerate an empty year (dropdown still loading): fall back to the
        # current year instead of hard-failing the request.
        year = str(timezone.now().year)

    month = f"{int(month):02d}"
    month_key = _heatmap_month_key(year, month)

    members = list(
        Member.objects.filter(department=department)
        .exclude(membership_status__iexact="retired")
        .order_by("full_name")
    )

    dues_rows = list(
        MonthlyDues.objects.filter(month_covered=month_key).select_related("member_id_FK")
    )

    paid_map = {}
    pending_members = set()
    for d in dues_rows:
        if d.payment_status in _PAID_DUES_STATUSES:
            paid_map.setdefault(d.member_id_FK_id, []).append(d)
        elif d.payment_status in _PENDING_DUES_STATUSES:
            pending_members.add(d.member_id_FK_id)

    member_rows = []
    summary = {"total_members": len(members), "paid": 0, "advance": 0, "pending": 0, "unpaid": 0}
    month_names = ["January", "February", "March", "April", "May", "June",
                   "July", "August", "September", "October", "November", "December"]
    month_display = f"{month_names[int(month) - 1]} {year}"

    for m in members:
        st = _heatmap_member_status(m.member_id_PK, paid_map, pending_members)
        dues_for_member = paid_map.get(m.member_id_PK, [])
        if not dues_for_member:
            dues_for_member = [d for d in dues_rows if d.member_id_FK_id == m.member_id_PK]

        latest = None
        if dues_for_member:
            latest = max(dues_for_member, key=lambda d: d.payment_date or d.dues_id_PK)

        if st == "paid":
            status_display = "Paid"
            summary["paid"] += 1
        elif st == "advance":
            status_display = "Advance / Covered"
            summary["advance"] += 1
        elif st == "pending":
            status_display = "Pending"
            summary["pending"] += 1
        else:
            status_display = "Unpaid"
            summary["unpaid"] += 1

        # When a payment-method filter is active, a member who is truly paid but
        # settled through a different method keeps their paid status; this flag lets
        # the UI label them "Paid -- Other Payment Method" instead of "Unpaid".
        paid_other_method = bool(
            payment_method and st in ("paid", "advance") and latest
            and latest.payment_method != payment_method
        )

        member_rows.append({
            "member_id": m.member_id_PK,
            "employee_id": m.employee_id or "",
            "full_name": m.full_name,
            "status_display": status_display,
            "payment_status": status_display,
            "payment_method": latest.payment_method if latest else "",
            "last_payment_date": str(latest.payment_date) if latest and latest.payment_date else "",
            "is_advance": st == "advance",
            "paid_other_method": paid_other_method,
        })

    return JsonResponse({
        "ok": True,
        "department": department,
        "month": month_display,
        "summary": summary,
        "members": member_rows,
    })


@require_GET
def auditor_member_payment_history(request: HttpRequest):
    """Per-month payment history for a single member.

    The window is flexible: it spans from the earliest month the member has a
    MonthlyDues record (or 11 months back from today, whichever is earlier) to the
    latest record month (or the current month, whichever is later), so advance /
    future covered months are always shown.
    """
    guard = require_role(request, role=["Auditor", "Treasurer", "President"])
    if guard is not None:
        return guard

    member_id = (request.GET.get("member_id") or "").strip()
    if not member_id.isdigit():
        return JsonResponse({"ok": False, "error": "member_id query parameter required."}, status=400)

    member = get_object_or_404(Member, member_id_PK=int(member_id))

    member_dues = MonthlyDues.objects.filter(member_id_FK=member)
    status_by_month = {}
    advance_by_month = {}
    for d in member_dues:
        st = d.payment_status
        if st in _PAID_DUES_STATUSES:
            status_by_month[d.month_covered] = "✅"
        elif st in _PENDING_DUES_STATUSES:
            status_by_month.setdefault(d.month_covered, "⏳")
        else:
            status_by_month.setdefault(d.month_covered, "❌")
        if getattr(d, "is_advance", False):
            # The month the advance covers is satisfied by the advance.
            advance_by_month[d.month_covered] = "Covered by Advance"
            # The month the money actually arrived shows the advance was made.
            if d.payment_date:
                pay_month = d.payment_date.strftime("%Y-%m")
                advance_by_month.setdefault(pay_month, "Advance")

    today = timezone.now().date()
    today_first = today.replace(day=1)
    month_names = ["January", "February", "March", "April", "May", "June",
                   "July", "August", "September", "October", "November", "December"]

    # Build a flexible month window instead of a fixed trailing 12 months:
    # it must include EVERY month the member has any MonthlyDues record for
    # (including future advance/covered months), plus the trailing 11 months
    # from today so unpaid history is still visible.
    parsed_months = []
    for d in member_dues:
        mc = (d.month_covered or "").strip()
        try:
            parsed_months.append(timezone.datetime.strptime(mc, "%Y-%m").date().replace(day=1))
        except (ValueError, TypeError):
            continue
    if not parsed_months:
        parsed_months = [today_first]

    def _months_back(d: object, n: int) -> object:
        total = d.year * 12 + (d.month - 1) - n
        return timezone.datetime(total // 12, total % 12 + 1, 1).date()

    start = min(min(parsed_months), _months_back(today_first, 11))
    end = max(max(parsed_months), today_first)

    history = []
    cursor = start
    while cursor <= end:
        key = cursor.strftime("%Y-%m")
        advance_label = advance_by_month.get(key, "")
        status = status_by_month.get(key, "❌")
        if advance_label == "Covered by Advance":
            status = "🔵"
        history.append({
            "status": status,
            "month_display": f"{month_names[cursor.month - 1][:3]} {cursor.year}",
            "advance_label": advance_label,
        })
        if cursor.month == 12:
            cursor = cursor.replace(year=cursor.year + 1, month=1)
        else:
            cursor = cursor.replace(month=cursor.month + 1)

    return JsonResponse({
        "ok": True,
        "member": {
            "full_name": member.full_name,
            "employee_id": member.employee_id or "",
            "department": member.department or "",
        },
        "payment_history": history,
    })


# ============================================================================
# AUDITOR: VISUALIZATION DATA ENDPOINTS
# ============================================================================

@require_GET
def auditor_dashboard_paid_pending_unpaid(request: HttpRequest):
    """Overall paid/pending/unpaid distribution for the current month."""
    guard = require_role(request, role=["Auditor", "Treasurer", "President"])
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
def auditor_dashboard_audit_pipeline(request: HttpRequest):
    """Audit pipeline status - how much work has been verified."""
    guard = require_role(request, role=["Auditor", "Treasurer", "President"])
    if guard is not None:
        return guard

    # Statuses used by the actual auditor queue (see auditor payments auditing).
    pending_statuses = [Status.PENDING, Status.PENDING_AUDITOR_REVIEW]
    acted_statuses = [Status.RETURNED_REVISION, Status.REJECTED]

    def _latest_qs(table_names):
        """Latest verification row per record (resubmits create duplicates)."""
        latest = (
            TransactionVerification.objects
            .filter(table_name__in=table_names)
            .values("table_name", "record_id")
            .annotate(latest_id=Max("verification_id"))
        )
        ids = [i["latest_id"] for i in latest if i["latest_id"] is not None]
        return TransactionVerification.objects.filter(verification_id__in=ids)

    # Payments: membership fees + monthly dues
    pay_qs = _latest_qs(["membership_fee", "monthly_dues"])
    payments_pending = pay_qs.filter(verification_status__in=pending_statuses).count()
    payments_verified = pay_qs.filter(verification_status=Status.AUDITOR_VERIFIED).count()
    payments_returned = pay_qs.filter(verification_status__in=acted_statuses).count()

    # Aid claims: medical + death aid
    aid_qs = _latest_qs(["medical_aid", "death_aid"])
    aids_pending = aid_qs.filter(verification_status__in=pending_statuses).count()
    aids_verified = aid_qs.filter(verification_status=Status.AUDITOR_VERIFIED).count()
    aids_returned = aid_qs.filter(verification_status__in=acted_statuses).count()

    # Contributions: live status lives on the Contribution model
    # (RECORDED/PENDING_VERIFICATION await auditor batch-verify -> PAID)
    contributions_pending = Contribution.objects.filter(
        status__in=[Contribution.STATUS_RECORDED, Contribution.STATUS_PENDING_VERIFICATION]
    ).count()
    contributions_verified = Contribution.objects.filter(
        status=Contribution.STATUS_PAID
    ).count()
    contributions_returned = 0  # contributions are skipped/repaid, never returned

    return JsonResponse({
        "ok": True,
        "payments": {
            "pending": payments_pending,
            "verified": payments_verified,
            "returned": payments_returned,
            "total": payments_pending + payments_verified + payments_returned,
        },
        "aid_claims": {
            "pending": aids_pending,
            "verified": aids_verified,
            "returned": aids_returned,
            "total": aids_pending + aids_verified + aids_returned,
        },
        "contributions": {
            "pending": contributions_pending,
            "verified": contributions_verified,
            "returned": contributions_returned,
            "total": contributions_pending + contributions_verified + contributions_returned,
        },
    })


@require_GET
def auditor_dashboard_audit_attention(request: HttpRequest):
    """Audit attention panel - items needing auditor review."""
    guard = require_role(request, role=["Auditor", "Treasurer", "President"])
    if guard is not None:
        return guard

    pending_statuses = [Status.PENDING, Status.PENDING_AUDITOR_REVIEW]

    def _latest_qs(table_names):
        latest = (
            TransactionVerification.objects
            .filter(table_name__in=table_names)
            .values("table_name", "record_id")
            .annotate(latest_id=Max("verification_id"))
        )
        ids = [i["latest_id"] for i in latest if i["latest_id"] is not None]
        return TransactionVerification.objects.filter(verification_id__in=ids)

    payments_awaiting = _latest_qs(["membership_fee", "monthly_dues"]).filter(
        verification_status__in=pending_statuses
    ).count()

    aids_awaiting = _latest_qs(["medical_aid", "death_aid"]).filter(
        verification_status__in=pending_statuses
    ).count()

    contributions_awaiting = Contribution.objects.filter(
        status__in=[Contribution.STATUS_RECORDED, Contribution.STATUS_PENDING_VERIFICATION]
    ).count()

    returned_records = TransactionVerification.objects.filter(
        table_name__in=["membership_fee", "monthly_dues", "medical_aid", "death_aid", "contribution"],
        verification_status__in=[Status.RETURNED_REVISION, Status.REJECTED],
    ).count()

    return JsonResponse({
        "ok": True,
        "payments_awaiting_verification": payments_awaiting,
        "aid_claims_requiring_review": aids_awaiting,
        "contributions_pending_verification": contributions_awaiting,
        "returned_records": returned_records,
    })


@require_POST
def auditor_send_payment_reminder(request: HttpRequest):
    """Send monthly-dues payment reminders to unpaid members."""
    guard = require_role(request, role=["Auditor", "Treasurer", "President"])
    if guard is not None:
        return guard

    try:
        body = json.loads(request.body or b"{}")
    except json.JSONDecodeError:
        body = {}

    member_ids = body.get("member_ids") or []
    month = (str(body.get("month") or "")).strip()
    year = (str(body.get("year") or "")).strip()

    if not month.isdigit() or not (1 <= int(month) <= 12):
        return JsonResponse({"ok": False, "error": "month is required."}, status=400)
    if not year.isdigit() or len(year) != 4:
        return JsonResponse({"ok": False, "error": "year is required."}, status=400)
    month = f"{int(month):02d}"
    month_key = _heatmap_month_key(year, month)

    try:
        member_ids = [int(x) for x in member_ids]
    except (TypeError, ValueError):
        return JsonResponse({"ok": False, "error": "Invalid member_ids."}, status=400)

    members = list(Member.objects.filter(member_id_PK__in=member_ids))

    officer = _get_officer_from_session(request)
    officer_name = officer.full_name if officer else "Auditor"

    month_names = ["January", "February", "March", "April", "May", "June",
                   "July", "August", "September", "October", "November", "December"]
    month_display = f"{month_names[int(month) - 1]} {year}"

    sent = 0
    for m in members:
        has_paid = MonthlyDues.objects.filter(
            member_id_FK=m, month_covered=month_key,
            payment_status__in=list(_PAID_DUES_STATUSES),
        ).exists()
        if has_paid:
            continue
        try:
            notify_member(
                m,
                notification_type="Monthly Dues Reminder",
                message=f"This is a reminder that your monthly dues for {month_display} have not yet been paid. Please settle your dues to remain in good standing.",
                category="dues",
                sender_name=officer_name,
                sender_role="Auditor",
            )
            sent += 1
        except Exception as notify_err:
            logger.error("auditor_send_payment_reminder: notify failed for member %s: %s", m.member_id_PK, notify_err)
            return JsonResponse({"ok": False, "error": f"Notification failed: {notify_err}"}, status=500)

    return JsonResponse({
        "ok": True,
        "message": f"Payment reminders sent to {sent} member(s).",
        "sent": sent,
    })
