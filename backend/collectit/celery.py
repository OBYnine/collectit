"""Celery-приложение. Подхватывает все @shared_task из приложений."""
import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "collectit.settings")

app = Celery("collectit")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()


@app.task(bind=True)
def debug_task(self):
    print(f"Request: {self.request!r}")
