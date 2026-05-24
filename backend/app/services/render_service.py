from datetime import datetime
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont
from sqlalchemy.orm import Session

from app.config import PUBLIC_BASE_URL, STORAGE_PATH
from app.models.carrossel import Carrossel
from app.services.log_service import registrar_log

CANVAS_SIZE = (1080, 1350)
MARGIN = 86
CONTENT_WIDTH = CANVAS_SIZE[0] - (MARGIN * 2)
DEFAULT_TEMPLATE = "mvp_deterministic_v1"
DEFAULT_PRIMARY_COLOR = "#6f9684"

BACKGROUND = (248, 250, 247)
INK = (23, 33, 31)
MUTED = (92, 108, 103)
MOSS = (111, 150, 132)
STEEL = (67, 93, 116)
LINE = (220, 226, 221)
WHITE = (255, 255, 255)
DARK = (18, 24, 27)

TEMPLATES: dict[str, dict[str, Any]] = {
    DEFAULT_TEMPLATE: {
        "label": "MVP determinístico",
        "default_color": DEFAULT_PRIMARY_COLOR,
        "background": BACKGROUND,
        "ink": INK,
        "muted": MUTED,
        "accent": MOSS,
    },
    "clean_editorial": {
        "label": "Clean editorial",
        "default_color": "#4f7f72",
        "background": (250, 250, 247),
        "paper": WHITE,
        "ink": (21, 28, 31),
        "muted": (98, 106, 105),
    },
    "bold_contrast": {
        "label": "Bold contrast",
        "default_color": "#ffb84d",
        "background": (17, 22, 28),
        "ink": WHITE,
        "muted": (202, 210, 213),
    },
    "soft_brand": {
        "label": "Soft brand",
        "default_color": "#7f9f91",
        "background": (246, 248, 244),
        "ink": (28, 38, 40),
        "muted": (88, 101, 101),
    },
}


def _font(size: int, *, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf" if bold else "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
    ]
    for candidate in candidates:
        if Path(candidate).exists():
            return ImageFont.truetype(candidate, size=size)
    return ImageFont.load_default()


def _line_height(font: ImageFont.FreeTypeFont | ImageFont.ImageFont, extra: int = 12) -> int:
    bbox = font.getbbox("Ag")
    return (bbox[3] - bbox[1]) + extra


def _measure(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont | ImageFont.ImageFont) -> int:
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[2] - bbox[0]


def _wrap_long_word(draw: ImageDraw.ImageDraw, word: str, font: ImageFont.FreeTypeFont | ImageFont.ImageFont, width: int) -> list[str]:
    chunks: list[str] = []
    current = ""
    for char in word:
        candidate = f"{current}{char}"
        if _measure(draw, candidate, font) <= width:
            current = candidate
        else:
            if current:
                chunks.append(current)
            current = char
    if current:
        chunks.append(current)
    return chunks


def _wrap_text(text: str | None, font: ImageFont.FreeTypeFont | ImageFont.ImageFont, width: int) -> list[str]:
    text = " ".join((text or "").split())
    if not text:
        return []

    probe = Image.new("RGB", (1, 1))
    draw = ImageDraw.Draw(probe)
    lines: list[str] = []
    current = ""

    for word in text.split(" "):
        candidate = f"{current} {word}".strip()
        if _measure(draw, candidate, font) <= width:
            current = candidate
            continue

        if current:
            lines.append(current)
            current = ""

        if _measure(draw, word, font) <= width:
            current = word
        else:
            chunks = _wrap_long_word(draw, word, font, width)
            lines.extend(chunks[:-1])
            current = chunks[-1] if chunks else ""

    if current:
        lines.append(current)
    return lines


def _draw_wrapped(
    draw: ImageDraw.ImageDraw,
    text: str | None,
    *,
    xy: tuple[int, int],
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    fill: tuple[int, int, int],
    width: int,
    max_lines: int,
    line_gap: int = 12,
) -> int:
    x, y = xy
    wrapped = _wrap_text(text, font, width)
    lines = wrapped[:max_lines]
    if len(wrapped) > max_lines and lines:
        lines[-1] = lines[-1].rstrip(" .") + "..."
    line_height = _line_height(font, line_gap)
    for line in lines:
        draw.text((x, y), line, font=font, fill=fill)
        y += line_height
    return y


def _hex_to_rgb(value: str | None, fallback: str = DEFAULT_PRIMARY_COLOR) -> tuple[int, int, int]:
    raw = (value or fallback).strip()
    if not raw.startswith("#") or len(raw) != 7:
        raw = fallback
    try:
        return tuple(int(raw[index:index + 2], 16) for index in (1, 3, 5))
    except ValueError:
        return _hex_to_rgb(fallback, DEFAULT_PRIMARY_COLOR)


def _rgb_to_hex(value: tuple[int, int, int]) -> str:
    return "#" + "".join(f"{part:02x}" for part in value)


def _blend(a: tuple[int, int, int], b: tuple[int, int, int], amount: float) -> tuple[int, int, int]:
    return tuple(int(a[index] + (b[index] - a[index]) * amount) for index in range(3))


def _template_name(template: str | None) -> str:
    candidate = (template or DEFAULT_TEMPLATE).strip()
    return candidate if candidate in TEMPLATES else DEFAULT_TEMPLATE


def _text_or_fallback(*values: Any, fallback: str = "Content Carousel") -> str:
    for value in values:
        if value:
            text = " ".join(str(value).split())
            if text:
                return text
    return fallback


def _brand_text(carrossel: Carrossel, brand_name: str | None) -> str:
    return _text_or_fallback(brand_name, getattr(carrossel, "tema", None), fallback="Content Carousel")[:80]


def _relative_slide_path(carrossel_id: int, numero_slide: int) -> Path:
    return Path("carrosseis") / str(carrossel_id) / "slides" / f"slide-{numero_slide:02d}.png"


def _public_url(relative_path: Path, version: str) -> str:
    base = PUBLIC_BASE_URL.rstrip("/")
    path = f"/storage/{relative_path.as_posix()}?v={version}"
    return f"{base}{path}" if base else path


def _resolve_storage_path(relative_path: str | None) -> Path | None:
    if not relative_path:
        return None
    path = Path(relative_path)
    if path.is_absolute():
        return None
    storage_root = Path(STORAGE_PATH).resolve()
    resolved = (storage_root / path).resolve()
    if storage_root == resolved or storage_root not in resolved.parents:
        return None
    return resolved


def _load_asset_image(asset_path: str | None) -> Image.Image | None:
    resolved = _resolve_storage_path(asset_path)
    if resolved is None or not resolved.exists():
        return None
    try:
        return Image.open(resolved).convert("RGB")
    except OSError:
        return None


def _cover_resize(image: Image.Image, size: tuple[int, int]) -> Image.Image:
    target_w, target_h = size
    source_w, source_h = image.size
    scale = max(target_w / source_w, target_h / source_h)
    resized = image.resize((int(source_w * scale), int(source_h * scale)))
    left = max(0, (resized.width - target_w) // 2)
    top = max(0, (resized.height - target_h) // 2)
    return resized.crop((left, top, left + target_w, top + target_h))


def _paste_asset_panel(
    image: Image.Image,
    asset_image: Image.Image | None,
    box: tuple[int, int, int, int],
    *,
    radius: int,
    opacity: float,
) -> None:
    if asset_image is None:
        return
    x1, y1, x2, y2 = box
    panel = _cover_resize(asset_image, (x2 - x1, y2 - y1)).convert("RGBA")
    if opacity < 1:
        alpha = panel.getchannel("A").point(lambda value: int(value * opacity))
        panel.putalpha(alpha)
    mask = Image.new("L", panel.size, 0)
    mask_draw = ImageDraw.Draw(mask)
    mask_draw.rounded_rectangle((0, 0, panel.size[0], panel.size[1]), radius=radius, fill=255)
    image.paste(panel.convert("RGB"), (x1, y1), mask)


def _draw_footer(draw: ImageDraw.ImageDraw, *, brand: str, accent: tuple[int, int, int], fill: tuple[int, int, int]) -> None:
    small_font = _font(23)
    tiny_font = _font(19)
    draw.text((MARGIN, 1262), brand, font=small_font, fill=fill)
    draw.rounded_rectangle((CANVAS_SIZE[0] - MARGIN - 142, 1258, CANVAS_SIZE[0] - MARGIN, 1292), radius=17, fill=accent)
    draw.text((CANVAS_SIZE[0] - MARGIN - 118, 1264), "preview", font=tiny_font, fill=WHITE)


def _draw_mvp_template(image: Image.Image, carrossel: Carrossel, slide, *, brand: str, accent: tuple[int, int, int], asset_image: Image.Image | None = None) -> None:
    draw = ImageDraw.Draw(image)
    title_font = _font(58, bold=True)
    main_font = _font(44, bold=True)
    secondary_font = _font(31)
    small_font = _font(24)
    tiny_font = _font(20)

    draw.rectangle((0, 0, CANVAS_SIZE[0], 22), fill=accent)
    draw.rounded_rectangle((MARGIN, 70, CANVAS_SIZE[0] - MARGIN, CANVAS_SIZE[1] - 70), radius=36, fill=WHITE, outline=LINE, width=2)
    _paste_asset_panel(image, asset_image, (MARGIN + 44, 810, CANVAS_SIZE[0] - MARGIN - 44, 1020), radius=28, opacity=0.62)
    draw.rounded_rectangle((MARGIN + 34, 112, MARGIN + 122, 168), radius=18, fill=_blend(accent, WHITE, 0.82))
    draw.text((MARGIN + 58, 126), f"{slide.numero_slide:02d}", font=small_font, fill=accent)

    y = 205
    y = _draw_wrapped(draw, slide.titulo or getattr(carrossel, "titulo", None), xy=(MARGIN + 44, y), font=title_font, fill=INK, width=CONTENT_WIDTH - 88, max_lines=3, line_gap=16)
    y += 44
    draw.line((MARGIN + 44, y, CANVAS_SIZE[0] - MARGIN - 44, y), fill=LINE, width=2)
    y += 58
    y = _draw_wrapped(draw, slide.texto_principal, xy=(MARGIN + 44, y), font=main_font, fill=INK, width=CONTENT_WIDTH - 88, max_lines=7, line_gap=18)

    if slide.texto_secundario:
        y += 34
        _draw_wrapped(draw, slide.texto_secundario, xy=(MARGIN + 44, y), font=secondary_font, fill=MUTED, width=CONTENT_WIDTH - 88, max_lines=3, line_gap=14)

    note_top = 1040
    draw.rounded_rectangle((MARGIN + 44, note_top, CANVAS_SIZE[0] - MARGIN - 44, 1190), radius=24, fill=(244, 247, 245), outline=LINE, width=1)
    draw.text((MARGIN + 70, note_top + 24), "Briefing visual", font=tiny_font, fill=STEEL)
    _draw_wrapped(draw, slide.observacao_visual, xy=(MARGIN + 70, note_top + 58), font=small_font, fill=MUTED, width=CONTENT_WIDTH - 140, max_lines=3, line_gap=8)
    _draw_footer(draw, brand=brand, accent=accent, fill=accent)


def _draw_clean_editorial(image: Image.Image, carrossel: Carrossel, slide, *, brand: str, accent: tuple[int, int, int], asset_image: Image.Image | None = None) -> None:
    draw = ImageDraw.Draw(image)
    title_font = _font(64, bold=True)
    main_font = _font(40, bold=True)
    body_font = _font(29)
    small_font = _font(22)
    eyebrow_font = _font(20, bold=True)
    ink = TEMPLATES["clean_editorial"]["ink"]
    muted = TEMPLATES["clean_editorial"]["muted"]
    paper = TEMPLATES["clean_editorial"]["paper"]

    draw.rectangle((0, 0, CANVAS_SIZE[0], CANVAS_SIZE[1]), fill=TEMPLATES["clean_editorial"]["background"])
    draw.rounded_rectangle((MARGIN, 82, CANVAS_SIZE[0] - MARGIN, 1210), radius=28, fill=paper, outline=(226, 229, 224), width=2)
    draw.rectangle((MARGIN, 82, MARGIN + 14, 1210), fill=accent)
    _paste_asset_panel(image, asset_image, (MARGIN + 52, 760, CANVAS_SIZE[0] - MARGIN - 52, 1000), radius=24, opacity=0.72)
    draw.text((MARGIN + 52, 132), f"SLIDE {slide.numero_slide:02d}", font=eyebrow_font, fill=accent)
    draw.text((CANVAS_SIZE[0] - MARGIN - 240, 132), brand, font=small_font, fill=muted)

    y = 210
    y = _draw_wrapped(draw, slide.titulo or getattr(carrossel, "titulo", None), xy=(MARGIN + 52, y), font=title_font, fill=ink, width=CONTENT_WIDTH - 104, max_lines=3, line_gap=18)
    y += 38
    draw.line((MARGIN + 52, y, MARGIN + 260, y), fill=accent, width=5)
    y += 52
    y = _draw_wrapped(draw, slide.texto_principal, xy=(MARGIN + 52, y), font=main_font, fill=ink, width=CONTENT_WIDTH - 104, max_lines=8, line_gap=17)

    if slide.texto_secundario:
        y += 32
        _draw_wrapped(draw, slide.texto_secundario, xy=(MARGIN + 52, y), font=body_font, fill=muted, width=CONTENT_WIDTH - 104, max_lines=4, line_gap=13)

    draw.rounded_rectangle((MARGIN + 52, 1020, CANVAS_SIZE[0] - MARGIN - 52, 1148), radius=20, fill=_blend(accent, WHITE, 0.9))
    draw.text((MARGIN + 78, 1043), "Direção visual", font=eyebrow_font, fill=accent)
    _draw_wrapped(draw, slide.observacao_visual, xy=(MARGIN + 78, 1074), font=small_font, fill=muted, width=CONTENT_WIDTH - 156, max_lines=2, line_gap=8)
    _draw_footer(draw, brand=brand, accent=accent, fill=muted)


def _draw_bold_contrast(image: Image.Image, carrossel: Carrossel, slide, *, brand: str, accent: tuple[int, int, int], asset_image: Image.Image | None = None) -> None:
    draw = ImageDraw.Draw(image)
    title_font = _font(76, bold=True)
    main_font = _font(46, bold=True)
    body_font = _font(31)
    small_font = _font(23)
    mini_font = _font(20, bold=True)
    bg = TEMPLATES["bold_contrast"]["background"]
    muted = TEMPLATES["bold_contrast"]["muted"]

    draw.rectangle((0, 0, CANVAS_SIZE[0], CANVAS_SIZE[1]), fill=bg)
    _paste_asset_panel(image, asset_image, (0, 34, CANVAS_SIZE[0], CANVAS_SIZE[1]), radius=0, opacity=0.25)
    draw.rectangle((0, 0, CANVAS_SIZE[0], 34), fill=accent)
    draw.ellipse((CANVAS_SIZE[0] - 360, 110, CANVAS_SIZE[0] + 180, 650), fill=_blend(accent, bg, 0.42))
    draw.rounded_rectangle((MARGIN, 108, MARGIN + 132, 164), radius=18, fill=accent)
    draw.text((MARGIN + 28, 123), f"{slide.numero_slide:02d}", font=small_font, fill=bg)
    draw.text((MARGIN + 160, 124), brand.upper(), font=mini_font, fill=muted)

    y = 232
    y = _draw_wrapped(draw, slide.titulo or getattr(carrossel, "titulo", None), xy=(MARGIN, y), font=title_font, fill=WHITE, width=CONTENT_WIDTH, max_lines=3, line_gap=14)
    y += 54
    y = _draw_wrapped(draw, slide.texto_principal, xy=(MARGIN, y), font=main_font, fill=WHITE, width=CONTENT_WIDTH, max_lines=7, line_gap=20)

    if slide.texto_secundario:
        y += 34
        _draw_wrapped(draw, slide.texto_secundario, xy=(MARGIN, y), font=body_font, fill=muted, width=CONTENT_WIDTH, max_lines=4, line_gap=13)

    draw.rounded_rectangle((MARGIN, 1060, CANVAS_SIZE[0] - MARGIN, 1192), radius=22, fill=(30, 38, 46), outline=_blend(accent, WHITE, 0.25), width=2)
    draw.text((MARGIN + 30, 1085), "BRIEFING", font=mini_font, fill=accent)
    _draw_wrapped(draw, slide.observacao_visual, xy=(MARGIN + 30, 1117), font=small_font, fill=muted, width=CONTENT_WIDTH - 60, max_lines=2, line_gap=8)
    _draw_footer(draw, brand=brand, accent=accent, fill=muted)


def _draw_soft_brand(image: Image.Image, carrossel: Carrossel, slide, *, brand: str, accent: tuple[int, int, int], asset_image: Image.Image | None = None) -> None:
    draw = ImageDraw.Draw(image)
    title_font = _font(60, bold=True)
    main_font = _font(39, bold=True)
    body_font = _font(30)
    small_font = _font(23)
    tiny_font = _font(19, bold=True)
    bg = TEMPLATES["soft_brand"]["background"]
    ink = TEMPLATES["soft_brand"]["ink"]
    muted = TEMPLATES["soft_brand"]["muted"]
    tint = _blend(accent, WHITE, 0.84)

    draw.rectangle((0, 0, CANVAS_SIZE[0], CANVAS_SIZE[1]), fill=bg)
    draw.rounded_rectangle((MARGIN, 78, CANVAS_SIZE[0] - MARGIN, 1235), radius=42, fill=_blend(tint, WHITE, 0.62))
    _paste_asset_panel(image, asset_image, (MARGIN + 56, 770, CANVAS_SIZE[0] - MARGIN - 56, 995), radius=30, opacity=0.70)
    draw.rounded_rectangle((MARGIN + 34, 120, CANVAS_SIZE[0] - MARGIN - 34, 224), radius=30, fill=WHITE)
    draw.rounded_rectangle((MARGIN + 60, 145, MARGIN + 162, 198), radius=18, fill=accent)
    draw.text((MARGIN + 91, 158), f"{slide.numero_slide:02d}", font=small_font, fill=WHITE)
    draw.text((MARGIN + 190, 156), brand, font=small_font, fill=muted)

    y = 286
    y = _draw_wrapped(draw, slide.titulo or getattr(carrossel, "titulo", None), xy=(MARGIN + 56, y), font=title_font, fill=ink, width=CONTENT_WIDTH - 112, max_lines=3, line_gap=17)
    y += 36
    draw.rounded_rectangle((MARGIN + 56, y, CANVAS_SIZE[0] - MARGIN - 56, min(y + 430, 880)), radius=30, fill=WHITE)
    y += 40
    y = _draw_wrapped(draw, slide.texto_principal, xy=(MARGIN + 92, y), font=main_font, fill=ink, width=CONTENT_WIDTH - 184, max_lines=7, line_gap=17)

    if slide.texto_secundario:
        y += 28
        _draw_wrapped(draw, slide.texto_secundario, xy=(MARGIN + 92, y), font=body_font, fill=muted, width=CONTENT_WIDTH - 184, max_lines=3, line_gap=12)

    draw.rounded_rectangle((MARGIN + 56, 1010, CANVAS_SIZE[0] - MARGIN - 56, 1155), radius=28, fill=_blend(accent, WHITE, 0.78))
    draw.text((MARGIN + 88, 1035), "NOTA VISUAL", font=tiny_font, fill=accent)
    _draw_wrapped(draw, slide.observacao_visual, xy=(MARGIN + 88, 1070), font=small_font, fill=muted, width=CONTENT_WIDTH - 176, max_lines=3, line_gap=8)
    _draw_footer(draw, brand=brand, accent=accent, fill=muted)


def _render_slide_image(
    carrossel: Carrossel,
    slide,
    output_path: Path,
    *,
    template: str,
    brand_name: str | None,
    primary_color: str | None,
    asset_image: Image.Image | None = None,
    asset_id: int | None = None,
) -> dict[str, Any]:
    template_config = TEMPLATES[template]
    fallback_color = template_config.get("default_color", DEFAULT_PRIMARY_COLOR)
    accent = _hex_to_rgb(primary_color, fallback_color)
    brand = _brand_text(carrossel, brand_name)
    image = Image.new("RGB", CANVAS_SIZE, template_config.get("background", BACKGROUND))

    if template == "clean_editorial":
        _draw_clean_editorial(image, carrossel, slide, brand=brand, accent=accent, asset_image=asset_image)
    elif template == "bold_contrast":
        _draw_bold_contrast(image, carrossel, slide, brand=brand, accent=accent, asset_image=asset_image)
    elif template == "soft_brand":
        _draw_soft_brand(image, carrossel, slide, brand=brand, accent=accent, asset_image=asset_image)
    else:
        _draw_mvp_template(image, carrossel, slide, brand=brand, accent=accent, asset_image=asset_image)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(output_path, format="PNG", optimize=True)
    return {"template": template, "brand_name": brand, "primary_color": _rgb_to_hex(accent), "asset_id": asset_id}


def renderizar_carrossel_slides(
    db: Session,
    carrossel: Carrossel,
    *,
    template: str | None = None,
    brand_name: str | None = None,
    primary_color: str | None = None,
    asset=None,
) -> Carrossel:
    selected_template = _template_name(template)
    asset_image = _load_asset_image(getattr(asset, "asset_path", None)) if asset is not None else None
    asset_id = getattr(asset, "id", None) if asset is not None else None
    registrar_log(
        db,
        carrossel_id=carrossel.id,
        etapa="renderizacao",
        status="INICIADO",
        mensagem="Renderização determinística dos slides iniciada.",
        detalhes={"slides": len(carrossel.slides), "template": selected_template, "asset_id": asset_id},
    )

    storage_root = Path(STORAGE_PATH).resolve()
    version = datetime.utcnow().strftime("%Y%m%d%H%M%S")

    for slide in carrossel.slides:
        relative_path = _relative_slide_path(carrossel.id, slide.numero_slide)
        output_path = storage_root / relative_path
        render_options = _render_slide_image(
            carrossel,
            slide,
            output_path,
            template=selected_template,
            brand_name=brand_name,
            primary_color=primary_color,
            asset_image=asset_image,
            asset_id=asset_id,
        )
        slide.imagem_path = relative_path.as_posix()
        slide.imagem_url = _public_url(relative_path, version)
        layout_config = slide.layout_config or {}
        slide.layout_config = {
            **layout_config,
            "renderer": "pillow",
            "template": render_options["template"],
            "brand_name": render_options["brand_name"],
            "primary_color": render_options["primary_color"],
            "asset_id": render_options["asset_id"],
            "canvas": {"width": CANVAS_SIZE[0], "height": CANVAS_SIZE[1]},
            "rendered_at": datetime.utcnow().isoformat(),
        }

    registrar_log(
        db,
        carrossel_id=carrossel.id,
        etapa="renderizacao",
        status="CONCLUIDO",
        mensagem="Renderização determinística dos slides concluída.",
        detalhes={"slides_renderizados": len(carrossel.slides), "template": selected_template, "asset_id": asset_id},
    )
    return carrossel
