from app.core.celery_app import celery_app
from app.services.cleanup_service import CleanupService


@celery_app.task
def cleanup_expired_links():
    return CleanupService.remove_expired_links()


@celery_app.task
def cleanup_inactive_links():
    return CleanupService.remove_inactive_links()