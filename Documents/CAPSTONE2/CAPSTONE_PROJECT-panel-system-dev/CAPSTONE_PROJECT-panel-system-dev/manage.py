#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import sys
from pathlib import Path

import uvicorn

def main() -> None:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "caufa_portal.settings")

    if len(sys.argv) > 1 and sys.argv[1] == "runserver":
        port = "8000"
        host = "127.0.0.1"
        if len(sys.argv) > 2:
            addrport = sys.argv[2]
            if ":" in addrport:
                host, port = addrport.split(":", 1)
            else:
                port = addrport
        if any(a in sys.argv for a in ("--help", "-h")):
            os.execv(sys.executable, [sys.executable, "-m", "uvicorn", "--help"])
            return

        uvicorn.run(
            "caufa_portal.asgi:application",
            host=host,
            port=int(port),
            reload=True,
            timeout_graceful_shutdown=0,
            reload_dirs=[
                str(Path(__file__).parent / "core_system"),
                str(Path(__file__).parent / "templates"),
                str(Path(__file__).parent / "static"),
                str(Path(__file__).parent / "caufa_portal"),
            ],
            reload_includes=[
                "*.py", "*.html", "*.js", "*.css", "*.json", "*.txt",
                "*.yml", "*.yaml", "*.toml", "*.env",
            ],
            reload_excludes=[
                "*.pyc", "*.pyo", "__pycache__", ".git", ".venv",
                "venv", "node_modules", ".kilo", ".opencode",
                ".aider*", ".migrations", "*.log",
                "*.sqlite3", "*.db",
            ],
        )
        return

    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
