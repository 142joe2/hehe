import os

from django.conf import settings
from django.core.files.storage import default_storage
from django.http import HttpRequest, JsonResponse, HttpResponse
from django.shortcuts import get_object_or_404
from django.template.loader import render_to_string
from django.views.decorators.http import require_GET, require_POST
from django.utils import timezone

from core_system.guards import require_role, check_zero_trust
from core_system.models import OfficerUser, OrganizationFundReport, Member
from core_system.services.reporting import (
    generate_unified_report,
)
from core_system.services.email_service import send_html_email


# ==========================================================================
# TREASURER: Create / List / Download Fund Reports
# ==========================================================================

@require_GET
def treasurer_fund_reports_list(request: HttpRequest):
    guard = require_role(request, role="Treasurer")
    if guard is not None:
        return guard

    reports = OrganizationFundReport.objects.all().order_by("-created_at")
    data = []
    for r in reports:
        data.append({
            "report_id": r.report_id_PK,
            "period": r.report_period,
            "report_type": r.report_type,
            "status": r.report_status,
            "file_path": r.file_path,
            "prepared_by": r.prepared_by_user_id_FK.full_name if r.prepared_by_user_id_FK else "",
            "verified_by": r.auditor_verified_by_user_id_FK.full_name if r.auditor_verified_by_user_id_FK else "",
            "verified_at": r.auditor_verified_at.isoformat() if r.auditor_verified_at else "",
            "return_reason": r.return_reason or "",
            "approved_by": r.approved_by_user_id_FK.full_name if r.approved_by_user_id_FK else "",
            "approved_at": r.approved_at.isoformat() if r.approved_at else "",
            "created_at": r.created_at.isoformat(),
        })
    return JsonResponse({"ok": True, "reports": data})


@require_POST
def treasurer_create_fund_report(request: HttpRequest):
    guard = require_role(request, role="Treasurer")
    if guard is not None:
        return guard

    year = (request.POST.get("year") or "").strip()
    month = (request.POST.get("month") or "").strip()
    report_type = (request.POST.get("report_type") or "monthly").strip().lower()

    if not year or not month:
        return JsonResponse({"error": "year and month are required."}, status=400)
    if report_type not in ("weekly", "monthly"):
        return JsonResponse({"error": "report_type must be 'weekly' or 'monthly'."}, status=400)

    try:
        year_int = int(year)
        month_int = int(month)
    except (ValueError, TypeError):
        return JsonResponse({"error": "year and month must be valid numbers."}, status=400)

    officer_id = request.session.get("officer_id")
    try:
        officer = OfficerUser.objects.get(user_id_PK=int(officer_id))
    except OfficerUser.DoesNotExist:
        return JsonResponse({"error": "Officer not found."}, status=400)

    wb = generate_unified_report(year_int, month_int)
    period = f"{year_int}-{month_int:02d}"
    filename = f"unified_report_{report_type}_{period}.xlsx"
    file_path = f"reports/{filename}"

    default_storage_path = getattr(settings, "MEDIA_ROOT", "")
    full_path = os.path.join(str(default_storage_path), file_path) if default_storage_path else file_path
    os.makedirs(os.path.dirname(full_path), exist_ok=True)
    wb.save(full_path)

    report = OrganizationFundReport.objects.create(
        report_period=period,
        report_type=report_type,
        report_status="Draft",
        file_path=file_path,
        prepared_by_user_id_FK=officer,
    )

    return JsonResponse({
        "report_id": report.report_id_PK,
        "period": report.report_period,
        "report_type": report.report_type,
        "status": report.report_status,
        "file_path": report.file_path,
    })


@require_GET
def treasurer_download_fund_report(request: HttpRequest, report_id: int):
    guard = require_role(request, role="Treasurer")
    if guard is not None:
        return guard

    report = get_object_or_404(OrganizationFundReport, pk=report_id)
    if not report.file_path:
        return HttpResponse("Report file not found.", status=404)

    full_path = os.path.join(settings.MEDIA_ROOT, report.file_path)
    if not os.path.exists(full_path):
        return HttpResponse("Report file not found on disk.", status=404)

    with open(full_path, "rb") as f:
        data = f.read()

    filename = os.path.basename(report.file_path)
    response = HttpResponse(
        data,
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


@require_POST
def treasurer_submit_fund_report(request: HttpRequest, report_id: int):
    """Treasurer submits a Draft/Rejected report for Auditor verification (maker step)."""
    guard = require_role(request, role="Treasurer")
    if guard is not None:
        return guard

    report = get_object_or_404(OrganizationFundReport, pk=report_id)
    if report.report_status not in ("Draft", "Rejected"):
        return JsonResponse({"error": "Only Draft or Rejected reports can be submitted for audit."}, status=400)

    officer_id = request.session.get("officer_id")
    officer = None
    if officer_id:
        try:
            officer = OfficerUser.objects.get(user_id_PK=int(officer_id))
        except OfficerUser.DoesNotExist:
            return JsonResponse({"error": "Officer not found."}, status=400)

    old_status = report.report_status
    report.report_status = "Submitted"
    report.save(update_fields=["report_status", "updated_at"])

    try:
        from core_system.shared_view_utils import _record_audit_trail
        _record_audit_trail(
            table="organization_fund_report",
            record_id=report.report_id_PK,
            action="SUBMITTED_FOR_AUDIT",
            actor=officer,
            old={"report_status": old_status},
            new={"report_status": report.report_status},
            ip=request.META.get("REMOTE_ADDR"),
            notes=f"Fund report {report.report_period} submitted for audit",
        )
    except Exception:
        pass

    return JsonResponse({"ok": True, "status": report.report_status})


# ==========================================================================
# AUDITOR: Submit Fund Report for President Approval
# ==========================================================================

@require_GET
def auditor_fund_reports_list(request: HttpRequest):
    """Reports submitted by the Treasurer awaiting Auditor verification,
    plus verification history (Auditor Verified / Rejected / Approved)."""
    guard = require_role(request, role="Auditor")
    if guard is not None:
        return guard

    reports = OrganizationFundReport.objects.exclude(
        report_status="Draft"
    ).order_by("-created_at")
    data = []
    for r in reports:
        data.append({
            "report_id": r.report_id_PK,
            "period": r.report_period,
            "report_type": r.report_type,
            "status": r.report_status,
            "file_path": r.file_path,
            "prepared_by": r.prepared_by_user_id_FK.full_name if r.prepared_by_user_id_FK else "",
            "verified_by": r.auditor_verified_by_user_id_FK.full_name if r.auditor_verified_by_user_id_FK else "",
            "verified_at": r.auditor_verified_at.isoformat() if r.auditor_verified_at else "",
            "return_reason": r.return_reason or "",
            "approved_by": r.approved_by_user_id_FK.full_name if r.approved_by_user_id_FK else "",
            "approved_at": r.approved_at.isoformat() if r.approved_at else "",
            "created_at": r.created_at.isoformat(),
        })
    return JsonResponse({"ok": True, "reports": data})


@require_POST
def auditor_verify_fund_report(request: HttpRequest, report_id: int):
    """Auditor verifies a Treasurer-submitted report and forwards it to the
    President for final approval (mockup: Submitted -> Auditor Verified)."""
    guard = require_role(request, role="Auditor")
    if guard is not None:
        return guard
    guard = check_zero_trust(request, level="approve")
    if guard is not None:
        return guard

    officer_id = request.session.get("officer_id")
    officer = None
    if officer_id:
        try:
            officer = OfficerUser.objects.get(user_id_PK=int(officer_id))
        except OfficerUser.DoesNotExist:
            return JsonResponse({"error": "Officer not found."}, status=400)

    report = get_object_or_404(OrganizationFundReport, pk=report_id)
    if report.report_status != "Submitted":
        return JsonResponse({"error": "Only Submitted reports can be verified."}, status=400)

    old_status = report.report_status
    report.report_status = "Auditor Verified"
    report.auditor_verified_by_user_id_FK = officer
    report.auditor_verified_at = timezone.now()
    report.return_reason = ""
    report.save(update_fields=[
        "report_status", "auditor_verified_by_user_id_FK", "auditor_verified_at",
        "return_reason", "updated_at",
    ])

    try:
        from core_system.shared_view_utils import _record_audit_trail
        _record_audit_trail(
            table="organization_fund_report",
            record_id=report.report_id_PK,
            action="AUDITOR_VERIFIED",
            actor=officer,
            old={"report_status": old_status},
            new={"report_status": report.report_status},
            ip=request.META.get("REMOTE_ADDR"),
            notes=f"Fund report {report.report_period} verified by Auditor — forwarded to President",
        )
    except Exception:
        pass

    return JsonResponse({"ok": True, "status": report.report_status})


@require_POST
def auditor_return_fund_report(request: HttpRequest, report_id: int):
    """Auditor returns a Treasurer-submitted report for revision
    (mockup: Submitted -> Returned to Treasurer, reason required)."""
    guard = require_role(request, role="Auditor")
    if guard is not None:
        return guard
    guard = check_zero_trust(request, level="approve")
    if guard is not None:
        return guard

    officer_id = request.session.get("officer_id")
    officer = None
    if officer_id:
        try:
            officer = OfficerUser.objects.get(user_id_PK=int(officer_id))
        except OfficerUser.DoesNotExist:
            return JsonResponse({"error": "Officer not found."}, status=400)

    remarks = (request.POST.get("remarks") or "").strip()
    if not remarks:
        return JsonResponse({"error": "A return reason is required."}, status=400)

    report = get_object_or_404(OrganizationFundReport, pk=report_id)
    if report.report_status != "Submitted":
        return JsonResponse({"error": "Only Submitted reports can be returned."}, status=400)

    old_status = report.report_status
    report.report_status = "Rejected"
    report.return_reason = remarks
    report.save(update_fields=["report_status", "return_reason", "updated_at"])

    try:
        from core_system.shared_view_utils import _record_audit_trail
        _record_audit_trail(
            table="organization_fund_report",
            record_id=report.report_id_PK,
            action="RETURNED_TO_TREASURER",
            actor=officer,
            old={"report_status": old_status},
            new={"report_status": report.report_status},
            ip=request.META.get("REMOTE_ADDR"),
            notes=f"Fund report {report.report_period} returned to Treasurer: {remarks}",
        )
    except Exception:
        pass

    return JsonResponse({"ok": True, "status": report.report_status})


@require_GET
def auditor_download_fund_report(request: HttpRequest, report_id: int):
    guard = require_role(request, role="Auditor")
    if guard is not None:
        return guard
    return _download_report_file(report_id)


@require_GET
def president_download_fund_report(request: HttpRequest, report_id: int):
    guard = require_role(request, role="President")
    if guard is not None:
        return guard
    return _download_report_file(report_id)


def _download_report_file(report_id: int):
    report = get_object_or_404(OrganizationFundReport, pk=report_id)
    if not report.file_path:
        return HttpResponse("Report file not found.", status=404)

    full_path = os.path.join(settings.MEDIA_ROOT, report.file_path)
    if not os.path.exists(full_path):
        return HttpResponse("Report file not found on disk.", status=404)

    with open(full_path, "rb") as f:
        data = f.read()

    filename = os.path.basename(report.file_path)
    response = HttpResponse(
        data,
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


# ==========================================================================
# PRESIDENT: Approve / Reject Fund Reports + Trigger Email
# ==========================================================================

@require_GET
def president_fund_reports_list(request: HttpRequest):
    """Reports verified by the Auditor awaiting President final approval,
    plus recently finalized ones for history."""
    guard = require_role(request, role="President")
    if guard is not None:
        return guard

    reports = OrganizationFundReport.objects.exclude(
        report_status__in=["Draft", "Submitted", "Rejected"]
    ).order_by("-created_at")
    data = []
    for r in reports:
        data.append({
            "report_id": r.report_id_PK,
            "period": r.report_period,
            "report_type": r.report_type,
            "status": r.report_status,
            "file_path": r.file_path,
            "prepared_by": r.prepared_by_user_id_FK.full_name if r.prepared_by_user_id_FK else "",
            "verified_by": r.auditor_verified_by_user_id_FK.full_name if r.auditor_verified_by_user_id_FK else "",
            "verified_at": r.auditor_verified_at.isoformat() if r.auditor_verified_at else "",
            "approved_by": r.approved_by_user_id_FK.full_name if r.approved_by_user_id_FK else "",
            "approved_at": r.approved_at.isoformat() if r.approved_at else "",
            "created_at": r.created_at.isoformat(),
        })
    return JsonResponse({"ok": True, "reports": data})


@require_POST
def president_approve_fund_report(request: HttpRequest, report_id: int):
    guard = require_role(request, role="President")
    if guard is not None:
        return guard
    guard = check_zero_trust(request, level="approve")
    if guard is not None:
        return guard

    officer_id = request.session.get("officer_id")
    try:
        officer = OfficerUser.objects.get(user_id_PK=int(officer_id))
    except OfficerUser.DoesNotExist:
        return JsonResponse({"error": "Officer not found."}, status=400)

    report = get_object_or_404(OrganizationFundReport, pk=report_id)
    if report.report_status not in ("Auditor Verified", "Submitted"):
        return JsonResponse({"error": "Only Auditor Verified reports can be approved."}, status=400)

    report.report_status = "Approved"
    report.approved_by_user_id_FK = officer
    report.approved_at = timezone.now()
    report.save(update_fields=["report_status", "approved_by_user_id_FK", "approved_at", "updated_at"])

    # Send email to all members with report attached
    _send_fund_report_email(report)

    return JsonResponse({"ok": True, "status": report.report_status})


@require_POST
def president_reject_fund_report(request: HttpRequest, report_id: int):
    guard = require_role(request, role="President")
    if guard is not None:
        return guard
    guard = check_zero_trust(request, level="approve")
    if guard is not None:
        return guard

    remarks = (request.POST.get("remarks") or "").strip()

    report = get_object_or_404(OrganizationFundReport, pk=report_id)
    if report.report_status not in ("Auditor Verified", "Submitted"):
        return JsonResponse({"error": "Only Auditor Verified reports can be rejected."}, status=400)

    report.report_status = "Rejected"
    report.return_reason = remarks or report.return_reason
    report.save(update_fields=["report_status", "return_reason", "updated_at"])
    return JsonResponse({"ok": True, "status": report.report_status})


def _send_fund_report_email(report):
    if not report.file_path:
        return False

    full_path = os.path.join(settings.MEDIA_ROOT, report.file_path)
    if not os.path.exists(full_path):
        return False

    members = Member.objects.exclude(
        membership_status__iexact="Retired"
    ).exclude(email__isnull=True).exclude(email__exact="")

    recipient_emails = list(members.values_list("email", flat=True))
    if not recipient_emails:
        return False

    period_label = report.report_period
    report_type_label = "Weekly" if report.report_type == "weekly" else "Monthly"

    context = {
        "period": period_label,
        "report_type": report_type_label,
        "prepared_by": report.prepared_by_user_id_FK.full_name if report.prepared_by_user_id_FK else "ISU CAUFA",
    }

    try:
        html_content = render_to_string("emails/fund_contribution_report.html", context)
    except Exception:
        html_content = (
            f"<p>Dear Member,</p>"
            f"<p>The {report_type_label} Organization Fund Report for {period_label} has been approved and is attached.</p>"
        )

    text_content = (
        f"ISU CAUFA {report_type_label} Fund Report - {period_label}\n"
        f"Prepared by: {context['prepared_by']}\n"
        "---\n"
        "This email was sent by ISU CAUFA.\n"
    )

    from email.mime.image import MIMEImage
    from pathlib import Path

    from django.core.mail import EmailMultiAlternatives

    msg = EmailMultiAlternatives(
        subject=f"ISU CAUFA {report_type_label} Fund Report - {period_label}",
        body=text_content,
        to=recipient_emails,
    )
    msg.attach_alternative(html_content, "text/html")

    with open(full_path, "rb") as f:
        msg.attach(
            os.path.basename(report.file_path),
            f.read(),
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    logo_path = Path(settings.BASE_DIR) / "static" / "images" / "isu_caufa_official.png"
    if logo_path.exists():
        with open(logo_path, "rb") as f:
            logo_data = f.read()
        image = MIMEImage(logo_data)
        image.add_header("Content-ID", "<logo_cid>")
        image.add_header("Content-Disposition", "inline", filename="isu_caufa_official.png")
        msg.attach(image)

    try:
        msg.send(fail_silently=False)
        return True
    except Exception as exc:
        logger = logging.getLogger(__name__)
        logger.error("Failed to send fund report email: %s", exc)
        return False
