from django.http import HttpRequest, HttpResponse, JsonResponse
from django.views.decorators.http import require_GET, require_POST
from django.utils import timezone

from core_system.guards import require_role
from core_system.models import OfficerUser, OrganizationFundReport
from core_system.services.reporting import generate_department_report, generate_contribution_report, generate_unified_report


def _report_role_guard(request):
    """Officer reports are restricted to financial officers; members cannot download the roster workbook."""
    return require_role(request, role=["Treasurer", "Auditor", "President"])


def _download_response(wb, filename):
    response = HttpResponse(
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    wb.save(response)
    return response


@require_GET
def download_overall_report(request: HttpRequest):
    guard = _report_role_guard(request)
    if guard:
        return guard

    year = request.GET.get("year")
    month = request.GET.get("month")
    if year:
        year = int(year)
    if month:
        month = int(month)

    wb = generate_unified_report(year, month)
    period = f"{year or 'current'}-{month or 'current'}"
    return _download_response(wb, f"unified_report_{period}.xlsx")


@require_GET
def download_department_report(request: HttpRequest, dept_id: int):
    guard = _report_role_guard(request)
    if guard:
        return guard

    year = request.GET.get("year")
    month = request.GET.get("month")
    if year:
        year = int(year)
    if month:
        month = int(month)

    wb = generate_department_report(dept_id=dept_id, year=year, month=month)
    if wb is None:
        return JsonResponse({"error": "Department not found."}, status=404)
    period = f"{year or 'current'}-{month or 'current'}"
    return _download_response(wb, f"department_report_{dept_id}_{period}.xlsx")


@require_GET
def download_contribution_report(request: HttpRequest):
    guard = _report_role_guard(request)
    if guard:
        return guard

    year = request.GET.get("year")
    month = request.GET.get("month")
    if year:
        year = int(year)
    if month:
        month = int(month)

    wb = generate_contribution_report()
    period = f"{year or 'current'}-{month or 'current'}"
    return _download_response(wb, f"contribution_report_{period}.xlsx")


@require_POST
def generate_unified_report_view(request: HttpRequest):
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

    import os
    from django.conf import settings
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
