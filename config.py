import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'chave-super-secreta-dev'
    
    # Detecção automática: Se houver DATABASE_URL (Render/Heroku/AWS), usa Postgres.
    # Senão, usa SQLite local.
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL')
    if SQLALCHEMY_DATABASE_URI and SQLALCHEMY_DATABASE_URI.startswith("postgres://"):
        SQLALCHEMY_DATABASE_URI = SQLALCHEMY_DATABASE_URI.replace("postgres://", "postgresql://", 1)
    
    if not SQLALCHEMY_DATABASE_URI:
        SQLALCHEMY_DATABASE_URI = 'sqlite:///gmm.db'

    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Redis configuration
    CELERY_BROKER_URL = os.environ.get('CELERY_BROKER_URL') or 'redis://localhost:6379/0'
    CELERY_RESULT_BACKEND = os.environ.get('CELERY_RESULT_BACKEND') or 'redis://localhost:6379/0'
    
    MEGA_API_KEY = os.environ.get('MEGA_API_KEY')
    MEGA_API_URL = "https://api.megaapi.com.br/v1/messages/send"
    
    FERNET_KEY = os.environ.get('FERNET_KEY') or '00000000000000000000000000000000'
    
    CELERY_IMPORTS = ('app.tasks',)