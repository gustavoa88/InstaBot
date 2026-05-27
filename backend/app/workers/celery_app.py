from celery import Celery
from app.config import REDIS_URL

celery_app = Celery(
    "content_carousel_platform",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=[
        "app.workers.tasks_generation",
        "app.workers.tasks_cleanup",
    ],
)

celery_app.conf.timezone = "UTC"
