import json

from django.http import HttpRequest, JsonResponse
from django.views.decorators.http import require_GET, require_POST, require_http_methods

from core_system.guards import require_role, check_zero_trust
from core_system.models import AuditFindingsReport
from core_system.services.reporting import (
    create_auditor_report,
    approve_auditor_report,
    request_report_revision,
)


@require_POST
def auditor_create_report(request: HttpRequest):
    guard = require_role(request, role="auditor")
    if guard:
        return guard
    guard = check_zero_trust(request, level="approve")
    if guard is not None:
        return guard

    try:
        body = json.loads(request.body)
        year = int(body.get("year", 0))
        month = int(body.get("month", 0))
    except (ValueError, TypeError, json.JSONDecodeError):
        return JsonResponse({"error": "year and month required"}, status=400)

    if not year or not month:
        return JsonResponse({"error": "year and month required"}, status=400)

    officer_id = request.session.get("officer_id")
    from core_system.models import OfficerUser

    try:
        officer = OfficerUser.objects.get(user_id_PK=officer_id)
    except OfficerUser.DoesNotExist:
        return JsonResponse({"error": "Officer not found"}, status=400)

    result = create_auditor_report(year, month, officer)
    return JsonResponse(result, status=201)


@require_GET
def auditor_reports_list(request: HttpRequest):
    guard = require_role(request, role="auditor")
    if guard:
        return guard

    reports = AuditFindingsReport.objects.all().order_by("-prepared_date")
    data = [
        {
            "report_id": r.audit_report_id_PK,
            "title": r.report_title,
            "period": r.report_period,
            "status": r.report_status,
            "prepared_date": str(r.prepared_date),
            "certification_status": r.certification_status,
        }
        for r in reports
    ]
    return JsonResponse(data, safe=False)


@require_GET
def auditor_report_detail(request: HttpRequest, report_id: int):
    guard = require_role(request, role="auditor")
    if guard:
        return guard

    try:
        report = AuditFindingsReport.objects.get(audit_report_id_PK=report_id)
    except AuditFindingsReport.DoesNotExist:
        return JsonResponse({"error": "Report not found"}, status=404)

    return JsonResponse({
        "report_id": report.audit_report_id_PK,
        "title": report.report_title,
        "period": report.report_period,
        "findings_summary": report.findings_summary,
        "status": report.report_status,
        "prepared_date": str(report.prepared_date),
        "presentation_status": report.presentation_status,
        "certification_status": report.certification_status,
    })


@require_GET
def president_auditor_reports_list(request: HttpRequest):
    guard = require_role(request, role="president")
    if guard:
        return guard

    reports = AuditFindingsReport.objects.filter(
        report_status="Submitted",
    ).order_by("-prepared_date")

    data = [
        {
            "report_id": r.audit_report_id_PK,
            "title": r.report_title,
            "period": r.report_period,
            "findings_summary": r.findings_summary,
            "prepared_date": str(r.prepared_date),
            "prepared_by": r.prepared_by_user_id_FK.full_name if r.prepared_by_user_id_FK else "",
        }
        for r in reports
    ]
    return JsonResponse(data, safe=False)


@require_POST
def president_approve_report(request: HttpRequest, report_id: int):
    guard = require_role(request, role="president")
    if guard:
        return guard
    guard = check_zero_trust(request, level="approve")
    if guard is not None:
        return guard

    officer_id = request.session.get("officer_id")
    from core_system.models import OfficerUser

    try:
        officer = OfficerUser.objects.get(user_id_PK=officer_id)
    except OfficerUser.DoesNotExist:
        return JsonResponse({"error": "Officer not found"}, status=400)

    result = approve_auditor_report(report_id, officer)
    if result is None:
        return JsonResponse({"error": "Report not found or not in Submitted status"}, status=404)
    return JsonResponse(result)


@require_POST
def president_request_report_revision(request: HttpRequest, report_id: int):
    guard = require_role(request, role="president")
    if guard:
        return guard
    guard = check_zero_trust(request, level="approve")
    if guard is not None:
        return guard

    officer_id = request.session.get("officer_id")
    from core_system.models import OfficerUser

    try:
        officer = OfficerUser.objects.get(user_id_PK=officer_id)
    except OfficerUser.DoesNotExist:
        return JsonResponse({"error": "Officer not found"}, status=400)

    try:
        body = json.loads(request.body) if request.body else {}
        remarks = body.get("remarks", "")
    except json.JSONDecodeError:
        remarks = ""

    result = request_report_revision(report_id, officer, remarks)
    if result is None:
        return JsonResponse({"error": "Report not found or not in Submitted status"}, status=404)
    return JsonResponse(result)
