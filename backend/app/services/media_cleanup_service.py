from datetime import datetime, timedelta
from pathlib import Path

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from app.config import MEDIA_RETENTION_DAYS, STORAGE_PATH
from app.models.carrossel import Carrossel, CarrosselSlide, STATUS_CANCELADO, STATUS_PUBLICADO, STATUS_REJEITADO
from app.services.log_service import registrar_log


def limpar_midias_expiradas(db: Session) -> int:
    limite = datetime.utcnow() - timedelta(days=MEDIA_RETENTION_DAYS)
    slides = (
        db.query(CarrosselSlide)
        .join(Carrossel)
        .filter(
            or_(
                Carrossel.status == STATUS_REJEITADO,
                Carrossel.status == STATUS_CANCELADO,
                and_(Carrossel.status == STATUS_PUBLICADO, Carrossel.publicado_em <= limite),
            )
        )
        .all()
    )

    removidos = 0
    storage_root = Path(STORAGE_PATH).resolve()
    for slide in slides:
        if not slide.imagem_path:
            continue
        path = Path(slide.imagem_path)
        if not path.is_absolute():
            path = storage_root / path
        try:
            resolved = path.resolve()
            if storage_root in resolved.parents and resolved.exists():
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
                detalhes={"slide_id": slide.id, "erro": str(exc)},
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
