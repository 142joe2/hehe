import json
from urllib import error as urllib_error
from urllib import parse as urllib_parse
from urllib import request as urllib_request

from django.conf import settings

TURNSTILE_VERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"


def _is_localhost_host(host: str | None) -> bool:
    if not host:
        return False
    host_value = host.split(":", 1)[0].strip().lower()
    return host_value in {"localhost", "127.0.0.1", "::1"}


def is_localhost_request(request=None) -> bool:
    if request is None:
        return False
    return _is_localhost_host(getattr(request, "get_host", lambda: "")())


def is_turnstile_enabled(request=None) -> bool:
    site_key = (getattr(settings, "TURNSTILE_SITE_KEY", "") or "").strip()
    secret_key = (getattr(settings, "TURNSTILE_SECRET_KEY", "") or "").strip()
    if not site_key or not secret_key:
        return False

    if is_localhost_request(request):
        return getattr(settings, "TURNSTILE_REQUIRE_ON_LOCALHOST", False)

    return True


def get_turnstile_site_key() -> str:
    return (getattr(settings, "TURNSTILE_SITE_KEY", "") or "").strip()


def _post_turnstile_siteverify(token: str, remote_ip: str | None = None) -> dict:
    secret_key = (getattr(settings, "TURNSTILE_SECRET_KEY", "") or "").strip()
    if not token or not secret_key:
        return {"success": False}

    payload = {
        "secret": secret_key,
        "response": token,
    }
    if remote_ip:
        payload["remoteip"] = remote_ip

    body = urllib_parse.urlencode(payload).encode("utf-8")
    req = urllib_request.Request(
        TURNSTILE_VERIFY_URL,
        data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )

    try:
        with urllib_request.urlopen(req, timeout=5) as response:
            data = response.read().decode("utf-8")
            return json.loads(data)
    except (urllib_error.URLError, urllib_error.HTTPError, json.JSONDecodeError, TimeoutError):
        return {"success": False}


def validate_turnstile_token(token: str, remote_ip: str | None = None, request=None) -> bool:
    if not token:
        return False
    if not is_turnstile_enabled(request):
        return True
    return bool(_post_turnstile_siteverify(token, remote_ip=remote_ip).get("success"))
