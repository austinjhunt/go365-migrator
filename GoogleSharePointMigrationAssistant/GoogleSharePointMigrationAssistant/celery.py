""" 
Use Celery for asynchronous task management 
to avoid long wait times for data migration and scans. 
"""

import os
from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "GoogleSharePointMigrationAssistant.settings")
app = Celery("GoogleSharePointMigrationAssistant")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()