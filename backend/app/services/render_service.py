from datetime import datetime
import hashlib
import re
from pathlib import Path
from typing import Any

from fastapi import HTTPException
from openai import OpenAI
from sqlalchemy.orm import Session

from app.config import OPENAI_ADMIN_IMAGE_RENDER_MAX_ATTEMPTS, OPENAI_IMAGE_MODEL, OPENAI_IMAGE_SIZE, PUBLIC_BASE_URL, STORAGE_PATH
from app.models.carrossel import Carrossel, Usuario
from app.services.image_asset_service import (
    ASSET_CALL_STARTED,
    _image_limit_status,
    _image_response_to_bytes,
    _limites_configurados,
    openai_image_configurado,
)
from app.services.log_service import registrar_log

OPENAI_API_KEY = ""
ASPECT_RATIO_OPTIONS = {
    "1:1": {"label": "Quadrado 1:1", "width": 1080, "height": 1080, "description": "quadrado 1:1"},
    "1.91:1": {"label": "Horizontal 1,91:1", "width": 1080, "height": 566, "description": "horizontal 1,91:1"},
    "4:5": {"label": "Vertical 4:5", "width": 1080, "height": 1350, "description": "vertical 4:5"},
}
DEFAULT_ASPECT_RATIO = "4:5"

DEFAULT_TEMPLATE = "mvp_deterministic_v1"
DEFAULT_PRIMARY_COLOR = "#6f9684"

BACKGROUND = (248, 250, 247)
INK = (23, 33, 31)
MUTED = (92, 108, 103)
MOSS = (111, 150, 132)
WHITE = (255, 255, 255)

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


def _aspect_ratio_config(aspect_ratio: str | None) -> dict[str, Any]:
    return ASPECT_RATIO_OPTIONS.get(aspect_ratio or DEFAULT_ASPECT_RATIO, ASPECT_RATIO_OPTIONS[DEFAULT_ASPECT_RATIO])


def _brand_text(carrossel: Carrossel, brand_name: str | None) -> str:
    return _text_or_fallback(brand_name, getattr(carrossel, "tema", None), fallback="Content Carousel")[:80]


def _prompt_full_slide(carrossel: Carrossel, slide, *, brand: str, primary_color: str, aspect: dict[str, Any]) -> str:
    secondary = (getattr(slide, "texto_secundario", None) or "").strip()
    width = aspect["width"]
    height = aspect["height"]
    return f"""
Crie UM slide final para redes sociais, pronto para uso, com estética editorial premium.
Formato: imagem {aspect["description"]}, canvas {width}x{height}px, composição moderna, forte hierarquia visual, margens seguras e alta legibilidade.

Contexto do carrossel:
- Título: {getattr(carrossel, 'titulo', None) or 'Carrossel'}
- Tema: {getattr(carrossel, 'tema', None) or 'conteúdo editorial'}
- Tom: {getattr(carrossel, 'tom', None) or 'profissional, claro e envolvente'}
- Público-alvo: {getattr(carrossel, 'publico_alvo', None) or 'público geral'}
- Marca/assinatura: {brand}
- Cor principal sugerida: {primary_color}

Campos obrigatórios do slide, que devem aparecer exatamente como fornecidos:
- titulo: {getattr(slide, 'titulo', None) or getattr(carrossel, 'titulo', None) or ''}
- texto_principal: {getattr(slide, 'texto_principal', None) or ''}
- texto_secundario: {secondary}
- observacao_visual: {getattr(slide, 'observacao_visual', None) or 'visual editorial forte e coerente com o tema'}

Regras obrigatórias:
- Use OPENAI_IMAGE_MODEL/DALL·E para gerar uma imagem final no formato {aspect["description"]}, com enquadramento visual equivalente a {width}x{height}px, usando OPENAI_IMAGE_SIZE como referência técnica.
- Renderize o título, texto principal e texto secundário dentro da imagem, totalmente contidos no quadro visível de {width}x{height}px.
- Use margens seguras de pelo menos 10-12% em todos os lados.
- Quebre linhas e use hierarquia visual clara para que nenhum texto seja cortado, encoste nas bordas ou saia do quadro.
- Renderize titulo, texto_principal e texto_secundario exatamente como fornecidos nos campos acima, sem alterar, reduzir, reescrever, resumir, traduzir ou acrescentar palavras.
- Se texto_secundario estiver vazio, não invente texto secundário.
- Use observacao_visual como direção criativa para cenário, estilo, composição, cores, textura e elementos visuais.
- Mantenha a proporção {aspect["description"]}, margens seguras, contraste suficiente, espaçamento confortável e legibilidade alta.
- Use imagens, ilustração ou fotografia como parte da composição, sem prejudicar a leitura dos textos.
- Não use logotipos reais, marcas registradas nem pessoas identificáveis.
""".strip()


def _prompt_hash(prompt: str) -> str:
    return hashlib.sha256(prompt.encode("utf-8")).hexdigest()


def _save_full_slide_bytes(content: bytes, output_path: Path) -> None:
    # temporary: use OpenAI bytes only; revert when Pillow improvements done.
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(content)


def _openai_status_code(exc: Exception) -> int | None:
    status = getattr(exc, "status_code", None)
    if status is not None:
        return int(status)
    response = getattr(exc, "response", None)
    status = getattr(response, "status_code", None)
    return int(status) if status is not None else None


def _redact_secret(value: str) -> str:
    return re.sub(r"sk-[A-Za-z0-9_\-]+", "sk-***", value)


def _openai_raw_error(exc: Exception) -> str:
    body = getattr(exc, "body", None)
    if body:
        return _redact_secret(str(body))
    response = getattr(exc, "response", None)
    text = getattr(response, "text", None)
    if text:
        return _redact_secret(str(text))
    return _redact_secret(str(exc))


def _openai_error_message(exc: Exception) -> str:
    status_code = _openai_status_code(exc)
    raw_error = _openai_raw_error(exc)
    if status_code == 401:
        return f"Chave OpenAI inválida ou expirada. Atualize OPENAI_API_KEY. Detalhe OpenAI: {raw_error}"
    if status_code == 429:
        return f"Limite de geração de imagem da OpenAI atingido. Detalhe OpenAI: {raw_error}"
    if status_code is not None:
        return f"Falha na OpenAI ao gerar imagem do slide (status {status_code}). Detalhe OpenAI: {raw_error}"
    return f"Falha na OpenAI ao gerar imagem do slide. Detalhe OpenAI: {raw_error}"


def _raise_openai_render_error(db: Session, carrossel: Carrossel, slide, exc: Exception, *, prompt_hash: str, attempt: int) -> None:
    status_code = _openai_status_code(exc) or 502
    message = _openai_error_message(exc)
    registrar_log(
        db,
        carrossel_id=carrossel.id,
        etapa="renderizacao",
        status="OPENAI_FULL_SLIDE_ERRO",
        mensagem=message,
        detalhes={
            "slide_id": getattr(slide, "id", None),
            "numero_slide": slide.numero_slide,
            "attempt": attempt,
            "status_code": status_code,
            "modelo": OPENAI_IMAGE_MODEL,
            "prompt_hash": prompt_hash,
        },
    )
    raise HTTPException(status_code=status_code, detail=message)


def _render_slide_with_openai(
    db: Session,
    carrossel: Carrossel,
    slide,
    output_path: Path,
    *,
    brand: str,
    primary_color: str,
    api_key: str | None,
    usuario: Usuario | None = None,
    max_attempts: int = 1,
    aspect: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    effective_api_key = api_key if api_key is not None else (OPENAI_API_KEY or None)
    if not openai_image_configurado(effective_api_key):
        return None

    limit_status = _image_limit_status(db, carrossel, usuario=usuario)
    if limit_status is not None:
        registrar_log(
            db,
            carrossel_id=carrossel.id,
            etapa="renderizacao",
            status="OPENAI_FULL_SLIDE_ERRO",
            mensagem="Limite de geração de imagem da OpenAI atingido; renderização abortada.",
            detalhes={"slide_id": getattr(slide, "id", None), "numero_slide": slide.numero_slide, "limit": limit_status},
        )
        raise HTTPException(status_code=429, detail="Limite de geração de imagem da OpenAI atingido. Tente novamente mais tarde ou ajuste os limites.")

    aspect_config = aspect or ASPECT_RATIO_OPTIONS[DEFAULT_ASPECT_RATIO]
    prompt = _prompt_full_slide(carrossel, slide, brand=brand, primary_color=primary_color, aspect=aspect_config)
    prompt_hash = _prompt_hash(prompt)
    client = OpenAI(api_key=effective_api_key)
    last_error: Exception | None = None

    for attempt in range(1, max_attempts + 1):
        registrar_log(
            db,
            carrossel_id=carrossel.id,
            etapa="asset_ia",
            status=ASSET_CALL_STARTED,
            mensagem="Renderização de slide completo com OpenAI iniciada.",
            detalhes={
                "modelo": OPENAI_IMAGE_MODEL,
                "size": OPENAI_IMAGE_SIZE,
                "aspect_ratio": aspect_config["label"],
                "canvas": {"width": aspect_config["width"], "height": aspect_config["height"]},
                "slide_id": getattr(slide, "id", None),
                "numero_slide": slide.numero_slide,
                "prompt_hash": prompt_hash,
                "attempt": attempt,
                "limites": _limites_configurados(usuario=usuario, carrossel=carrossel),
            },
        )
        try:
            response = client.images.generate(
                model=OPENAI_IMAGE_MODEL,
                prompt=prompt,
                size=OPENAI_IMAGE_SIZE,
                n=1,
            )
            content, provider_metadata = _image_response_to_bytes(response)
            _save_full_slide_bytes(content, output_path)
            break
        except Exception as exc:
            last_error = exc
            if _openai_status_code(exc) == 401 or attempt == max_attempts:
                _raise_openai_render_error(db, carrossel, slide, exc, prompt_hash=prompt_hash, attempt=attempt)
    else:
        if last_error is not None:
            _raise_openai_render_error(db, carrossel, slide, last_error, prompt_hash=prompt_hash, attempt=max_attempts)
        raise HTTPException(status_code=502, detail="Falha na OpenAI ao gerar imagem do slide.")

    registrar_log(
        db,
        carrossel_id=carrossel.id,
        etapa="renderizacao",
        status="OPENAI_FULL_SLIDE_CONCLUIDO",
        mensagem="Slide completo renderizado com OpenAI.",
        detalhes={
            "slide_id": getattr(slide, "id", None),
            "numero_slide": slide.numero_slide,
            "modelo": OPENAI_IMAGE_MODEL,
            "prompt_hash": prompt_hash,
        },
    )
    return {
        "renderer": "openai_full_slide",
        "provider": "openai",
        "image_model": OPENAI_IMAGE_MODEL,
        "image_size": OPENAI_IMAGE_SIZE,
        "aspect_ratio": aspect_config["label"],
        "aspect_ratio_value": next((key for key, value in ASPECT_RATIO_OPTIONS.items() if value == aspect_config), DEFAULT_ASPECT_RATIO),
        "canvas": {"width": aspect_config["width"], "height": aspect_config["height"]},
        "resize_strategy": "openai_bytes_only",
        "image_prompt": prompt,
        "image_prompt_hash": prompt_hash,
        "provider_response": provider_metadata,
    }


def _relative_slide_path(carrossel_id: int, numero_slide: int) -> Path:
    return Path("carrosseis") / str(carrossel_id) / "slides" / f"slide-{numero_slide:02d}.png"


def _public_url(relative_path: Path, version: str) -> str:
    base = PUBLIC_BASE_URL.rstrip("/")
    path = f"/storage/{relative_path.as_posix()}?v={version}"
    return f"{base}{path}" if base else path



def renderizar_carrossel_slides(
    db: Session,
    carrossel: Carrossel,
    *,
    template: str | None = None,
    brand_name: str | None = None,
    primary_color: str | None = None,
    asset=None,
    api_key: str | None = None,
    usuario: Usuario | None = None,
    aspect_ratio: str | None = None,
) -> Carrossel:
    selected_template = _template_name(template)
    if asset is not None:
        # temporary: asset-based Pillow render is disabled while slides are OpenAI-only.
        raise HTTPException(
            status_code=409,
            detail="Renderização com asset selecionado está temporariamente indisponível no modo OpenAI-only. Remova o asset_id e renderize novamente.",
        )

    effective_api_key = api_key if api_key is not None else (OPENAI_API_KEY or None)
    if not openai_image_configurado(effective_api_key):
        raise HTTPException(status_code=409, detail="Configure sua OPENAI_API_KEY na tela de configurações antes de renderizar com IA.")

    registrar_log(
        db,
        carrossel_id=carrossel.id,
        etapa="renderizacao",
        status="INICIADO",
        mensagem="Renderização OpenAI-only dos slides iniciada.",
        detalhes={"slides": len(carrossel.slides), "template": selected_template, "renderer": "openai_full_slide"},
    )

    storage_root = Path(STORAGE_PATH).resolve()
    version = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    brand = _brand_text(carrossel, brand_name)
    accent = _hex_to_rgb(primary_color, TEMPLATES[selected_template].get("default_color", DEFAULT_PRIMARY_COLOR))
    primary_hex = _rgb_to_hex(accent)
    max_attempts = OPENAI_ADMIN_IMAGE_RENDER_MAX_ATTEMPTS if bool(getattr(usuario, "is_admin", False)) else 1
    aspect_config = _aspect_ratio_config(aspect_ratio)

    generated_slides: list[tuple[Any, Path, Path, Path, dict[str, Any]]] = []
    temp_paths: list[Path] = []
    try:
        for slide in carrossel.slides:
            relative_path = _relative_slide_path(carrossel.id, slide.numero_slide)
            output_path = storage_root / relative_path
            temp_path = output_path.with_name(f".{output_path.stem}-openai-{version}.tmp.png")
            temp_paths.append(temp_path)
            render_options = _render_slide_with_openai(
                db,
                carrossel,
                slide,
                temp_path,
                brand=brand,
                primary_color=primary_hex,
                api_key=effective_api_key,
                usuario=usuario,
                max_attempts=max_attempts,
                aspect=aspect_config,
            )
            generated_slides.append((slide, relative_path, output_path, temp_path, {
                "template": selected_template,
                "brand_name": brand,
                "primary_color": primary_hex,
                "asset_id": None,
                **(render_options or {}),
            }))
    except Exception:
        for temp_path in temp_paths:
            temp_path.unlink(missing_ok=True)
        raise

    for slide, relative_path, output_path, temp_path, render_options in generated_slides:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path.replace(output_path)
        slide.imagem_path = relative_path.as_posix()
        slide.imagem_url = _public_url(relative_path, version)
        layout_config = slide.layout_config or {}
        slide.layout_config = {
            **layout_config,
            "renderer": "openai_full_slide",
            "template": render_options["template"],
            "brand_name": render_options["brand_name"],
            "primary_color": render_options["primary_color"],
            "asset_id": None,
            "slide_asset_id": None,
            "slide_asset_path": None,
            "slide_asset_prompt": None,
            "slide_asset_prompt_hash": None,
            "provider": render_options.get("provider"),
            "image_model": render_options.get("image_model"),
            "image_size": render_options.get("image_size"),
            "resize_strategy": render_options.get("resize_strategy"),
            "image_prompt": render_options.get("image_prompt"),
            "image_prompt_hash": render_options.get("image_prompt_hash"),
            "fallback_reason": None,
            "fallback_error": None,
            "limit": None,
            "aspect_ratio": render_options.get("aspect_ratio"),
            "aspect_ratio_value": render_options.get("aspect_ratio_value"),
            "canvas": render_options.get("canvas"),
            "rendered_at": datetime.utcnow().isoformat(),
        }

    registrar_log(
        db,
        carrossel_id=carrossel.id,
        etapa="renderizacao",
        status="CONCLUIDO",
        mensagem="Renderização OpenAI-only dos slides concluída.",
        detalhes={"slides_renderizados": len(carrossel.slides), "template": selected_template, "aspect_ratio": aspect_config["label"], "canvas": {"width": aspect_config["width"], "height": aspect_config["height"]}},
    )
    return carrossel
