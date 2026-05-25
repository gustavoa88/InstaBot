import base64
import hashlib
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
FALLBACK_MODEL = "fallback_pillow_asset_v2"


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


def _relative_slide_asset_path(carrossel_id: int, numero_slide: int, version: str) -> Path:
    return Path("carrosseis") / str(carrossel_id) / "assets" / f"slide-{numero_slide:02d}-asset-{version}.png"


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
    return f"""
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


def _prompt_slide_asset(carrossel: Carrossel, slide) -> str:
    visual_note = (getattr(slide, "observacao_visual", None) or "").strip()
    slide_text = (getattr(slide, "texto_principal", None) or "").strip()
    idea = (getattr(carrossel, "ideia_original", None) or "").strip()
    return f"""
Crie uma imagem vertical exclusiva para o slide {getattr(slide, 'numero_slide', '')} de um carrossel de Instagram.
Tema do carrossel: {carrossel.tema or 'conteúdo profissional'}.
Título do carrossel: {carrossel.titulo or 'carrossel de conteúdo'}.
Briefing visual específico do slide: {visual_note[:900] or 'composição limpa e coerente com o conteúdo'}.
Texto principal do slide para contexto: {slide_text[:500] or 'não informado'}.
Ideia original para contexto: {idea[:500] or 'não informada'}.

Regras obrigatórias:
- Não inclua texto, letras, números, logotipos ou marcas.
- Não use pessoas identificáveis.
- Faça uma composição diferente dos demais slides, com visual próprio para este briefing.
- Preserve áreas de respiro para que textos sejam aplicados depois.
- Visual profissional, vertical e pronto para servir como apoio ao preview do slide.
""".strip()


def _prompt_hash(prompt: str) -> str:
    return hashlib.sha256(prompt.encode("utf-8")).hexdigest()


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


def _image_limit_status(db: Session, carrossel: Carrossel) -> dict[str, int | str] | None:
    if OPENAI_IMAGE_DAILY_REQUEST_LIMIT > 0:
        inicio_dia = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        chamadas_dia = _count_openai_image_calls(db, desde=inicio_dia)
        if chamadas_dia >= OPENAI_IMAGE_DAILY_REQUEST_LIMIT:
            return {"escopo": "diário", "limite": OPENAI_IMAGE_DAILY_REQUEST_LIMIT, "chamadas": chamadas_dia}
    if OPENAI_IMAGE_CARROSSEL_REQUEST_LIMIT > 0:
        chamadas_carrossel = _count_openai_image_calls(db, carrossel_id=carrossel.id)
        if chamadas_carrossel >= OPENAI_IMAGE_CARROSSEL_REQUEST_LIMIT:
            return {"escopo": "por carrossel", "limite": OPENAI_IMAGE_CARROSSEL_REQUEST_LIMIT, "chamadas": chamadas_carrossel}
    return None


def _save_bytes(content: bytes, relative_path: Path) -> None:
    storage_root = Path(STORAGE_PATH).resolve()
    output_path = storage_root / relative_path
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(content)


def _fallback_image(carrossel: Carrossel, relative_path: Path, slide=None) -> None:
    width, height = 1024, 1536
    seed_text = f"{getattr(slide, 'numero_slide', '')}|{getattr(slide, 'observacao_visual', '')}|{carrossel.tema or ''}"
    digest = hashlib.sha256(seed_text.encode("utf-8")).digest()
    image = Image.new("RGB", (width, height), (244, 247, 245))
    draw = ImageDraw.Draw(image)
    accent = (70 + digest[0] % 135, 72 + digest[1] % 128, 82 + digest[2] % 118)
    deep = tuple(max(18, part - 55) for part in accent)
    warm = (232 + digest[3] % 18, 214 + digest[4] % 28, 190 + digest[5] % 36)
    mist = tuple(min(255, int(part * 0.38 + 210)) for part in accent)
    for y in range(height):
        ratio = y / height
        color = (
            int(warm[0] + (mist[0] - warm[0]) * ratio),
            int(warm[1] + (mist[1] - warm[1]) * ratio),
            int(warm[2] + (mist[2] - warm[2]) * ratio),
        )
        draw.line((0, y, width, y), fill=color)

    shift = digest[6] % 220
    draw.ellipse((-260 + shift, 80, 520 + shift, 860), fill=tuple(min(255, part + 64) for part in accent))
    draw.ellipse((570 - shift // 2, 520, 1280 - shift // 2, 1290), fill=deep)
    draw.rounded_rectangle((88, 170, width - 88, height - 220), radius=88, outline=(255, 255, 255), width=14)
    draw.rounded_rectangle((146, 952, width - 146, 1162), radius=54, fill=tuple(min(255, part + 104) for part in mist))
    draw.polygon(
        [
            (0, 1080 + digest[7] % 120),
            (width, 820 + digest[8] % 140),
            (width, height),
            (0, height),
        ],
        fill=tuple(max(0, part - 18) for part in accent),
    )
    draw.rounded_rectangle((690, 1020, width + 60, 1288), radius=70, fill=tuple(max(0, part - 36) for part in deep))
    draw.line((138, 1288, 460, 1288), fill=(255, 255, 255), width=8)
    if slide is not None:
        draw.text((138, 1328), f"{slide.numero_slide:02d}", font=_font(52, bold=True), fill=(255, 255, 255))
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


def _asset_file_exists(asset: CarrosselAsset) -> bool:
    asset_path = getattr(asset, "asset_path", None)
    if not asset_path:
        return False
    path = Path(asset_path)
    if path.is_absolute():
        return False
    storage_root = Path(STORAGE_PATH).resolve()
    resolved = (storage_root / path).resolve()
    return storage_root in resolved.parents and resolved.exists()


def _asset_matches_slide(asset: CarrosselAsset, *, slide, prompt_hash: str) -> bool:
    response = getattr(asset, "provider_response", None) or {}
    if response.get("provider") == "local" and (getattr(asset, "modelo", None) or response.get("model")) != FALLBACK_MODEL:
        return False
    return (
        getattr(asset, "tipo", None) == "slide_background"
        and getattr(asset, "status", None) == ASSET_STATUS_ATIVO
        and response.get("numero_slide") == getattr(slide, "numero_slide", None)
        and response.get("prompt_hash") == prompt_hash
        and _asset_file_exists(asset)
    )


def _find_reusable_slide_asset(db: Session, carrossel: Carrossel, slide, prompt_hash: str) -> CarrosselAsset | None:
    local_candidates = [
        item
        for item in getattr(db, "added", [])
        if isinstance(item, CarrosselAsset) and getattr(item, "carrossel_id", None) == carrossel.id
    ]
    for asset in reversed(local_candidates):
        if _asset_matches_slide(asset, slide=slide, prompt_hash=prompt_hash):
            return asset

    if not hasattr(db, "query"):
        return None
    try:
        candidates = (
            db.query(CarrosselAsset)
            .filter(CarrosselAsset.carrossel_id == carrossel.id)
            .filter(CarrosselAsset.status == ASSET_STATUS_ATIVO)
            .filter(CarrosselAsset.tipo == "slide_background")
            .all()
        )
    except Exception:
        return None
    for asset in reversed(candidates):
        if _asset_matches_slide(asset, slide=slide, prompt_hash=prompt_hash):
            return asset
    return None


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


def _fallback_provider_response(*, slide, prompt_hash: str, reason: str) -> dict[str, Any]:
    return {
        "provider": "local",
        "mock": True,
        "model": FALLBACK_MODEL,
        "size": "1024x1536",
        "slide_id": getattr(slide, "id", None),
        "numero_slide": slide.numero_slide,
        "prompt_hash": prompt_hash,
        "fallback_reason": reason,
        "generated_at": datetime.utcnow().isoformat(),
    }


def gerar_asset_visual_slide(db: Session, carrossel: Carrossel, slide) -> CarrosselAsset:
    prompt = _prompt_slide_asset(carrossel, slide)
    prompt_hash = _prompt_hash(prompt)
    reusable = _find_reusable_slide_asset(db, carrossel, slide, prompt_hash)
    if reusable is not None:
        registrar_log(
            db,
            carrossel_id=carrossel.id,
            etapa="asset_ia",
            status="REUTILIZADO",
            mensagem="Asset visual do slide reutilizado.",
            detalhes={
                "asset_id": reusable.id,
                "asset_path": reusable.asset_path,
                "slide_id": getattr(slide, "id", None),
                "numero_slide": slide.numero_slide,
                "prompt_hash": prompt_hash,
            },
        )
        return reusable

    version = datetime.utcnow().strftime("%Y%m%d%H%M%S%f")
    relative_path = _relative_slide_asset_path(carrossel.id, slide.numero_slide, version)
    revised_prompt = None
    limit_status = _image_limit_status(db, carrossel) if openai_image_configurado() else None

    if openai_image_configurado() and limit_status is None:
        registrar_log(
            db,
            carrossel_id=carrossel.id,
            etapa="asset_ia",
            status=ASSET_CALL_STARTED,
            mensagem="Geração de asset visual do slide com OpenAI iniciada.",
            detalhes={
                "modelo": OPENAI_IMAGE_MODEL,
                "size": OPENAI_IMAGE_SIZE,
                "slide_id": getattr(slide, "id", None),
                "numero_slide": slide.numero_slide,
                "prompt_hash": prompt_hash,
                "limites": _limites_configurados(),
            },
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
            "slide_id": getattr(slide, "id", None),
            "numero_slide": slide.numero_slide,
            "prompt_hash": prompt_hash,
            "response": provider_metadata,
            "generated_at": datetime.utcnow().isoformat(),
        }
        log_status = "CONCLUIDO"
        log_message = "Asset visual do slide com OpenAI concluído."
    else:
        _fallback_image(carrossel, relative_path, slide=slide)
        modelo = FALLBACK_MODEL
        reason = "limite_openai" if limit_status else "openai_nao_configurado"
        provider_response = _fallback_provider_response(slide=slide, prompt_hash=prompt_hash, reason=reason)
        if limit_status:
            provider_response["limit"] = limit_status
        log_status = "FALLBACK_LIMITE" if limit_status else "FALLBACK_MOCK"
        log_message = (
            "Limite de OpenAI atingido; asset visual fallback do slide gerado localmente."
            if limit_status
            else "Asset visual fallback do slide gerado localmente."
        )

    asset = CarrosselAsset(
        carrossel_id=carrossel.id,
        tipo="slide_background",
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
        detalhes={
            "asset_id": asset.id,
            "modelo": modelo,
            "asset_path": asset.asset_path,
            "slide_id": getattr(slide, "id", None),
            "numero_slide": slide.numero_slide,
            "prompt_hash": prompt_hash,
            "limit": limit_status,
        },
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
