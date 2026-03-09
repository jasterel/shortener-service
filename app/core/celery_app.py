from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "shortener",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
)

celery_app.conf.timezone = "UTC"
celery_app.conf.task_routes = {
    "app.tasks.cleanup_tasks.*": {"queue": "cleanup"}
}
celery_app.conf.beat_schedule = {
    "cleanup-expired-links": {
        "task": "app.tasks.cleanup_tasks.cleanup_expired_links",
        "schedule": 300.0,
    },
    "cleanup-inactive-links": {
        "task": "app.tasks.cleanup_tasks.cleanup_inactive_links",
        "schedule": 3600.0,
    },
}