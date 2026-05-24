from app.database import SessionLocal
from app.services.media_cleanup_service import limpar_midias_expiradas
from app.workers.celery_app import celery_app


@celery_app.task(name="app.workers.tasks_cleanup.limpar_midias_expiradas_task")
def limpar_midias_expiradas_task():
    db = SessionLocal()
    try:
        total = limpar_midias_expiradas(db)
        db.commit()
        return {"ok": True, "arquivos_removidos": total}
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
