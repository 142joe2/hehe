from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PolicyAmounts:
    membership_fee: float = 100.00
    monthly_dues: float = 50.00
    accidental_sickness_aid_threshold: float = 20000.00
    accidental_sickness_aid_benefit: float = 100.00
    death_aid_member: float = 500.00
    death_aid_spouse: float = 300.00
    death_aid_parent_child: float = 250.00
    death_aid_full_blood_sibling: float = 100.00


POLICY = PolicyAmounts()

_POLICY_OVERRIDE_PREFIX = "policy."
_POLICY_CONSTANT_KEYS = [
    ("membership_fee", "Membership Fee (₱)", "float"),
    ("monthly_dues", "Monthly Dues (₱)", "float"),
    ("accidental_sickness_aid_threshold", "Accidental/Sickness Aid Threshold (₱)", "float"),
    ("accidental_sickness_aid_benefit", "Accidental/Sickness Aid Benefit (₱)", "float"),
    ("death_aid_member", "Death Aid — Member (₱)", "float"),
    ("death_aid_spouse", "Death Aid — Spouse (₱)", "float"),
    ("death_aid_parent_child", "Death Aid — Parent/Child (₱)", "float"),
    ("death_aid_full_blood_sibling", "Death Aid — Full-Blood Sibling (₱)", "float"),
]


def _get_setting_override(key: str) -> str | None:
    from django.conf import settings as django_settings
    from core_system.models import SystemSetting
    if "core_system" not in django_settings.INSTALLED_APPS:
        return None
    try:
        row = SystemSetting.objects.filter(setting_key=f"{_POLICY_OVERRIDE_PREFIX}{key}").first()
        return row.setting_value if row else None
    except Exception:
        return None


def _get_float(key: str, default: float) -> float:
    raw = _get_setting_override(key)
    if raw is None:
        return default
    try:
        return float(raw)
    except (TypeError, ValueError):
        return default


def get_membership_fee_amount() -> float:
    return _get_float("membership_fee", POLICY.membership_fee)


def get_monthly_dues_amount() -> float:
    return _get_float("monthly_dues", POLICY.monthly_dues)


def get_accidental_sickness_aid_threshold() -> float:
    return _get_float("accidental_sickness_aid_threshold", POLICY.accidental_sickness_aid_threshold)


def get_accidental_sickness_aid_benefit() -> float:
    return _get_float("accidental_sickness_aid_benefit", POLICY.accidental_sickness_aid_benefit)


def get_death_aid_amount(relationship: str) -> float:
    if not relationship:
        return 0.0
    normalized = relationship.strip().lower()
    amount_map = {
        "member": _get_float("death_aid_member", POLICY.death_aid_member),
        "self": _get_float("death_aid_member", POLICY.death_aid_member),
        "spouse": _get_float("death_aid_spouse", POLICY.death_aid_spouse),
        "husband": _get_float("death_aid_spouse", POLICY.death_aid_spouse),
        "wife": _get_float("death_aid_spouse", POLICY.death_aid_spouse),
        "parent": _get_float("death_aid_parent_child", POLICY.death_aid_parent_child),
        "child": _get_float("death_aid_parent_child", POLICY.death_aid_parent_child),
        "father": _get_float("death_aid_parent_child", POLICY.death_aid_parent_child),
        "mother": _get_float("death_aid_parent_child", POLICY.death_aid_parent_child),
        "son": _get_float("death_aid_parent_child", POLICY.death_aid_parent_child),
        "daughter": _get_float("death_aid_parent_child", POLICY.death_aid_parent_child),
        "full-blood brother": _get_float("death_aid_full_blood_sibling", POLICY.death_aid_full_blood_sibling),
        "full-blood sister": _get_float("death_aid_full_blood_sibling", POLICY.death_aid_full_blood_sibling),
        "full blood brother": _get_float("death_aid_full_blood_sibling", POLICY.death_aid_full_blood_sibling),
        "full blood sister": _get_float("death_aid_full_blood_sibling", POLICY.death_aid_full_blood_sibling),
        "full blood sibling": _get_float("death_aid_full_blood_sibling", POLICY.death_aid_full_blood_sibling),
        "brother": _get_float("death_aid_full_blood_sibling", POLICY.death_aid_full_blood_sibling),
        "sister": _get_float("death_aid_full_blood_sibling", POLICY.death_aid_full_blood_sibling),
        "sibling": _get_float("death_aid_full_blood_sibling", POLICY.death_aid_full_blood_sibling),
    }
    return amount_map.get(normalized, 0.0)


DEATH_AID_RELATIONSHIP_MAP = {
    "member": "immediate",
    "self": "immediate",
    "spouse": "immediate",
    "husband": "immediate",
    "wife": "immediate",
    "parent": "immediate",
    "child": "immediate",
    "father": "immediate",
    "mother": "immediate",
    "son": "immediate",
    "daughter": "immediate",
    "full-blood brother": "extended",
    "full-blood sister": "extended",
    "full blood brother": "extended",
    "full blood sister": "extended",
    "full blood sibling": "extended",
    "brother": "extended",
    "sister": "extended",
    "sibling": "extended",
}


def is_retired_member(member) -> bool:
    status = (getattr(member, "membership_status", None) or "").strip()
    return status.casefold() == "retired"


def is_exempt_from_dues_and_aid(member) -> bool:
    return is_retired_member(member)


def get_expected_dues_amount() -> float:
    return get_monthly_dues_amount()


def get_contribution_amount_for_aid(aid_type: str, relationship: str = "") -> float:
    if aid_type == "death_aid":
        return get_death_aid_amount(relationship)
    return get_accidental_sickness_aid_benefit()


def get_medical_aid_contribution_amount() -> float:
    return get_accidental_sickness_aid_benefit()


def check_medical_aid_once_per_year(member, year: int) -> str | None:
    from core_system.models import MedicalAid
    if MedicalAid.objects.filter(member_id_FK=member, claim_year=year).exclude(status__in=["Rejected", "Returned"]).exists():
        return (
            f"Member already has a Medical Aid record for {year}. "
            "Per ARTICLE XI Section 1.b, accidental/sickness aid is limited to once a year."
        )
    return None
