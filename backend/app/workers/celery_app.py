from celery import Celery
from celery.schedules import crontab

from app.config import REDIS_URL

celery_app = Celery(
    "content_carousel_platform",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=[
        "app.workers.tasks_generation",
        "app.workers.tasks_publication",
        "app.workers.tasks_cleanup",
    ],
)

celery_app.conf.timezone = "UTC"
celery_app.conf.beat_schedule = {
    "publish-due-posts-every-minute": {
        "task": "app.workers.tasks_publication.publicar_publicacoes_vencidas",
        "schedule": 60.0,
    },
    "cleanup-expired-media-daily": {
        "task": "app.workers.tasks_cleanup.limpar_midias_expiradas_task",
        "schedule": crontab(hour=3, minute=0),
    },
}
