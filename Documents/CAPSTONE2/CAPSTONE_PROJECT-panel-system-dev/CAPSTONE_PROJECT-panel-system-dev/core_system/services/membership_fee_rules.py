from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from django.contrib.contenttypes.models import ContentType

from core_system.models import (
    FinancialDocumentArchive,
    Member,
    MembershipFee,
    OfficerUser,
    TransactionVerification,
)
from core_system.shared_view_utils import _record_audit_trail


# ==========================================================================
# POLICY — membership_fee_policy.py merged here
# ==========================================================================

@dataclass(frozen=True)
class MembershipFeePolicyResult:
    required_to_pay: bool
    exception_reason: str | None = None


def check_membership_fee_requirement(member: Member) -> MembershipFeePolicyResult:
    status = (getattr(member, "membership_status", None) or "").strip()

    if status.casefold() == "retired":
        return MembershipFeePolicyResult(
            required_to_pay=False,
            exception_reason="Exempt per ARTICLE XI Section 2 (Retired members are not required to pay).",
        )

    if status in ("Permanent", "Temporary"):
        return MembershipFeePolicyResult(required_to_pay=True)

    reason = f"Membership fee not required for membership_status='{status}'"
    return MembershipFeePolicyResult(required_to_pay=False, exception_reason=reason)


def is_member_in_good_standing(member: Member) -> bool:
    status = (getattr(member, "membership_status", None) or "").strip()
    return status.casefold() != "retired" and status in ("Permanent", "Temporary")


# ==========================================================================
# VALIDATION — membership_fee_validation.py merged here
# ==========================================================================

@dataclass(frozen=True)
class ValidationResult:
    valid: bool
    errors: list[str] = field(default_factory=list)
    normalized: dict[str, Any] = field(default_factory=dict)


def validate_membership_fee_payment(*, payload: dict[str, Any]) -> ValidationResult:
    errors: list[str] = []

    fee_status = (payload.get("fee_status") or "").strip()
    fee_ref = (payload.get("fee_ref") or "").strip()

    fee_amount = payload.get("fee_amount")
    fee_partial_amount = payload.get("fee_partial_amount")

    normalized: dict[str, Any] = {}

    if not fee_ref:
        errors.append("Receipt / Reference Number is required.")

    def _to_float(value: Any) -> float | None:
        if value is None:
            return None
        s = str(value).strip()
        if not s:
            return None
        try:
            return float(s)
        except Exception:
            return None

    if fee_status not in ("", "Full Payment", "Partial"):
        errors.append("Payment status must be Full Payment or Partial.")

    if fee_status == "Partial":
        partial = _to_float(fee_partial_amount)
        if partial is None:
            errors.append("Partial Payment Amount is required when status is Partial.")
        else:
            if partial <= 0:
                errors.append("Partial Payment Amount must be greater than 0.")
            normalized["fee_amount"] = partial

    else:
        amt = _to_float(fee_amount)
        if amt is None:
            errors.append("Amount Paid is required.")
        else:
            if amt <= 0:
                errors.append("Amount Paid must be greater than 0.")
            normalized["fee_amount"] = amt

    if errors:
        return ValidationResult(valid=False, errors=errors, normalized=normalized)

    return ValidationResult(valid=True, errors=[], normalized=normalized)


# ==========================================================================
# RULES — membership_fee_rules.py content (duplicate check)
# ==========================================================================

@dataclass(frozen=True)
class MembershipFeeDuplicateCheckResult:
    is_duplicate: bool
    existing_fee_id: int | None = None


def has_duplicate_membership_fee(
    *,
    member: Member,
    receipt_number: str,
) -> MembershipFeeDuplicateCheckResult:
    rcpt = (receipt_number or "").strip()
    if not rcpt:
        return MembershipFeeDuplicateCheckResult(is_duplicate=False, existing_fee_id=None)

    existing = (
        MembershipFee.objects.filter(member_id_FK=member, receipt_number=rcpt)
        .only("fee_id_PK")
        .first()
    )

    if not existing:
        return MembershipFeeDuplicateCheckResult(is_duplicate=False, existing_fee_id=None)

    return MembershipFeeDuplicateCheckResult(
        is_duplicate=True,
        existing_fee_id=int(existing.fee_id_PK),
    )


# ==========================================================================
# CORRECTION — membership_fee_correction_service.py merged here
# ==========================================================================

@dataclass(frozen=True)
class MembershipFeeCorrectionContext:
    fee: MembershipFee
    officer: OfficerUser
    validation_errors: list[str]


def create_correction_artifacts_for_membership_fee(
    *,
    fee: MembershipFee,
    officer: OfficerUser,
    validation_errors: list[str],
    request,
) -> None:
    TransactionVerification.objects.filter(
        table_name="membership_fee",
        record_id=fee.fee_id_PK,
    ).update(
        verification_status="Returned for Revision",
    )

    snapshot: dict[str, Any] = {
        "fee_id": fee.fee_id_PK,
        "member_id_FK": fee.member_id_FK_id,
        "receipt_number": fee.receipt_number,
        "amount": str(fee.amount),
        "payment_date": str(fee.payment_date),
        "payment_method": fee.payment_method,
        "payment_status": fee.payment_status,
        "deposit_reference": fee.deposit_reference,
    }

    archive = FinancialDocumentArchive.objects.create(
        related_module="MEMBERSHIP_FEE",
        related_record_id=fee.fee_id_PK,
        document_type="treasurer_validation_correction",
        file_path="",
        file_hash="",
        verification_status="Returned for Revision",
        uploaded_by_user_id_FK=officer,
    )

    _record_audit_trail(
        table="membership_fee",
        record_id=fee.fee_id_PK,
        action="CORRECTION_REQUIRED",
        actor=officer,
        new=snapshot,
        ip=request.META.get("REMOTE_ADDR", "0.0.0.0"),
        notes="Payment requires correction: " + "; ".join(validation_errors),
    )


# ==========================================================================
# POLICY EXCEPTION — membership_fee_policy_exception_service.py merged here
# ==========================================================================

def record_membership_fee_policy_exception(*, member: Member, reason: str, officer: OfficerUser, request) -> None:
    archive = FinancialDocumentArchive.objects.create(
        related_module="MEMBERSHIP_FEE",
        related_record_id=member.member_id_PK,
        document_type="treasurer_policy_exception",
        file_path="",
        file_hash="",
        verification_status="Policy Exception",
        uploaded_by_user_id_FK=officer,
    )

    _record_audit_trail(
        table="membership_fee",
        record_id=member.member_id_PK,
        action="POLICY_EXCEPTION",
        actor=officer,
        ip=request.META.get("REMOTE_ADDR", "0.0.0.0"),
        notes=f"Membership fee policy exception: {reason}",
    )


