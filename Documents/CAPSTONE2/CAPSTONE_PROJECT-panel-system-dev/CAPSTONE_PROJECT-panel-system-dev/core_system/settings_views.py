import json

from django.http import HttpRequest, JsonResponse
from django.views.decorators.http import require_GET, require_http_methods

from core_system.guards import require_role
from core_system.models import SystemSetting


@require_http_methods(["GET", "PUT"])
def grace_period_setting(request: HttpRequest):
    guard = require_role(request, role="president")
    if guard:
        return guard

    if request.method == "GET":
        setting, _ = SystemSetting.objects.get_or_create(
            setting_key="grace_period_days",
            defaults={"setting_value": "15"},
        )
        return JsonResponse({
            "key": setting.setting_key,
            "value": int(setting.setting_value),
        })

    try:
        body = json.loads(request.body)
        value = body.get("value")
        if value is None:
            return JsonResponse({"error": "value is required"}, status=400)
        int_value = int(value)
        if int_value < 1 or int_value > 60:
            return JsonResponse({"error": "value must be between 1 and 60"}, status=400)
    except (ValueError, TypeError):
        return JsonResponse({"error": "value must be an integer between 1 and 60"}, status=400)

    setting, _ = SystemSetting.objects.update_or_create(
        setting_key="grace_period_days",
        defaults={"setting_value": str(int_value)},
    )
    return JsonResponse({
        "key": setting.setting_key,
        "value": int(setting.setting_value),
        "message": "Grace period updated",
    })


@require_http_methods(["GET", "PUT"])
def notification_settings(request: HttpRequest):
    guard = require_role(request, role="president")
    if guard:
        return guard

    if request.method == "GET":
        keys = ["reminder_intervals", "reminder_channels", "reminder_message_templates"]
        result = {}
        for key in keys:
            setting, _ = SystemSetting.objects.get_or_create(
                setting_key=key,
                defaults={"setting_value": "{}" if "template" in key else "[]" if "intervals" in key else "{}"},
            )
            try:
                result[key] = json.loads(setting.setting_value)
            except (json.JSONDecodeError, TypeError):
                result[key] = setting.setting_value
        return JsonResponse(result)

    try:
        body = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    allowed_keys = {"reminder_intervals", "reminder_channels", "reminder_message_templates"}
    for key, value in body.items():
        if key not in allowed_keys:
            continue
        serialized = json.dumps(value) if isinstance(value, (dict, list)) else str(value)
        SystemSetting.objects.update_or_create(
            setting_key=key,
            defaults={"setting_value": serialized},
        )

    return JsonResponse({"message": "Notification settings updated"})
