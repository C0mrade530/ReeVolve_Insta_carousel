"""
Premium Image Generation for Instagram Carousels.
Single expert template — user-uploaded background (подложка) with text overlay.

Flow:
1. User uploads a ready background image (подложка)
2. Uploaded image = background for ALL slides (darkened for content slides)
3. Text, @username, page counter, arrows are overlaid on top

Design:
- Uploaded background as base for every slide
- @username top-left with gold accent line underneath
- Large white text on left ~55%
- Page counter "1/8" bottom-left
- ">>>" arrows bottom-right (on non-last slides)
"""

import logging
import os
import math
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageChops

from .font_manager import get_font, FONT_PAIRINGS

logger = logging.getLogger(__name__)

# Slide dimensions (Instagram 4:5)
W = 1080
H = 1350

# Single expert template colors
TMPL = {
    "bg": "#080808",
    "text": "#ffffff",
    "text2": "#b0b0b0",
    "accent": "#d4a853",
    "accent2": "#c7935a",
    "gradient_start": "#080808",
    "gradient_end": "#0f0f14",
    "font_pairing": "luxury",
}

# 12 design presets — each defines a complete color scheme
DESIGN_TEMPLATES = {
    "expert": {
        **TMPL,
        "name": "Классика",
        "bg2": "#111111",
        "gradient_dir": "vertical",
        "decor": "expert",
        "is_expert": True,
    },
    "classic": {**TMPL, "name": "Классика"},
    "minimal": {
        "bg": "#ffffff", "text": "#1a1a1a", "text2": "#666666",
        "accent": "#000000", "accent2": "#333333",
        "gradient_start": "#ffffff", "gradient_end": "#f5f5f5",
        "font_pairing": "minimal_light", "name": "Минимал",
    },
    "dark": {
        "bg": "#1a1a1a", "text": "#f0f0f0", "text2": "#999999",
        "accent": "#808080", "accent2": "#666666",
        "gradient_start": "#1a1a1a", "gradient_end": "#222222",
        "font_pairing": "modern_clean", "name": "Тёмный",
    },
    "blue": {
        "bg": "#0a1628", "text": "#ffffff", "text2": "#8eb8e5",
        "accent": "#4a90d9", "accent2": "#3a7bc8",
        "gradient_start": "#0a1628", "gradient_end": "#0f1f35",
        "font_pairing": "business_pro", "name": "Синий",
    },
    "red": {
        "bg": "#0a0a0a", "text": "#ffffff", "text2": "#b0b0b0",
        "accent": "#dc3545", "accent2": "#c82333",
        "gradient_start": "#0a0a0a", "gradient_end": "#120a0a",
        "font_pairing": "bold_impact", "name": "Красный",
    },
    "forest": {
        "bg": "#0a1a0a", "text": "#e0f0e0", "text2": "#8fbc8f",
        "accent": "#2d8a4e", "accent2": "#1e6b3a",
        "gradient_start": "#0a1a0a", "gradient_end": "#0f200f",
        "font_pairing": "modern_clean", "name": "Лес",
    },
    "emerald": {
        "bg": "#061a14", "text": "#ffffff", "text2": "#a0d8b8",
        "accent": "#50c878", "accent2": "#40a060",
        "gradient_start": "#061a14", "gradient_end": "#0a201a",
        "font_pairing": "elegant_serif", "name": "Изумруд",
    },
    "lavender": {
        "bg": "#1a0a2e", "text": "#f0e0ff", "text2": "#c39bd3",
        "accent": "#9b59b6", "accent2": "#8e44ad",
        "gradient_start": "#1a0a2e", "gradient_end": "#221238",
        "font_pairing": "editorial", "name": "Лаванда",
    },
    "pastel": {
        "bg": "#faf5f0", "text": "#4a3728", "text2": "#8b7355",
        "accent": "#d4956a", "accent2": "#c08050",
        "gradient_start": "#faf5f0", "gradient_end": "#f0ebe5",
        "font_pairing": "minimal_light", "name": "Пастель",
    },
    "contrast": {
        "bg": "#000000", "text": "#ffffff", "text2": "#cccccc",
        "accent": "#ffffff", "accent2": "#e0e0e0",
        "gradient_start": "#000000", "gradient_end": "#050505",
        "font_pairing": "bold_impact", "name": "Контраст",
    },
    "elegant": {
        "bg": "#0f0f0f", "text": "#f5f0e8", "text2": "#a09080",
        "accent": "#c0a882", "accent2": "#a89070",
        "gradient_start": "#0f0f0f", "gradient_end": "#141210",
        "font_pairing": "editorial", "name": "Элегант",
    },
    "ai_design": {
        "bg": "#0a0a0a", "text": "#ffffff", "text2": "#d4d4d4",
        "accent": "#a855f7", "accent2": "#7c3aed",
        "gradient_start": "#0a0a0a", "gradient_end": "#0f0a14",
        "font_pairing": "bold_impact", "name": "AI Design",
    },
}

# ═══════════════════════════════════════════════════════════════
# CARD-STYLE TEXT TEMPLATES (clean, modern — no photo background)
# ═══════════════════════════════════════════════════════════════

CARD_TEMPLATES = {
    "card_standard": {
        "bg": "#1a1a1a", "text": "#ffffff", "accent": "#4ade80",
        "text2": "#b0b0b0", "follow_color": "#888888",
        "font_pairing": "modern_clean", "name": "Стандарт",
    },
    "card_bright": {
        "bg": "#ff3b30", "text": "#ffffff", "accent": "#ffcc00",
        "text2": "#ffe0e0", "follow_color": "#ffe0e0",
        "font_pairing": "bold_impact", "name": "Яркий",
    },
    "card_classic": {
        "bg": "#f5f0eb", "text": "#1a1a1a", "accent": "#c8553d",
        "text2": "#5a4a3a", "follow_color": "#8a7a6a",
        "font_pairing": "elegant_serif", "name": "Классика",
    },
    "card_contrast": {
        "bg": "#000000", "text": "#ffffff", "accent": "#ff006e",
        "text2": "#cccccc", "follow_color": "#888888",
        "font_pairing": "bold_impact", "name": "Контраст",
    },
    "card_pastel": {
        "bg": "#e8d5c4", "text": "#2d1810", "accent": "#ff8c42",
        "text2": "#5a4030", "follow_color": "#8a7060",
        "font_pairing": "minimal_light", "name": "Пастель",
    },
    "card_dark": {
        "bg": "#0f0f0f", "text": "#e0e0e0", "accent": "#00d4ff",
        "text2": "#808080", "follow_color": "#606060",
        "font_pairing": "modern_clean", "name": "Тёмный",
    },
    "card_elegant": {
        "bg": "#1a0a2e", "text": "#f0e5ff", "accent": "#c084fc",
        "text2": "#a080c0", "follow_color": "#8060a0",
        "font_pairing": "editorial", "name": "Элегант",
    },
}


def get_template(template_id: str) -> dict:
    """Get template colors by ID. Falls back to classic."""
    return DESIGN_TEMPLATES.get(template_id, DESIGN_TEMPLATES["expert"])


# ═══════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════

def _hex(color: str) -> tuple:
    c = color.lstrip("#")
    return tuple(int(c[i:i+2], 16) for i in (0, 2, 4))


def _rgba(color: str, alpha: int) -> tuple:
    return _hex(color) + (alpha,)


def _lerp_color(c1: tuple, c2: tuple, t: float) -> tuple:
    return tuple(int(a + (b - a) * t) for a, b in zip(c1, c2))


def _wrap(text: str, font: ImageFont.FreeTypeFont, max_w: int) -> list[str]:
    """Word-wrap text to fit max_w pixels."""
    if not text:
        return []
    words = text.split()
    lines, cur = [], ""
    for w in words:
        test = f"{cur} {w}".strip()
        if font.getbbox(test)[2] <= max_w:
            cur = test
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def _text_shadow(draw, xy, text, font, fill, shadow_color="#00000090", offset=4):
    """Draw text with drop shadow."""
    x, y = xy
    draw.text((x + offset, y + offset), text, fill=shadow_color, font=font)
    draw.text((x, y), text, fill=fill, font=font)


def _split_into_paragraphs(text: str, max_paragraphs: int = 5) -> list[str]:
    """
    Split body text into readable paragraphs.
    First tries explicit \\n splits, then splits by sentences.
    Each paragraph = 1-2 sentences for easy reading.
    """
    # If text already has newlines, use them
    if "\n" in text:
        parts = [p.strip() for p in text.split("\n") if p.strip()]
        if len(parts) >= 2:
            return parts[:max_paragraphs]

    # Split by sentence endings (. ! ?)
    import re
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    sentences = [s.strip() for s in sentences if s.strip()]

    if len(sentences) <= 2:
        return [text]

    # Group 1-2 sentences per paragraph
    paragraphs = []
    i = 0
    while i < len(sentences):
        if i + 1 < len(sentences) and len(sentences[i]) < 60:
            # Short sentence — combine with next
            paragraphs.append(f"{sentences[i]} {sentences[i+1]}")
            i += 2
        else:
            paragraphs.append(sentences[i])
            i += 1

    return paragraphs[:max_paragraphs]


# ═══════════════════════════════════════════════════════════════
# BACKGROUND — dark gradient base (used when no NanoBanana bg)
# ═══════════════════════════════════════════════════════════════

def _make_dark_gradient() -> Image.Image:
    """Create dark cinematic gradient background."""
    img = Image.new("RGB", (W, H), "#080808")
    draw = ImageDraw.Draw(img)
    c1, c2 = _hex("#080808"), _hex("#0f0f14")
    for y in range(H):
        c = _lerp_color(c1, c2, y / H)
        draw.line([(0, y), (W, y)], fill=c)

    # Subtle radial glow from right side (where photo will be)
    glow = Image.new("RGB", (W, H), (0, 0, 0))
    glow_draw = ImageDraw.Draw(glow)
    cx, cy = int(W * 0.72), int(H * 0.40)
    ac = _hex("#d4a853")
    for r in range(500, 0, -4):
        intensity = max(0, int(18 * (1 - r / 500)))
        color = (
            min(255, ac[0] * intensity // 255),
            min(255, ac[1] * intensity // 255),
            min(255, ac[2] * intensity // 255),
        )
        glow_draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=color)

    return ImageChops.add(img, glow)


# ═══════════════════════════════════════════════════════════════
# PHOTO HANDLING
# ═══════════════════════════════════════════════════════════════

def _load_photo(path: str | None, target_h: int = 1000) -> Image.Image | None:
    """Load speaker photo, resize proportionally. Returns RGBA or None."""
    if not path or not os.path.exists(path):
        return None
    try:
        photo = Image.open(path).convert("RGBA")
        ratio = target_h / photo.height
        new_w = int(photo.width * ratio)
        return photo.resize((new_w, target_h), Image.LANCZOS)
    except Exception as e:
        logger.warning(f"[Image] Failed to load speaker photo '{path}': {e}")
        return None


def _paste_photo_right(img: Image.Image, photo: Image.Image,
                       y_offset: int = 0) -> int:
    """
    Paste photo on right side with left-edge gradient fade.
    Returns x position where photo starts.
    """
    ph_w, ph_h = photo.size
    paste_x = W - ph_w + 30  # slight right overflow OK
    paste_y = H - ph_h + y_offset

    # Gradient mask: fade left edge
    mask = Image.new("L", (ph_w, ph_h), 255)
    mask_draw = ImageDraw.Draw(mask)
    fade_zone = min(200, ph_w // 3)
    for x in range(fade_zone):
        alpha = int(255 * (x / fade_zone) ** 1.3)
        mask_draw.line([(x, 0), (x, ph_h)], fill=alpha)

    # Bottom fade
    bottom_fade = 120
    for y in range(max(0, ph_h - bottom_fade), ph_h):
        t = (y - (ph_h - bottom_fade)) / bottom_fade
        dim = 1 - t * 0.8
        for x in range(ph_w):
            cur = mask.getpixel((x, y))
            mask.putpixel((x, y), int(cur * dim))

    # Combine with photo's own alpha channel
    if photo.mode == "RGBA":
        orig_alpha = photo.split()[3]
        mask = ImageChops.darker(orig_alpha, mask)

    img_rgba = img.convert("RGBA")
    img_rgba.paste(photo, (paste_x, paste_y), mask)
    img.paste(img_rgba.convert("RGB"))

    return paste_x


# ═══════════════════════════════════════════════════════════════
# SLIDE ELEMENTS (per reference screenshot)
# ═══════════════════════════════════════════════════════════════

def _draw_top_bar(draw: ImageDraw.Draw, username: str, pairing: str):
    """@username top-left with gold underline."""
    font = get_font(pairing, "accent_medium", 28)
    text = f"@{username.upper()}"
    draw.text((65, 50), text, fill=TMPL["accent"], font=font)
    # Gold underline
    tw = font.getbbox(text)[2]
    draw.rectangle([(65, 88), (65 + tw + 10, 91)], fill=TMPL["accent"])


def _draw_page_counter(draw: ImageDraw.Draw, num: int, total: int, pairing: str,
                       center: bool = False):
    """Page counter: bottom-left or bottom-center."""
    font = get_font(pairing, "accent_medium", 28)
    text = f"{num}/{total}"
    if center:
        tw = font.getbbox(text)[2]
        draw.text(((W - tw) // 2, H - 65), text, fill=TMPL["text2"], font=font)
    else:
        draw.text((65, H - 65), text, fill=TMPL["text2"], font=font)


def _draw_arrows(draw: ImageDraw.Draw, pairing: str):
    """Swipe arrows bottom-right: >>>"""
    font = get_font(pairing, "display_bold", 36)
    draw.text((W - 160, H - 68), ">>>", fill=TMPL["accent"] + "80", font=font)


def _draw_thin_lines(draw: ImageDraw.Draw):
    """Subtle accent lines top and bottom."""
    draw.rectangle([(0, 0), (W, 2)], fill=TMPL["accent"])
    draw.rectangle([(0, H - 2), (W, H)], fill=TMPL["accent"])


# ═══════════════════════════════════════════════════════════════
# SLIDE RENDERS
# ═══════════════════════════════════════════════════════════════

def _render_cover(img: Image.Image, draw: ImageDraw.Draw,
                  title: str, username: str, pairing: str,
                  total: int, photo: Image.Image | None):
    """
    Cover slide (slide 1):
    - @USERNAME top-left with gold underline
    - Large bold title on left side
    - Photo on right
    - 1/N bottom-left, >>> bottom-right
    """
    text_max_w = 860

    if photo:
        photo_x = _paste_photo_right(img, photo)
        text_max_w = max(420, photo_x - 90)
        draw = ImageDraw.Draw(img)

    _draw_thin_lines(draw)
    _draw_top_bar(draw, username, pairing)

    # Title — large, left-aligned
    font_title = get_font(pairing, "display_bold", 62)
    lines = _wrap(title, font_title, text_max_w)
    line_h = 78

    # Center vertically with slight upward offset
    total_h = len(lines) * line_h
    start_y = max(200, (H - total_h) // 2 - 60)

    for i, line in enumerate(lines):
        y = start_y + i * line_h
        _text_shadow(draw, (65, y), line, font_title, TMPL["text"])

    # Gold accent line below title
    last_y = start_y + len(lines) * line_h + 18
    draw.rectangle([(65, last_y), (65 + min(380, text_max_w), last_y + 4)], fill=TMPL["accent"])

    _draw_page_counter(draw, 1, total, pairing)
    _draw_arrows(draw, pairing)

    return draw


def _render_content(img: Image.Image, draw: ImageDraw.Draw,
                    slide_num: int, total: int,
                    title: str, body: str, username: str,
                    pairing: str, photo: Image.Image | None):
    """
    Content slides (slides 2..N-1) — reference @IVAN.LOGINOV_AI style:
    - Title starts from MIDDLE of slide (~500px), not top
    - ALL text is WHITE, large, easily readable
    - Numbered title: "1. Title" in bold
    - Body split into paragraphs, same white color
    - Text fills bottom half of slide
    - @USERNAME top-left, page counter bottom-center, >>> bottom-right
    """
    point_num = slide_num - 1
    cx = 65  # left margin
    content_w = W - cx - 65  # ~950px

    if photo:
        small = photo.copy()
        new_h = int(photo.height * 0.75)
        ratio = new_h / small.height
        new_w = int(small.width * ratio)
        small = small.resize((new_w, new_h), Image.LANCZOS)
        photo_x = _paste_photo_right(img, small, y_offset=50)
        content_w = max(420, photo_x - cx - 40)
        draw = ImageDraw.Draw(img)

    _draw_thin_lines(draw)
    _draw_top_bar(draw, username, pairing)

    # ── Fonts ──
    font_title = get_font(pairing, "display_bold", 52)
    font_body = get_font(pairing, "display_medium", 36)  # пожирнее, белый

    title_text = f"{point_num}. {title}"
    title_lines = _wrap(title_text, font_title, content_w)
    title_line_h = 68

    paragraphs = _split_into_paragraphs(body)
    body_line_h = 52
    para_gap = 24
    divider_gap = 36  # title -> divider -> body

    # ── Pre-calculate total text block height ──
    body_total_lines = 0
    for para in paragraphs:
        body_total_lines += len(_wrap(para, font_body, content_w))

    total_text_h = (
        len(title_lines) * title_line_h +
        divider_gap +
        body_total_lines * body_line_h +
        max(0, len(paragraphs) - 1) * para_gap
    )

    # ── Vertically center text block between top bar (100) and bottom counter (H-90) ──
    usable_top = 110
    usable_bottom = H - 90
    usable_h = usable_bottom - usable_top
    start_y = usable_top + max(0, (usable_h - total_text_h) // 2)

    # ── Numbered title: "1. Title" — bold white ──
    y = start_y
    for line in title_lines:
        _text_shadow(draw, (cx, y), line, font_title, "#ffffff",
                     shadow_color="#000000c0", offset=3)
        y += title_line_h

    # Gold accent divider
    y += 10
    draw.rectangle([(cx, y), (cx + 90, y + 4)], fill=TMPL["accent"])
    y += divider_gap - 10

    # ── Body text — WHITE, bolder font, split into paragraphs ──
    for i, para in enumerate(paragraphs):
        para_lines = _wrap(para, font_body, content_w)
        for line in para_lines:
            _text_shadow(draw, (cx, y), line, font_body, "#ffffff",
                         shadow_color="#000000a0", offset=2)
            y += body_line_h

        if i < len(paragraphs) - 1:
            y += para_gap

    _draw_page_counter(draw, slide_num, total, pairing, center=True)
    _draw_arrows(draw, pairing)

    return draw


def _render_cta(img: Image.Image, draw: ImageDraw.Draw,
                total: int, cta_text: str, body: str,
                username: str, pairing: str, photo: Image.Image | None):
    """
    CTA slide (last slide) — white text, vertically centered:
    - 2-3 lines finishing the carousel (cta_text) — bold white
    - Gold divider
    - Lead magnet text (body) — white, slightly smaller
    - No button, no subscribe — clean lead magnet CTA
    - @username at bottom, page counter centered
    """
    cx = 65
    content_w = W - cx - 65

    if photo:
        photo_x = _paste_photo_right(img, photo)
        content_w = max(420, photo_x - cx - 40)
        draw = ImageDraw.Draw(img)

    _draw_thin_lines(draw)
    _draw_top_bar(draw, username, pairing)

    # ── Fonts ──
    font_cta = get_font(pairing, "display_bold", 48)
    font_lead = get_font(pairing, "display_medium", 36)
    font_user = get_font(pairing, "accent_medium", 26)

    # ── Pre-calculate heights for centering ──
    cta_lines = _wrap(cta_text, font_cta, content_w)
    cta_line_h = 64

    lead_lines = []
    lead_line_h = 52
    lead_paragraphs = []
    if body:
        lead_paragraphs = _split_into_paragraphs(body)
        for para in lead_paragraphs:
            lead_lines.extend(_wrap(para, font_lead, content_w))

    divider_h = 40  # gap for gold divider between cta and lead magnet
    username_h = 50

    total_h = (
        len(cta_lines) * cta_line_h +
        (divider_h if body else 0) +
        len(lead_lines) * lead_line_h +
        (max(0, len(lead_paragraphs) - 1) * 20 if lead_paragraphs else 0) +
        username_h
    )

    usable_top = 110
    usable_bottom = H - 90
    usable_h = usable_bottom - usable_top
    y = usable_top + max(0, (usable_h - total_h) // 2)

    # ── CTA text — bold white ──
    for line in cta_lines:
        _text_shadow(draw, (cx, y), line, font_cta, "#ffffff",
                     shadow_color="#000000c0", offset=3)
        y += cta_line_h

    # ── Lead magnet block ──
    if body:
        # Gold divider
        y += 12
        draw.rectangle([(cx, y), (cx + 90, y + 4)], fill=TMPL["accent"])
        y += divider_h - 12

        # Lead magnet text — white, paragraph-split
        for i, para in enumerate(lead_paragraphs):
            para_lines = _wrap(para, font_lead, content_w)
            for line in para_lines:
                _text_shadow(draw, (cx, y), line, font_lead, "#ffffff",
                             shadow_color="#000000a0", offset=2)
                y += lead_line_h
            if i < len(lead_paragraphs) - 1:
                y += 20

    # @username at bottom
    y += 20
    draw.text((cx, y), f"@{username}", fill=TMPL["text2"], font=font_user)

    _draw_page_counter(draw, total, total, pairing, center=True)

    return draw


# ═══════════════════════════════════════════════════════════════
# CARD-STYLE RENDERERS (text-only, clean modern layout)
# ═══════════════════════════════════════════════════════════════

def _draw_accent_text(draw: ImageDraw.Draw, text: str, xy: tuple,
                      font: ImageFont.FreeTypeFont, fill: str,
                      accent_color: str, max_w: int,
                      shadow: bool = True, uppercase: bool = True):
    """
    Render text with accent-colored highlighted words.
    Words wrapped in *asterisks* get a colored background box.
    Returns total height used.
    """
    import re
    if uppercase:
        text = text.upper()

    x_start, y = xy
    line_h = int(font.size * 1.35)

    # Split into segments: normal and *accented*
    pattern = r'\*([^*]+)\*'
    parts = re.split(pattern, text)
    is_accent = [False] + [i % 2 == 1 for i in range(len(parts) - 1)]
    # Re-index: odd indices are accent groups
    segments = []
    raw_parts = re.split(pattern, text)
    for i, part in enumerate(raw_parts):
        if not part:
            continue
        segments.append({"text": part, "accent": i % 2 == 1})

    # Word-wrap and render with accent boxes
    words_with_accent = []
    for seg in segments:
        for word in seg["text"].split():
            words_with_accent.append({"word": word, "accent": seg["accent"]})

    # Build lines
    lines = []
    cur_line = []
    cur_w = 0
    space_w = font.getbbox(" ")[2]

    for item in words_with_accent:
        w_bbox = font.getbbox(item["word"])
        w_w = w_bbox[2]
        test_w = cur_w + (space_w if cur_line else 0) + w_w
        if test_w <= max_w or not cur_line:
            cur_line.append(item)
            cur_w = test_w
        else:
            lines.append(cur_line)
            cur_line = [item]
            cur_w = w_w
    if cur_line:
        lines.append(cur_line)

    total_h = 0
    for line_items in lines:
        x = x_start
        for i, item in enumerate(line_items):
            word = item["word"]
            w_bbox = font.getbbox(word)
            w_w = w_bbox[2]
            w_h = w_bbox[3]

            if item["accent"]:
                # Draw colored background box behind accent word
                pad_x, pad_y = 8, 4
                box_y = y - pad_y
                draw.rectangle(
                    [(x - pad_x, box_y), (x + w_w + pad_x, box_y + w_h + pad_y * 2)],
                    fill=accent_color,
                )
                if shadow:
                    draw.text((x + 2, y + 2), word, fill="#00000060", font=font)
                draw.text((x, y), word, fill=fill, font=font)
            else:
                if shadow:
                    draw.text((x + 2, y + 2), word, fill="#00000040", font=font)
                draw.text((x, y), word, fill=fill, font=font)

            x += w_w + space_w
        y += line_h
        total_h += line_h

    return total_h


def _render_card_cover(img: Image.Image, tmpl: dict, title: str, body: str,
                       username: str, accent_color: str, font_pairing: str):
    """
    Card-style cover slide:
    - @username top-left (small, muted)
    - Title: large bold uppercase with accent-highlighted word
    - Body: regular text below
    - "Follow me →" bottom-left
    """
    draw = ImageDraw.Draw(img)
    bg = _hex(tmpl["bg"])
    img.paste(bg + (255,) if len(bg) == 3 else bg, [0, 0, W, H])
    draw = ImageDraw.Draw(img)

    pairing = font_pairing or tmpl.get("font_pairing", "modern_clean")
    text_color = tmpl["text"]
    muted_color = tmpl["text2"]

    # @username top-left
    font_user = get_font(pairing, "accent_medium", 26)
    draw.text((60, 55), f"@{username}", fill=muted_color, font=font_user)

    # Title — large bold with accent highlights
    font_title = get_font(pairing, "display_bold", 64)
    title_y = 140
    title_h = _draw_accent_text(
        draw, title, (60, title_y), font_title, text_color,
        accent_color, max_w=W - 120, uppercase=True,
    )

    # Body text
    body_y = title_y + title_h + 40
    font_body = get_font(pairing, "text_regular", 30)
    if not font_body:
        font_body = get_font(pairing, "display_medium", 30)

    if body:
        body_lines = _wrap(body, font_body, W - 120)
        for line in body_lines[:8]:
            draw.text((60, body_y), line, fill=muted_color, font=font_body)
            body_y += 42

    # "Follow me →" bottom-left
    font_follow = get_font(pairing, "accent_medium", 24)
    follow_color = tmpl.get("follow_color", "#888888")
    draw.text((60, H - 80), "Follow me", fill=follow_color, font=font_follow)
    draw.text((W - 100, H - 80), "→", fill=follow_color, font=font_follow)


def _render_card_content(img: Image.Image, tmpl: dict, slide_num: int, total: int,
                         title: str, body: str, username: str,
                         accent_color: str, font_pairing: str):
    """Card-style content slide with title + body text."""
    draw = ImageDraw.Draw(img)
    bg = _hex(tmpl["bg"])
    img.paste(bg + (255,) if len(bg) == 3 else bg, [0, 0, W, H])
    draw = ImageDraw.Draw(img)

    pairing = font_pairing or tmpl.get("font_pairing", "modern_clean")
    text_color = tmpl["text"]
    muted_color = tmpl["text2"]

    # @username top-left
    font_user = get_font(pairing, "accent_medium", 26)
    draw.text((60, 55), f"@{username}", fill=muted_color, font=font_user)

    # Numbered title with accent
    point_num = slide_num - 1
    numbered_title = f"{point_num}. {title}"
    font_title = get_font(pairing, "display_bold", 52)
    title_y = 140
    title_h = _draw_accent_text(
        draw, numbered_title, (60, title_y), font_title, text_color,
        accent_color, max_w=W - 120, uppercase=False,
    )

    # Body text
    body_y = title_y + title_h + 30
    font_body = get_font(pairing, "display_medium", 32)
    if body:
        paragraphs = _split_into_paragraphs(body)
        for para in paragraphs:
            para_lines = _wrap(para, font_body, W - 120)
            for line in para_lines:
                if body_y > H - 120:
                    break
                draw.text((60, body_y), line, fill=text_color, font=font_body)
                body_y += 48
            body_y += 16

    # Follow me + arrow
    font_follow = get_font(pairing, "accent_medium", 24)
    follow_color = tmpl.get("follow_color", "#888888")
    draw.text((60, H - 80), "Follow me", fill=follow_color, font=font_follow)
    draw.text((W - 100, H - 80), "→", fill=follow_color, font=font_follow)


def _render_card_cta(img: Image.Image, tmpl: dict, total: int,
                     cta_text: str, body: str, username: str,
                     accent_color: str, font_pairing: str):
    """Card-style CTA/last slide."""
    draw = ImageDraw.Draw(img)
    bg = _hex(tmpl["bg"])
    img.paste(bg + (255,) if len(bg) == 3 else bg, [0, 0, W, H])
    draw = ImageDraw.Draw(img)

    pairing = font_pairing or tmpl.get("font_pairing", "modern_clean")
    text_color = tmpl["text"]
    muted_color = tmpl["text2"]

    # @username top-left
    font_user = get_font(pairing, "accent_medium", 26)
    draw.text((60, 55), f"@{username}", fill=muted_color, font=font_user)

    # CTA title with accent
    font_cta = get_font(pairing, "display_bold", 56)
    cta_y = 200
    cta_h = _draw_accent_text(
        draw, cta_text, (60, cta_y), font_cta, text_color,
        accent_color, max_w=W - 120, uppercase=True,
    )

    # Lead magnet body
    if body:
        body_y = cta_y + cta_h + 50
        font_body = get_font(pairing, "display_medium", 32)
        body_lines = _wrap(body, font_body, W - 120)
        for line in body_lines[:6]:
            draw.text((60, body_y), line, fill=muted_color, font=font_body)
            body_y += 48

    # @username at bottom
    draw.text((60, H - 80), f"@{username}", fill=muted_color, font=font_user)


# ═══════════════════════════════════════════════════════════════
# AI DESIGN RENDERERS (AI background top + text bottom)
# ═══════════════════════════════════════════════════════════════

def _draw_ai_separator(draw: ImageDraw.Draw, img: Image.Image,
                       username: str, pairing: str, accent_color: str,
                       avatar_path: str | None = None):
    """Draw horizontal lines + circular avatar + @username at vertical midpoint."""
    mid_y = H // 2
    line_color = "#ffffff40"
    avatar_r = 24

    # Left line
    draw.line([(60, mid_y), (W // 2 - 80, mid_y)], fill=line_color, width=2)
    # Right line
    draw.line([(W // 2 + 80, mid_y), (W - 60, mid_y)], fill=line_color, width=2)

    # Avatar circle (placeholder if no avatar)
    cx, cy = W // 2, mid_y
    if avatar_path and os.path.exists(avatar_path):
        try:
            avatar = Image.open(avatar_path).convert("RGBA")
            avatar = avatar.resize((avatar_r * 2, avatar_r * 2), Image.LANCZOS)
            # Circular mask
            mask = Image.new("L", (avatar_r * 2, avatar_r * 2), 0)
            mask_draw = ImageDraw.Draw(mask)
            mask_draw.ellipse([0, 0, avatar_r * 2, avatar_r * 2], fill=255)
            img.paste(avatar, (cx - avatar_r, cy - avatar_r), mask)
        except Exception:
            # Fallback: colored circle
            draw.ellipse(
                [cx - avatar_r, cy - avatar_r, cx + avatar_r, cy + avatar_r],
                fill=accent_color,
            )
    else:
        draw.ellipse(
            [cx - avatar_r, cy - avatar_r, cx + avatar_r, cy + avatar_r],
            fill=accent_color,
        )

    # @username below center
    font_user = get_font(pairing, "accent_medium", 22)
    user_text = f"@{username}" if username else ""
    if user_text:
        tw = font_user.getbbox(user_text)[2]
        draw.text(((W - tw) // 2, mid_y + avatar_r + 8), user_text,
                  fill="#ffffff", font=font_user)


def _render_ai_cover(img: Image.Image, ai_bg_bytes: bytes | None,
                     title: str, username: str, accent_color: str,
                     pairing: str, total: int,
                     avatar_path: str | None = None):
    """
    AI Design cover slide:
    - Top ~50%: AI-generated background
    - Middle: separator with avatar + username
    - Bottom ~50%: dark bg with bold accented title
    - "СВАЙПАЙ →" at bottom
    """
    # AI background on top half
    if ai_bg_bytes:
        try:
            ai_img = Image.open(BytesIO(ai_bg_bytes)).convert("RGB")
            ai_img = ai_img.resize((W, H // 2), Image.LANCZOS)
            img.paste(ai_img, (0, 0))
        except Exception as e:
            logger.warning(f"Failed to load AI background: {e}")

    # Dark bottom half
    draw = ImageDraw.Draw(img)
    draw.rectangle([(0, H // 2 + 40), (W, H)], fill="#0a0a0a")

    # Gradient transition from image to dark
    for y in range(H // 2 - 40, H // 2 + 40):
        t = (y - (H // 2 - 40)) / 80
        alpha = int(255 * t)
        draw.line([(0, y), (W, y)], fill=(10, 10, 10, alpha))

    # Separator with avatar
    _draw_ai_separator(draw, img, username, pairing, accent_color, avatar_path)

    # Title in bottom half — bold with accent
    font_title = get_font(pairing, "display_bold", 58)
    title_y = H // 2 + 100
    _draw_accent_text(
        draw, title, (60, title_y), font_title, "#ffffff",
        accent_color, max_w=W - 120, uppercase=True, shadow=True,
    )

    # "СВАЙПАЙ →" at bottom
    font_swipe = get_font(pairing, "accent_medium", 22)
    sw_text = "СВАЙПАЙ"
    sw_w = font_swipe.getbbox(sw_text)[2]
    sw_x = (W - sw_w - 40) // 2
    draw.text((sw_x, H - 70), sw_text, fill="#ffffff80", font=font_swipe)
    draw.text((sw_x + sw_w + 12, H - 70), "→", fill="#ffffff80", font=font_swipe)


def _render_ai_content(img: Image.Image, ai_bg_bytes: bytes | None,
                       slide_num: int, total: int,
                       title: str, body: str, username: str,
                       accent_color: str, pairing: str,
                       avatar_path: str | None = None):
    """
    AI Design content slide:
    - Top ~50%: AI background
    - Middle: separator
    - Bottom: title (accent) + body text
    """
    # AI background on top half
    if ai_bg_bytes:
        try:
            ai_img = Image.open(BytesIO(ai_bg_bytes)).convert("RGB")
            ai_img = ai_img.resize((W, H // 2), Image.LANCZOS)
            img.paste(ai_img, (0, 0))
        except Exception as e:
            logger.warning(f"Failed to load AI background: {e}")

    draw = ImageDraw.Draw(img)
    draw.rectangle([(0, H // 2 + 40), (W, H)], fill="#0a0a0a")

    # Gradient transition
    for y in range(H // 2 - 40, H // 2 + 40):
        t = (y - (H // 2 - 40)) / 80
        alpha = int(255 * t)
        draw.line([(0, y), (W, y)], fill=(10, 10, 10, alpha))

    _draw_ai_separator(draw, img, username, pairing, accent_color, avatar_path)

    # Title with accent color
    font_title = get_font(pairing, "display_bold", 48)
    title_y = H // 2 + 100
    title_h = _draw_accent_text(
        draw, title, (60, title_y), font_title, "#ffffff",
        accent_color, max_w=W - 120, uppercase=True, shadow=True,
    )

    # Body text
    if body:
        body_y = title_y + title_h + 24
        font_body = get_font(pairing, "display_medium", 32)
        paragraphs = _split_into_paragraphs(body)
        for para in paragraphs:
            para_lines = _wrap(para, font_body, W - 120)
            for line in para_lines:
                if body_y > H - 80:
                    break
                _text_shadow(draw, (60, body_y), line, font_body,
                             "#ffffff", shadow_color="#00000080", offset=2)
                body_y += 46
            body_y += 12


def _render_ai_cta(img: Image.Image, ai_bg_bytes: bytes | None,
                   total: int, cta_text: str, body: str,
                   username: str, accent_color: str, pairing: str,
                   avatar_path: str | None = None):
    """AI Design CTA slide."""
    if ai_bg_bytes:
        try:
            ai_img = Image.open(BytesIO(ai_bg_bytes)).convert("RGB")
            ai_img = ai_img.resize((W, H // 2), Image.LANCZOS)
            img.paste(ai_img, (0, 0))
        except Exception as e:
            logger.warning(f"Failed to load AI background: {e}")

    draw = ImageDraw.Draw(img)
    draw.rectangle([(0, H // 2 + 40), (W, H)], fill="#0a0a0a")

    for y in range(H // 2 - 40, H // 2 + 40):
        t = (y - (H // 2 - 40)) / 80
        alpha = int(255 * t)
        draw.line([(0, y), (W, y)], fill=(10, 10, 10, alpha))

    _draw_ai_separator(draw, img, username, pairing, accent_color, avatar_path)

    # CTA text with accent
    font_cta = get_font(pairing, "display_bold", 52)
    cta_y = H // 2 + 100
    cta_h = _draw_accent_text(
        draw, cta_text, (60, cta_y), font_cta, "#ffffff",
        accent_color, max_w=W - 120, uppercase=True, shadow=True,
    )

    # Lead magnet body
    if body:
        body_y = cta_y + cta_h + 30
        font_body = get_font(pairing, "display_medium", 30)
        body_lines = _wrap(body, font_body, W - 120)
        for line in body_lines[:5]:
            draw.text((60, body_y), line, fill="#b0b0b0", font=font_body)
            body_y += 44

    # @username at bottom
    font_user = get_font(pairing, "accent_medium", 22)
    draw.text((60, H - 70), f"@{username}", fill="#808080", font=font_user)


# ═══════════════════════════════════════════════════════════════
# STICKER SUPPORT
# ═══════════════════════════════════════════════════════════════

def paste_sticker(img: Image.Image, sticker_path: str,
                  x: int, y: int, size: int = 120) -> Image.Image:
    """Paste a PNG sticker onto image at given position and size."""
    if not sticker_path or not os.path.exists(sticker_path):
        return img
    try:
        sticker = Image.open(sticker_path).convert("RGBA")
        sticker = sticker.resize((size, size), Image.LANCZOS)
        img_rgba = img.convert("RGBA")
        img_rgba.paste(sticker, (x, y), sticker)
        return img_rgba.convert("RGB")
    except Exception as e:
        logger.warning(f"Failed to paste sticker '{sticker_path}': {e}")
        return img


# ═══════════════════════════════════════════════════════════════
# MAIN ENTRY POINT
# ═══════════════════════════════════════════════════════════════

def generate_topic_slide(
    slide_number: int,
    total_slides: int,
    title: str,
    body: str,
    username: str,
    style: dict | None = None,
    font_style: str = "luxury",
    design_template: str = "expert",
    speaker_photo_path: str | None = None,
    expert_template_path: str | None = None,
    ai_background_bytes: bytes | None = None,
    accent_color: str | None = None,
    avatar_path: str | None = None,
    stickers: list | None = None,
    canvas_width: int | None = None,
    canvas_height: int | None = None,
) -> bytes:
    """
    Generate a carousel slide.

    Supports three rendering modes:
    1. Expert/classic — user-uploaded background or dark gradient
    2. Card templates (card_*) — clean text-only design
    3. AI Design — NanoBanana AI background + text
    """
    global W, H
    orig_w, orig_h = W, H

    # Apply custom canvas size if specified
    if canvas_width and canvas_height:
        W, H = canvas_width, canvas_height

    pairing = font_style if font_style in FONT_PAIRINGS else "luxury"

    # ─── CARD TEMPLATES ───
    if design_template in CARD_TEMPLATES:
        tmpl = CARD_TEMPLATES[design_template]
        ac = accent_color or tmpl["accent"]
        fp = font_style if font_style in FONT_PAIRINGS else tmpl.get("font_pairing", "modern_clean")
        img = Image.new("RGB", (W, H), _hex(tmpl["bg"]))

        if slide_number == 1:
            _render_card_cover(img, tmpl, title, body, username, ac, fp)
        elif slide_number == total_slides:
            _render_card_cta(img, tmpl, total_slides, title, body, username, ac, fp)
        else:
            _render_card_content(img, tmpl, slide_number, total_slides,
                                title, body, username, ac, fp)

        # Paste stickers if any
        if stickers:
            for s in stickers:
                img = paste_sticker(img, s.get("path", ""),
                                    s.get("x", 0), s.get("y", 0),
                                    s.get("size", 120))

        buf = BytesIO()
        img.save(buf, format="PNG", quality=95)
        W, H = orig_w, orig_h
        return buf.getvalue()

    # ─── AI DESIGN ───
    if design_template == "ai_design":
        ac = accent_color or "#a855f7"
        img = Image.new("RGB", (W, H), (10, 10, 10))

        if slide_number == 1:
            _render_ai_cover(img, ai_background_bytes, title, username,
                             ac, pairing, total_slides, avatar_path)
        elif slide_number == total_slides:
            _render_ai_cta(img, ai_background_bytes, total_slides, title, body,
                           username, ac, pairing, avatar_path)
        else:
            _render_ai_content(img, ai_background_bytes, slide_number, total_slides,
                               title, body, username, ac, pairing, avatar_path)

        if stickers:
            for s in stickers:
                img = paste_sticker(img, s.get("path", ""),
                                    s.get("x", 0), s.get("y", 0),
                                    s.get("size", 120))

        buf = BytesIO()
        img.save(buf, format="PNG", quality=95)
        W, H = orig_w, orig_h
        return buf.getvalue()

    # ─── EXPERT / CLASSIC TEMPLATES ───
    if expert_template_path and os.path.exists(expert_template_path):
        img = Image.open(expert_template_path).convert("RGB").copy()
        img = img.resize((W, H), Image.LANCZOS)

        if slide_number > 1:
            overlay = Image.new("RGBA", (W, H), (0, 0, 0, 160))
            img_rgba = img.convert("RGBA")
            img = Image.alpha_composite(img_rgba, overlay).convert("RGB")

        speaker_photo = None
    else:
        img = _make_dark_gradient()
        speaker_photo = _load_photo(speaker_photo_path, target_h=1000)

    draw = ImageDraw.Draw(img)

    if slide_number == 1:
        draw = _render_cover(img, draw, title, username, pairing,
                             total_slides, speaker_photo)
    elif slide_number == total_slides:
        draw = _render_cta(img, draw, total_slides, title, body,
                           username, pairing, speaker_photo)
    else:
        draw = _render_content(img, draw, slide_number, total_slides,
                               title, body, username, pairing, speaker_photo)

    if stickers:
        for s in stickers:
            img = paste_sticker(img, s.get("path", ""),
                                s.get("x", 0), s.get("y", 0),
                                s.get("size", 120))

    buf = BytesIO()
    img.save(buf, format="PNG", quality=95)
    W, H = orig_w, orig_h
    return buf.getvalue()


# ═══════════════════════════════════════════════════════════════
# PROPERTY CAROUSEL SLIDES (6-slide format with real photos)
# ═══════════════════════════════════════════════════════════════

def _load_photo_bg(path: str, crop_variant: int = 0) -> Image.Image:
    """
    Load and crop photo to 1080x1350 (cover-fill).
    crop_variant controls offset when the same photo is reused:
      0 = center crop (default)
      1 = upper-left bias
      2 = lower-right bias
      3 = upper-right bias
    This produces visually different slides even from the same source photo.
    """
    if not path or not os.path.exists(path):
        return _make_dark_gradient()

    try:
        img = Image.open(path).convert("RGB")
    except Exception as e:
        logger.warning(f"[Image] Failed to open background image '{path}': {e}")
        return _make_dark_gradient()

    # Cover-fill: resize to cover 1080x1350 then offset crop
    target_ratio = W / H  # 0.8
    img_ratio = img.width / img.height

    if img_ratio > target_ratio:
        new_h = H
        new_w = int(img.width * (H / img.height))
    else:
        new_w = W
        new_h = int(img.height * (W / img.width))

    img = img.resize((new_w, new_h), Image.LANCZOS)

    # Compute crop with variant offset
    extra_w = new_w - W
    extra_h = new_h - H

    if crop_variant == 0:
        left = extra_w // 2
        top = extra_h // 2
    elif crop_variant == 1:
        left = extra_w // 5
        top = extra_h // 5
    elif crop_variant == 2:
        left = extra_w * 4 // 5
        top = extra_h * 4 // 5
    elif crop_variant == 3:
        left = extra_w * 4 // 5
        top = extra_h // 5
    else:
        left = extra_w // 2
        top = extra_h // 2

    img = img.crop((left, top, left + W, top + H))
    return img


def _add_gradient_overlay(img: Image.Image, alpha: int = 160,
                          gradient_bottom: bool = False) -> Image.Image:
    """Add dark overlay. If gradient_bottom=True, fade from transparent top to dark bottom."""
    img_rgba = img.convert("RGBA")

    if gradient_bottom:
        overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)
        for y in range(H):
            # Top 30% is mostly transparent, bottom 70% gets progressively darker
            if y < H * 0.25:
                a = 0
            else:
                t = (y - H * 0.25) / (H * 0.75)
                a = int(alpha * t ** 0.8)
            draw.line([(0, y), (W, y)], fill=(0, 0, 0, a))
    else:
        overlay = Image.new("RGBA", (W, H), (0, 0, 0, alpha))

    return Image.alpha_composite(img_rgba, overlay).convert("RGB")


def _render_property_hook(img: Image.Image, title: str, subtitle: str,
                          pairing: str) -> Image.Image:
    """Slide 1: Hook — bold white title + orange italic subtitle."""
    # Bottom gradient for text readability
    img = _add_gradient_overlay(img, alpha=200, gradient_bottom=True)
    draw = ImageDraw.Draw(img)

    font_title = get_font(pairing, "display_bold", 64)
    font_sub = get_font(pairing, "display_bold", 42)

    cx = 60
    max_w = W - cx * 2  # 960px

    # Title — bold white, vertically in middle-lower area
    title_lines = _wrap(title, font_title, max_w)
    title_line_h = 82
    title_block_h = len(title_lines) * title_line_h

    # Subtitle
    sub_lines = _wrap(subtitle, font_sub, max_w)
    sub_line_h = 56
    sub_block_h = len(sub_lines) * sub_line_h

    total_h = title_block_h + 30 + sub_block_h
    start_y = H - total_h - 100  # 100px from bottom

    # Draw title
    y = start_y
    for line in title_lines:
        _text_shadow(draw, (cx, y), line, font_title, "#ffffff",
                     shadow_color="#000000d0", offset=4)
        y += title_line_h

    y += 30  # gap

    # Draw subtitle — orange/golden italic
    for line in sub_lines:
        _text_shadow(draw, (cx, y), line, font_sub, "#e88a2d",
                     shadow_color="#000000c0", offset=3)
        y += sub_line_h

    return img


def _render_property_text(img: Image.Image, title: str, body: str,
                          pairing: str, alpha: int = 180) -> Image.Image:
    """Slides 2-4: Full photo bg + dark overlay + white text."""
    img = _add_gradient_overlay(img, alpha=alpha)
    draw = ImageDraw.Draw(img)

    font_title = get_font(pairing, "display_bold", 52)
    font_body = get_font(pairing, "display_medium", 38)

    cx = 60
    max_w = W - cx * 2

    # Title — bold white
    title_lines = _wrap(title, font_title, max_w)
    title_line_h = 68

    # Body — regular white
    body_paragraphs = _split_into_paragraphs(body) if body else []
    body_line_h = 54
    para_gap = 26

    # Calculate total height for centering
    body_total_lines = 0
    for para in body_paragraphs:
        body_total_lines += len(_wrap(para, font_body, max_w))

    total_h = (
        len(title_lines) * title_line_h +
        (40 if body else 0) +
        body_total_lines * body_line_h +
        max(0, len(body_paragraphs) - 1) * para_gap
    )

    start_y = max(120, (H - total_h) // 2 - 30)

    # Title
    y = start_y
    for line in title_lines:
        _text_shadow(draw, (cx, y), line, font_title, "#ffffff",
                     shadow_color="#000000c0", offset=3)
        y += title_line_h

    # Body
    if body_paragraphs:
        y += 40
        for i, para in enumerate(body_paragraphs):
            para_lines = _wrap(para, font_body, max_w)
            for line in para_lines:
                _text_shadow(draw, (cx, y), line, font_body, "#e0e0e0",
                             shadow_color="#000000a0", offset=2)
                y += body_line_h
            if i < len(body_paragraphs) - 1:
                y += para_gap

    return img


def _render_property_features(img: Image.Image, title: str, body: str,
                              pairing: str) -> Image.Image:
    """Slide 5: Photo bg + white card overlay with features list."""
    img_rgba = img.convert("RGBA")

    # White semi-transparent card in bottom-right
    card_w, card_h = 640, 520
    card_x = W - card_w - 40
    card_y = H - card_h - 60

    card = Image.new("RGBA", (card_w, card_h), (255, 255, 255, 230))
    # Rounded corners effect (simple: just paste)
    img_rgba.paste(card, (card_x, card_y), card)
    img = img_rgba.convert("RGB")
    draw = ImageDraw.Draw(img)

    # Text inside card — dark text on white card
    font_body = get_font(pairing, "display_medium", 34)
    cx = card_x + 40
    max_w = card_w - 80

    # Combine title + body
    full_text = title
    if body:
        full_text += "\n\n" + body

    paragraphs = _split_into_paragraphs(full_text, max_paragraphs=6)
    y = card_y + 40
    line_h = 50
    para_gap = 24

    for i, para in enumerate(paragraphs):
        para_lines = _wrap(para, font_body, max_w)
        for line in para_lines:
            if y + line_h > card_y + card_h - 20:
                break
            draw.text((cx, y), line, fill="#1a1a1a", font=font_body)
            y += line_h
        if i < len(paragraphs) - 1:
            y += para_gap

    return img


def _render_property_conditions(title: str, conditions: dict,
                                cta_text: str, pairing: str) -> Image.Image:
    """Slide 6: Dark luxury bg + conditions + payment table + CTA."""
    img = _make_dark_gradient()
    draw = ImageDraw.Draw(img)

    font_title = get_font(pairing, "display_bold", 48)
    font_label = get_font(pairing, "display_bold", 36)
    font_body = get_font(pairing, "display_medium", 32)
    font_cta = get_font(pairing, "display_medium", 30)

    cx = 60
    max_w = W - cx * 2
    accent = "#e88a2d"

    # Decorative "Условия" title in orange
    y = 60
    _text_shadow(draw, (cx, y), "Условия", get_font(pairing, "display_bold", 56),
                 accent, shadow_color="#000000a0", offset=3)
    y += 90

    # Main title — white bold
    title_lines = _wrap(title, font_title, max_w)
    for line in title_lines:
        _text_shadow(draw, (cx, y), line, font_title, accent,
                     shadow_color="#000000a0", offset=2)
        y += 62
    y += 30

    # Payment info
    first_pct = conditions.get("first_payment_percent", 0)
    first_amount = conditions.get("first_payment_amount", 0)
    schedule = conditions.get("payment_schedule", [])

    if first_pct or first_amount:
        label = f"Первый взнос {first_pct}%"
        if first_amount:
            label += f" — {first_amount:,.0f} ₽".replace(",", " ")
        draw.text((cx, y), label, fill="#ffffff", font=font_label)
        y += 50

    # Payment schedule table
    if schedule:
        y += 10
        draw.text((cx, y), "Платежи:", fill="#b0b0b0", font=font_body)
        y += 44

        for payment in schedule[:8]:
            year = payment.get("year") or payment.get("date", "")
            amount = payment.get("amount", 0)
            if amount:
                amount_str = f"{amount:,.0f} ₽".replace(",", " ")
            else:
                amount_str = "по договору"
            line = f"Платеж в декабре {year} года — {amount_str}"
            draw.text((cx + 20, y), line, fill="#d0d0d0", font=font_body)
            y += 42

    # CTA
    y += 30
    if cta_text:
        cta_lines = _wrap(cta_text, font_cta, max_w)
        for line in cta_lines:
            draw.text((cx, y), line, fill="#e88a2d", font=font_cta)
            y += 44

    # Top/bottom accent lines
    draw.rectangle([(0, 0), (W, 3)], fill=accent)
    draw.rectangle([(0, H - 3), (W, H)], fill=accent)

    return img


def generate_property_carousel_slide(
    slide_number: int,
    total_slides: int,
    photo_path: str,
    title: str,
    body: str = "",
    slide_type: str = "text",
    conditions: dict | None = None,
    cta_text: str = "",
    font_style: str = "luxury",
    crop_variant: int = 0,
) -> bytes:
    """
    Generate a single property carousel slide with real photo background.

    slide_type: "hook", "anti", "location", "neighborhood", "features", "conditions"
    crop_variant: when the same photo is reused, vary the crop offset (0-3)
    """
    pairing = font_style if font_style in FONT_PAIRINGS else "luxury"

    if slide_type == "hook":
        bg = _load_photo_bg(photo_path, crop_variant=crop_variant)
        img = _render_property_hook(bg, title, body, pairing)
    elif slide_type == "features":
        bg = _load_photo_bg(photo_path, crop_variant=crop_variant)
        img = _render_property_features(bg, title, body, pairing)
    elif slide_type == "conditions":
        img = _render_property_conditions(
            title, conditions or {}, cta_text, pairing
        )
    else:
        # anti, location, neighborhood — photo bg + text overlay
        bg = _load_photo_bg(photo_path, crop_variant=crop_variant)
        alpha = 180 if slide_type == "anti" else 160
        img = _render_property_text(bg, title, body, pairing, alpha=alpha)

    # Page counter
    draw = ImageDraw.Draw(img)
    font_counter = get_font(pairing, "accent_medium", 26)
    counter_text = f"{slide_number}/{total_slides}"
    tw = font_counter.getbbox(counter_text)[2]
    draw.text(((W - tw) // 2, H - 55), counter_text, fill="#b0b0b0", font=font_counter)

    # Arrows (not on last slide)
    if slide_number < total_slides:
        font_arrow = get_font(pairing, "display_bold", 32)
        draw.text((W - 140, H - 58), ">>>", fill="#ffffff60", font=font_arrow)

    buf = BytesIO()
    img.save(buf, format="PNG", quality=95)
    return buf.getvalue()


# Backward compatibility
def generate_property_slide(
    slide_number: int,
    total_slides: int,
    headline: str,
    subtext: str,
    style: dict | None = None,
    font_style: str = "luxury",
    design_template: str = "expert",
    background_image_path: str | None = None,
) -> bytes:
    return generate_topic_slide(
        slide_number=slide_number,
        total_slides=total_slides,
        title=headline,
        body=subtext,
        username="",
        style=style,
        font_style=font_style,
        design_template=design_template,
    )


def get_template_names() -> dict[str, str]:
    """Get all available template names (design + card)."""
    names = {k: v["name"] for k, v in DESIGN_TEMPLATES.items()}
    names.update({k: v["name"] for k, v in CARD_TEMPLATES.items()})
    return names


def get_all_templates() -> list[dict]:
    """Get all templates with full metadata for frontend."""
    result = []
    for k, v in DESIGN_TEMPLATES.items():
        result.append({
            "id": k, "name": v["name"], "type": "design",
            "bg": v["bg"], "text": v["text"], "accent": v["accent"],
            "font_pairing": v.get("font_pairing", "luxury"),
        })
    for k, v in CARD_TEMPLATES.items():
        result.append({
            "id": k, "name": v["name"], "type": "card",
            "bg": v["bg"], "text": v["text"], "accent": v["accent"],
            "font_pairing": v.get("font_pairing", "modern_clean"),
        })
    return result
