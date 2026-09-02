# caufa_portal/urls.py
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from django.http import FileResponse
from django.contrib.auth import views as auth_views
from core_system.auth_views import change_password, forgot_password, officer_login, reset_password

from django.contrib.staticfiles.urls import staticfiles_urlpatterns

from core_system.public_views import (
    homepage, about_page, officers_page, activities_page,
    gallery_page, resources_page, announcements_page, news_page, news_detail,
    announcement_detail,
)
from django.views.generic import RedirectView

def sw_js(request):
    sw_path = settings.BASE_DIR / "static" / "sw.js"
    return FileResponse(open(sw_path, 'rb'), content_type="application/javascript")  # noqa: SIM115

urlpatterns = [
    path("favicon.ico", RedirectView.as_view(url="/static/img/isu_caufa_official.png", permanent=True)),
    path("sw.js", sw_js),
    path("admin/", admin.site.urls),
    # 1. Main Landing: Dynamic homepage that queries existing backend data
    path("", homepage, name="home"),
    # Page routes
    path("about/", about_page, name="about_page"),
    path("officers/", officers_page, name="officers_page"),
    path("activities/", activities_page, name="activities_page"),
    path("gallery/", gallery_page, name="gallery_page"),
    path("news/", news_page, name="news_page"),
    path("news/<slug:slug>/", news_detail, name="news_detail"),
    path("resources/", resources_page, name="resources_page"),
    path("announcements/", announcements_page, name="announcements_page"),
    path("announcements/<int:announcement_id>/", announcement_detail, name="announcement_detail"),
    # 2. Login Portal: Moved to http://127.0.0.1:8000/login/
    path(
        "login/",
        officer_login,
        name="login",
    ),
    path("forgot-password/", forgot_password, name="forgot_password"),
    path("reset-password/", reset_password, name="reset_password"),
    path("change-password/", change_password, name="change_password"),
    # Treasurer workspace + internal module fragments
    path("", include("core_system.urls")),
]

# Serve uploaded media and static files during development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += staticfiles_urlpatterns()
    urlpatterns += [path("__reload__/", include("django_browser_reload.urls"))]

handler403 = "core_system.president_views.permission_denied_view"
