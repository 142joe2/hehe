from __future__ import annotations

import logging
import re
import zipfile
from io import BytesIO

from bs4 import BeautifulSoup
from django.core.paginator import Paginator
from django.db.models import Case, IntegerField, Value, When
from django.db.utils import ProgrammingError
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

logger = logging.getLogger(__name__)

from core_system.auth_utils import sha256_hex
from core_system.services.email_service import send_registration_received_email, generate_secure_password
from core_system.constants.policy_constants import POLICY, _get_setting_override
from core_system.constants.status_constants import RegistrationStatus
from core_system.models import BylawsFile, MemberRegistrationRequest, Member, OfficerProfile, Album, NewsArticle, NewsCategory, NewsGallery
from core_system.shared_view_utils import _link_proof_to_record


_POLICY_LABELS = [
    ("membership_fee", "Membership Fee"),
    ("monthly_dues", "Monthly Dues"),
    ("accidental_sickness_aid_threshold", "Accidental/Sickness Aid Threshold"),
    ("accidental_sickness_aid_benefit", "Accidental/Sickness Aid Benefit"),
    ("death_aid_member", "Death Aid — Member"),
    ("death_aid_spouse", "Death Aid — Spouse"),
    ("death_aid_parent_child", "Death Aid — Parent/Child"),
    ("death_aid_full_blood_sibling", "Death Aid — Full-Blood Sibling"),
]

# Grouped policy constants for public display (homepage + resources).
_POLICY_GROUPS = [
    (
        "Membership & Dues",
        "Join the association",
        [
            ("membership_fee", "Membership Fee (one-time)"),
            ("monthly_dues", "Monthly Due"),
        ],
    ),
    (
        "Medical / Accidental-Sickness Aid",
        "For hospital bills exceeding ₱20,000 (once a year only)",
        [
            ("accidental_sickness_aid_threshold", "Hospital Bill Threshold"),
            ("accidental_sickness_aid_benefit", "Aid Benefit"),
        ],
    ),
    (
        "Death Aid Benefits",
        "Received by the member's family",
        [
            ("death_aid_member", "Member"),
            ("death_aid_spouse", "Husband / Wife of a Member"),
            ("death_aid_parent_child", "Parents & Children"),
            ("death_aid_full_blood_sibling", "Brother / Sister (Full Blood)"),
        ],
    ),
]


def _public_policy_constants():
    """Return grouped policy constants with live overrides applied."""
    groups = []
    for group_label, group_subtitle, items in _POLICY_GROUPS:
        rows = []
        for key, label in items:
            raw = _get_setting_override(key)
            if raw is not None:
                try:
                    value = float(raw)
                except (TypeError, ValueError):
                    value = getattr(POLICY, key)
            else:
                value = getattr(POLICY, key)
            rows.append({
                "key": key,
                "label": label,
                "value": float(value),
            })
        groups.append({
            "name": group_label,
            "subtitle": group_subtitle,
            "items": rows,
        })
    return groups


@require_GET
def public_bylaws(request: HttpRequest):
    """Public endpoint returning policy constants and uploaded bylaws documents.

    No authentication required — used by the landing page to render the
    Bylaws / Policy section.
    """

    constants = []
    for key, label in _POLICY_LABELS:
        raw = _get_setting_override(key)
        if raw is not None:
            try:
                value = float(raw)
            except (TypeError, ValueError):
                value = getattr(POLICY, key)
        else:
            value = getattr(POLICY, key)
        constants.append({
            "key": key,
            "label": label,
            "value": float(value),
        })

    files = BylawsFile.objects.filter(
        verification_status="Active",
    ).exclude(
        document_type=BylawsFile.BYLAWS_DOCUMENT_TYPE_PUBLIC,
        is_public_visible=False,
    ).order_by("-uploaded_at")

    file_list = []
    for f in files:
        file_list.append({
            "document_id": f.bylaws_file_id,
            "file_name": f.file_name,
            "file_type": f.file_type or "application/octet-stream",
            "uploaded_at": f.uploaded_at.strftime("%Y-%m-%d") if f.uploaded_at else None,
        })

    return JsonResponse({
        "ok": True,
        "generated_at": timezone.now().isoformat(),
        "constants": constants,
        "files": file_list,
    })


@require_GET
def public_register(request: HttpRequest):
    """Render the public membership registration request form."""
    membership_fee_amount = _get_setting_override("membership_fee")
    if membership_fee_amount is None:
        from core_system.constants.policy_constants import POLICY
        membership_fee_amount = getattr(POLICY, "membership_fee")
    return render(request, "website/public_register.html", {
        "membership_fee_amount": float(membership_fee_amount),
    })


@require_GET
def public_registration_status(request: HttpRequest):
    """Show the step-by-step status of a pending membership registration."""
    email = (request.GET.get("email") or "").strip()
    status = None
    error = None
    current_step = 0
    rejected = False
    returned = False

    if email:
        try:
            request_row = (
                MemberRegistrationRequest.objects.filter(email__iexact=email)
                .order_by("-submitted_at")
                .first()
            )
        except ProgrammingError:
            request_row = None

        if request_row is None:
            error = (
                "No registration request was found for that email address. "
                "Please check the spelling or submit a new registration request."
            )
        else:
            status = request_row.status
            if status == RegistrationStatus.REJECTED:
                rejected = True
            elif status == RegistrationStatus.RETURNED_FOR_REVISION:
                returned = True
            elif status == RegistrationStatus.PENDING_TREASURER_REVIEW:
                current_step = 1
            elif status in {RegistrationStatus.TREASURER_VERIFIED, RegistrationStatus.PENDING_AUDITOR_REVIEW}:
                current_step = 2
            elif status in {RegistrationStatus.AUDITOR_VERIFIED, RegistrationStatus.PENDING_PRESIDENT_APPROVAL}:
                current_step = 3
            elif status == RegistrationStatus.PRESIDENT_APPROVED:
                current_step = 4

    return render(request, "website/public_registration_status.html", {
        "email": email,
        "status": status,
        "error": error,
        "current_step": current_step,
        "rejected": rejected,
        "returned": returned,
    })



@require_GET
def public_registration_field_availability(request: HttpRequest):
    """Return whether a username or email is already taken."""
    field = (request.GET.get("field") or "").strip().lower()
    value = (request.GET.get("value") or "").strip()
    if field not in {"username", "email"} or not value:
        return JsonResponse({"ok": False, "error": "Invalid validation request."}, status=400)

    try:
        if field == "username":
            taken = (
                Member.objects.filter(employee_id__iexact=value).exists()
                or MemberRegistrationRequest.objects.filter(employee_id__iexact=value).exclude(status=RegistrationStatus.REJECTED).exists()
            )
        else:
            taken = (
                Member.objects.filter(email__iexact=value).exists()
                or MemberRegistrationRequest.objects.filter(email__iexact=value).exclude(status=RegistrationStatus.REJECTED).exists()
            )
    except ProgrammingError:
        if field == "username":
            taken = Member.objects.filter(employee_id__iexact=value).exists()
        else:
            taken = Member.objects.filter(email__iexact=value).exists()

    return JsonResponse({"ok": True, "field": field, "value": value, "available": not taken})


@require_POST
def public_submit_registration_request(request: HttpRequest):
    """Accept a public member registration request with proof upload."""
    field_labels = {
        "first_name": "First Name",
        "last_name": "Last Name",
        "username": "Username",
        "email": "Email Address",
        "department": "Department",
        "payment_method": "Payment Method",
        "amount": "Amount Paid",
    }

    for field, label in field_labels.items():
        if not request.POST.get(field, "").strip():
            return JsonResponse({"ok": False, "error": f"{label} is required."}, status=400)

    first_name = request.POST.get("first_name", "").strip()
    middle_initial = request.POST.get("middle_initial", "").strip()
    if middle_initial and len(middle_initial) > 1:
        return JsonResponse({"ok": False, "error": "Middle Initial must be only 1 character."}, status=400)
    last_name = request.POST.get("last_name", "").strip()
    username = request.POST.get("username", "").strip()
    email = request.POST.get("email", "").strip()
    department = request.POST.get("department", "").strip()
    position = request.POST.get("position", "").strip()
    membership_category = request.POST.get("membership_category", "Permanent").strip() or "Permanent"
    payment_method = request.POST.get("payment_method", "").strip()
    payment_date_raw = request.POST.get("payment_date", "").strip()
    amount_raw = request.POST.get("amount", "").strip()

    full_name = f"{first_name}{' ' + middle_initial if middle_initial else ''} {last_name}".strip()

    if not re.match(r"^[^\s@]+@[^\s@]+\.[^\s@]+$", email):
        return JsonResponse({"ok": False, "error": "Please enter a valid email address, e.g. user@gmail.com."}, status=400)
    
    # Auto-generate secure password
    generated_password = generate_secure_password()

    # Prevent duplicate member username/email or pending requests for same username/email
    try:
        if Member.objects.filter(employee_id__iexact=username).exists():
            return JsonResponse({"ok": False, "error": "A member with this username already exists."}, status=409)
        if MemberRegistrationRequest.objects.filter(employee_id__iexact=username).exclude(status=RegistrationStatus.REJECTED).exists():
            return JsonResponse({"ok": False, "error": "A pending registration request already exists for this username."}, status=409)
        if Member.objects.filter(email__iexact=email).exists():
            return JsonResponse({"ok": False, "error": "A member with this email already exists."}, status=409)
        if MemberRegistrationRequest.objects.filter(email__iexact=email).exclude(status=RegistrationStatus.REJECTED).exists():
            return JsonResponse({"ok": False, "error": "A pending registration request already exists for this email."}, status=409)
    except ProgrammingError:
        logger.exception("Registration check failed because MemberRegistrationRequest table is unavailable")
        return JsonResponse({"ok": False, "error": "Membership registration is temporarily unavailable. Please try again later."}, status=503)

    try:
        amount_value = float(amount_raw)
    except (TypeError, ValueError):
        return JsonResponse({"ok": False, "error": "Amount must be a valid number."}, status=400)

    payment_date = None
    if payment_date_raw:
        try:
            payment_date = timezone.datetime.fromisoformat(payment_date_raw).date()
        except ValueError:
            return JsonResponse({"ok": False, "error": "Payment Date must be valid."}, status=400)
    else:
        payment_date = timezone.now().date()

    receipt_number_value = f"REG-{timezone.now().strftime('%Y%m%d%H%M%S')}-{username}" if username else f"REG-{timezone.now().strftime('%Y%m%d%H%M%S')}"

    try:
        request_row = MemberRegistrationRequest.objects.create(
            full_name=full_name,
            employee_id=username,
            email=email or None,
            department=department or None,
            position=position or None,
            membership_category=membership_category,
            payment_method=payment_method,
            amount=amount_value,
            receipt_number=receipt_number_value,
            payment_date=payment_date,
            password_hash=sha256_hex(generated_password),
            status=RegistrationStatus.PENDING_TREASURER_REVIEW,
            submitted_by_ip=request.META.get("REMOTE_ADDR"),
            submitted_by_user_agent=request.META.get("HTTP_USER_AGENT", "")[:255],
        )
    except ProgrammingError:
        logger.exception("Failed to create MemberRegistrationRequest because table is unavailable")
        return JsonResponse({"ok": False, "error": "Membership registration is temporarily unavailable. Please try again later."}, status=503)

    uploaded_file = request.FILES.get("proof_file")
    if uploaded_file and uploaded_file.size > 0:
        try:
            _link_proof_to_record(uploaded_file, request_row, None)
        except Exception:
            logger.exception("Failed to attach supporting proof for registration request %s", request_row.request_id_PK)

    try:
        send_registration_received_email(request_row.email, request_row.full_name, request_row.employee_id)
    except Exception:
        logger.exception("Failed to send registration received email for %s", request_row.full_name)

    return JsonResponse({"ok": True, "request_id": request_row.request_id_PK})


@require_GET
def public_bylaws_render(request: HttpRequest, document_id: int):
    """Render a bylaws document to HTML for in-browser preview."""
    doc = get_object_or_404(
        BylawsFile,
        pk=document_id,
        verification_status="Active",
    )
    if doc.document_type == BylawsFile.BYLAWS_DOCUMENT_TYPE_PUBLIC and not doc.is_public_visible:
        return JsonResponse({"ok": False, "error": "Not found"}, status=404)

    file_type = (doc.file_type or "").lower()
    file_name = doc.file_name or ""

    try:
        if file_name.lower().endswith(".docx") or "wordprocessingml" in file_type:
            html = _render_docx_to_html(doc.file_data)
        elif file_name.lower().endswith(".txt") or file_type == "text/plain":
            text = doc.file_data.decode("utf-8", errors="replace")
            html = "<pre>" + escapeHtml(text) + "</pre>"
        elif file_name.lower().endswith(".pdf") or file_type == "application/pdf":
            html = (
                "<p><strong>PDF Preview</strong></p>"
                "<p>This is a PDF document. Use the <strong>Download</strong> button above to view it, "
                "or open it in a new tab.</p>"
            )
        else:
            html = "<p>Preview not available for this file type. Use the <strong>Download</strong> button above.</p>"
    except Exception as e:
        return JsonResponse({
            "ok": False,
            "error": "This document could not be previewed in-browser (" + str(e) + "). Please use the Download button.",
        }, status=500)

    return JsonResponse({"ok": True, "html": html, "file_name": doc.file_name})


@require_GET
def public_bylaws_file(request: HttpRequest, document_id: int):
    """Public file download for an Active bylaws document. No login required."""
    doc = get_object_or_404(
        BylawsFile,
        pk=document_id,
        verification_status="Active",
    )
    if doc.document_type == BylawsFile.BYLAWS_DOCUMENT_TYPE_PUBLIC and not doc.is_public_visible:
        return HttpResponse("Not found", status=404)

    content_type = doc.file_type or "application/octet-stream"
    response = HttpResponse(doc.file_data, content_type=content_type)
    disposition = "attachment" if request.GET.get("download") else "inline"
    response["Content-Disposition"] = f'{disposition}; filename="{doc.file_name}"'
    response["Content-Length"] = str(len(doc.file_data) if doc.file_data else 0)
    return response


@require_GET
def public_document_render(request: HttpRequest, document_id: int):
    """Render a public Document to HTML for in-browser preview."""
    import os
    from django.conf import settings
    from core_system.models import Document

    doc = get_object_or_404(Document, pk=document_id, is_archived=False)
    if not doc.is_public_visible:
        return JsonResponse({"ok": False, "error": "Not found"}, status=404)

    file_path = doc.file_path or ""
    if not os.path.isabs(file_path):
        file_path = os.path.join(settings.MEDIA_ROOT, file_path)

    try:
        with open(file_path, "rb") as fh:
            data = fh.read()
    except OSError:
        return JsonResponse({
            "ok": False,
            "error": "This file could not be read for preview. Please use the Download button.",
        }, status=404)

    file_name = doc.file_name or ""
    file_type = (doc.file_type or "").lower()

    try:
        if file_name.lower().endswith(".docx") or "wordprocessingml" in file_type:
            html = _render_docx_to_html(data)
        elif file_name.lower().endswith(".txt") or file_type == "text/plain":
            text = data.decode("utf-8", errors="replace")
            html = "<pre>" + escapeHtml(text) + "</pre>"
        else:
            html = ""
    except Exception as e:
        return JsonResponse({
            "ok": False,
            "error": "This document could not be previewed in-browser (" + str(e) + "). Please use the Download button.",
        }, status=500)

    return JsonResponse({"ok": True, "html": html, "file_name": doc.file_name})


def _local_name(name):
    """Return the tag name without any XML namespace prefix."""
    return (name or "").split(":")[-1]


def _find_child(tag, name, recursive=True):
    """Find a descendant whose local tag name matches `name`."""
    return tag.find(lambda t: _local_name(t.name) == name, recursive=recursive)


def _render_docx_to_html(data: bytes) -> str:
    with zipfile.ZipFile(BytesIO(data)) as zf:
        names = zf.namelist()
        if "word/document.xml" not in names:
            raise ValueError("word/document.xml not found in DOCX archive")
        xml = zf.read("word/document.xml")

    soup = BeautifulSoup(xml, "xml")

    root = None
    for tag in soup.find_all():
        if _local_name(tag.name) == "document":
            root = tag
            break
    if root is None:
        return "<p>Empty document.</p>"

    body = _find_child(root, "body", recursive=False)
    if body is None:
        return "<p>Empty document body.</p>"

    parts = []
    for child in body.find_all(recursive=False):
        tag = _local_name(child.name)
        if tag == "p":
            parts.append(_docx_paragraph_to_html(child))
        elif tag == "tbl":
            parts.append(_docx_table_to_html(child))
        elif tag == "sectPr":
            pass

    html = "\n".join(parts)
    return html if html else "<p>No readable content found.</p>"


def _docx_paragraph_to_html(para):
    pPr = _find_child(para, "pPr")
    style = ""
    if pPr is not None:
        pStyle = _find_child(pPr, "pStyle")
        if pStyle is not None:
            style = (pStyle.get("w:val") or pStyle.get("val") or "").lower()

    text_parts = []
    is_bold = False
    is_italic = False
    is_underline = False

    for r in [t for t in para.find_all(recursive=False) if _local_name(t.name) == "r"]:
        rPr = _find_child(r, "rPr")
        if rPr is not None:
            if _find_child(rPr, "b") is not None:
                is_bold = True
            if _find_child(rPr, "i") is not None:
                is_italic = True
            if _find_child(rPr, "u") is not None:
                is_underline = True

        t = _find_child(r, "t")
        if t is not None and t.string:
            text = t.string
            if is_bold:
                text = "<strong>" + escapeHtml(text) + "</strong>"
            elif is_italic:
                text = "<em>" + escapeHtml(text) + "</em>"
            elif is_underline:
                text = "<u>" + escapeHtml(text) + "</u>"
            else:
                text = escapeHtml(text)
            text_parts.append(text)

        if _find_child(r, "br") is not None:
            text_parts.append("<br/>")

    text = "".join(text_parts) or "&nbsp;"

    if "heading" in style or "title" in style:
        level = re.search(r"(\d+)", style)
        level = level.group(1) if level else "1"
        return "<h" + level + ">" + text + "</h" + level + ">"
    if style == "listparagraph" or _find_child(para, "numPr") is not None:
        return "<li>" + text + "</li>"
    return "<p>" + text + "</p>"


def _docx_table_to_html(tbl):
    rows = []
    for tr in [t for t in tbl.find_all(recursive=False) if _local_name(t.name) == "tr"]:
        cells = []
        for tc in [t for t in tr.find_all(recursive=False) if _local_name(t.name) == "tc"]:
            cell_texts = []
            for p in [t for t in tc.find_all(recursive=False) if _local_name(t.name) == "p"]:
                cell_texts.append(_docx_paragraph_to_html(p))
            cells.append("".join(cell_texts))
        rows.append("<tr>" + "".join("<td>" + c + "</td>" for c in cells) + "</tr>")
    return "<table>" + "".join(rows) + "</table>"


def escapeHtml(s):
    return str(s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _safe_model_queryset(model, **kwargs):
    """Return a queryset or an empty queryset when the backing table is missing."""
    try:
        return model.objects.filter(**kwargs)
    except ProgrammingError:
        logger.warning("Skipping %s query because the backing table is unavailable.", model._meta.label_lower)
        return model.objects.none()


def _site_setting(key, default=""):
    from core_system.models import SystemSetting
    try:
        return SystemSetting.objects.get(setting_key=key).setting_value
    except SystemSetting.DoesNotExist:
        return default
    except ProgrammingError:
        logger.warning("Skipping SystemSetting lookup for %s because the table is unavailable.", key)
        return default


def _public_resources(limit=50):
    """Build a list of public document dicts with resolved media URLs."""
    import os
    from django.conf import settings
    from core_system.models import Document

    public_doc_types = [
        "Constitution", "By-Laws", "Resolution", "Memorandum",
        "Circular", "Office Order", "Financial Document", "Other",
    ]
    qs = Document.objects.filter(
        document_type__in=public_doc_types,
        is_archived=False,
        is_public_visible=True,
    ).order_by("-uploaded_at")[:limit]

    resources = []
    for doc in qs:
        url = ""
        if doc.file_path:
            try:
                rel = os.path.relpath(doc.file_path, settings.MEDIA_ROOT)
                if not rel.startswith(".."):
                    url = settings.MEDIA_URL + rel.replace("\\", "/")
            except ValueError:
                url = doc.file_path
        resources.append({
            "id": doc.document_id_PK,
            "title": doc.title,
            "document_type": doc.document_type,
            "file_name": doc.file_name,
            "file_url": url,
            "uploaded_at": doc.uploaded_at,
        })
    return resources


def _public_documents(limit=50):
    """Merge president 'Public Documents' bylaws files and secretary documents
    marked as publicly visible into a single list for the resources page."""
    import os
    from django.conf import settings
    from django.urls import reverse
    from core_system.models import Document

    items = []

    bylaws_qs = BylawsFile.objects.filter(
        verification_status="Active",
        document_type=BylawsFile.BYLAWS_DOCUMENT_TYPE_PUBLIC,
        is_public_visible=True,
    ).order_by("-uploaded_at")[:limit]
    for f in bylaws_qs:
        items.append({
            "document_type": f.document_type,
            "file_name": f.file_name,
            "uploaded_at": f.uploaded_at,
            "download_url": reverse("public_bylaws_file", args=[f.bylaws_file_id]),
            "render_url": reverse("public_bylaws_render", args=[f.bylaws_file_id]),
        })

    doc_qs = Document.objects.filter(
        is_public_visible=True,
        is_archived=False,
    ).order_by("-uploaded_at")[:limit]
    for doc in doc_qs:
        url = ""
        if doc.file_path:
            try:
                rel = os.path.relpath(doc.file_path, settings.MEDIA_ROOT)
                if not rel.startswith(".."):
                    url = settings.MEDIA_URL + rel.replace("\\", "/")
            except ValueError:
                url = doc.file_path
        items.append({
            "document_type": doc.document_type,
            "file_name": doc.file_name or doc.title,
            "uploaded_at": doc.uploaded_at,
            "download_url": url,
            "render_url": reverse("public_document_render", args=[doc.document_id_PK]),
        })

    items.sort(key=lambda d: d["uploaded_at"], reverse=True)
    return items[:limit]


def _public_albums():
    """Build a list of album dicts with cover URL and photo count."""
    from core_system.models import Album

    albums = []
    for album in Album.objects.filter(is_active=True).order_by("-created_at"):
        cover_url = ""
        if album.cover_photo and album.cover_photo.image:
            cover_url = album.cover_photo.image.url
        else:
            first_photo = album.photos.order_by("-uploaded_at").first()
            if first_photo and first_photo.image:
                cover_url = first_photo.image.url
        albums.append({
            "album_id": album.album_id_PK,
            "title": album.title,
            "description": album.description,
            "cover_url": cover_url,
            "photo_count": album.photos.count(),
            "created_at": album.created_at,
        })
    return albums


def _public_featured_photos():
    """Build a list of featured photo dicts."""
    from core_system.models import Photo

    featured = []
    for photo in Photo.objects.filter(is_featured=True).order_by("-uploaded_at")[:24]:
        featured.append({
            "image_url": photo.image.url if photo.image else "",
            "caption": photo.caption,
            "album_title": photo.album.title if photo.album else "",
        })
    return featured


def _public_bylaws_files(document_type=None):
    """Build a list of active bylaws file dicts, optionally filtered by type.

    'Public Documents' type files are only listed when marked visible.
    """
    from core_system.models import BylawsFile

    qs = BylawsFile.objects.filter(verification_status="Active")
    if document_type:
        qs = qs.filter(document_type=document_type)
        if document_type == BylawsFile.BYLAWS_DOCUMENT_TYPE_PUBLIC:
            qs = qs.filter(is_public_visible=True)

    files = []
    for f in qs.order_by("-uploaded_at"):
        files.append({
            "document_id": f.bylaws_file_id,
            "document_type": f.document_type,
            "file_name": f.file_name,
            "file_type": f.file_type or "",
            "uploaded_at": f.uploaded_at,
        })
    return files


def homepage(request):
    """Public homepage - gathers all data from existing backend models."""
    from datetime import date
    from core_system.models import Announcement, Event, NewsArticle

    announcements = _safe_model_queryset(Announcement, is_active=True).order_by("-published_at")[:3]

    today = date.today()
    upcoming_events = _safe_model_queryset(
        Event,
        event_date__gte=today,
        status__in=["Upcoming", "Ongoing"],
    ).order_by("event_date", "event_time")[:6]

    # Featured news for homepage
    featured_news = _safe_model_queryset(
        NewsArticle,
        is_published=True,
        is_featured=True,
    ).order_by('-published_at')[:3]

    # Hero carousel slides (managed by PIO)
    from core_system.models import HeroSlide
    hero_slides = _safe_model_queryset(HeroSlide, is_active=True).order_by("sort_order")[:5]

    context = {
        "announcements": announcements,
        "upcoming_events": upcoming_events,
        "featured_news": featured_news,
        "hero_slides": hero_slides,
        "policy_constants": _public_policy_constants(),
        "site_email": _site_setting("contact_email", ""),
        "site_phone": _site_setting("contact_phone", ""),
        "site_address": _site_setting("office_address", ""),
        "facebook_url": _site_setting("facebook_url", "#"),
        "mission": _site_setting("mission", ""),
        "vision": _site_setting("vision", ""),
        "objectives": _site_setting("objectives", ""),
        "org_description": _site_setting("org_description", ""),
        "history": _site_setting("history", ""),
        "core_values": _site_setting("core_values", ""),
    }

    return render(request, "website/index.html", context)


def _full_context(request):
    """Return the full context so every secondary public page renders correctly."""
    from datetime import date
    from core_system.models import Announcement, Event

    today = date.today()

    announcements = _safe_model_queryset(Announcement, is_active=True).order_by("-published_at")

    upcoming_events = _safe_model_queryset(
        Event,
        event_date__gte=today,
        status__in=["Upcoming", "Ongoing"],
    ).order_by("event_date", "event_time")

    past_events = _safe_model_queryset(
        Event,
        status__in=["Completed", "Cancelled"],
    ).order_by("-event_date", "-event_time")[:20]

    all_events = _safe_model_queryset(Event).order_by("event_date", "event_time")

    # Featured news for homepage
    featured_news = _safe_model_queryset(
        NewsArticle,
        is_published=True,
        is_featured=True,
    ).order_by('-published_at')[:3]

    exec_rank = Case(
        When(position__iexact="President", then=Value(0)),
        When(position__iexact="Vice President", then=Value(1)),
        When(position__iexact="Secretary", then=Value(2)),
        When(position__iexact="Treasurer", then=Value(3)),
        When(position__iexact="Auditor", then=Value(4)),
        When(position__iexact="Business Manager", then=Value(5)),
        When(position__iexact="Public Information Officer", then=Value(6)),
        default=Value(99),
        output_field=IntegerField(),
    )
    executive_officers = (
        OfficerProfile.objects.filter(
            status="Active", category="Executive Officer",
        ).order_by(exec_rank, "full_name")
    )
    board_members = (
        OfficerProfile.objects.filter(
            status="Active", category="Board of Directors",
        ).order_by("full_name")
    )
    advisers = (
        OfficerProfile.objects.filter(
            status="Active", category="Adviser",
        ).order_by("full_name")
    )

    resources = _public_resources(50)
    financial_docs = [r for r in resources if r["document_type"] == "Financial Document"]
    constitution_docs = _public_bylaws_files(document_type="Constitution")
    bylaws_files = _public_bylaws_files(document_type="By-Laws")
    public_docs = _public_documents()

    return {
        "announcements": announcements,
        "upcoming_events": upcoming_events,
        "past_events": past_events,
        "events": all_events,
        "featured_news": featured_news,
        "executive_officers": executive_officers,
        "board_members": board_members,
        "advisers": advisers,
        "resources": resources,
        "constitution_docs": constitution_docs,
        "public_docs": public_docs,
        "financial_docs": financial_docs,
        "bylaws_files": bylaws_files,
        "policy_constants": _public_policy_constants(),
        "albums": _public_albums(),
        "featured_photos": _public_featured_photos(),
        "videos": [],
        "site_email": _site_setting("contact_email", ""),
        "site_phone": _site_setting("contact_phone", ""),
        "site_address": _site_setting("office_address", ""),
        "facebook_url": _site_setting("facebook_url", "#"),
        "mission": _site_setting("mission", ""),
        "vision": _site_setting("vision", ""),
        "objectives": _site_setting("objectives", ""),
        "org_description": _site_setting("org_description", ""),
        "history": _site_setting("history", ""),
        "core_values": _site_setting("core_values", ""),
        "org_structure": _site_setting("org_structure", ""),
    }


@require_GET
def about_page(request):
    return render(request, "website/about.html", _full_context(request))


@require_GET
def officers_page(request):
    return render(request, "website/officers.html", _full_context(request))


@require_GET
def activities_page(request):
    from datetime import date
    from core_system.models import Event

    context = _full_context(request)

    past_qs = Event.objects.filter(
        status__in=["Completed", "Cancelled"],
    ).order_by("-event_date", "-event_time")

    calendar_qs = Event.objects.order_by("event_date", "event_time")

    context["past_events"] = Paginator(past_qs, 8).get_page(request.GET.get("past_page"))
    context["events"] = Paginator(calendar_qs, 10).get_page(request.GET.get("events_page"))

    section = request.GET.get("section")
    if section == "past":
        return render(request, "website/partials/_past_activities.html", context)
    if section == "calendar":
        return render(request, "website/partials/_event_calendar.html", context)
    return render(request, "website/activities.html", context)


@require_GET
def gallery_page(request):
    return render(request, "website/gallery.html", _full_context(request))


@require_GET
def news_page(request):
    """News & Highlights page with featured and recent news articles."""
    context = _full_context(request)
    
    # Featured news articles
    featured_news = NewsArticle.objects.filter(
        is_published=True,
        is_featured=True
    ).order_by('-published_at')[:3]
    
    # Recent news articles
    recent_news = NewsArticle.objects.filter(
        is_published=True
    ).order_by('-published_at')
    
    # Categories
    categories = NewsCategory.objects.filter(is_active=True).order_by('order', 'name')
    
    # Apply category filter if specified
    category_slug = request.GET.get('category')
    if category_slug:
        recent_news = recent_news.filter(category__slug=category_slug)
    
    context["featured_news"] = featured_news
    ua = (request.META.get("HTTP_USER_AGENT") or "").lower()
    per_page = 3 if "windows nt" not in ua else 9
    context["recent_news"] = Paginator(recent_news, per_page).get_page(request.GET.get("page"))
    context["categories"] = categories
    context["current_category"] = category_slug
    
    return render(request, "website/news.html", context)


@require_GET
def news_detail(request, slug):
    """Individual news article detail page with gallery and video support."""
    context = _full_context(request)
    
    article = get_object_or_404(NewsArticle, slug=slug, is_published=True)
    
    # Increment view count
    article.view_count += 1
    article.save(update_fields=['view_count'])
    
    # Get related articles (same category, excluding current)
    related_articles = NewsArticle.objects.filter(
        category=article.category,
        is_published=True
    ).exclude(news_id=article.news_id)[:4]
    
    # Get article gallery
    gallery = article.galleries.filter(is_featured=False).order_by('order')
    featured_gallery = article.galleries.filter(is_featured=True).first()

    # Normalize video URL (watch/shorts -> embed) so older articles render too
    if article.video_url:
        from core_system.pio_views import _normalize_video_url, _video_watch_url, _is_direct_video_file
        article.video_url = _normalize_video_url(article.video_url)
        context["video_watch_url"] = _video_watch_url(article.video_url) or article.video_url
        context["video_is_direct_file"] = _is_direct_video_file(article.video_url)

    context["article"] = article
    context["related_articles"] = related_articles
    context["gallery"] = gallery
    context["featured_gallery"] = featured_gallery
    
    return render(request, "website/news_detail.html", context)


@require_GET
def resources_page(request):
    return render(request, "website/resources.html", _full_context(request))


@require_GET
def announcements_page(request):
    context = _full_context(request)
    context["announcements"] = Paginator(context["announcements"], 6).get_page(
        request.GET.get("page")
    )
    if request.GET.get("section") == "list":
        return render(request, "website/partials/_announcements_list.html", context)
    return render(request, "website/announcements.html", context)


@require_GET
def announcement_detail(request, announcement_id):
    """Individual announcement detail page."""
    from core_system.models import Announcement

    context = _full_context(request)
    context["announcement"] = get_object_or_404(
        Announcement,
        announcement_id_PK=announcement_id,
        is_active=True,
    )
    return render(request, "website/announcement_detail.html", context)
