from django.urls import re_path

from core_system.consumers import (
    AuditorDashboardConsumer,
    MemberDashboardConsumer,
    PresidentDashboardConsumer,
    TreasurerDashboardConsumer,
)

websocket_urlpatterns = [
    re_path(r"ws/auditor-dashboard/$", AuditorDashboardConsumer.as_asgi()),
    re_path(r"ws/treasurer-dashboard/$", TreasurerDashboardConsumer.as_asgi()),
    re_path(r"ws/president-dashboard/$", PresidentDashboardConsumer.as_asgi()),
    re_path(r"ws/member-dashboard/$", MemberDashboardConsumer.as_asgi()),
]
