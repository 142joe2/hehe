import io
from pathlib import Path

from django.conf import settings

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

GREEN = colors.HexColor("#2d5016")
GOLD = colors.HexColor("#d4af37")
ORANGE = colors.HexColor("#FFA500")
CREAM = colors.HexColor("#fffdf0")
DARK = colors.HexColor("#333333")

CAMPUS_ADDRESS = (
    "18 Dacanay Street, Barangay San Fermin, "
    "Cauayan City, Isabela, 3305, Philippines"
)


def _resolve_image(value):
    """Accept a local absolute path, a /media/... path, or a /static/... path."""
    if not value:
        return None
    try:
        raw = str(value)
        p = Path(raw)
        if p.is_absolute() and p.exists():
            return str(p)
        if raw.startswith("/media/"):
            cand = Path(settings.MEDIA_ROOT) / raw.lstrip("/media/")
            if cand.exists():
                return str(cand)
        if raw.startswith("/"):
            cand = Path(settings.BASE_DIR).resolve() / raw.lstrip("/")
            if cand.exists():
                return str(cand)
    except (OSError, ValueError):
        return None
    return None


def _wrap(c, text, font, size, max_width):
    c.setFont(font, size)
    words = text.split()
    lines = []
    current = ""
    for word in words:
        candidate = (current + " " + word).strip()
        if c.stringWidth(candidate, font, size) <= max_width:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def _draw_ornament(c, x, y, r=14):
    c.setStrokeColor(GOLD)
    c.setLineWidth(2)
    c.circle(x, y, r, stroke=1, fill=0)
    c.setStrokeColor(GREEN)
    c.setLineWidth(1.5)
    c.circle(x, y, r * 0.72, stroke=1, fill=0)
    c.line(x, y - r - 3, x, y + r + 3)
    c.line(x - r - 3, y, x + r + 3, y)


def _draw_floral(c, x, y, mirror=False):
    petals = [
        (0, 1, GOLD),
        (0.85, 0.5, ORANGE),
        (0.85, -0.5, GOLD),
        (0, -1, ORANGE),
        (-0.85, -0.5, GOLD),
        (-0.85, 0.5, ORANGE),
    ]
    c.saveState()
    c.translate(x, y)
    if mirror:
        c.scale(-1, 1)
    for px, py, col in petals:
        c.setFillColor(col)
        c.ellipse(px - 5, py - 8, px + 5, py + 8, stroke=0, fill=1)
    c.setFillColor(GOLD)
    c.circle(0, 0, 4, stroke=0, fill=1)
    c.restoreState()


def _draw_seal(c, path, x, y, radius=36):
    if not path:
        return
    try:
        c.saveState()
        clip = c.beginPath()
        clip.circle(x, y, radius)
        c.clipPath(clip, stroke=0, fill=1)
        c.drawImage(
            path,
            x - radius,
            y - radius,
            radius * 2,
            radius * 2,
            mask="auto",
            preserveAspectRatio=True,
            anchor="c",
        )
        c.restoreState()
        c.setStrokeColor(GOLD)
        c.setLineWidth(2.5)
        c.circle(x, y, radius, stroke=1, fill=0)
        c.setStrokeColor(GREEN)
        c.setLineWidth(1)
        c.circle(x, y, radius - 3, stroke=1, fill=0)
    except Exception:
        pass


def generate_certificate_pdf(cert_data):
    """Render an A4-landscape Certificate of Attendance using reportlab."""
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=landscape(A4))
    c.setTitle("Certificate of Attendance")
    w, h = landscape(A4)
    M = 10 * mm

    # Background
    c.setFillColor(CREAM)
    c.rect(0, 0, w, h, stroke=0, fill=1)

    # Borders (green / gold / fine green)
    c.setStrokeColor(GREEN)
    c.setLineWidth(8)
    c.rect(M - 6, M - 6, w - 2 * M + 12, h - 2 * M + 12, stroke=1, fill=0)
    c.setStrokeColor(GOLD)
    c.setLineWidth(4)
    c.rect(M + 6, M + 6, w - 2 * M - 12, h - 2 * M - 12, stroke=1, fill=0)
    c.setStrokeColor(GREEN)
    c.setLineWidth(1.5)
    c.rect(M + 12, M + 12, w - 2 * M - 24, h - 2 * M - 24, stroke=1, fill=0)

    # Decorative top / bottom bands (alternating green/gold)
    band_x0, band_x1 = M + 28, w - M - 28
    for band_y in (h - M - 20, M + 14):
        x = band_x0
        i = 0
        while x < band_x1:
            seg = min(18, band_x1 - x)
            c.setFillColor(GREEN if i % 2 == 0 else GOLD)
            c.rect(x, band_y, seg, 6, stroke=0, fill=1)
            x += 18
            i += 1
        c.setStrokeColor(GREEN)
        c.setLineWidth(1)
        c.line(band_x0, band_y, band_x1, band_y)
        c.line(band_x0, band_y + 6, band_x1, band_y + 6)

    # Corner ornaments + florals
    _draw_ornament(c, M + 24, h - M - 24)
    _draw_ornament(c, w - M - 24, h - M - 24)
    _draw_ornament(c, M + 24, M + 24)
    _draw_ornament(c, w - M - 24, M + 24)
    _draw_floral(c, M + 8, h - M - 8)
    _draw_floral(c, w - M - 8, h - M - 8, mirror=True)
    _draw_floral(c, M + 8, M + 8)
    _draw_floral(c, w - M - 8, M + 8, mirror=True)

    # Watermark logo (transparency is baked directly into the pixels by
    # compositing the faded logo over the cream background, so it renders as a
    # faint watermark on every reportlab build / PDF viewer without relying on
    # alpha-channel or soft-mask support).
    wm_path = Path(settings.BASE_DIR) / "static" / "img" / "isu_caufa_official.png"
    if wm_path.exists():
        try:
            from PIL import Image, ImageEnhance

            CREAM_RGB = (0xFF, 0xFD, 0xF0)
            img = Image.open(str(wm_path)).convert("RGBA")
            alpha = img.split()[3]
            alpha = ImageEnhance.Brightness(alpha).enhance(0.08)
            img.putalpha(alpha)
            base = Image.new("RGBA", img.size, CREAM_RGB + (255,))
            base.alpha_composite(img)
            base = base.convert("RGB")
            c.saveState()
            clip = c.beginPath()
            clip.circle(w / 2, h / 2, 100)
            c.clipPath(clip, stroke=0, fill=1)
            c.drawImage(
                ImageReader(base),
                w / 2 - 100,
                h / 2 - 100,
                200,
                200,
                preserveAspectRatio=True,
            )
            c.restoreState()
        except Exception:
            pass

    # Header
    c.setFont("Times-Bold", 8)
    c.setFillColor(GREEN)
    c.drawCentredString(w / 2, h - M - 30, "REPUBLIC OF THE PHILIPPINES")

    c.setFont("Times-Bold", 17)
    c.drawCentredString(w / 2, h - M - 76, "ISABELA STATE UNIVERSITY  CAUAYAN")

    c.setFont("Times-Bold", 12)
    c.drawCentredString(w / 2, h - M - 92, "FACULTY ASSOCIATION (ISU-CAUFA)")

    c.setFont("Times-Roman", 9)
    c.setFillColor(DARK)
    c.drawCentredString(w / 2, h - M - 106, CAMPUS_ADDRESS)

    # Seals
    left_seal = Path(settings.BASE_DIR) / "static" / "img" / "isu_official.png"
    right_seal = Path(settings.BASE_DIR) / "static" / "img" / "isu_caufa_official.png"
    seal_y = h - M - 88
    _draw_seal(c, str(left_seal) if left_seal.exists() else None, M + 58, seal_y)
    _draw_seal(c, str(right_seal) if right_seal.exists() else None, w - M - 58, seal_y)

    # Title
    c.setFont("Times-Bold", 40)
    c.setFillColor(GREEN)
    c.drawCentredString(w / 2, h - M - 175, "CERTIFICATE")

    c.setFont("Times-BoldItalic", 20)
    c.setFillColor(GOLD)
    c.drawCentredString(w / 2, h - M - 205, "OF ATTENDANCE")

    # Intro
    c.setFont("Times-Italic", 12)
    c.setFillColor(DARK)
    c.drawCentredString(w / 2, h - M - 232, "This certificate is presented to")

    # Recipient name (bordered by lines)
    name = (cert_data.get("recipient_name") or "").strip()
    name_w = 360
    c.setStrokeColor(DARK)
    c.setLineWidth(1.5)
    c.line(w / 2 - name_w / 2, h - M - 245, w / 2 + name_w / 2, h - M - 245)
    c.line(w / 2 - name_w / 2, h - M - 275, w / 2 + name_w / 2, h - M - 275)
    c.setFont("Times-Bold", 18)
    c.setFillColor(GREEN)
    c.drawCentredString(w / 2, h - M - 262, name or "[COMPLETE NAME OF RECIPIENT]")

    # Body
    event_title = (cert_data.get("event_title") or "").strip()
    event_date = (cert_data.get("event_date") or "").strip()
    event_venue = (cert_data.get("event_venue") or "").strip()
    body = (
        f"for attending the {event_title} organized by the Isabela State "
        "University Faculty Association (ISU-CAUFA), held on "
        f"{event_date} at {event_venue}"
    )
    font, size = "Times-Roman", 11
    lines = _wrap(c, body, font, size, 520)
    y0 = h - M - 290
    c.setFont(font, size)
    c.setFillColor(DARK)
    for i, ln in enumerate(lines):
        c.drawCentredString(w / 2, y0 - i * 14, ln)
    body_bottom = y0 - (len(lines) - 1) * 14

    # Date line
    day = cert_data.get("day") or ""
    month_year = (cert_data.get("month_year") or "").strip()
    place = (cert_data.get("place") or "").strip()
    date_line = f"Given this {day} of {month_year} at {place}"
    c.setFont("Times-Italic", 11)
    c.setFillColor(DARK)
    c.drawCentredString(w / 2, body_bottom - 28, date_line)

    # Signatures
    sigs = []
    sigs.append(
        (
            cert_data.get("president_name") or "",
            cert_data.get("president_position") or "ISU-CAUFA President",
            cert_data.get("president_signature_url"),
        )
    )
    sigs.append(
        (
            cert_data.get("secretary_name") or "",
            cert_data.get("secretary_position") or "ISU CAUFA Secretary",
            cert_data.get("secretary_signature_url"),
        )
    )
    if cert_data.get("faculty_regent_name"):
        sigs.append(
            (
                cert_data.get("faculty_regent_name") or "",
                cert_data.get("faculty_regent_position") or "Faculty Regent",
                cert_data.get("faculty_regent_signature_url"),
            )
        )

    slot_w = 230
    n = len(sigs)
    start_x = w / 2 - ((n - 1) * slot_w) / 2
    sig_top = body_bottom - 60

    for idx, (sig_name, sig_title, sig_url) in enumerate(sigs):
        x = start_x + idx * slot_w
        img = _resolve_image(sig_url)
        line_y = sig_top
        if img:
            try:
                ir = ImageReader(img)
                iw, ih = ir.getSize()
                max_h, max_w = 42.0, 160.0
                ratio = min(max_w / iw, max_h / ih)
                dw, dh = iw * ratio, ih * ratio
                c.drawImage(
                    img,
                    x - dw / 2,
                    line_y - dh,
                    dw,
                    dh,
                    mask="auto",
                    preserveAspectRatio=True,
                )
                line_y = line_y - dh - 4
            except Exception:
                pass
        if not img:
            c.setStrokeColor(DARK)
            c.setLineWidth(1.5)
            c.line(x - 75, line_y, x + 75, line_y)
        name_y = line_y - 10
        c.setFont("Times-Bold", 10)
        c.setFillColor(GREEN)
        c.drawCentredString(x, name_y, (sig_name or "").upper())
        c.setFont("Times-Roman", 8.5)
        c.setFillColor(DARK)
        c.drawCentredString(x, name_y - 12, sig_title or "")

    # Certificate number
    cert_no = cert_data.get("certificate_number") or ""
    c.setFont("Times-Bold", 9)
    c.setFillColor(GREEN)
    c.drawCentredString(w / 2, M + 30, f"Certificate No.: {cert_no}")

    c.showPage()
    c.save()
    return buf.getvalue()