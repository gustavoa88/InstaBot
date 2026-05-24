from datetime import datetime

from sqlalchemy.orm import Session

from app.models.carrossel import (
    Carrossel,
    Publicacao,
    STATUS_AGENDADO,
    STATUS_ERRO_PUBLICACAO,
    STATUS_PUBLICADO,
)
from app.services.log_service import registrar_log


def publicar_mockado(db: Session, publicacao: Publicacao) -> Publicacao:
    carrossel = publicacao.carrossel
    if publicacao.status == STATUS_PUBLICADO:
        return publicacao

    if carrossel.status == STATUS_PUBLICADO:
        publicacao.status = STATUS_ERRO_PUBLICACAO
        publicacao.erro = "Carrossel já publicado."
        registrar_log(
            db,
            carrossel_id=carrossel.id,
            etapa="publicacao",
            status="ERRO",
            mensagem="Publicação duplicada bloqueada.",
            detalhes={"publicacao_id": publicacao.id},
        )
        return publicacao

    now = datetime.utcnow()
    publicacao.status = STATUS_PUBLICADO
    publicacao.publicado_em = now
    publicacao.external_post_id = f"mock-{publicacao.id}"
    publicacao.resposta_api = {"mock": True, "message": "Publicação simulada com sucesso."}
    publicacao.erro = None

    carrossel.status = STATUS_PUBLICADO
    carrossel.publicado_em = now
    carrossel.erro_publicacao = None

    registrar_log(
        db,
        carrossel_id=carrossel.id,
        etapa="publicacao",
        status="CONCLUIDO",
        mensagem="Publicação mockada concluída.",
        detalhes={"publicacao_id": publicacao.id},
    )
    return publicacao


def publicar_agendadas_vencidas(db: Session) -> int:
    vencidas = (
        db.query(Publicacao)
        .filter(Publicacao.status == STATUS_AGENDADO)
        .filter(Publicacao.agendado_para <= datetime.utcnow())
        .all()
    )
    for publicacao in vencidas:
        publicar_mockado(db, publicacao)
    return len(vencidas)
