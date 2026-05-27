import io
import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path


def _iso_z(value):
    if value is None:
        value = datetime.now(timezone.utc)
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _resolve_slide_path(storage_root: Path, imagem_path: str | None) -> Path | None:
    if not imagem_path:
        return None
    path = Path(imagem_path)
    if path.is_absolute():
        return None
    resolved = (storage_root / path).resolve()
    if storage_root != resolved and storage_root not in resolved.parents:
        return None
    return resolved if resolved.exists() else None


def _readme_text(carrossel) -> str:
    hashtags = " ".join(carrossel.hashtags or [])
    return f"""INSTRUÇÕES: Como enviar seu Carrossel para Facebook Content Calendar
=============================================================================

1. Acesse: https://business.facebook.com/latest/content_calendar
2. Clique em "Criar publicação" ou "Upload em lote"
3. Selecione as imagens da pasta "slides/" em sequência (01.png, 02.png, etc.)
4. Cole a legenda e hashtags (veja abaixo)

Legenda:
{carrossel.legenda or ""}

Hashtags:
{hashtags}

5. Escolha data/horário de publicação
6. Clique em "Agendar"

Pronto! Seu carrossel ficara pronto para envio manual no calendario de conteudo.
"""


def export_carousel_to_zip(db, carrossel, storage_path) -> bytes:
    slides = sorted(carrossel.slides or [], key=lambda slide: slide.numero_slide)
    if not slides:
        raise ValueError("Carrossel não possui slides renderizados.")

    storage_root = Path(storage_path).resolve()
    slide_files = []
    for slide in slides:
        slide_path = _resolve_slide_path(storage_root, slide.imagem_path)
        if slide_path is None:
            raise ValueError("Um ou mais slides não têm imagem renderizada.")
        slide_files.append((slide, slide_path))

    metadata = {
        "carousel_id": carrossel.id,
        "title": carrossel.titulo,
        "caption": carrossel.legenda,
        "hashtags": carrossel.hashtags or [],
        "total_slides": len(slides),
        "created_at": _iso_z(carrossel.created_at),
        "slides": [
            {
                "number": slide.numero_slide,
                "titulo": slide.titulo,
                "texto_principal": slide.texto_principal,
                "texto_secundario": slide.texto_secundario,
            }
            for slide in slides
        ],
    }

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for index, (_slide, slide_path) in enumerate(slide_files, start=1):
            archive.write(slide_path, f"slides/{index:02d}.png")
        archive.writestr("metadata.json", json.dumps(metadata, ensure_ascii=False, indent=2))
        archive.writestr("README.txt", _readme_text(carrossel))

    return buffer.getvalue()
