import hashlib
import hmac
import json
import logging
import re
from datetime import datetime
from typing import Any, Dict, Optional

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.core.cache import cache
from django.http import HttpRequest
from django.utils import timezone

from core_system.constants.status_constants import Status
from core_system.constants.policy_constants import (
    get_membership_fee_amount,
    get_monthly_dues_amount,
    is_exempt_from_dues_and_aid,
)
from core_system.models import (
    AuditFindingsReport,
    Contribution,
    DeathAid,
    FinancialDocumentArchive,
    GlobalAuditTrail,
    MedicalAid,
    Member,
    MembershipFee,
    MonthlyDues,
    OfficerUser,
    PayrollBatch,
    SensitiveReadLog,
    SupportingProof,
    TransactionArchive,
    TransactionVerification,
)

def parse_aware_datetime(value):
    """Parse a form-supplied date/datetime string into a timezone-aware datetime, or None.

    Prevents Django's 'DateTimeField received a naive datetime' RuntimeWarning.
    """
    if not value:
        return None
    if isinstance(value, datetime):
        return value if timezone.is_aware(value) else timezone.make_aware(value)
    try:
        parsed = datetime.fromisoformat(str(value).strip())
    except (ValueError, TypeError):
        return None
    if parsed.tzinfo is None:
        parsed = timezone.make_aware(parsed)
    return parsed


MODEL_MAP = {
    "membership_fee": MembershipFee,
    "monthly_dues": MonthlyDues,
    "medical_aid": MedicalAid,
    "death_aid": DeathAid,
    "payroll_batch": PayrollBatch,
    "contribution": Contribution,
}

UPDATABLE_FIELDS = {
    "membership_fee": ["amount", "payment_method", "payment_status", "payment_date", "receipt_number", "deposit_reference"],
    "monthly_dues": ["month_covered", "amount", "payment_method", "payment_status", "receipt_number", "payment_date", "remittance_reference", "deduction_batch_reference"],
    "medical_aid": ["request_date", "requested_amount", "hospital_name", "hospital_date", "hospital_bill_amount", "document_status"],
    "death_aid": ["claim_date", "claim_type", "deceased_name", "relationship_to_member", "relationship_group", "bill_amount", "document_status"],
}

MONTH_COVERED_PATTERN = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")

PAYMENT_ENTITY_TYPE_LABELS = {
    "membership_fee": "MembershipFee",
    "monthly_dues": "MonthlyDues",
}

PAYMENT_SOURCE_LABELS = {
    "membership_fee": "Membership Fee",
    "monthly_dues": "Monthly Dues",
}


def normalize_month_covered(value: str) -> str:
    value = (value or "").strip()
    full_date_match = re.match(r"^(\d{4})-(0[1-9]|1[0-2])-(\d{2})$", value)
    if full_date_match:
        return f"{full_date_match.group(1)}-{full_date_match.group(2)}"
    return value


def get_request_month_covered(request: HttpRequest) -> str:
    for field_name in ("fee_month", "month_covered", "fee_month_covered", "covered_period"):
        value = request.POST.get(field_name)
        if value:
            return value.strip()
    return ""


def resolve_officer_from_session(request) -> Optional["OfficerUser"]:
    stored_officer_id = request.session.get("officer_id")
    if stored_officer_id is not None:
        try:
            return OfficerUser.objects.get(user_id_PK=int(stored_officer_id))
        except Exception:
            return None
    return None


def resolve_member_from_input(member_input: str):
    clean = str(member_input).strip()
    if clean.upper().startswith("M-"):
        clean = clean[2:]
    try:
        pk = int(clean)
    except ValueError:
        return None, JsonResponse(
            {"ok": False, "error": "Member ID must be numeric (e.g., 1) or 'M-<id>'."},
            status=400,
        )
    try:
        return Member.objects.get(member_id_PK=pk), None
    except Member.DoesNotExist:
        return None, JsonResponse({"ok": False, "error": "Member not found."}, status=404)


def check_member_not_retired(member: Member):
    if is_exempt_from_dues_and_aid(member):
        return JsonResponse(
            {"ok": False, "error": "Retired members are exempt from monthly dues per ARTICLE XI Section 2."},
            status=400,
        )
    return None


def _sha256_of_uploaded_file(uploaded_file) -> str:
    sha = hashlib.sha256()
    for chunk in uploaded_file.chunks():
        sha.update(chunk)
    return sha.hexdigest()


def _compute_row_signature(file_digest: str, object_id: int) -> str:
    message = f"{file_digest}:{object_id}:{settings.SECRET_KEY}".encode()
    return hmac.new(
        settings.SECRET_KEY.encode(),
        message,
        hashlib.sha256,
    ).hexdigest()


def _link_proof_to_record(uploaded_file, parent_instance, officer):
    file_digest = _sha256_of_uploaded_file(uploaded_file)
    content_type = ContentType.objects.get_for_model(parent_instance)

    proof = SupportingProof(
        content_type=content_type,
        object_id=parent_instance.pk,
        file=uploaded_file,
        file_name=uploaded_file.name,
        file_type=getattr(uploaded_file, "content_type", None) or "application/octet-stream",
        file_sha256=file_digest,
        uploaded_by=officer,
    )
    proof.row_signature = _compute_row_signature(file_digest, parent_instance.pk)
    proof.save()


def _audit_evidence_filename(file_path):
    if not file_path:
        return ""
    return str(file_path).replace("\\", "/").split("/")[-1]


def _get_rejection_info(table_name: str, record_id: int):
    revision = GlobalAuditTrail.objects.filter(
        table_name=table_name,
        record_id=record_id,
        action__in=["RETURNED", "CORRECTION_REQUIRED", "REJECTED"],
    ).order_by("-timestamp").first()
    rejection_reason = revision.notes if revision else ""
    rejection_details = []
    tv = TransactionVerification.objects.filter(
        table_name=table_name, record_id=record_id
    ).first()
    if tv and tv.auditor_remarks:
        try:
            parsed = json.loads(tv.auditor_remarks)
            if isinstance(parsed, dict) and "rejection_details" in parsed:
                rejection_details = parsed["rejection_details"]
        except (json.JSONDecodeError, TypeError):
            pass
    return rejection_reason, rejection_details


def _get_encoder_name(record) -> str:
    encoder_name = ""
    if getattr(record, "recorded_by_user_id_FK", None) is not None:
        encoder_name = getattr(record.recorded_by_user_id_FK, "full_name", None)
        if not encoder_name:
            encoder_name = str(getattr(record.recorded_by_user_id_FK, "user_id_PK",
                                       getattr(record, "recorded_by_user_id_FK_id", "")))
    return encoder_name


def _get_proof_url(content_type_model, object_id) -> str:
    try:
        proof = SupportingProof.objects.filter(
            content_type=ContentType.objects.get_for_model(content_type_model),
            object_id=object_id,
        ).order_by("-uploaded_at").first()
        if proof and getattr(proof, "file", None):
            return proof.file.url
    except Exception:
        pass
    return ""


def _get_monthly_dues_proof_url(dues) -> str:
    """Return the first proof URL for a MonthlyDues record, including proofs
    linked to sibling rows of the same submission (multi-month advance payments
    only link the uploaded proof to the first row)."""
    try:
        ct = ContentType.objects.get_for_model(dues.__class__)
        sibling_ids = [dues.dues_id_PK]
        if getattr(dues, "receipt_number", None):
            sibling_ids.extend(
                type(dues)
                .objects.filter(
                    member_id_FK=dues.member_id_FK,
                    receipt_number=dues.receipt_number,
                )
                .exclude(dues_id_PK=dues.dues_id_PK)
                .values_list("dues_id_PK", flat=True)
            )
        proof = (
            SupportingProof.objects.filter(
                content_type=ct,
                object_id__in=sibling_ids,
            )
            .order_by("-uploaded_at")
            .first()
        )
        if proof and getattr(proof, "file", None):
            return proof.file.url
    except Exception:
        pass
    return ""


def _get_auditor_finding_evidence(table_name, record_id):
    archive = FinancialDocumentArchive.objects.filter(
        related_module=str(table_name).upper(),
        related_record_id=int(record_id),
        document_type="auditor_finding",
    ).order_by("-uploaded_at", "-document_id_PK").first()
    return _audit_evidence_filename(getattr(archive, "file_path", "")) if archive else ""


def _get_auditor_verification_remarks(table_name, record_id):
    entity_type = PAYMENT_ENTITY_TYPE_LABELS.get(str(table_name).lower(), str(table_name).title())
    report = AuditFindingsReport.objects.filter(
        report_title=f"Auditor findings: {entity_type} #{record_id}",
    ).order_by("-prepared_date", "-audit_report_id_PK").first()
    remarks = getattr(report, "findings_summary", "") or ""
    if remarks.strip():
        return remarks.strip()
    return "Auditor verified and forwarded to President for final executive sign-off."


def _get_auditor_verification(table_name: str, record_id: int):
    return TransactionVerification.objects.filter(
        table_name=str(table_name).lower(),
        record_id=int(record_id),
    ).order_by("-verified_at").first()


def _serialize_value(value):
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    if hasattr(value, "__float__"):
        return str(value)
    if isinstance(value, str):
        stripped = value.strip()
        return stripped if stripped else None
    if hasattr(value, "_meta"):
        data = {"id": value.pk}
        if hasattr(value, "full_name"):
            data["name"] = value.full_name
        return data
    if isinstance(value, dict):
        return {k: _serialize_value(v) for k, v in value.items()}
    return value


def _serialize_for_audit(data):
    if not isinstance(data, dict):
        return None
    result = {}
    for key, value in data.items():
        result[key] = _serialize_value(value)
    return result


def _compute_entry_hash(
    previous_hash, table, record_id, action, old_str, new_str, timestamp_str
):
    chain_str = f"{previous_hash}:{table}:{record_id}:{action}:{old_str}:{new_str}:{timestamp_str}"
    entry_hash = hashlib.sha256(chain_str.encode()).hexdigest()
    hmac_sig = hmac.new(
        settings.SECRET_KEY.encode(),
        entry_hash.encode(),
        hashlib.sha256,
    ).hexdigest()
    return entry_hash, hmac_sig


def _record_audit_trail(
    table,
    record_id,
    action,
    actor,
    old=None,
    new=None,
    ip=None,
    device_info=None,
    notes=None,
    actor_type_override=None,
    actor_name_override=None,
):
    actor_id = None
    actor_name = ""
    actor_type = ""
    if actor is not None:
        actor_id = getattr(actor, "user_id_PK", None)
        actor_name = actor_name_override or getattr(actor, "full_name", "") or str(actor)
        actor_type = actor_type_override or getattr(actor, "role", "") or ""

    latest = GlobalAuditTrail.objects.order_by("-trail_id").first()
    previous_hash = latest.entry_hash if (latest and latest.entry_hash) else "0" * 64

    old_serialized = _serialize_for_audit(old)
    new_serialized = _serialize_for_audit(new)

    entry = GlobalAuditTrail.objects.create(
        table_name=table,
        record_id=int(record_id),
        action=action,
        old_values=old_serialized,
        new_values=new_serialized,
        actor_type=actor_type,
        actor_id=actor_id,
        actor_name=actor_name,
        ip_address=ip,
        device_info=device_info,
        notes=notes.strip() if isinstance(notes, str) else notes,
        previous_hash=previous_hash,
    )

    old_str = json.dumps(old_serialized, sort_keys=True) if old_serialized else ""
    new_str = json.dumps(new_serialized, sort_keys=True) if new_serialized else ""
    timestamp_str = entry.timestamp.isoformat()

    entry.entry_hash, entry.hmac_signature = _compute_entry_hash(
        previous_hash, table, record_id, action, old_str, new_str, timestamp_str
    )
    entry.save(update_fields=["entry_hash", "hmac_signature"])


def _record_bulk_audit_trail(entries, actor):
    """Bulk-create audit entries with hash-chain integrity.

    `entries` is a list of dicts, each with keys:
        table, record_id, action, [old], [new], [ip], [device_info], [notes]
    All entries share the same `actor`.
    Each entry is chained to the previous via `previous_hash`.
    """
    actor_id = None
    actor_name = ""
    actor_type = ""
    if actor is not None:
        actor_id = getattr(actor, "user_id_PK", None)
        actor_name = getattr(actor, "full_name", "") or str(actor)
        actor_type = getattr(actor, "role", "") or ""

    latest = GlobalAuditTrail.objects.order_by("-trail_id").first()
    prev_hash = latest.entry_hash if (latest and latest.entry_hash) else "0" * 64

    now = timezone.now()
    instances = []
    for e in entries:
        old_serialized = _serialize_for_audit(e.get("old"))
        new_serialized = _serialize_for_audit(e.get("new"))
        old_str = json.dumps(old_serialized, sort_keys=True) if old_serialized else ""
        new_str = json.dumps(new_serialized, sort_keys=True) if new_serialized else ""
        timestamp_str = now.isoformat()

        entry_hash, hmac_sig = _compute_entry_hash(
            prev_hash, e["table"], e["record_id"], e["action"],
            old_str, new_str, timestamp_str,
        )

        instances.append(GlobalAuditTrail(
            table_name=e["table"],
            record_id=int(e["record_id"]),
            action=e["action"],
            old_values=old_serialized,
            new_values=new_serialized,
            actor_type=actor_type,
            actor_id=actor_id,
            actor_name=actor_name,
            ip_address=e.get("ip"),
            device_info=e.get("device_info"),
            notes=e.get("notes", "").strip() if isinstance(e.get("notes"), str) else e.get("notes"),
            previous_hash=prev_hash,
            entry_hash=entry_hash,
            hmac_signature=hmac_sig,
        ))
        prev_hash = entry_hash

    GlobalAuditTrail.objects.bulk_create(instances)



def _log_sensitive_read(request, table_name, record_ids, description="", device_info=None):
    """Log read access to sensitive records.
    - SensitiveReadLog: one entry per record_id
    - GlobalAuditTrail: one summary entry with notes describing the bulk read.
    """
    officer = resolve_officer_from_session(request)
    actor_id = getattr(officer, "user_id_PK", None) if officer else None
    actor_name = getattr(officer, "full_name", "") if officer else ""
    actor_type = getattr(officer, "role", "") if officer else ""
    ip = request.META.get("REMOTE_ADDR")
    if device_info is None:
        device_info = request.META.get("HTTP_USER_AGENT", "")

    # SensitiveReadLog model only contains: table_name, record_id, reader_type, reader_id, device_info, read_at
    batch = [
        SensitiveReadLog(
            table_name=table_name,
            record_id=rid,
            reader_type=actor_type,
            reader_id=actor_id,
            device_info=device_info,
        )
        for rid in record_ids
    ]
    SensitiveReadLog.objects.bulk_create(batch)

    _record_audit_trail(
        table=table_name,
        record_id=0,
        action="READ",
        actor=officer,
        ip=ip,
        device_info=device_info,
        notes=f"{description} ({len(record_ids)} records)",
    )


def _payment_type_label(kind: str, obj: Any) -> str:
    if kind == "monthly_dues":
        method = str(getattr(obj, "payment_method", "") or "").strip()
        if method.lower() == "salary deduction":
            return "Salary Deduction"
    return "OTC Payment"


def _payment_item_to_json(kind: str, obj: Any) -> Dict[str, Any]:
    member = getattr(obj, "member_id_FK", None)
    amount = getattr(obj, "amount", None)
    payment_date = getattr(obj, "payment_date", None)
    payment_method = getattr(obj, "payment_status", None) if kind == "membership_fee" else getattr(obj, "payment_method", None)
    month_covered = getattr(obj, "month_covered", None)
    expected_amount = (
        get_membership_fee_amount()
        if kind == "membership_fee"
        else get_monthly_dues_amount()
    )

    return {
        "id": str(obj.fee_id_PK if kind == "membership_fee" else obj.dues_id_PK),
        "entity_id": int(obj.fee_id_PK if kind == "membership_fee" else obj.dues_id_PK),
        "source": kind,
        "source_label": PAYMENT_SOURCE_LABELS.get(kind, kind.replace("_", " ").title()),
        "payment_type": _payment_type_label(kind, obj),
        "type": "OTC Fee Payment" if kind == "membership_fee" else "Monthly Dues",
        "ref": (getattr(obj, "remittance_reference", None) or getattr(obj, "receipt_number", None) or "") if kind == "monthly_dues" else (getattr(obj, "receipt_number", None) or ""),
        "batch_reference": getattr(obj, "deduction_batch_reference", None) or "",
        "member": {
            "member_id": member.member_id_PK if member else None,
            "member_name": member.full_name if member else "",
            "employee_id": member.employee_id or "" if member else "",
            "department": member.department or "" if member else "",
            "position": member.position or "" if member else "",
            "contact": getattr(member, "contact_number", None) or "",
            "email": getattr(member, "email", None) or "",
            "membership_status": getattr(member, "membership_status", None) or "",
        },
        "amount": str(amount) if amount is not None else "0",
        "expected": str(expected_amount),
        "month": month_covered or "N/A",
        "date": str(payment_date) if payment_date is not None else "",
        "method": str(payment_method) if payment_method is not None else "",
        "encoded_by": getattr(getattr(obj, "recorded_by_user_id_FK", None), "full_name", "") or "",
        "payment_status": getattr(obj, "payment_status", None) or "",
    }


def _finance_item_label(table_name: str, record=None) -> str:
    """Human-readable label used in member notifications/emails."""
    labels = {
        "membership_fee": "Membership Fee",
        "monthly_dues": "Monthly Dues",
        "medical_aid": "Medical Aid Claim",
        "death_aid": "Death Aid Claim",
    }
    label = labels.get(str(table_name).lower(), str(table_name).replace("_", " ").title())
    if str(table_name).lower() == "monthly_dues" and record is not None:
        month = getattr(record, "month_covered", "") or ""
        if month:
            label = f"Monthly Dues ({month})"
    return label


def _status_field_updates(table_name: str, is_rejected: bool = False) -> Dict[str, str]:
    """Map a finance table to the model status fields to update when returned/rejected."""
    tn = str(table_name).lower()
    returned = "Rejected" if is_rejected else Status.RETURNED_REVISION
    if tn == "membership_fee":
        return {"payment_status": "Returned" if not is_rejected else "Rejected"}
    if tn == "monthly_dues":
        return {
            "treasurer_status": Status.RETURNED_REVISION,
            "payment_status": "Returned" if not is_rejected else "Rejected",
        }
    if tn in ("medical_aid", "death_aid"):
        return {"status": returned}
    return {}


def _apply_status_updates(record, table_name: str, extra_updates: Optional[Dict[str, Any]] = None) -> None:
    updates = _status_field_updates(table_name)
    if extra_updates:
        updates.update(extra_updates)
    if not updates or record is None:
        return
    applied = []
    for field, value in updates.items():
        if hasattr(record, field):
            setattr(record, field, value)
            applied.append(field)
    if applied:
        record.save(update_fields=applied)


def _upsert_returned_tv(table_name: str, record_id: int, remarks: str = "", tv_status: str = Status.RETURNED_REVISION) -> TransactionVerification:
    """Canonical get_or_create upsert of the returned/rejected TransactionVerification row.

    Always writes the row (fixes the bug where an absent TV row silently skipped the
    reject) and uses the lowercase canonical table name.
    """
    table_name = str(table_name).lower()
    tv, created = TransactionVerification.objects.get_or_create(
        table_name=table_name,
        record_id=int(record_id),
        defaults={
            "verification_status": tv_status,
            "returned_reason": remarks or "",
            "return_count": 1,
        },
    )
    if not created:
        tv.verification_status = tv_status
        tv.returned_reason = remarks or tv.returned_reason
        tv.return_count = (tv.return_count or 0) + 1
        tv.save(update_fields=["verification_status", "returned_reason", "return_count"])
    return tv


def _notify_finance_status(member, table_name: str, record, remarks: str = "", is_rejected: bool = False, details: str = "", officer=None) -> None:
    """Single entry point: create the member Notification and send the returned/rejected email."""
    from core_system.services.email_service import send_member_finance_status_email

    if not member:
        return
    try:
        receipt_number = ""
        if record is not None:
            receipt_number = getattr(record, "receipt_number", "") or getattr(record, "reference_number", "") or ""
        send_member_finance_status_email(
            member,
            item_label=_finance_item_label(table_name, record),
            details=details,
            remarks=remarks,
            is_rejected=is_rejected,
            sender_name=officer.full_name if officer else "",
            sender_role=(officer.role or "") if officer else "",
            receipt_number=str(receipt_number),
        )
    except Exception:
        logging.getLogger(__name__).exception("Failed to notify member for returned finance item")


def set_treasurer_rejected(
    table_name: str,
    record_id: int,
    officer,
    remarks: str = "",
    request=None,
    *,
    member=None,
    details: str = "",
    is_rejected: bool = False,
    extra_updates: Optional[Dict[str, Any]] = None,
    tv_updates: Optional[Dict[str, Any]] = None,
) -> Optional[TransactionVerification]:
    """Treasurer rejects/returns a finance item.

    Always writes the TransactionVerification row (get_or_create) with the lowercase
    canonical table name, updates the model status fields, records the audit trail,
    and notifies the member (in-app notification + email).
    """
    table_name = str(table_name).lower()
    model = MODEL_MAP.get(table_name)
    record = model.objects.filter(pk=int(record_id)).first() if model else None
    member = member or (getattr(record, "member_id_FK", None) if record else None)

    tv_status = Status.REJECTED if is_rejected else Status.RETURNED_REVISION
    if record is not None:
        _apply_status_updates(record, table_name, extra_updates)

    tv = _upsert_returned_tv(table_name, int(record_id), remarks, tv_status)
    if tv_updates:
        for field, value in tv_updates.items():
            if hasattr(tv, field):
                setattr(tv, field, value)
        tv.save()

    _record_audit_trail(
        table=table_name,
        record_id=int(record_id),
        action="REJECTED" if is_rejected else "RETURNED",
        actor=officer,
        new={"verification_status": tv_status, "returned_reason": remarks or ""},
        ip=request.META.get("REMOTE_ADDR") if request else None,
        notes=remarks or None,
    )

    _notify_finance_status(member, table_name, record, remarks, is_rejected=is_rejected, details=details, officer=officer)
    return tv


def route_back_to_treasurer(
    table_name: str,
    record_id: int,
    officer,
    remarks: str = "",
    request=None,
    *,
    member=None,
    details: str = "",
    force_returned: bool = True,
    extra_updates: Optional[Dict[str, Any]] = None,
    tv_updates: Optional[Dict[str, Any]] = None,
) -> Optional[TransactionVerification]:
    """Route a rejected/returned finance item back into the Treasurer queue.

    Used by downstream officers (President/Auditor) so their rejection cascades back
    to the Treasurer instead of stranding the record. Force-sets the model status to
    'Returned for Revision' by default (non-terminal), upserts the canonical lowercase
    TransactionVerification row, records the audit trail, and notifies the member.
    """
    table_name = str(table_name).lower()
    model = MODEL_MAP.get(table_name)
    record = model.objects.filter(pk=int(record_id)).first() if model else None
    member = member or (getattr(record, "member_id_FK", None) if record else None)

    if force_returned and record is not None:
        _apply_status_updates(record, table_name, extra_updates)

    tv = _upsert_returned_tv(table_name, int(record_id), remarks, Status.RETURNED_REVISION)
    if tv_updates:
        for field, value in tv_updates.items():
            if hasattr(tv, field):
                setattr(tv, field, value)
        tv.save()

    _record_audit_trail(
        table=table_name,
        record_id=int(record_id),
        action="RETURNED",
        actor=officer,
        new={"verification_status": Status.RETURNED_REVISION, "returned_reason": remarks or ""},
        ip=request.META.get("REMOTE_ADDR") if request else None,
        notes=remarks or None,
    )

    _notify_finance_status(member, table_name, record, remarks, is_rejected=False, details=details, officer=officer)
    return tv


def _officer_to_json(officer):
    # Safely get department info - OfficerUser may not have department field
    department = None
    try:
        if hasattr(officer, 'department_id_FK'):
            department = officer.department_id_FK
    except:
        pass
    
    return {
        "id": officer.user_id_PK,
        "full_name": officer.full_name,
        "username": officer.username,
        "email": getattr(officer, "email", "") or "",
        "role": officer.role,
        "account_status": officer.account_status,
        "term_start": officer.term_start.isoformat() if officer.term_start else "",
        "term_end": officer.term_end.isoformat() if officer.term_end else "",
        "department_id": department.department_id_PK if department else None,
        "department_name": department.name if department else "",
        "department_code": department.code if department else "",
        "mfa_enabled": bool(officer.mfa_enabled),
        "created_at": officer.created_at.isoformat() if officer.created_at else "",
        "updated_at": officer.updated_at.isoformat() if officer.updated_at else "",
    }


def archive_transaction(table_name, pk, officer=None):
    model = MODEL_MAP.get(table_name)
    if not model:
        return None

    record = model.objects.filter(pk=pk).first()
    if not record:
        return None

    member = getattr(record, "member_id_FK", None)
    member_name = getattr(member, "full_name", "") if member else ""
    member_id = getattr(member, "member_id_PK", None) if member else None

    amount = 0.0
    validated_amount = None
    payment_method = getattr(record, "payment_method", None)
    status = getattr(record, "status", None) or getattr(
        record, "payment_status", "Approved"
    )
    release_reference = getattr(record, "release_reference", None)
    released_by = getattr(record, "released_by_user_id_FK", None)
    verified_at = getattr(record, "request_date", None) or getattr(
        record, "payment_date", None
    )

    if table_name == "membership_fee":
        amount = float(getattr(record, "amount", 0) or 0)
    elif table_name == "monthly_dues":
        amount = float(getattr(record, "amount", 0) or 0)
    elif table_name == "medical_aid":
        amount = float(getattr(record, "validated_aid_amount", 0) or 0)
        validated_amount = amount
    elif table_name == "death_aid":
        amount = float(getattr(record, "benefit_amount", 0) or 0)
        validated_amount = amount
    elif table_name == "payroll_batch":
        amount = float(getattr(record, "total_amount", 0) or 0)
    elif table_name == "contribution":
        amount = float(getattr(record, "paid_amount", 0) or 0)
        verified_at = getattr(record, "payment_date", None)

    return TransactionArchive.objects.create(
        transaction_type=table_name,
        record_id=record.pk,
        member_id_FK_id=member_id,
        member_name=member_name,
        amount=amount,
        validated_amount=validated_amount,
        status=status,
        payment_method=payment_method,
        release_reference=release_reference,
        released_by_user_id_FK=released_by,
        verified_at=verified_at,
        archived_by_user_id_FK=officer,
    )


def _broadcast_to_group(group_name: str, message: dict) -> None:
    try:
        async_to_sync(get_channel_layer().group_send)(
            group_name,
            message,
        )
    except Exception:
        pass


def _broadcast_pending_counts(target_groups: Optional[list[str]] = None) -> None:
    from core_system.models import MemberRegistrationRequest, TransactionVerification
    from core_system.constants.status_constants import RegistrationStatus

    cache.delete_many(["auditor_pending_count", "president_pending_count"])

    auditor_pending = TransactionVerification.objects.filter(
        verification_status=Status.PENDING,
        auditor_id_FK__isnull=True,
    ).count()
    cache.set("auditor_pending_count", auditor_pending, 30)

    president_pending = TransactionVerification.objects.filter(
        verification_status=Status.AUDITOR_VERIFIED,
        president_id_FK__isnull=True,
    ).count()
    cache.set("president_pending_count", president_pending, 30)

    auditor_reg_count = MemberRegistrationRequest.objects.filter(
        status=RegistrationStatus.TREASURER_VERIFIED
    ).count()
    president_reg_count = MemberRegistrationRequest.objects.filter(
        status=RegistrationStatus.AUDITOR_VERIFIED
    ).count()
    treasurer_reg_count = MemberRegistrationRequest.objects.filter(
        status=RegistrationStatus.PENDING_TREASURER_REVIEW
    ).count()

    # --- Financial pending counts ---
    from core_system.models import MembershipFee, MedicalAid, DeathAid
    treasurer_mf_count = MembershipFee.objects.filter(payment_status="Pending").count()
    treasurer_ma_count = MedicalAid.objects.filter(status__in=["Pending", "Pending Treasurer Review"]).count()
    treasurer_da_count = DeathAid.objects.filter(status__in=["Pending", "Pending Treasurer Review"]).count()

    auditor_mf_count = TransactionVerification.objects.filter(
        verification_status=Status.PENDING, auditor_id_FK__isnull=True,
    ).count()

    if target_groups is None or "auditor_dashboard" in target_groups:
        _broadcast_to_group("auditor_dashboard", {
            "type": "data_changed",
            "section": "registration",
            "pending_count": auditor_reg_count,
        })
        _broadcast_to_group("auditor_dashboard", {
            "type": "data_changed",
            "section": "financial",
            "pending_count": auditor_pending,
            "membership_fees": auditor_mf_count,
        })
        _broadcast_to_group("auditor_dashboard", {
            "type": "notification_summary",
            "pending_count": auditor_pending,
            "message": f"You have {auditor_pending} pending item(s) for review.",
        })

    if target_groups is None or "president_dashboard" in target_groups:
        _broadcast_to_group("president_dashboard", {
            "type": "data_changed",
            "section": "registration",
            "pending_count": president_reg_count,
        })
        _broadcast_to_group("president_dashboard", {
            "type": "notification_summary",
            "pending_count": president_pending,
            "message": f"You have {president_pending} pending item(s) awaiting signature.",
        })

    if target_groups is None or "treasurer_dashboard" in target_groups:
        _broadcast_to_group("treasurer_dashboard", {
            "type": "data_changed",
            "section": "registration",
            "pending_count": treasurer_reg_count,
        })
        _broadcast_to_group("treasurer_dashboard", {
            "type": "data_changed",
            "section": "financial",
            "membership_fees": treasurer_mf_count,
            "medical_aid": treasurer_ma_count,
            "death_aid": treasurer_da_count,
            "registration": treasurer_reg_count,
        })
        _broadcast_to_group("treasurer_dashboard", {
            "type": "notification_summary",
            "pending_count": 0,
            "message": "",
        })

    try:
        _send_push_notifications(auditor_pending, president_pending)
    except Exception:
        pass


def _push_abs_url(path: str) -> str:
    """Resolve a push payload path against the production BASE_URL so devices
    subscribed under an old ngrok tunnel still hit the real domain."""
    if not path:
        return settings.BASE_URL.rstrip("/") + "/"
    if "://" in path:
        return path
    return settings.BASE_URL.rstrip("/") + "/" + path.lstrip("/")


def _send_push_notifications(auditor_pending: int, president_pending: int) -> None:
    from core_system.models import PushSubscription, OfficerUser
    from pywebpush import webpush
    import logging

    logger = logging.getLogger(__name__)

    vapid_private_key = settings.VAPID_PRIVATE_KEY
    vapid_public_key = settings.VAPID_PUBLIC_KEY

    auditor_officers = OfficerUser.objects.filter(role="Auditor").values_list("user_id_PK", flat=True)
    if auditor_pending > 0 and auditor_officers:
        auditor_subs = PushSubscription.objects.filter(officer_id_FK__in=list(auditor_officers))
        payload = json.dumps({
            "title": "Pending Reviews",
            "body": f"You have {auditor_pending} item(s) awaiting review.",
            "url": _push_abs_url("/auditor/"),
        })
        for sub in auditor_subs:
            try:
                webpush(
                    subscription_info={
                        "endpoint": sub.endpoint,
                        "keys": {"p256dh": sub.p256dh_key, "auth": sub.auth_key},
                    },
                    data=payload,
                    vapid_private_key=vapid_private_key,
                    vapid_claims={
                        "sub": "mailto:admin@caufa.local",
                    },
                )
            except Exception as exc:
                logger.warning("Push notification failed for auditor subscription %s: %s", sub.pk, exc)

    president_officers = OfficerUser.objects.filter(role="President").values_list("user_id_PK", flat=True)
    if president_pending > 0 and president_officers:
        president_subs = PushSubscription.objects.filter(officer_id_FK__in=list(president_officers))
        payload = json.dumps({
            "title": "Pending Signatures",
            "body": f"You have {president_pending} item(s) awaiting your signature.",
            "url": _push_abs_url("/president/"),
        })
        for sub in president_subs:
            try:
                webpush(
                    subscription_info={
                        "endpoint": sub.endpoint,
                        "keys": {"p256dh": sub.p256dh_key, "auth": sub.auth_key},
                    },
                    data=payload,
                    vapid_private_key=vapid_private_key,
                    vapid_claims={
                        "sub": "mailto:admin@caufa.local",
                    },
                )
            except Exception as exc:
                logger.warning("Push notification failed for president subscription %s: %s", sub.pk, exc)


def _notify_release(post, officer, request=None):
    from core_system.models import PushSubscription, OfficerUser
    from core_system.services.email_service import send_html_email
    from pywebpush import webpush

    archive = getattr(post, "archive_id_FK", None)
    member_name = archive.member_name if archive else "Unknown"
    aid_label = "Medical Aid" if post.aid_type == "medical_aid" else "Death Aid"

    total = Contribution.objects.filter(aid_tracking_post_id_FK=post).count()
    paid = Contribution.objects.filter(
        aid_tracking_post_id_FK=post, status__in=["PAID", "RECORDED"],
    ).count()
    skipped = Contribution.objects.filter(
        aid_tracking_post_id_FK=post, status="SKIPPED",
    ).count()
    ip = request.META.get("REMOTE_ADDR") if request else None

    summary = (
        f"Release completed \u2014 {aid_label} for {member_name}. "
        f"\u20b1{post.total_collected} collected | {paid}/{total} members paid"
    )

    _record_audit_trail(
        table="AID_TRACKING_POST",
        record_id=post.post_id_PK,
        action="RELEASE_NOTIFIED",
        actor=officer,
        new={
            "total_collected": float(post.total_collected),
            "total_members": total,
            "paid_count": paid,
            "skipped_count": skipped,
        },
        ip=ip,
        notes=f"Release completed \u2014 {aid_label} for {member_name}. \u20b1{post.total_collected} from {paid}/{total} members. Released by {officer.full_name}",
    )

    _broadcast_to_group("auditor_dashboard", {
        "type": "release_notification",
        "post_id": post.post_id_PK,
        "member_name": member_name,
        "aid_label": aid_label,
        "total_collected": float(post.total_collected),
        "paid_count": paid,
        "total_count": total,
        "released_by": officer.full_name,
    })
    _broadcast_to_group("president_dashboard", {
        "type": "release_notification",
        "post_id": post.post_id_PK,
        "member_name": member_name,
        "aid_label": aid_label,
        "total_collected": float(post.total_collected),
        "paid_count": paid,
        "total_count": total,
        "released_by": officer.full_name,
    })

    try:
        for role_name in ("Auditor", "President"):
            officer_ids = OfficerUser.objects.filter(role=role_name).values_list("user_id_PK", flat=True)
            subs = PushSubscription.objects.filter(officer_id_FK__in=list(officer_ids))
            if not subs:
                continue
            payload = json.dumps({
                "title": f"Release: {member_name[:20]}\u2019s {aid_label.split()[0]} Aid",
                "body": f"\u20b1{post.total_collected} from {paid}/{total} members",
                "url": _push_abs_url(f"/{role_name.lower()}/"),
            })
            for sub in subs:
                try:
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
                    )
                except Exception:
                    pass
    except Exception:
        pass

    try:
        for role_name in ("Auditor", "President"):
            officers = OfficerUser.objects.filter(role=role_name)
            recipient_emails = [o.email for o in officers if o.email]
            if not recipient_emails:
                continue
            send_html_email(
                subject=f"Release Completed \u2014 {aid_label} for {member_name}",
                recipient_list=recipient_emails,
                html_template="emails/release_notification.html",
                context={
                    "aid_type": aid_label,
                    "member_name": member_name,
                    "total_collected": f"{post.total_collected:,.2f}",
                    "paid_count": paid,
                    "total_count": total,
                    "skipped_count": skipped,
                    "released_by": officer.full_name,
                    "released_at": timezone.now().strftime("%Y-%m-%d %H:%M"),
                },
            )
    except Exception:
        pass
