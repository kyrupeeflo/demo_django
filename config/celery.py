# config/celery.py
import os

from celery import Celery

# Point Celery at your Django settings module.
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

# The name here ("config") is just the app label Celery uses internally.
app = Celery("config")

# Load any CELERY_* settings from Django settings, using the CELERY namespace.
app.config_from_object("django.conf:settings", namespace="CELERY")

# Auto-discover tasks.py in each installed app (e.g. books/tasks.py).
app.autodiscover_tasks()


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    """Quick sanity-check task: `debug_task.delay()` and watch the worker log."""
    print(f"Request: {self.request!r}")