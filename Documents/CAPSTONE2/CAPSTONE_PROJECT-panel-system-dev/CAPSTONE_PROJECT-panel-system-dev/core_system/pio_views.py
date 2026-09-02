from __future__ import annotations

import json
import logging

from django.conf import settings
from django.db.models import Max
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST
from django.views.decorators.csrf import csrf_exempt

from core_system.guards import require_role
from core_system.models import (
    OfficerUser, Announcement, AnnouncementCategory, Event, Document,
    Album, Photo, SystemSetting, OfficerProfile, NewsArticle, NewsCategory, NewsGallery,
    HeroSlide,
)
from core_system.shared_view_utils import parse_aware_datetime

logger = logging.getLogger(__name__)


@require_GET
def pio_dashboard(request: HttpRequest):
    guard = require_role(request, role=["Public Information Officer"])
    if guard is not None:
        return guard

    officer_id = request.session.get("officer_id")
    officer = OfficerUser.objects.get(user_id_PK=officer_id) if officer_id else None

    announcements = Announcement.objects.filter(is_active=True).order_by("-published_at")[:5]
    news_articles = NewsArticle.objects.filter(is_published=True).order_by("-published_at")[:5]
    events = Event.objects.order_by("-event_date", "-event_time")[:5]

    def _setting(key, default=""):
        try:
            return SystemSetting.objects.get(setting_key=key).setting_value
        except SystemSetting.DoesNotExist:
            return default

    return render(request, "website/PIO/pio_dashboard.html", {
        "officer": officer,
        "announcements": announcements,
        "news_articles": news_articles,
        "events": events,
        "site_email": _setting("contact_email", ""),
        "site_phone": _setting("contact_phone", ""),
        "site_address": _setting("office_address", ""),
        "facebook_url": _setting("facebook_url", ""),
        "mission": _setting("mission", ""),
        "vision": _setting("vision", ""),
        "objectives": _setting("objectives", ""),
        "org_description": _setting("org_description", ""),
        "history": _setting("history", ""),
        "core_values": _setting("core_values", ""),
        "org_structure": _setting("org_structure", ""),
    })


# ---- Announcements -----------------------------------------------------------

@require_GET
def pio_announcements_list(request: HttpRequest):
    guard = require_role(request, role=["Public Information Officer"])
    if guard is not None:
        return guard

    announcements = Announcement.objects.all().order_by("-published_at")
    data = []
    for a in announcements:
        data.append({
            "announcement_id": a.announcement_id_PK,
            "title": a.title,
            "category": a.category,
            "description": a.description,
            "published_by": a.published_by_user_id_FK.full_name if a.published_by_user_id_FK else "Unknown",
            "published_at": timezone.localtime(a.published_at).strftime("%Y-%m-%d %H:%M") if a.published_at else "",
            "expiry_date": a.expiry_date.strftime("%Y-%m-%d") if a.expiry_date else None,
            "is_active": a.is_active,
            "image_url": a.image.url if a.image else None,
        })

    return JsonResponse({"ok": True, "announcements": data, "total": len(data)})


@require_POST
@csrf_exempt
def pio_announcement_create(request: HttpRequest):
    guard = require_role(request, role=["Public Information Officer"])
    if guard is not None:
        return guard

    try:
        officer_id = request.session.get("officer_id")
        officer = OfficerUser.objects.get(user_id_PK=officer_id) if officer_id else None

        announcement_id = request.POST.get("announcement_id")
        title = request.POST.get("title")
        category = request.POST.get("category")
        description = request.POST.get("description")
        expiry_date = parse_aware_datetime(request.POST.get("expiry_date"))
        image = request.FILES.get("image")

        logger.info("PIO announcement create/update request - ID: %s, Title: %s, Action: %s", 
                    announcement_id, title, "Update" if announcement_id else "Create")
        
        logger.info("Request data - Title: '%s', Category: '%s', Description length: %d", 
                    title, category, len(description) if description else 0)

        if announcement_id:
            announcement = Announcement.objects.get(announcement_id_PK=announcement_id)
            announcement.title = title
            announcement.category = category
            announcement.description = description
            announcement.expiry_date = expiry_date if expiry_date else None
            if image:
                announcement.image = image
            announcement.save()
            logger.info("Announcement updated successfully: %s", announcement_id)
        else:
            announcement = Announcement.objects.create(
                title=title, category=category, description=description,
                expiry_date=expiry_date if expiry_date else None,
                published_by_user_id_FK=officer,
            )
            if image:
                announcement.image = image
                announcement.save()
            
            logger.info("New announcement created with ID: %s", announcement.announcement_id_PK)
            
            # Send notification to all members about new announcement (synchronous so
            # delivery is guaranteed on shared hosting where daemon threads get killed).
            _send_announcement_notifications_background(
                announcement.announcement_id_PK, title, category, description, expiry_date, officer
            )
            logger.info("Announcement notification delivery completed")

        return JsonResponse({"ok": True, "message": "Announcement saved", "announcement_id": announcement.announcement_id_PK})
        
    except Announcement.DoesNotExist:
        import traceback
        logger.error("Announcement not found: %s\n%s", announcement_id, traceback.format_exc())
        return JsonResponse({"ok": False, "error": "Announcement not found"}, status=404)
    except Exception as e:
        import traceback
        logger.error("Error in PIO announcement create/update: %s\n%s", e, traceback.format_exc())
        return JsonResponse({"ok": False, "error": str(e)}, status=500)


def _send_announcement_notifications_background(announcement_id, title, category, description, expiry_date, officer):
    """Send announcement notifications synchronously.

    Runs inside the PIO request (not a daemon thread) so delivery is guaranteed:
    shared hosting kills daemon threads when the request ends, which made
    push/email delivery random or never happen. In-app rows are bulk-inserted,
    push is sent in one batch, and emails go out over a single SMTP connection.
    """
    try:
        from core_system.services.notifications import _send_push_subs
        from core_system.services.email_service import send_html_emails_bulk
        from core_system.models import Member, Notification, PushSubscription
        from django.utils import timezone
        
        logger.info("Announcement notification started for announcement ID: %s", announcement_id)
        
        # Get all non-retired members
        members = Member.objects.exclude(membership_status__iexact="Retired")
        member_count = members.count()
        
        logger.info("Found %d non-retired members to send announcement notifications to", member_count)
        
        if member_count == 0:
            logger.warning("No non-retired members found to send announcement notifications to")
        else:
            posted_date = timezone.now().strftime('%B %d, %Y')
            logger.info("Will send notifications with posted_date: %s", posted_date)

            # 1) Create the in-app Notification rows SYNCHRONOUSLY (fast bulk
            #    insert). This guarantees every member gets the bell dot / in-app
            #    notification immediately.
            message = f"New announcement: {title}. {description[:100] if description else ''}"
            Notification.objects.bulk_create([
                Notification(
                    recipient_type="member",
                    recipient_id=m.member_id_PK,
                    recipient_name=m.full_name or "",
                    recipient_contact=m.email or m.contact_number or "",
                    notification_type="Announcement",
                    message=message,
                    delivery_status="Sent",
                    category="announcement",
                    channel="push",
                    sender_name=officer.full_name if officer else "PIO",
                    sender_role="Public Information Officer",
                )
                for m in members
            ])
            logger.info("Created %d in-app notification rows for announcement %s", member_count, announcement_id)

            # 2) Send device push to ALL member subscriptions in ONE batch call
            member_ids = list(members.values_list("member_id_PK", flat=True))
            subs = PushSubscription.objects.filter(member_id_FK_id__in=member_ids)
            try:
                _send_push_subs(subs, "Announcement", message, "/member/")
            except Exception as exc:
                logger.error("Push batch for announcement %s failed: %s", announcement_id, exc)

            # 3) Send announcement emails over a single SMTP connection
            email_tasks = []
            for member in members:
                contact = member.email or ""
                if "@" not in contact:
                    continue
                email_tasks.append({
                    "subject": "ISU CAUFA: Announcement",
                    "recipient_list": [contact],
                    "html_template": "emails/announcement_notification.html",
                    "context": {
                        "member_name": member.full_name or "Member",
                        "notification_type": "Announcement",
                        "message": message,
                        "sender_name": officer.full_name if officer else "PIO",
                        "sender_role": "Public Information Officer",
                        "receipt_number": "",
                        "announcement_title": title,
                        "announcement_category": category or "General",
                        "announcement_description": description or message,
                        "posted_date": posted_date,
                        "expiry_date": expiry_date if expiry_date else None,
                    },
                })

            if email_tasks:
                sent = send_html_emails_bulk(email_tasks)
                logger.info("Sent %d/%d announcement emails", sent, len(email_tasks))

            logger.info("Announcement notification delivery completed for announcement %s", announcement_id)
    except Exception as e:
        import traceback
        logger.error("Error in announcement notification: %s\n%s", e, traceback.format_exc())


@require_POST
@csrf_exempt
def pio_announcement_toggle(request: HttpRequest, announcement_id: int):
    guard = require_role(request, role=["Public Information Officer"])
    if guard is not None:
        return guard

    try:
        announcement = Announcement.objects.get(announcement_id_PK=announcement_id)
        announcement.is_active = not announcement.is_active
        announcement.save()
        return JsonResponse({"ok": True, "is_active": announcement.is_active})
    except Announcement.DoesNotExist:
        return JsonResponse({"ok": False, "error": "Announcement not found"}, status=404)


@require_POST
@csrf_exempt
def pio_announcement_delete(request: HttpRequest, announcement_id: int):
    guard = require_role(request, role=["Public Information Officer"])
    if guard is not None:
        return guard

    try:
        announcement = Announcement.objects.get(announcement_id_PK=announcement_id)
        announcement.delete()
        return JsonResponse({"ok": True, "message": "Announcement deleted"})
    except Announcement.DoesNotExist:
        return JsonResponse({"ok": False, "error": "Announcement not found"}, status=404)


# ---- Announcement Categories -------------------------------------------------

@require_GET
def pio_announcement_categories_list(request: HttpRequest):
    guard = require_role(request, role=["Public Information Officer"])
    if guard is not None:
        return guard
    try:
        cats = AnnouncementCategory.objects.all().values("category_id_PK", "name")
        return JsonResponse({"ok": True, "categories": list(cats)})
    except Exception as e:
        return JsonResponse({"ok": False, "error": str(e)}, status=500)


@require_POST
@csrf_exempt
def pio_announcement_category_create(request: HttpRequest):
    guard = require_role(request, role=["Public Information Officer"])
    if guard is not None:
        return guard
    try:
        data = json.loads(request.body)
        name = data.get("name", "").strip()
        if not name:
            return JsonResponse({"ok": False, "error": "Category name is required"}, status=400)
        cat, created = AnnouncementCategory.objects.get_or_create(name=name)
        return JsonResponse({
            "ok": True,
            "category": {"category_id_PK": cat.category_id_PK, "name": cat.name},
            "created": created,
        })
    except Exception as e:
        return JsonResponse({"ok": False, "error": str(e)}, status=500)


@require_POST
@csrf_exempt
def pio_announcement_category_rename(request: HttpRequest):
    guard = require_role(request, role=["Public Information Officer"])
    if guard is not None:
        return guard
    try:
        data = json.loads(request.body)
        cat_id = data.get("category_id")
        new_name = data.get("name", "").strip()
        if not cat_id or not new_name:
            return JsonResponse({"ok": False, "error": "category_id and name required"}, status=400)
        cat = AnnouncementCategory.objects.get(category_id_PK=cat_id)
        cat.name = new_name
        cat.save()
        return JsonResponse({"ok": True, "message": "Category renamed"})
    except AnnouncementCategory.DoesNotExist:
        return JsonResponse({"ok": False, "error": "Category not found"}, status=404)
    except Exception as e:
        return JsonResponse({"ok": False, "error": str(e)}, status=500)


@require_POST
@csrf_exempt
def pio_announcement_category_delete(request: HttpRequest):
    guard = require_role(request, role=["Public Information Officer"])
    if guard is not None:
        return guard
    try:
        data = json.loads(request.body)
        cat_id = data.get("category_id")
        if not cat_id:
            return JsonResponse({"ok": False, "error": "category_id required"}, status=400)
        AnnouncementCategory.objects.get(category_id_PK=cat_id).delete()
        return JsonResponse({"ok": True, "message": "Category deleted"})
    except AnnouncementCategory.DoesNotExist:
        return JsonResponse({"ok": False, "error": "Category not found"}, status=404)
    except Exception as e:
        return JsonResponse({"ok": False, "error": str(e)}, status=500)


# ---- Gallery (Albums + Photos) -----------------------------------------------

@require_GET
def pio_albums_list(request: HttpRequest):
    guard = require_role(request, role=["Public Information Officer"])
    if guard is not None:
        return guard

    albums = Album.objects.all().order_by("-created_at")
    data = []
    for album in albums:
        photo_count = album.photos.count()
        cover = album.cover_photo
        cover_url = cover.image.url if cover and cover.image else ""
        data.append({
            "album_id": album.album_id_PK,
            "title": album.title,
            "description": album.description,
            "photo_count": photo_count,
            "cover_url": cover_url,
            "is_active": album.is_active,
            "created_at": album.created_at.strftime("%Y-%m-%d") if album.created_at else "",
        })

    return JsonResponse({"ok": True, "albums": data})


@require_POST
@csrf_exempt
def pio_album_create(request: HttpRequest):
    guard = require_role(request, role=["Public Information Officer"])
    if guard is not None:
        return guard

    try:
        officer_id = request.session.get("officer_id")
        officer = OfficerUser.objects.get(user_id_PK=officer_id) if officer_id else None

        data = json.loads(request.body)
        album = Album.objects.create(
            title=data.get("title"),
            description=data.get("description", ""),
            created_by=officer,
        )
        return JsonResponse({"ok": True, "album_id": album.album_id_PK, "title": album.title})
    except Exception as e:
        return JsonResponse({"ok": False, "error": str(e)}, status=500)


@require_POST
@csrf_exempt
def pio_album_delete(request: HttpRequest, album_id: int):
    guard = require_role(request, role=["Public Information Officer"])
    if guard is not None:
        return guard

    try:
        album = Album.objects.get(album_id_PK=album_id)
        album.delete()
        return JsonResponse({"ok": True, "message": "Album deleted"})
    except Album.DoesNotExist:
        return JsonResponse({"ok": False, "error": "Album not found"}, status=404)


@require_GET
def pio_album_photos(request: HttpRequest, album_id: int):
    guard = require_role(request, role=["Public Information Officer"])
    if guard is not None:
        return guard

    try:
        album = Album.objects.get(album_id_PK=album_id)
        photos = album.photos.all().order_by("-uploaded_at")
        data = []
        for p in photos:
            data.append({
                "photo_id": p.photo_id_PK,
                "image_url": p.image.url if p.image else "",
                "caption": p.caption,
                "is_featured": p.is_featured,
                "uploaded_at": p.uploaded_at.strftime("%Y-%m-%d %H:%M") if p.uploaded_at else "",
            })
        return JsonResponse({"ok": True, "album_id": album_id, "album_title": album.title, "photos": data})
    except Album.DoesNotExist:
        return JsonResponse({"ok": False, "error": "Album not found"}, status=404)


@require_POST
@csrf_exempt
def pio_photo_upload(request: HttpRequest, album_id: int):
    guard = require_role(request, role=["Public Information Officer"])
    if guard is not None:
        return guard

    try:
        album = Album.objects.get(album_id_PK=album_id)
        officer_id = request.session.get("officer_id")
        officer = OfficerUser.objects.get(user_id_PK=officer_id) if officer_id else None

        image = request.FILES.get("image")
        if not image:
            return JsonResponse({"ok": False, "error": "No image provided"}, status=400)

        caption = request.POST.get("caption", "")
        is_featured = request.POST.get("is_featured") == "true"

        photo = Photo.objects.create(
            album=album, image=image, caption=caption,
            is_featured=is_featured, uploaded_by=officer,
        )

        if is_featured:
            album.cover_photo = photo
            album.save()

        return JsonResponse({
            "ok": True, "photo_id": photo.photo_id_PK,
            "image_url": photo.image.url,
        })
    except Album.DoesNotExist:
        return JsonResponse({"ok": False, "error": "Album not found"}, status=404)
    except Exception as e:
        return JsonResponse({"ok": False, "error": str(e)}, status=500)


@require_POST
@csrf_exempt
def pio_photo_delete(request: HttpRequest, photo_id: int):
    guard = require_role(request, role=["Public Information Officer"])
    if guard is not None:
        return guard

    try:
        photo = Photo.objects.get(photo_id_PK=photo_id)
        album = photo.album
        if album.cover_photo and album.cover_photo.photo_id_PK == photo.photo_id_PK:
            album.cover_photo = None
            album.save()
        photo.delete()
        return JsonResponse({"ok": True, "message": "Photo deleted"})
    except Photo.DoesNotExist:
        return JsonResponse({"ok": False, "error": "Photo not found"}, status=404)


@require_POST
@csrf_exempt
def pio_photo_set_featured(request: HttpRequest):
    guard = require_role(request, role=["Public Information Officer"])
    if guard is not None:
        return guard

    try:
        data = json.loads(request.body)
        photo = Photo.objects.get(photo_id_PK=data.get("photo_id"))
        photo.is_featured = not photo.is_featured
        photo.save()
        if photo.is_featured:
            photo.album.cover_photo = photo
            photo.album.save()
        return JsonResponse({"ok": True, "is_featured": photo.is_featured})
    except Photo.DoesNotExist:
        return JsonResponse({"ok": False, "error": "Photo not found"}, status=404)


# ---- About Us Content (SystemSettings) ---------------------------------------

@require_GET
def pio_about_content(request: HttpRequest):
    guard = require_role(request, role=["Public Information Officer"])
    if guard is not None:
        return guard

    def _setting(key, default=""):
        try:
            return SystemSetting.objects.get(setting_key=key).setting_value
        except SystemSetting.DoesNotExist:
            return default

    return JsonResponse({
        "ok": True,
        "mission": _setting("mission"),
        "vision": _setting("vision"),
        "objectives": _setting("objectives"),
        "org_description": _setting("org_description"),
        "history": _setting("history"),
        "core_values": _setting("core_values"),
        "org_structure": _setting("org_structure"),
        "site_email": _setting("contact_email"),
        "site_phone": _setting("contact_phone"),
        "site_address": _setting("office_address"),
        "facebook_url": _setting("facebook_url"),
    })


@require_POST
@csrf_exempt
def pio_about_save(request: HttpRequest):
    guard = require_role(request, role=["Public Information Officer"])
    if guard is not None:
        return guard

    try:
        data = json.loads(request.body)
        for key in ("mission", "vision", "objectives", "org_description",
                     "history", "core_values", "org_structure",
                     "contact_email", "contact_phone", "office_address", "facebook_url"):
            if key in data:
                SystemSetting.objects.update_or_create(
                    setting_key=key, defaults={"setting_value": str(data[key])},
                )
        return JsonResponse({"ok": True, "message": "Content saved"})
    except Exception as e:
        return JsonResponse({"ok": False, "error": str(e)}, status=500)


# ---- Public-facing events & officers (read-only) -----------------------------

@require_GET
def pio_events_list(request: HttpRequest):
    guard = require_role(request, role=["Public Information Officer"])
    if guard is not None:
        return guard

    events = Event.objects.all().order_by("-event_date", "-event_time")[:20]
    data = []
    for e in events:
        data.append({
            "event_id": e.event_id_PK,
            "title": e.title,
            "description": e.description,
            "venue": e.venue,
            "event_date": e.event_date.strftime("%Y-%m-%d") if e.event_date else "",
            "event_time": e.event_time.strftime("%I:%M %p") if e.event_time else "",
            "event_type": e.event_type,
            "status": e.status,
        })
    return JsonResponse({"ok": True, "events": data})


@require_GET
def pio_officers_list(request: HttpRequest):
    guard = require_role(request, role=["Public Information Officer"])
    if guard is not None:
        return guard

    profiles = OfficerProfile.objects.all()
    data = []
    for o in profiles:
        data.append({
            "officer_profile_id": o.officer_profile_id,
            "full_name": o.full_name,
            "position": o.position,
            "category": o.category,
            "department": o.department or "",
            "school_year": o.school_year or "",
            "term_start": o.term_start.strftime("%Y-%m-%d") if o.term_start else "",
            "term_end": o.term_end.strftime("%Y-%m-%d") if o.term_end else "",
            "email": o.email or "",
            "facebook": o.facebook or "",
            "biography": o.biography or "",
            "photo_url": o.photo.url if o.photo else "",
            "status": o.status,
        })
    return JsonResponse({"ok": True, "officers": data})


@require_POST
@csrf_exempt
def pio_officer_profile_save(request: HttpRequest):
    guard = require_role(request, role=["Public Information Officer"])
    if guard is not None:
        return guard

    try:
        officer_id = request.session.get("officer_id")
        officer = OfficerUser.objects.get(user_id_PK=officer_id) if officer_id else None

        if request.content_type and "multipart/form-data" in request.content_type:
            data = request.POST
            photo = request.FILES.get("photo")
        else:
            data = json.loads(request.body)
            photo = None

        profile_id = data.get("officer_profile_id") or None
        full_name = (data.get("full_name") or "").strip()
        if not full_name:
            return JsonResponse({"ok": False, "error": "Full name is required."}, status=400)

        def _date(val):
            return val.strip() if isinstance(val, str) and val.strip() else None

        category = (data.get("category") or "Executive Officer").strip()
        position = (data.get("position") or "").strip()
        if category == "Board of Directors":
            position = "Board Member"

        if not profile_id and category == "Board of Directors":
            existing_board = OfficerProfile.objects.filter(
                category="Board of Directors",
                full_name__iexact=full_name,
                status="Active",
            ).first()
            if existing_board:
                profile_id = existing_board.officer_profile_id

        if not position:
            return JsonResponse({"ok": False, "error": "Position is required."}, status=400)

        if category == "Executive Officer":
            dup = OfficerProfile.objects.filter(
                category="Executive Officer",
                position__iexact=position,
                status="Active",
            ).exclude(officer_profile_id=profile_id).first()
            if dup:
                return JsonResponse({
                    "ok": False,
                    "error": f"{dup.full_name} is already assigned the position \"{position}\".",
                }, status=400)

        defaults = {
            "full_name": full_name,
            "position": position,
            "category": category,
            "department": _date(data.get("department")),
            "school_year": _date(data.get("school_year")),
            "term_start": _date(data.get("term_start")),
            "term_end": _date(data.get("term_end")),
        }

        if profile_id:
            profile = OfficerProfile.objects.get(officer_profile_id=profile_id)
            for k, v in defaults.items():
                setattr(profile, k, v)
            if photo:
                profile.photo = photo
            profile.save()
        else:
            profile = OfficerProfile.objects.create(created_by=officer, status="Active", **defaults)
            if photo:
                profile.photo = photo
                profile.save()

        return JsonResponse({
            "ok": True,
            "officer": {
                "officer_profile_id": profile.officer_profile_id,
                "full_name": profile.full_name,
                "photo_url": profile.photo.url if profile.photo else "",
            },
        })
    except OfficerProfile.DoesNotExist:
        return JsonResponse({"ok": False, "error": "Officer profile not found."}, status=404)
    except Exception as e:
        return JsonResponse({"ok": False, "error": str(e)}, status=500)


@require_POST
@csrf_exempt
def pio_officer_profile_delete(request: HttpRequest, profile_id: int):
    guard = require_role(request, role=["Public Information Officer"])
    if guard is not None:
        return guard

    try:
        profile = OfficerProfile.objects.get(officer_profile_id=profile_id)
        profile.delete()
        return JsonResponse({"ok": True, "message": "Officer profile deleted"})
    except OfficerProfile.DoesNotExist:
        return JsonResponse({"ok": False, "error": "Officer profile not found."}, status=404)


@require_GET
def pio_public_resources(request: HttpRequest):
    guard = require_role(request, role=["Public Information Officer"])
    if guard is not None:
        return guard

    import os
    docs = Document.objects.filter(is_archived=False).order_by("-uploaded_at")[:30]
    data = []
    for d in docs:
        url = ""
        if d.file_path:
            try:
                rel = os.path.relpath(d.file_path, settings.MEDIA_ROOT)
                if not rel.startswith(".."):
                    url = settings.MEDIA_URL + rel.replace("\\", "/")
            except ValueError:
                url = d.file_path
        data.append({
            "document_id": d.document_id_PK,
            "title": d.title,
            "document_type": d.document_type,
            "file_name": d.file_name,
            "file_url": url,
            "uploaded_at": d.uploaded_at.strftime("%Y-%m-%d") if d.uploaded_at else "",
        })
    return JsonResponse({"ok": True, "resources": data})


# ---- News & Highlights Management -----------------------------------------

@require_GET
def pio_news_list(request: HttpRequest):
    guard = require_role(request, role=["Public Information Officer"])
    if guard is not None:
        return guard

    news = NewsArticle.objects.all().order_by("-published_at", "-created_at")
    data = []
    for n in news:
        data.append({
            "news_id": n.news_id,
            "title": n.title,
            "category": n.category.name if n.category else "Uncategorized",
            "category_id": n.category.category_id if n.category else None,
            "summary": n.summary,
            "published_at": n.published_at.strftime("%Y-%m-%d %H:%M") if n.published_at else "Draft",
            "is_featured": n.is_featured,
            "is_published": n.is_published,
            "view_count": n.view_count,
        })

    return JsonResponse({"ok": True, "news": data, "total": len(data)})


@require_GET
def pio_news_detail(request: HttpRequest, news_id: int):
    guard = require_role(request, role=["Public Information Officer"])
    if guard is not None:
        return guard

    try:
        news = NewsArticle.objects.get(news_id=news_id)
        return JsonResponse({
            "ok": True,
            "news": {
                "news_id": news.news_id,
                "title": news.title,
                "category": news.category.name if news.category else None,
                "category_id": news.category.category_id if news.category else None,
                "summary": news.summary,
                "content": news.content,
                "event_date": news.event_date.strftime("%Y-%m-%d") if news.event_date else None,
                "event_time": news.event_time.strftime("%H:%M") if news.event_time else None,
                "venue": news.venue,
                "video_url": news.video_url,
                "is_featured": news.is_featured,
                "is_published": news.is_published,
                "view_count": news.view_count,
                "gallery": [
                    {
                        "gallery_id": g.gallery_id,
                        "image_url": g.image.url if g.image else "",
                        "caption": g.caption,
                        "is_featured": g.is_featured,
                    }
                    for g in news.galleries.order_by("order", "-uploaded_at")
                ],
            }
        })
    except NewsArticle.DoesNotExist:
        return JsonResponse({"ok": False, "error": "News article not found"}, status=404)


def _normalize_video_url(url):
    """Convert common video platform URLs to an embeddable URL.

    YouTube/Vimeo/Dailymotion block direct embedding of their normal page URLs
    (X-Frame-Options), so news iframes show "refused to connect". This maps them
    to their embeddable player URLs. Any other URL (including direct .mp4 files
    or other platforms) is passed through unchanged.
    """
    if not url:
        return url
    import re
    url = url.strip()

    # YouTube: watch / youtu.be / shorts / embed
    m = re.search(r"(?:youtube\.com/watch\?.*?v=|youtu\.be/|youtube\.com/embed/|youtube\.com/shorts/)([A-Za-z0-9_-]{11})", url)
    if m:
        return f"https://www.youtube.com/embed/{m.group(1)}"

    # Vimeo: vimeo.com/<id> or vimeo.com/<id>/<slug>
    m = re.search(r"vimeo\.com/(?:video/)?(\d+)", url)
    if m:
        return f"https://player.vimeo.com/video/{m.group(1)}"

    # Dailymotion: dailymotion.com/video/<id>
    m = re.search(r"dailymotion\.com/video/([a-zA-Z0-9]+)", url)
    if m:
        return f"https://www.dailymotion.com/embed/video/{m.group(1)}"

    return url


def _video_watch_url(url):
    """Return the canonical page URL for a video, for a fallback "watch it" link.

    For embedded player URLs this maps back to the normal page URL so the link
    opens the platform's own player. For any other URL it is returned unchanged.
    """
    if not url:
        return url
    import re
    url = url.strip()

    m = re.search(r"(?:youtube\.com/(?:watch\?.*?v=|embed/|shorts/)|youtu\.be/)([A-Za-z0-9_-]{11})", url)
    if m:
        return f"https://www.youtube.com/watch?v={m.group(1)}"

    m = re.search(r"player\.vimeo\.com/video/(\d+)", url)
    if m:
        return f"https://vimeo.com/{m.group(1)}"

    m = re.search(r"dailymotion\.com/embed/video/([a-zA-Z0-9]+)", url)
    if m:
        return f"https://www.dailymotion.com/video/{m.group(1)}"

    return url


def _is_direct_video_file(url):
    """Return True if the URL points directly to a video file (.mp4/.webm/.ogg...).

    Direct files should be rendered with a native <video> tag rather than an
    iframe, since most servers send them with application/octet-stream or
    without frame-embedding headers.
    """
    if not url:
        return False
    path = url.split("?")[0].split("#")[0].lower().rstrip("/")
    return path.endswith((".mp4", ".webm", ".ogg", ".ogv", ".mov", ".m4v", ".mpg", ".mpeg", ".avi"))


def _compress_image_file(uploaded_file, max_dim=1280, quality=80):
    """Downscale and re-encode an uploaded image to shrink upload size.

    Phone photos are often 3-10MB. Downscaling to max 1280px JPEG reduces them
    to a few hundred KB, cutting upload time on shared hosting dramatically.
    Returns an InMemoryUploadedFile (or the original if PIL is unavailable).
    """
    from django.core.files.uploadedfile import InMemoryUploadedFile, TemporaryUploadedFile
    from io import BytesIO

    try:
        from PIL import Image
    except ImportError:
        return uploaded_file

    try:
        img = Image.open(uploaded_file)
        img = img.convert("RGB")
        width, height = img.size
        if width > max_dim or height > max_dim:
            ratio = min(max_dim / width, max_dim / height)
            img = img.resize((max(1, int(width * ratio)), max(1, int(height * ratio))), Image.LANCZOS)

        buf = BytesIO()
        img.save(buf, format="JPEG", quality=quality, optimize=True)
        buf.seek(0)
        name = f"{uploaded_file.name or 'image'}.jpg"
        if not name.lower().endswith(".jpg"):
            name += ".jpg"
        return InMemoryUploadedFile(
            buf, "image", name, "image/jpeg", buf.getbuffer().nbytes, uploaded_file.charset
        )
    except Exception:
        return uploaded_file


@csrf_exempt
def pio_news_create(request: HttpRequest):
    guard = require_role(request, role=["Public Information Officer"])
    if guard is not None:
        return guard

    try:
        officer_id = request.session.get("officer_id")
        officer = OfficerUser.objects.get(user_id_PK=officer_id) if officer_id else None

        news_id = request.POST.get("news_id")
        title = request.POST.get("title")
        category_id = request.POST.get("category")
        summary = request.POST.get("summary")
        content = request.POST.get("content")
        event_date = request.POST.get("event_date")
        event_time = request.POST.get("event_time")
        venue = request.POST.get("venue")
        video_url = _normalize_video_url(request.POST.get("video_url"))
        is_featured = request.POST.get("is_featured") == "on"
        is_published = request.POST.get("is_published") == "on"
        featured_image = request.FILES.get("featured_image")
        if featured_image:
            featured_image = _compress_image_file(featured_image)
        gallery_images = [ _compress_image_file(g) for g in request.FILES.getlist("gallery_images") ]
        remove_gallery_ids = [i for i in request.POST.get("remove_gallery_ids", "").split(",") if i]

        if news_id:
            news = NewsArticle.objects.get(news_id=news_id)
            news.title = title
            news.summary = summary
            news.content = content
            news.event_date = event_date if event_date else None
            news.event_time = event_time if event_time else None
            news.venue = venue
            news.video_url = video_url
            news.is_featured = is_featured
            news.is_published = is_published
            if category_id:
                news.category = NewsCategory.objects.get(category_id=category_id)
            if featured_image:
                news.featured_image = featured_image
            if is_published and not news.published_at:
                news.published_at = timezone.now()
            news.save()
        else:
            category = NewsCategory.objects.get(category_id=category_id) if category_id else None
            news = NewsArticle.objects.create(
                title=title,
                summary=summary,
                content=content,
                event_date=event_date if event_date else None,
                event_time=event_time if event_time else None,
                venue=venue,
                video_url=video_url,
                is_featured=is_featured,
                is_published=is_published,
                category=category,
                author=officer,
                published_at=timezone.now() if is_published else None,
            )
            if featured_image:
                news.featured_image = featured_image
                news.save()

        if remove_gallery_ids:
            NewsGallery.objects.filter(
                article=news, gallery_id__in=remove_gallery_ids
            ).delete()

        if gallery_images:
            start_order = news.galleries.aggregate(max_order=Max("order"))["max_order"] or -1
            for i, img in enumerate(gallery_images):
                NewsGallery.objects.create(
                    article=news,
                    image=img,
                    caption="",
                    is_featured=(i == 0 and not news.featured_image),
                    order=start_order + 1 + i,
                )

        return JsonResponse({"ok": True, "message": "News article saved", "news_id": news.news_id})
    except NewsArticle.DoesNotExist:
        return JsonResponse({"ok": False, "error": "News article not found"}, status=404)
    except Exception as e:
        return JsonResponse({"ok": False, "error": str(e)}, status=500)


@require_POST
@csrf_exempt
def pio_news_delete(request: HttpRequest, news_id: int):
    guard = require_role(request, role=["Public Information Officer"])
    if guard is not None:
        return guard

    try:
        news = NewsArticle.objects.get(news_id=news_id)
        news.delete()
        return JsonResponse({"ok": True, "message": "News article deleted"})
    except NewsArticle.DoesNotExist:
        return JsonResponse({"ok": False, "error": "News article not found"}, status=404)


@require_GET
def pio_news_categories_list(request: HttpRequest):
    guard = require_role(request, role=["Public Information Officer"])
    if guard is not None:
        return guard

    try:
        cats = NewsCategory.objects.filter(is_active=True).values("category_id", "name")
        return JsonResponse({"ok": True, "categories": list(cats)})
    except Exception as e:
        return JsonResponse({"ok": False, "error": str(e)}, status=500)


@require_POST
@csrf_exempt
def pio_news_category_create(request: HttpRequest):
    guard = require_role(request, role=["Public Information Officer"])
    if guard is not None:
        return guard

    try:
        data = json.loads(request.body)
        name = data.get("name", "").strip()
        if not name:
            return JsonResponse({"ok": False, "error": "Category name is required"}, status=400)
        
        # Generate slug from name
        slug = name.lower().replace(" ", "-").replace(",", "").replace(".", "")
        
        cat, created = NewsCategory.objects.get_or_create(
            name=name,
            defaults={"slug": slug}
        )
        return JsonResponse({
            "ok": True,
            "category": {"category_id": cat.category_id, "name": cat.name},
            "created": created,
        })
    except Exception as e:
        return JsonResponse({"ok": False, "error": str(e)}, status=500)


@require_POST
@csrf_exempt
def pio_news_category_rename(request: HttpRequest):
    guard = require_role(request, role=["Public Information Officer"])
    if guard is not None:
        return guard

    try:
        data = json.loads(request.body)
        cat_id = data.get("category_id")
        new_name = data.get("name", "").strip()
        if not cat_id or not new_name:
            return JsonResponse({"ok": False, "error": "category_id and name required"}, status=400)
        
        cat = NewsCategory.objects.get(category_id=cat_id)
        cat.name = new_name
        cat.slug = new_name.lower().replace(" ", "-").replace(",", "").replace(".", "")
        cat.save()
        return JsonResponse({"ok": True, "message": "Category renamed"})
    except NewsCategory.DoesNotExist:
        return JsonResponse({"ok": False, "error": "Category not found"}, status=404)
    except Exception as e:
        return JsonResponse({"ok": False, "error": str(e)}, status=500)


@require_POST
@csrf_exempt
def pio_news_category_delete(request: HttpRequest):
    guard = require_role(request, role=["Public Information Officer"])
    if guard is not None:
        return guard

    try:
        data = json.loads(request.body)
        cat_id = data.get("category_id")
        if not cat_id:
            return JsonResponse({"ok": False, "error": "category_id required"}, status=400)
        
        cat = NewsCategory.objects.get(category_id=cat_id)
        cat.delete()
        return JsonResponse({"ok": True, "message": "Category deleted"})
    except NewsCategory.DoesNotExist:
        return JsonResponse({"ok": False, "error": "Category not found"}, status=404)
    except Exception as e:
        return JsonResponse({"ok": False, "error": str(e)}, status=500)


# ---- Hero Carousel -----------------------------------------------------------

@require_GET
def pio_hero_list(request: HttpRequest):
    guard = require_role(request, role=["Public Information Officer"])
    if guard is not None:
        return guard

    slides = HeroSlide.objects.all()
    data = []
    for s in slides:
        data.append({
            "hero_id": s.hero_id,
            "title": s.title,
            "subtitle": s.subtitle,
            "image_url": s.image.url if s.image else "",
            "button_text": s.button_text,
            "button_url": s.button_url,
            "sort_order": s.sort_order,
            "is_active": s.is_active,
            "updated_at": timezone.localtime(s.updated_at).strftime("%Y-%m-%d %H:%M") if s.updated_at else "",
        })

    return JsonResponse({"ok": True, "slides": data, "total": len(data)})


@require_GET
def pio_hero_detail(request: HttpRequest, hero_id: int):
    guard = require_role(request, role=["Public Information Officer"])
    if guard is not None:
        return guard

    try:
        slide = HeroSlide.objects.get(hero_id=hero_id)
        return JsonResponse({
            "ok": True,
            "slide": {
                "hero_id": slide.hero_id,
                "title": slide.title,
                "subtitle": slide.subtitle,
                "image_url": slide.image.url if slide.image else "",
                "button_text": slide.button_text,
                "button_url": slide.button_url,
                "sort_order": slide.sort_order,
                "is_active": slide.is_active,
            }
        })
    except HeroSlide.DoesNotExist:
        return JsonResponse({"ok": False, "error": "Hero slide not found"}, status=404)


@require_POST
@csrf_exempt
def pio_hero_create(request: HttpRequest):
    guard = require_role(request, role=["Public Information Officer"])
    if guard is not None:
        return guard

    try:
        hero_id = request.POST.get("hero_id")
        title = request.POST.get("title")
        if not title:
            return JsonResponse({"ok": False, "error": "Title is required"}, status=400)

        subtitle = request.POST.get("subtitle", "")
        button_text = request.POST.get("button_text", "") or "Read More"
        button_url = request.POST.get("button_url", "")
        try:
            sort_order = int(request.POST.get("sort_order", 0))
        except (TypeError, ValueError):
            sort_order = 0
        is_active = request.POST.get("is_active") == "on"
        image = request.FILES.get("image")

        if hero_id:
            slide = HeroSlide.objects.get(hero_id=hero_id)
            slide.title = title
            slide.subtitle = subtitle
            slide.button_text = button_text
            slide.button_url = button_url
            slide.sort_order = sort_order
            slide.is_active = is_active
            if image:
                slide.image = image
            slide.save()
            return JsonResponse({"ok": True, "hero_id": slide.hero_id, "message": "Hero slide updated"})
        else:
            slide = HeroSlide.objects.create(
                title=title,
                subtitle=subtitle,
                button_text=button_text,
                button_url=button_url,
                sort_order=sort_order,
                is_active=is_active,
            )
            if image:
                slide.image = image
                slide.save()
            return JsonResponse({"ok": True, "hero_id": slide.hero_id, "message": "Hero slide created"})
    except HeroSlide.DoesNotExist:
        return JsonResponse({"ok": False, "error": "Hero slide not found"}, status=404)
    except Exception as e:
        return JsonResponse({"ok": False, "error": str(e)}, status=500)


@require_POST
@csrf_exempt
def pio_hero_toggle(request: HttpRequest, hero_id: int):
    guard = require_role(request, role=["Public Information Officer"])
    if guard is not None:
        return guard

    try:
        slide = HeroSlide.objects.get(hero_id=hero_id)
        slide.is_active = not slide.is_active
        slide.save()
        return JsonResponse({"ok": True, "is_active": slide.is_active})
    except HeroSlide.DoesNotExist:
        return JsonResponse({"ok": False, "error": "Hero slide not found"}, status=404)


@require_POST
@csrf_exempt
def pio_hero_delete(request: HttpRequest, hero_id: int):
    guard = require_role(request, role=["Public Information Officer"])
    if guard is not None:
        return guard

    try:
        slide = HeroSlide.objects.get(hero_id=hero_id)
        slide.delete()
        return JsonResponse({"ok": True, "message": "Hero slide deleted"})
    except HeroSlide.DoesNotExist:
        return JsonResponse({"ok": False, "error": "Hero slide not found"}, status=404)
