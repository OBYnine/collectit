# Делаем celery-app доступным как `from collectit import celery_app`,
# а также активируем его при загрузке Django (чтобы @shared_task работал).
from .celery import app as celery_app

__all__ = ("celery_app",)
