from app.database import SessionLocal
from app.services.publication_service import publicar_agendadas_vencidas
from app.workers.celery_app import celery_app


@celery_app.task(name="app.workers.tasks_publication.publicar_publicacoes_vencidas")
def publicar_publicacoes_vencidas():
    db = SessionLocal()
    try:
        total = publicar_agendadas_vencidas(db)
        db.commit()
        return {"ok": True, "publicacoes_processadas": total}
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
