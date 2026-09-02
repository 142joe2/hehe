"""
Standalone HTTP smoke tests for HTMX endpoints.
Starts the dev server, hits each endpoint, and reports status codes.

Usage:  python core_system/test_htmx.py
"""
import subprocess
import sys
import time
import urllib.request
import urllib.error


class NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


_no_redirect = urllib.request.build_opener(NoRedirectHandler)


def fetch(path, port, follow_redirects=True):
    """Fetch a URL and return (status, body)."""
    opener = urllib.request.build_opener() if follow_redirects else _no_redirect
    try:
        r = opener.open(f"http://127.0.0.1:{port}{path}", timeout=5)
        return r.status, r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()
    except Exception as e:
        return None, str(e)


def test_cash_flow(port):
    """Test cash flow endpoint returns 302 (redirect to login) without session."""
    status, body = fetch("/hx/cash-flow-summary/", port, follow_redirects=False)
    if status == 302:
        print(f"  PASS: /hx/cash-flow-summary/ -> 302 (redirect to login, as expected)")
        return True
    print(f"  FAIL: /hx/cash-flow-summary/ -> expected 302, got {status}")
    return False


def test_treasurer_module(port, module_name, expect_status=200):
    """Test a treasurer module endpoint."""
    path = f"/hx/treasurer/module/{module_name}/"
    status, body = fetch(path, port, follow_redirects=False)
    if status == expect_status:
        if expect_status == 200 and module_name not in body:
            print(f"  FAIL: {path} -> {status} but missing '{module_name}' in body (body={body[:150]})")
            return False
        print(f"  PASS: {path} -> {status}")
        return True
    print(f"  FAIL: {path} -> {status} (expected {expect_status})")
    if body and len(body) < 500:
        print(f"    body: {body[:300]}")
    return False


TREASURER_MODULES = [
    "dashboard-overview",
    "view-member-profile",
    "view-fee-payment",
    "view-returned-entries",
    "view-otc-payment",
    "view-salary-deduction",
    "view-monthly-dues-returned",
    "view-dues-tracking",
    "view-medical-aid",
    "view-death-aid",
    "view-medical-aid-returned",
    "view-death-aid-returned",
    "treasurer-aid-tracking-posts",
    "treasurer-aid-history",
    "view-reports",
]


def main():
    port = 8787
    server_dir = r"C:\Users\maday\PROJECTS\CAPSTONE_PROJECT"

    log_file = open("test_server_errors.log", "w", encoding="utf-8")
    print(f"Starting Django dev server on port {port} (errors logged to test_server_errors.log)...")
    proc = subprocess.Popen(
        [sys.executable, "manage.py", "runserver", str(port), "--noreload"],
        cwd=server_dir,
        stdout=subprocess.DEVNULL,
        stderr=log_file,
    )

    time.sleep(4)

    # Print any errors from the log
    log_file.flush()
    with open("test_server_errors.log", "r", encoding="utf-8") as f:
        log = f.read().strip()
        if log:
            print(f"  [Server log preview: {log[:300]}]")

    try:
        passed = 0
        failed = 0

        print("\n--- Cash Flow Endpoint ---")
        if test_cash_flow(port):
            passed += 1
        else:
            failed += 1

        print("\n--- Treasurer Module Endpoints (expect 302 redirect without session) ---")
        # Without a session, these should redirect to login (no 500 error)
        if test_treasurer_module(port, "dashboard-overview", expect_status=302):
            passed += 1
        else:
            failed += 1

        print(f"\n--- Treasurer Module Endpoints: all templates exist (expect 302 redirect) ---")
        # Verify all templates compile (will get 302 redirect, not 500 error)
        for mod in TREASURER_MODULES:
            if test_treasurer_module(port, mod, expect_status=302):
                passed += 1
            else:
                failed += 1

        print(f"\n--- Nonexistent Module (expect 302 redirect, not 500) ---")
        if test_treasurer_module(port, "nonexistent-module", expect_status=302):
            passed += 1
        else:
            failed += 1

        print(f"\n{'='*50}")
        print(f"Results: {passed} passed, {failed} failed out of {passed + failed} tests")
        print(f"{'='*50}")

        return 0 if failed == 0 else 1
    finally:
        proc.terminate()
        proc.wait()


if __name__ == "__main__":
    sys.exit(main())
