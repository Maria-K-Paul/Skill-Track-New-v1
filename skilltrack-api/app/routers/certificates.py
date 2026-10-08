"""Badges (per-level PNG seals), domain certificates (PDF), and public verification."""
import math
from io import BytesIO

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import Response
from PIL import Image, ImageDraw, ImageFont
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas
from sqlalchemy import select
from sqlalchemy.orm import Session
import qrcode

from ..config import FRONTEND_URL, PUBLIC_BASE_URL
from ..database import get_db
from ..deps import require_roles
from ..models import Badge, Certificate, Domain, Enrollment, Attempt, Level, User
from ..ratelimit import verify_rate

router = APIRouter(tags=["certificates"])

student_only = require_roles("student")

# ── Colour palette ────────────────────────────────────────────────────────────

NAVY = (15, 23, 42)      # slate-950
WHITE = (255, 255, 255)

_ACCENTS: list[tuple[int, int, int]] = [
    (99, 102, 241),   # indigo-500
    (16, 185, 129),   # emerald-500
    (245, 158, 11),   # amber-500
    (59, 130, 246),   # blue-500
    (168, 85, 247),   # purple-500
    (236, 72, 153),   # pink-500
    (20, 184, 166),   # teal-500
    (249, 115, 22),   # orange-500
]

INDIGO = colors.HexColor("#4f46e5")
SLATE = colors.HexColor("#334155")
MUTED = colors.HexColor("#64748b")


def _accent(domain_id: int) -> tuple[int, int, int]:
    return _ACCENTS[domain_id % len(_ACCENTS)]


def _accent_light(base: tuple[int, int, int]) -> tuple[int, int, int]:
    return tuple(min(255, c + 70) for c in base)  # type: ignore[return-value]


def _find_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Return the best available bold font at the requested size."""
    candidates = [
        # Linux (Render / Railway)
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/ubuntu/Ubuntu-B.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
        # macOS
        "/Library/Fonts/Arial Bold.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        # Windows dev
        "C:/Windows/Fonts/arialbd.ttf",
        "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/calibrib.ttf",
    ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except (IOError, OSError):
            pass
    try:
        return ImageFont.load_default(size=size)  # Pillow >= 10.1
    except TypeError:
        return ImageFont.load_default()


def _badge_png(domain_name: str, level_name: str, level_number: int, domain_id: int) -> bytes:
    """Render a circular dark-navy seal badge and return PNG bytes."""
    SIZE = 400
    HALF = SIZE // 2

    OUTER_R = 178          # outermost radius (scallop tip)
    SCALLOP_COUNT = 32
    SCALLOP_R = 13         # radius of each scallop circle
    SCALLOP_DIST = OUTER_R - SCALLOP_R + 1
    BODY_R = OUTER_R - SCALLOP_R + 6   # navy circle covers inner halves of scallops
    RING1_R = BODY_R - 10
    RING2_R = RING1_R - 7

    acc = _accent(domain_id)
    acc_light = _accent_light(acc)

    img = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Scalloped border
    for i in range(SCALLOP_COUNT):
        angle = 2 * math.pi * i / SCALLOP_COUNT - math.pi / 2
        cx = HALF + SCALLOP_DIST * math.cos(angle)
        cy = HALF + SCALLOP_DIST * math.sin(angle)
        draw.ellipse([cx - SCALLOP_R, cy - SCALLOP_R, cx + SCALLOP_R, cy + SCALLOP_R], fill=(*acc, 255))

    # Main navy body (covers inner portion of scallops)
    draw.ellipse([HALF - BODY_R, HALF - BODY_R, HALF + BODY_R, HALF + BODY_R], fill=(*NAVY, 255))

    # Inner accent rings
    draw.ellipse([HALF - RING1_R, HALF - RING1_R, HALF + RING1_R, HALF + RING1_R], outline=(*acc, 255), width=3)
    draw.ellipse([HALF - RING2_R, HALF - RING2_R, HALF + RING2_R, HALF + RING2_R], outline=(*acc, 160), width=1)

    # Level number pill (accent colour, near top)
    PILL_W, PILL_H = 70, 38
    pill_cy = HALF - 68
    draw.rounded_rectangle(
        [HALF - PILL_W // 2, pill_cy - PILL_H // 2, HALF + PILL_W // 2, pill_cy + PILL_H // 2],
        radius=19, fill=(*acc, 255),
    )
    fn_num = _find_font(26)
    num_txt = str(level_number)
    bb = draw.textbbox((0, 0), num_txt, font=fn_num)
    draw.text((HALF - (bb[2] - bb[0]) // 2, pill_cy - (bb[3] - bb[1]) // 2), num_txt, font=fn_num, fill=(255, 255, 255, 255))

    # "LEVEL" label above pill
    fn_tiny = _find_font(13)
    lbl = "LEVEL"
    bb = draw.textbbox((0, 0), lbl, font=fn_tiny)
    draw.text((HALF - (bb[2] - bb[0]) // 2, pill_cy - PILL_H // 2 - 20), lbl, font=fn_tiny, fill=(*acc, 200))

    # Domain name (centred, white, wrapped)
    fn_dom = _find_font(21)
    max_w = (RING2_R - 14) * 2
    words = domain_name.upper().split()
    lines: list[str] = []
    cur = ""
    for word in words:
        test = (cur + " " + word).strip()
        bb = draw.textbbox((0, 0), test, font=fn_dom)
        if bb[2] - bb[0] <= max_w:
            cur = test
        else:
            if cur:
                lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)

    line_h = 28
    y = HALF - len(lines) * line_h // 2 + 16
    for line in lines:
        bb = draw.textbbox((0, 0), line, font=fn_dom)
        draw.text((HALF - (bb[2] - bb[0]) // 2, y), line, font=fn_dom, fill=(255, 255, 255, 255))
        y += line_h

    # Level name (below domain, accent-light)
    fn_lname = _find_font(15)
    lname = level_name
    bb = draw.textbbox((0, 0), lname, font=fn_lname)
    if bb[2] - bb[0] > max_w:
        while bb[2] - bb[0] > max_w and lname:
            lname = lname[:-1]
            bb = draw.textbbox((0, 0), lname + "…", font=fn_lname)
        lname += "…"
    bb = draw.textbbox((0, 0), lname, font=fn_lname)
    draw.text((HALF - (bb[2] - bb[0]) // 2, HALF + 50), lname, font=fn_lname, fill=(*acc_light, 220))

    # "SkillTrack" branding
    fn_brand = _find_font(11)
    brand = "SkillTrack"
    bb = draw.textbbox((0, 0), brand, font=fn_brand)
    draw.text((HALF - (bb[2] - bb[0]) // 2, HALF + 76), brand, font=fn_brand, fill=(255, 255, 255, 100))

    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


# ── PDF certificate ───────────────────────────────────────────────────────────

def _render_pdf(cert: Certificate, holder: User, domain: Domain) -> bytes:
    buffer = BytesIO()
    width, height = landscape(A4)
    pdf = canvas.Canvas(buffer, pagesize=(width, height))
    pdf.setTitle(f"Certificate {cert.code}")
    pdf.setAuthor("SkillTrack")

    # Double border
    pdf.setStrokeColor(INDIGO)
    pdf.setLineWidth(4)
    pdf.rect(28, 28, width - 56, height - 56)
    pdf.setLineWidth(1)
    pdf.rect(38, 38, width - 76, height - 76)

    max_text_width = width - 76 - 60

    def centred(text: str, y: float, font: str, size: int, colour=SLATE) -> None:
        while size > 8 and stringWidth(text, font, size) > max_text_width:
            size -= 1
        pdf.setFont(font, size)
        pdf.setFillColor(colour)
        pdf.drawCentredString(width / 2, y, text)

    student = cert.student_name or holder.name
    domain_label = cert.domain_name or domain.name

    centred("SKILLTRACK", height - 90, "Helvetica-Bold", 14, INDIGO)
    centred("Certificate of Achievement", height - 140, "Times-Bold", 36)
    centred("This is to certify that", height - 190, "Helvetica", 14, MUTED)
    centred(student, height - 245, "Times-BoldItalic", 34, INDIGO)

    details = " · ".join(part for part in (holder.reg_no, holder.department) if part)
    if details:
        centred(details, height - 272, "Helvetica", 12, MUTED)

    centred("has successfully completed all requirements for", height - 315, "Helvetica", 14, MUTED)
    centred(domain_label, height - 350, "Helvetica-Bold", 20)

    issued = cert.issued_at.strftime("%d %B %Y")
    centred(f"Issued on {issued}", 128, "Helvetica", 12)
    centred(f"Certificate ID: {cert.code}", 106, "Courier-Bold", 12)

    # QR encodes the verification URL; use verification_token if present (new certs),
    # fall back to code for certs issued before this feature was added.
    token = cert.verification_token or cert.code
    verify_url = f"{PUBLIC_BASE_URL}/verify/{token}"
    centred(verify_url, 88, "Helvetica", 7, MUTED)
    qr = qrcode.QRCode(box_size=4, border=0)
    qr.add_data(verify_url)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="black", back_color="white")
    pdf.drawImage(ImageReader(qr_img.get_image()), width - 110, 48, width=50, height=50)
    pdf.setFont("Helvetica", 6)
    pdf.setFillColor(MUTED)
    pdf.drawCentredString(width - 85, 40, "Scan to Verify Certificate")

    pdf.showPage()
    pdf.save()
    return buffer.getvalue()


def _load_cert_by_code(db: Session, code: str) -> tuple[Certificate, User, Domain]:
    cert = db.scalar(select(Certificate).where(Certificate.code == code))
    if cert is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Certificate not found")
    return _resolve_cert(db, cert)


def _resolve_cert(db: Session, cert: Certificate) -> tuple[Certificate, User, Domain]:
    holder = db.get(User, cert.user_id)
    if cert.domain_id:
        domain = db.get(Domain, cert.domain_id)
    else:
        level = db.get(Level, cert.level_id)
        domain = db.get(Domain, level.domain_id)
    return cert, holder, domain


# ── Student endpoints ────────────────────────────────────────────────────────

@router.get("/me/credentials")
def get_credentials(user: User = Depends(student_only), db: Session = Depends(get_db)):
    """All badges and domain certificates for the current student, grouped by domain."""
    badge_rows = db.execute(
        select(Badge, Level, Domain)
        .join(Level, Level.id == Badge.level_id)
        .join(Domain, Domain.id == Badge.domain_id)
        .where(Badge.user_id == user.id)
        .order_by(Domain.id, Level.number)
    ).all()

    badges_out = [
        {
            "id": b.id,
            "domain_id": b.domain_id,
            "domain_name": d.name,
            "level_id": b.level_id,
            "level_number": lv.number,
            "level_name": lv.name,
            "awarded_at": b.awarded_at,
        }
        for b, lv, d in badge_rows
    ]

    # All enrollments (non-common) with progress
    enr_rows = db.execute(
        select(Enrollment, Domain)
        .join(Domain, Domain.id == Enrollment.domain_id)
        .where(Enrollment.user_id == user.id, Domain.is_common.is_(False))
    ).all()

    passed_level_ids_by_domain: dict[int, set[int]] = {}
    for _, att_level_id, att_domain_id in db.execute(
        select(Attempt.user_id, Attempt.level_id, Level.domain_id)
        .join(Level, Level.id == Attempt.level_id)
        .where(Attempt.user_id == user.id, Attempt.passed.is_(True))
    ):
        passed_level_ids_by_domain.setdefault(att_domain_id, set()).add(att_level_id)

    certs_by_domain = {
        c.domain_id: c
        for c in db.scalars(
            select(Certificate).where(
                Certificate.user_id == user.id,
                Certificate.domain_id.is_not(None),
                Certificate.status != "legacy",
            )
        )
    }

    domains_out = []
    for enr, domain in enr_rows:
        total = len(domain.levels)
        passed = len(passed_level_ids_by_domain.get(domain.id, set()))
        cert = certs_by_domain.get(domain.id)
        domains_out.append({
            "domain_id": domain.id,
            "domain_name": domain.name,
            "total_levels": total,
            "passed_levels": passed,
            "completed": total > 0 and passed >= total,
            "certificate": {
                "code": cert.code,
                "issued_at": cert.issued_at,
                "status": cert.status or "valid",
            } if cert else None,
        })

    return {"badges": badges_out, "domains": domains_out}


@router.get("/me/badges/{badge_id}/png")
def download_badge(
    badge_id: int,
    inline: bool = Query(False),
    user: User = Depends(student_only),
    db: Session = Depends(get_db),
):
    badge = db.get(Badge, badge_id)
    if badge is None or badge.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Badge not found")
    level = db.get(Level, badge.level_id)
    domain = db.get(Domain, badge.domain_id)
    png = _badge_png(domain.name, level.name, level.number, domain.id)
    filename = f"badge-{domain.name.lower().replace(' ', '-')}-level-{level.number}.png"
    disposition = "inline" if inline else f'attachment; filename="{filename}"'
    return Response(
        content=png,
        media_type="image/png",
        headers={"Content-Disposition": disposition, "Cache-Control": "private, max-age=300"},
    )


@router.get("/me/certificates/{code}/pdf")
def download_certificate(
    code: str,
    inline: bool = Query(False),
    user: User = Depends(student_only),
    db: Session = Depends(get_db),
):
    cert, holder, domain = _load_cert_by_code(db, code)
    if holder.id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Certificate not found")
    disposition = "inline" if inline else f'attachment; filename="{cert.code}.pdf"'
    return Response(
        content=_render_pdf(cert, holder, domain),
        media_type="application/pdf",
        headers={"Content-Disposition": disposition, "Cache-Control": "private, max-age=300"},
    )


# ── Public verification ───────────────────────────────────────────────────────

@router.get("/verify/{token}/pdf")
def verify_certificate_pdf(token: str, req: Request, db: Session = Depends(get_db)):
    """Public inline PDF for a valid certificate — used by the verify page preview."""
    verify_rate.check(req.client.host if req.client else "unknown")
    cert = db.scalar(select(Certificate).where(Certificate.verification_token == token))
    if cert is None:
        cert = db.scalar(select(Certificate).where(Certificate.code == token))
    if cert is None or cert.status == "legacy":
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Certificate not found")
    _, holder, domain = _resolve_cert(db, cert)
    return Response(
        content=_render_pdf(cert, holder, domain),
        media_type="application/pdf",
        headers={"Content-Disposition": "inline", "Cache-Control": "public, max-age=3600"},
    )


@router.get("/verify/{token}")
def verify_certificate(token: str, req: Request, db: Session = Depends(get_db)):
    """Public (no login): verify a certificate by its verification_token or legacy code.
    Returns minimum data; no internal IDs or email addresses are exposed."""
    verify_rate.check(req.client.host if req.client else "unknown")

    # Try verification_token first (new certs), then fall back to code (legacy QR codes)
    cert = db.scalar(select(Certificate).where(Certificate.verification_token == token))
    if cert is None:
        cert = db.scalar(select(Certificate).where(Certificate.code == token))
    if cert is None or cert.status == "legacy":
        return {"valid": False}

    holder = db.get(User, cert.user_id)
    if cert.domain_id:
        domain_label = cert.domain_name or (db.get(Domain, cert.domain_id) and db.get(Domain, cert.domain_id).name)
    else:
        level = db.get(Level, cert.level_id)
        domain_label = db.get(Domain, level.domain_id).name if level else None

    return {
        "valid": True,
        "code": cert.code,
        "holder": cert.student_name or holder.name,
        "credential": domain_label,
        "issued_at": cert.issued_at,
        "status": (cert.status or "VALID").upper(),
    }
