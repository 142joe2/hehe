from __future__ import annotations

from typing import Optional

from django.utils import timezone

from core_system.constants.status_constants import Status
from core_system.models import (
    DeathAid,
    MedicalAid,
    MembershipFee,
    MonthlyDues,
    TransactionVerification,
)

MODEL_MAP = {
    "membership_fee": (MembershipFee, "fee_id_PK", "payment_status"),
    "monthly_dues": (MonthlyDues, "dues_id_PK", "payment_status"),
    "medical_aid": (MedicalAid, "medical_aid_id_PK", "status"),
    "death_aid": (DeathAid, "death_aid_id_PK", "status"),
}

TABLE_NAMES = set(MODEL_MAP)


def _write_model_status(table_name: str, record_id: int, status: str) -> None:
    info = MODEL_MAP.get(table_name)
    if info is None:
        return
    model_cls, pk_field, status_field = info
    model_cls.objects.filter(**{pk_field: record_id}).update(**{status_field: status})


def set_auditor_verified(
    table_name: str,
    record_id: int,
    officer,
    remarks: str = "",
) -> None:
    canonical = Status.AUDITOR_VERIFIED
    now = timezone.now()

    _write_model_status(table_name, record_id, canonical)

    TransactionVerification.objects.update_or_create(
        table_name=table_name,
        record_id=record_id,
        defaults={
            "verification_status": canonical,
            "auditor_id_FK": officer,
            "verified_at": now,
            "auditor_remarks": remarks or "",
        },
    )


def set_returned_for_revision(
    table_name: str,
    record_id: int,
    officer,
    remarks: str = "",
) -> None:
    canonical = Status.RETURNED_REVISION
    now = timezone.now()

    _write_model_status(table_name, record_id, canonical)

    tv, created = TransactionVerification.objects.update_or_create(
        table_name=table_name,
        record_id=record_id,
        defaults={
            "verification_status": canonical,
            "auditor_id_FK": officer,
            "verified_at": now,
            "auditor_remarks": remarks or "",
            "returned_by_auditor_id_FK": officer,
            "returned_reason": remarks or "",
        },
    )
    if not created:
        tv.return_count = (tv.return_count or 0) + 1
        tv.save(update_fields=["return_count"])


def set_president_decision(
    table_name: str,
    record_id: int,
    president,
    decision: str,
    remarks: str = "",
) -> None:
    if decision not in {Status.APPROVED, Status.REJECTED}:
        raise ValueError(f"Invalid president decision: {decision}")

    _write_model_status(table_name, record_id, decision)

    TransactionVerification.objects.update_or_create(
        table_name=table_name,
        record_id=record_id,
        defaults={
            "verification_status": decision,
            "president_id_FK": president,
            "approved_at": timezone.now(),
        },
    )


def set_pending(
    table_name: str,
    record_id: int,
    officer,
) -> None:
    canonical = Status.PENDING

    _write_model_status(table_name, record_id, canonical)

    TransactionVerification.objects.update_or_create(
        table_name=table_name,
        record_id=record_id,
        defaults={
            "verification_status": canonical,
            "auditor_id_FK": None,
            "auditor_remarks": "",
        },
    )


def hard_set(table_name: str, record_id: int, status: str) -> None:
    """Low-level utility: set model status to an arbitrary value without touching TV.
    Used for edge cases like backfill or release flows that bypass normal verification."""
    _write_model_status(table_name, record_id, status)
