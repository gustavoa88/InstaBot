from pathlib import Path

from sqlalchemy.orm import Session

from app.config import STORAGE_PATH
from app.models.carrossel import ASSET_STATUS_REMOVIDO, CarrosselAsset, CarrosselSlide
from app.services.log_service import registrar_log


def _resolver_storage_path(imagem_path: str | None, storage_root: Path) -> Path | None:
    if not imagem_path:
        return None
    path = Path(imagem_path)
    if path.is_absolute():
        return None
    resolved = (storage_root / path).resolve()
    if storage_root == resolved or storage_root not in resolved.parents:
        return None
    return resolved


def limpar_midias_expiradas(db: Session) -> int:
    slides_expirados = []

    removidos = 0
    storage_root = Path(STORAGE_PATH).resolve()
    expirados_ids = {slide.id for slide in slides_expirados}
    referencias_ativas = set()
    for slide in db.query(CarrosselSlide).all():
        if slide.id in expirados_ids:
            continue
        resolved = _resolver_storage_path(slide.imagem_path, storage_root)
        if resolved is not None:
            referencias_ativas.add(resolved)
    for asset in db.query(CarrosselAsset).filter(CarrosselAsset.status != ASSET_STATUS_REMOVIDO).all():
        resolved = _resolver_storage_path(asset.asset_path, storage_root)
        if resolved is not None:
            referencias_ativas.add(resolved)

    for slide in slides_expirados:
        resolved = _resolver_storage_path(slide.imagem_path, storage_root)
        if resolved is None:
            slide.imagem_path = None
            slide.imagem_url = None
            continue
        try:
            if resolved not in referencias_ativas and resolved.exists():
                resolved.unlink()
                removidos += 1
            slide.imagem_path = None
            slide.imagem_url = None
        except OSError as exc:
            registrar_log(
                db,
                carrossel_id=slide.carrossel_id,
                etapa="limpeza_midia",
                status="ERRO",
                mensagem="Falha ao remover mídia expirada.",
                detalhes={"slide_id": slide.id, "erro": exc.__class__.__name__},
            )

    registrar_log(
        db,
        carrossel_id=None,
        etapa="limpeza_midia",
        status="CONCLUIDO",
        mensagem="Limpeza automática de mídia concluída.",
        detalhes={"arquivos_removidos": removidos},
    )
    return removidos
