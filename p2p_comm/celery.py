import os
from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "p2p_comm.settings")

app = Celery("p2p_comm")
app.conf.update(timezone = 'Asia/Kolkata')

# Load settings from Django
app.config_from_object("django.conf:settings", namespace="CELERY")

# Auto-discover tasks inside each app
app.autodiscover_tasks()

@app.task(bind=True)
def debug_task(self):
    print('Request: {0!r}'.format(self.request))