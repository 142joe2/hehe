from django.forms.models import model_to_dict


def member_to_json(member):
    # Serializes fields required by the Treasurer dashboard frontend.
    return {
        "member_id": getattr(member, "member_id_PK", None),
        "full_name": member.full_name,
        "employee_id": member.employee_id or "",
        "officer_user_id": getattr(member, "officer_user_id_FK_id", None),
        "self_enrolled": bool(getattr(member, "officer_user_id_FK_id", None)),
        "department": member.department_id_FK.name if member.department_id_FK else (member.department or ""),
        "position": member.position or "",
        "contact_number": member.contact_number,
        "email": member.email,
        "employment_status": member.employment_status,
        "membership_status": member.membership_status,
        "member_type": member.member_type or member.employee_id,
        "date_joined": str(member.date_joined),
    }

