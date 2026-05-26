from app.database import SessionLocal
from app.models.carrossel import Carrossel
from app.services.generation_service import gerar_carrossel_textual
from app.services.user_config_service import credentials_for_user
from app.workers.celery_app import celery_app


@celery_app.task(name="app.workers.tasks_generation.gerar_carrossel")
def gerar_carrossel(carrossel_id: int, regenerar: bool = False):
    db = SessionLocal()
    try:
        carrossel = db.query(Carrossel).filter(Carrossel.id == carrossel_id).first()
        if carrossel is None:
            return {"ok": False, "erro": "Carrossel não encontrado."}
        if carrossel.usuario is None:
            return {"ok": False, "erro": "Carrossel sem usuário associado."}
        gerar_carrossel_textual(
            db,
            carrossel,
            credentials=credentials_for_user(db, carrossel.usuario),
            regenerar=regenerar,
            usuario=carrossel.usuario,
        )
        db.commit()
        return {"ok": True, "carrossel_id": carrossel_id}
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
