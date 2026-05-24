from app.database import SessionLocal
from app.models.carrossel import Carrossel
from app.services.generation_service import gerar_carrossel_mockado
from app.workers.celery_app import celery_app


@celery_app.task(name="app.workers.tasks_generation.gerar_carrossel")
def gerar_carrossel(carrossel_id: int, regenerar: bool = False):
    db = SessionLocal()
    try:
        carrossel = db.query(Carrossel).filter(Carrossel.id == carrossel_id).first()
        if carrossel is None:
            return {"ok": False, "erro": "Carrossel não encontrado."}
        gerar_carrossel_mockado(db, carrossel, regenerar=regenerar)
        db.commit()
        return {"ok": True, "carrossel_id": carrossel_id}
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
