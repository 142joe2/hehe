import os

from channels.auth import AuthMiddlewareStack
from channels.routing import ProtocolTypeRouter, URLRouter
from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "caufa_portal.settings")

asgi_app = get_asgi_application()

import core_system.routing  # noqa: E402

application = ProtocolTypeRouter(
    {
        "http": asgi_app,
        "websocket": AuthMiddlewareStack(
            URLRouter(core_system.routing.websocket_urlpatterns)
        ),
    }
)
