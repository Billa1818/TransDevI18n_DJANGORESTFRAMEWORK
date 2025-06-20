from __future__ import absolute_import, unicode_literals
import os
from celery import Celery
from celery.schedules import crontab



# Définir le module de configuration de Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'TransDevI18n.settings')

app = Celery('TransDevI18n')

# Charger la configuration de Django pour Celery avec le namespace CELERY
app.config_from_object('django.conf:settings', namespace='CELERY')

# Découverte automatique des tâches dans toutes les apps Django dans le fichier tasks.py
app.autodiscover_tasks()

# Configuration des queues et du routage
app.conf.update(
    task_default_queue='celery',
    task_default_exchange='celery',
    task_default_routing_key='celery',
    task_routes={
        'translations.tasks.*': {'queue': 'celery'},
        'notifications.tasks.*': {'queue': 'celery'},
        'files.tasks.*': {'queue': 'celery'},
        'accounts.tasks.*': {'queue': 'celery'},
    },
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
)

# Planification des tâches avec Celery Beat
app.conf.beat_schedule = {
    'cleanup-old-notifications': {
        'task': 'notifications.tasks.cleanup_old_notifications',
        'schedule': crontab(hour=2, minute=0),  # Tous les jours à 2h00
        'kwargs': {'days_to_keep': 30}
    },
    'cleanup-read-notifications': {
        'task': 'notifications.tasks.cleanup_read_notifications',
        'schedule': crontab(hour=3, minute=0),  # Tous les jours à 3h00
        'kwargs': {'days_to_keep': 7}
    },
    'cleanup-notifications-comprehensive': {
        'task': 'notifications.tasks.cleanup_notifications_comprehensive',
        'schedule': crontab(hour=1, minute=0, day_of_week=0),  # Tous les dimanches à 1h00
    },
}

@app.task(bind=True)
def debug_task(self):
    print(f'Requête : {self.request!r}')

# demarer le worker Celery avec la commande :
# celery -A TransDevI18n worker --loglevel=info