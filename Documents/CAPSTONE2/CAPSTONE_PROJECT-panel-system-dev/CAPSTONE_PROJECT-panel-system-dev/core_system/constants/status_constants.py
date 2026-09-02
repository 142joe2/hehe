from __future__ import annotations

from typing import Set


class Status:
    """Canonical status string constants — single source of truth."""

    # ── Individual canonical values ──
    PENDING             = "Pending"
    PENDING_VERIF       = "Pending Verification"
    PENDING_TRES_CHECK  = "Pending Treasurer Check"
    PENDING_AUDITOR_VERIFICATION = "Pending Auditor Verification"
    PENDING_TREASURER_REVIEW = "Pending Treasurer Review"
    PENDING_AUDITOR_REVIEW = "Pending Auditor Review"
    PENDING_PRESIDENT_APPROVAL = "Pending President Approval"
    AUDITOR_VERIFIED    = "Auditor Verified"
    RETURNED_REVISION   = "Returned for Revision"
    APPROVED            = "Approved"
    PRESIDENT_APPROVED  = "President Approved"
    REJECTED            = "Rejected"
    RELEASED            = "Released"
    COMPLETED           = "Completed"
    TREASURER_DIRECT    = "Treasurer Direct"  # Treasurer-created claims that go directly to Auditor

    # ── Query groups ──
    ALL_PENDING: Set[str] = {
        PENDING,
        PENDING_VERIF,
        PENDING_TRES_CHECK,
        PENDING_AUDITOR_VERIFICATION,
        PENDING_AUDITOR_REVIEW,
        PENDING_TREASURER_REVIEW,
        PENDING_PRESIDENT_APPROVAL,
        TREASURER_DIRECT,  # Include treasurer-created claims in pending list
    }

    ALL_AUDITOR_VERIFIED: Set[str] = {
        AUDITOR_VERIFIED, APPROVED, PRESIDENT_APPROVED, RELEASED, COMPLETED,
        # Writer statuses used by treasurer/president flows (C1):
        "Paid", "Full Payment", "Partial",
    }

    ALL_AUDITOR_ACTED: Set[str] = {AUDITOR_VERIFIED, RETURNED_REVISION}

    ALL_PRESIDENT_CAN_ACT: Set[str] = {
        PENDING, PENDING_VERIF, PENDING_TRES_CHECK,
        AUDITOR_VERIFIED, RETURNED_REVISION,
    }

    ALL_APPROVED: Set[str] = {APPROVED, PRESIDENT_APPROVED}

    ALL_FINAL: Set[str] = {APPROVED, REJECTED, RELEASED, PRESIDENT_APPROVED}


class RegistrationStatus:
    PENDING_TREASURER_REVIEW = "Pending Treasurer Review"
    RETURNED_FOR_REVISION = "Returned for Revision"
    TREASURER_VERIFIED = "Treasurer Verified"
    PENDING_AUDITOR_REVIEW = "Pending Auditor Review"
    AUDITOR_VERIFIED = "Auditor Verified"
    PENDING_PRESIDENT_APPROVAL = "Pending President Approval"
    PRESIDENT_APPROVED = "President Approved"
    REJECTED = "Rejected"


# ── Read-side helpers ──


def is_pending(status: str) -> bool:
    return status in Status.ALL_PENDING


def is_auditor_verified(status: str) -> bool:
    return status in Status.ALL_AUDITOR_VERIFIED


def is_auditor_acted(status: str) -> bool:
    return status in Status.ALL_AUDITOR_ACTED


def is_returned(status: str) -> bool:
    return status == Status.RETURNED_REVISION


def is_approved(status: str) -> bool:
    return status in Status.ALL_APPROVED


def is_rejected(status: str) -> bool:
    return status == Status.REJECTED


def is_released(status: str) -> bool:
    return status == Status.RELEASED


def can_president_act(status: str) -> bool:
    return status in Status.ALL_PRESIDENT_CAN_ACT
