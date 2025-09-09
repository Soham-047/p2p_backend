import os
import ssl
from celery import Celery
from django.conf import settings

# Default Django settings
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "p2p_comm.settings")

app = Celery("p2p_comm")

# Load from Django settings with CELERY_ namespace
app.config_from_object("django.conf:settings", namespace="CELERY")

# SSL config if using rediss://
if settings.REDIS_URL.startswith("rediss://"):
    app.conf.update(
        broker_use_ssl={"ssl_cert_reqs": ssl.CERT_NONE},   # or ssl.CERT_REQUIRED if needed
        redis_backend_use_ssl={"ssl_cert_reqs": ssl.CERT_NONE},
    )

# Auto-discover tasks
app.autodiscover_tasks()

@app.task(bind=True)
def debug_task(self):
    print(f"Request: {self.request!r}")
