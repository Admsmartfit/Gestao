from celery.schedules import crontab

CELERYBEAT_SCHEDULE = {
    'verificar-saude-whatsapp': {
        'task': 'app.tasks.whatsapp_tasks.verificar_saude_whatsapp',
        'schedule': crontab(minute='*/5'),  # A cada 5 minutos
    },
    'limpar-estados-expirados': {
        'task': 'app.tasks.whatsapp_tasks.limpar_estados_expirados',
        'schedule': crontab(minute=0, hour='*'),  # A cada hora
    },
    'agregar-metricas': {
        'task': 'app.tasks.whatsapp_tasks.agregar_metricas_horarias',
        'schedule': crontab(minute=5, hour='*'),  # xx:05
    }
}
