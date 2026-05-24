from sqlalchemy.orm import Session

from app.models.carrossel import LogExecucao


def registrar_log(
    db: Session,
    *,
    carrossel_id: int | None,
    etapa: str,
    status: str,
    mensagem: str,
    detalhes: dict | None = None,
) -> LogExecucao:
    log = LogExecucao(
        carrossel_id=carrossel_id,
        etapa=etapa,
        status=status,
        mensagem=mensagem,
        detalhes=detalhes or {},
    )
    db.add(log)
    return log
