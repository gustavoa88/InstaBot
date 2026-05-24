import base64
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.request import urlopen

from fastapi import HTTPException
from openai import OpenAI
from PIL import Image, ImageDraw, ImageFont
from sqlalchemy.orm import Session

from app.config import (
    OPENAI_API_KEY,
    OPENAI_IMAGE_CARROSSEL_REQUEST_LIMIT,
    OPENAI_IMAGE_DAILY_REQUEST_LIMIT,
    OPENAI_IMAGE_MODEL,
    OPENAI_IMAGE_SIZE,
    STORAGE_PATH,
    PUBLIC_BASE_URL,
)
from app.models.carrossel import ASSET_STATUS_ATIVO, ASSET_STATUS_REMOVIDO, Carrossel, CarrosselAsset, LogExecucao
from app.services.log_service import registrar_log

ASSET_CALL_STARTED = "INICIADO"
ASSET_LIMIT_BLOCKED = "BLOQUEADO_LIMITE"
FALLBACK_MODEL = "fallback_pillow_asset_v1"


def openai_image_configurado() -> bool:
    return bool(OPENAI_API_KEY.strip())


def _font(size: int, *, bold: bool = False):
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
    ]
    for candidate in candidates:
        if Path(candidate).exists():
            return ImageFont.truetype(candidate, size=size)
    return ImageFont.load_default()


def _limites_configurados() -> dict[str, int]:
    return {
        "daily_request_limit": OPENAI_IMAGE_DAILY_REQUEST_LIMIT,
        "carrossel_request_limit": OPENAI_IMAGE_CARROSSEL_REQUEST_LIMIT,
    }


def _relative_asset_path(carrossel_id: int, version: str) -> Path:
    return Path("carrosseis") / str(carrossel_id) / "assets" / f"asset-{version}.png"


def _public_url(relative_path: Path, version: str) -> str:
    base = PUBLIC_BASE_URL.rstrip("/")
    path = f"/storage/{relative_path.as_posix()}?v={version}"
    return f"{base}{path}" if base else path


def _prompt_asset(carrossel: Carrossel) -> str:
    observacoes = ""
    if carrossel.prompt_config and carrossel.prompt_config.get("observacoes_adicionais"):
        observacoes = str(carrossel.prompt_config["observacoes_adicionais"])
    visual_notes = " ".join(
        (slide.observacao_visual or "").strip()
        for slide in (carrossel.slides or [])[:5]
        if slide.observacao_visual
    )
    base = f"""
Crie uma imagem vertical para fundo/ilustração de um carrossel de Instagram.
Tema: {carrossel.tema or 'conteúdo profissional'}.
Título: {carrossel.titulo or 'carrossel de conteúdo'}.
Ideia original: {carrossel.ideia_original[:900]}.
Público-alvo: {carrossel.publico_alvo or 'público geral'}.
Tom: {carrossel.tom or 'profissional e claro'}.
Observações do usuário: {observacoes[:500] or 'nenhuma'}.
Briefings visuais dos slides: {visual_notes[:800] or 'visual limpo, abstrato e versátil'}.

Regras obrigatórias:
- Não inclua texto, letras, números, logotipos ou marcas.
- Não use pessoas identificáveis.
- Gere uma composição com áreas de respiro para textos serem aplicados depois.
- Visual profissional, coerente e reutilizável em todos os slides.
""".strip()
    return base


def _count_openai_image_calls(db: Session, *, carrossel_id: int | None = None, desde: datetime | None = None) -> int:
    query = db.query(LogExecucao).filter(
        LogExecucao.etapa == "asset_ia",
        LogExecucao.status == ASSET_CALL_STARTED,
    )
    if carrossel_id is not None:
        query = query.filter(LogExecucao.carrossel_id == carrossel_id)
    if desde is not None:
        query = query.filter(LogExecucao.created_at >= desde)
    return query.count()


def _block_limit(db: Session, *, carrossel_id: int, escopo: str, limite: int, chamadas: int) -> None:
    registrar_log(
        db,
        carrossel_id=carrossel_id,
        etapa="asset_ia",
        status=ASSET_LIMIT_BLOCKED,
        mensagem=f"Geração de asset com OpenAI bloqueada pelo limite {escopo}.",
        detalhes={
            "escopo": escopo,
            "limite": limite,
            "chamadas_registradas": chamadas,
            "modelo": OPENAI_IMAGE_MODEL,
            "limites": _limites_configurados(),
        },
    )
    db.commit()
    raise HTTPException(status_code=429, detail=f"Limite {escopo} de geração de imagem atingido ({chamadas}/{limite}).")


def _verify_limits(db: Session, carrossel: Carrossel) -> None:
    if OPENAI_IMAGE_DAILY_REQUEST_LIMIT > 0:
        inicio_dia = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        chamadas_dia = _count_openai_image_calls(db, desde=inicio_dia)
        if chamadas_dia >= OPENAI_IMAGE_DAILY_REQUEST_LIMIT:
            _block_limit(db, carrossel_id=carrossel.id, escopo="diário", limite=OPENAI_IMAGE_DAILY_REQUEST_LIMIT, chamadas=chamadas_dia)
    if OPENAI_IMAGE_CARROSSEL_REQUEST_LIMIT > 0:
        chamadas_carrossel = _count_openai_image_calls(db, carrossel_id=carrossel.id)
        if chamadas_carrossel >= OPENAI_IMAGE_CARROSSEL_REQUEST_LIMIT:
            _block_limit(db, carrossel_id=carrossel.id, escopo="por carrossel", limite=OPENAI_IMAGE_CARROSSEL_REQUEST_LIMIT, chamadas=chamadas_carrossel)


def _save_bytes(content: bytes, relative_path: Path) -> None:
    storage_root = Path(STORAGE_PATH).resolve()
    output_path = storage_root / relative_path
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(content)


def _fallback_image(carrossel: Carrossel, relative_path: Path) -> None:
    width, height = 1024, 1536
    image = Image.new("RGB", (width, height), (244, 247, 245))
    draw = ImageDraw.Draw(image)
    accent = (111, 150, 132)
    ink = (35, 45, 43)
    muted = (100, 113, 108)
    for y in range(height):
        ratio = y / height
        color = (
            int(244 - 26 * ratio),
            int(247 - 20 * ratio),
            int(245 - 14 * ratio),
        )
        draw.line((0, y, width, y), fill=color)
    draw.ellipse((-230, 120, 480, 820), fill=(219, 232, 224))
    draw.ellipse((620, 520, 1270, 1260), fill=(203, 220, 214))
    draw.rounded_rectangle((112, 250, width - 112, height - 260), radius=72, outline=(255, 255, 255), width=12)
    title = (carrossel.tema or carrossel.titulo or "Content Carousel")[:42]
    draw.text((140, 1180), title, font=_font(46, bold=True), fill=ink)
    draw.text((140, 1242), "Asset visual fallback", font=_font(28), fill=muted)
    draw.rounded_rectangle((140, 1320, 350, 1378), radius=28, fill=accent)
    draw.text((178, 1334), "sem custo", font=_font(24, bold=True), fill=(255, 255, 255))
    storage_root = Path(STORAGE_PATH).resolve()
    output_path = storage_root / relative_path
    output_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(output_path, format="PNG", optimize=True)


def _image_response_to_bytes(response: Any) -> tuple[bytes, dict[str, Any]]:
    data = response.data[0]
    metadata = data.model_dump() if hasattr(data, "model_dump") else {}
    b64_json = getattr(data, "b64_json", None) or metadata.get("b64_json")
    url = getattr(data, "url", None) or metadata.get("url")
    if b64_json:
        return base64.b64decode(b64_json), {k: v for k, v in metadata.items() if k != "b64_json"}
    if url:
        with urlopen(url, timeout=45) as handle:
            return handle.read(), {**metadata, "url": url}
    raise ValueError("OpenAI image response did not include b64_json or url.")


def gerar_asset_visual(db: Session, carrossel: Carrossel) -> CarrosselAsset:
    prompt = _prompt_asset(carrossel)
    version = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    relative_path = _relative_asset_path(carrossel.id, version)

    if openai_image_configurado():
        _verify_limits(db, carrossel)
        registrar_log(
            db,
            carrossel_id=carrossel.id,
            etapa="asset_ia",
            status=ASSET_CALL_STARTED,
            mensagem="Geração de asset visual com OpenAI iniciada.",
            detalhes={"modelo": OPENAI_IMAGE_MODEL, "size": OPENAI_IMAGE_SIZE, "limites": _limites_configurados()},
        )
        client = OpenAI(api_key=OPENAI_API_KEY)
        response = client.images.generate(
            model=OPENAI_IMAGE_MODEL,
            prompt=prompt,
            size=OPENAI_IMAGE_SIZE,
            n=1,
        )
        content, provider_metadata = _image_response_to_bytes(response)
        _save_bytes(content, relative_path)
        revised_prompt = provider_metadata.get("revised_prompt")
        modelo = OPENAI_IMAGE_MODEL
        provider_response = {
            "provider": "openai",
            "model": OPENAI_IMAGE_MODEL,
            "size": OPENAI_IMAGE_SIZE,
            "response": provider_metadata,
            "generated_at": datetime.utcnow().isoformat(),
        }
        log_status = "CONCLUIDO"
        log_message = "Asset visual com OpenAI concluído."
    else:
        _fallback_image(carrossel, relative_path)
        revised_prompt = None
        modelo = FALLBACK_MODEL
        provider_response = {
            "provider": "local",
            "mock": True,
            "model": FALLBACK_MODEL,
            "size": "1024x1536",
            "generated_at": datetime.utcnow().isoformat(),
        }
        log_status = "FALLBACK_MOCK"
        log_message = "Asset visual fallback gerado localmente."

    asset = CarrosselAsset(
        carrossel_id=carrossel.id,
        tipo="background",
        status=ASSET_STATUS_ATIVO,
        prompt=prompt,
        revised_prompt=revised_prompt,
        asset_path=relative_path.as_posix(),
        asset_url=_public_url(relative_path, version),
        modelo=modelo,
        provider_response=provider_response,
    )
    db.add(asset)
    db.flush()
    registrar_log(
        db,
        carrossel_id=carrossel.id,
        etapa="asset_ia",
        status=log_status,
        mensagem=log_message,
        detalhes={"asset_id": asset.id, "modelo": modelo, "asset_path": asset.asset_path},
    )
    return asset


def remover_asset_visual(db: Session, asset: CarrosselAsset) -> CarrosselAsset:
    asset.status = ASSET_STATUS_REMOVIDO
    registrar_log(
        db,
        carrossel_id=asset.carrossel_id,
        etapa="asset_ia",
        status="REMOVIDO",
        mensagem="Asset visual removido da seleção.",
        detalhes={"asset_id": asset.id},
    )
    return asset
