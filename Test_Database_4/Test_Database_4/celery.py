import os
from celery import Celery
from django.conf import settings

# Set default Django settings module for 'celery' program
os.environ.setdefault("DJANGO_SETTINGS_MODULE", 'Test_Database_4.settings')

app = Celery("Test_Database_4")

# Load configuration from Django settings with CELERY namespace
app.config_from_object('django.conf:settings', namespace="CELERY")

# Load task modules from all registered Django apps
app.autodiscover_tasks()

@app.task(bind=True)
def debug_task(self):
    print(f'Request: {self.request!r}')