"""
Font Manager — handles font loading with Cyrillic support.
Premium font pairings for Instagram carousel designs.

Available font families (all with Cyrillic support):
- Poppins: Modern geometric sans-serif (like Montserrat)
- Lato: Elegant humanist sans-serif with full weight range
- Roboto: Google's flagship UI font
- Lora: Beautiful variable serif
- Liberation Sans/Serif: Metrically compatible with Arial/Times
- Carlito: Calibri-compatible
- DejaVu Sans/Serif: Comprehensive Unicode
- NimbusSans/Roman: High-quality URW fonts
- URWGothic: Avant Garde style
- P052: Palatino-style serif
"""

import os
from functools import lru_cache
from PIL import ImageFont

FONTS_DIR = os.path.join(
    os.path.dirname(__file__), "..", "..", "..", "assets", "fonts"
)

# ═══════════════════════════════════════════════════════════════
# FONT PAIRINGS — curated combinations for premium designs
# Each pairing defines: display (titles), text (body), accent (numbers/highlights)
# ═══════════════════════════════════════════════════════════════

FONT_PAIRINGS = {
    # Modern & Clean
    "modern_clean": {
        "name": "Современный",
        "display_bold": "Roboto-Black.ttf",
        "display_medium": "Roboto-Bold.ttf",
        "text_regular": "Roboto-Regular.ttf",
        "text_light": "Roboto-Light.ttf",
        "accent_bold": "Roboto-Bold.ttf",
        "accent_medium": "Roboto-Medium.ttf",
        "number_display": "Lato-Black.ttf",
    },
    # Elegant Serif + Sans
    "elegant_serif": {
        "name": "Элегантный",
        "display_bold": "P052-Bold.otf",
        "display_medium": "P052-Roman.otf",
        "text_regular": "Lato-Regular.ttf",
        "text_light": "Lato-Light.ttf",
        "accent_bold": "Lato-Bold.ttf",
        "accent_medium": "Lato-Medium.ttf",
        "number_display": "P052-Bold.otf",
    },
    # Bold Impact
    "bold_impact": {
        "name": "Жирный",
        "display_bold": "Lato-Black.ttf",
        "display_medium": "Lato-Heavy.ttf",
        "text_regular": "Lato-Regular.ttf",
        "text_light": "Lato-Light.ttf",
        "accent_bold": "Lato-Black.ttf",
        "accent_medium": "Lato-Bold.ttf",
        "number_display": "Lato-Black.ttf",
    },
    # Minimal Light
    "minimal_light": {
        "name": "Минимализм",
        "display_bold": "Lato-Semibold.ttf",
        "display_medium": "Lato-Regular.ttf",
        "text_regular": "Lato-Light.ttf",
        "text_light": "Lato-Thin.ttf",
        "accent_bold": "Lato-Medium.ttf",
        "accent_medium": "Lato-Regular.ttf",
        "number_display": "Lato-Hairline.ttf",
    },
    # Business Pro
    "business_pro": {
        "name": "Бизнес",
        "display_bold": "LiberationSans-Bold.ttf",
        "display_medium": "Carlito-Bold.ttf",
        "text_regular": "Carlito-Regular.ttf",
        "text_light": "LiberationSans-Regular.ttf",
        "accent_bold": "LiberationSansNarrow-Bold.ttf",
        "accent_medium": "LiberationSansNarrow-Regular.ttf",
        "number_display": "LiberationSans-Bold.ttf",
    },
    # Editorial (serif display + clean body)
    "editorial": {
        "name": "Редакторский",
        "display_bold": "NimbusRoman-Bold.otf",
        "display_medium": "NimbusRoman-Regular.otf",
        "text_regular": "NimbusSans-Regular.otf",
        "text_light": "NimbusSans-Regular.otf",
        "accent_bold": "NimbusSans-Bold.otf",
        "accent_medium": "NimbusSans-Regular.otf",
        "number_display": "NimbusRoman-Bold.otf",
    },
    # Luxury (condensed + wide)
    "luxury": {
        "name": "Люкс",
        "display_bold": "Lato-Heavy.ttf",
        "display_medium": "Lato-Bold.ttf",
        "text_regular": "Lato-Light.ttf",
        "text_light": "Lato-Thin.ttf",
        "accent_bold": "Lato-Bold.ttf",
        "accent_medium": "Lato-Semibold.ttf",
        "number_display": "Lato-Hairline.ttf",
    },
    # Classic Gothic
    "gothic": {
        "name": "Готика",
        "display_bold": "URWGothic-Demi.otf",
        "display_medium": "URWGothic-Book.otf",
        "text_regular": "DejaVuSans.ttf",
        "text_light": "DejaVuSans-ExtraLight.ttf",
        "accent_bold": "URWGothic-Demi.otf",
        "accent_medium": "URWGothic-Book.otf",
        "number_display": "URWGothic-Demi.otf",
    },
}


# ═══════════════════════════════════════════════════════════════
# FONT LOADING
# ═══════════════════════════════════════════════════════════════

# Fallback chain
_FALLBACK_BOLD = [
    "Poppins-Bold.ttf",
    "Lato-Bold.ttf",
    "Roboto-Bold.ttf",
    "DejaVuSans-Bold.ttf",
    "LiberationSans-Bold.ttf",
    "NimbusSans-Bold.otf",
]

_FALLBACK_REGULAR = [
    "Roboto-Regular.ttf",
    "Lato-Regular.ttf",
    "DejaVuSans.ttf",
    "LiberationSans-Regular.ttf",
    "NimbusSans-Regular.otf",
]


@lru_cache(maxsize=128)
def load_font(font_file: str, size: int) -> ImageFont.FreeTypeFont:
    """Load a specific font file at given size. Cached."""
    # Try project fonts dir
    path = os.path.join(FONTS_DIR, font_file)
    try:
        return ImageFont.truetype(path, size)
    except (IOError, OSError):
        pass

    # Try system paths
    for base in [
        "/usr/share/fonts/truetype/google-fonts/",
        "/usr/share/fonts/truetype/lato/",
        "/usr/share/fonts/truetype/dejavu/",
        "/usr/share/fonts/truetype/liberation/",
        "/usr/share/fonts/truetype/crosextra/",
        "/usr/share/fonts/opentype/urw-base35/",
    ]:
        try:
            return ImageFont.truetype(os.path.join(base, font_file), size)
        except (IOError, OSError):
            pass

    # Fallback
    fallbacks = _FALLBACK_BOLD if "Bold" in font_file or "Black" in font_file or "Heavy" in font_file else _FALLBACK_REGULAR
    for fb in fallbacks:
        fb_path = os.path.join(FONTS_DIR, fb)
        try:
            return ImageFont.truetype(fb_path, size)
        except (IOError, OSError):
            pass

    return ImageFont.load_default()


def get_font(pairing: str, role: str, size: int) -> ImageFont.FreeTypeFont:
    """
    Get font by pairing name and role.

    Roles:
    - display_bold: Main titles, headlines
    - display_medium: Subtitles
    - text_regular: Body text
    - text_light: Secondary text, captions
    - accent_bold: Emphasized elements
    - accent_medium: Tags, labels
    - number_display: Large decorative numbers
    """
    config = FONT_PAIRINGS.get(pairing, FONT_PAIRINGS["modern_clean"])
    font_file = config.get(role, config.get("text_regular", "Roboto-Regular.ttf"))
    return load_font(font_file, size)


def get_pairing_names() -> dict[str, str]:
    """Return dict of pairing_id -> display_name."""
    return {k: v["name"] for k, v in FONT_PAIRINGS.items()}
