from datetime import datetime
from pathlib import Path
import textwrap

from PIL import Image, ImageDraw, ImageFont
from sqlalchemy.orm import Session

from app.config import PUBLIC_BASE_URL, STORAGE_PATH
from app.models.carrossel import Carrossel
from app.services.log_service import registrar_log

CANVAS_SIZE = (1080, 1350)
MARGIN = 86
CONTENT_WIDTH = CANVAS_SIZE[0] - (MARGIN * 2)
BACKGROUND = (248, 250, 247)
INK = (23, 33, 31)
MUTED = (92, 108, 103)
MOSS = (111, 150, 132)
STEEL = (67, 93, 116)
LINE = (220, 226, 221)
WHITE = (255, 255, 255)


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


def _wrap_text(text: str | None, font: ImageFont.FreeTypeFont | ImageFont.ImageFont, width: int) -> list[str]:
    text = " ".join((text or "").split())
    if not text:
        return []

    words = text.split(" ")
    lines: list[str] = []
    current = ""
    probe = Image.new("RGB", (1, 1))
    draw = ImageDraw.Draw(probe)

    for word in words:
        candidate = f"{current} {word}".strip()
        if draw.textbbox((0, 0), candidate, font=font)[2] <= width:
            current = candidate
        else:
            if current:
                lines.append(current)
            if draw.textbbox((0, 0), word, font=font)[2] <= width:
                current = word
            else:
                lines.extend(textwrap.wrap(word, width=18))
                current = ""
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
    lines = _wrap_text(text, font, width)[:max_lines]
    if len(_wrap_text(text, font, width)) > max_lines and lines:
        lines[-1] = lines[-1].rstrip(" .") + "..."
    line_height = _line_height(font, line_gap)
    for line in lines:
        draw.text((x, y), line, font=font, fill=fill)
        y += line_height
    return y


def _relative_slide_path(carrossel_id: int, numero_slide: int) -> Path:
    return Path("carrosseis") / str(carrossel_id) / "slides" / f"slide-{numero_slide:02d}.png"


def _public_url(relative_path: Path, version: str) -> str:
    base = PUBLIC_BASE_URL.rstrip("/")
    path = f"/storage/{relative_path.as_posix()}?v={version}"
    return f"{base}{path}" if base else path


def _render_slide_image(carrossel: Carrossel, slide, output_path: Path) -> None:
    image = Image.new("RGB", CANVAS_SIZE, BACKGROUND)
    draw = ImageDraw.Draw(image)

    title_font = _font(58, bold=True)
    main_font = _font(44, bold=True)
    secondary_font = _font(31)
    small_font = _font(24)
    tiny_font = _font(20)

    draw.rectangle((0, 0, CANVAS_SIZE[0], 22), fill=MOSS)
    draw.rounded_rectangle((MARGIN, 70, CANVAS_SIZE[0] - MARGIN, CANVAS_SIZE[1] - 70), radius=36, fill=WHITE, outline=LINE, width=2)

    badge = f"{slide.numero_slide:02d}"
    draw.rounded_rectangle((MARGIN + 34, 112, MARGIN + 122, 168), radius=18, fill=(231, 240, 235))
    draw.text((MARGIN + 58, 126), badge, font=small_font, fill=MOSS)

    y = 205
    y = _draw_wrapped(draw, slide.titulo or carrossel.titulo, xy=(MARGIN + 44, y), font=title_font, fill=INK, width=CONTENT_WIDTH - 88, max_lines=3, line_gap=16)
    y += 44
    draw.line((MARGIN + 44, y, CANVAS_SIZE[0] - MARGIN - 44, y), fill=LINE, width=2)
    y += 58

    y = _draw_wrapped(draw, slide.texto_principal, xy=(MARGIN + 44, y), font=main_font, fill=INK, width=CONTENT_WIDTH - 88, max_lines=7, line_gap=18)

    if slide.texto_secundario:
        y += 34
        y = _draw_wrapped(draw, slide.texto_secundario, xy=(MARGIN + 44, y), font=secondary_font, fill=MUTED, width=CONTENT_WIDTH - 88, max_lines=3, line_gap=14)

    note_top = 1040
    draw.rounded_rectangle((MARGIN + 44, note_top, CANVAS_SIZE[0] - MARGIN - 44, 1190), radius=24, fill=(244, 247, 245), outline=LINE, width=1)
    draw.text((MARGIN + 70, note_top + 24), "Briefing visual", font=tiny_font, fill=STEEL)
    _draw_wrapped(draw, slide.observacao_visual, xy=(MARGIN + 70, note_top + 58), font=small_font, fill=MUTED, width=CONTENT_WIDTH - 140, max_lines=3, line_gap=8)

    footer = carrossel.tema or "Content Carousel"
    draw.text((MARGIN + 44, 1230), footer, font=small_font, fill=MOSS)
    draw.text((CANVAS_SIZE[0] - MARGIN - 208, 1230), "MVP Preview", font=tiny_font, fill=MUTED)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(output_path, format="PNG", optimize=True)


def renderizar_carrossel_slides(db: Session, carrossel: Carrossel) -> Carrossel:
    registrar_log(
        db,
        carrossel_id=carrossel.id,
        etapa="renderizacao",
        status="INICIADO",
        mensagem="Renderização determinística dos slides iniciada.",
        detalhes={"slides": len(carrossel.slides)},
    )

    storage_root = Path(STORAGE_PATH).resolve()
    version = datetime.utcnow().strftime("%Y%m%d%H%M%S")

    for slide in carrossel.slides:
        relative_path = _relative_slide_path(carrossel.id, slide.numero_slide)
        output_path = storage_root / relative_path
        _render_slide_image(carrossel, slide, output_path)
        slide.imagem_path = relative_path.as_posix()
        slide.imagem_url = _public_url(relative_path, version)
        layout_config = slide.layout_config or {}
        slide.layout_config = {
            **layout_config,
            "renderer": "pillow",
            "template": "mvp_deterministic_v1",
            "canvas": {"width": CANVAS_SIZE[0], "height": CANVAS_SIZE[1]},
            "rendered_at": datetime.utcnow().isoformat(),
        }

    registrar_log(
        db,
        carrossel_id=carrossel.id,
        etapa="renderizacao",
        status="CONCLUIDO",
        mensagem="Renderização determinística dos slides concluída.",
        detalhes={"slides_renderizados": len(carrossel.slides)},
    )
    return carrossel
