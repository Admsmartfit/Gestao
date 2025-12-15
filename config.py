import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'chave-super-secreta-dev'
    # Configuração SQLite para desenvolvimento [cite: 22]
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///gmm.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    CELERY_BROKER_URL = os.environ.get('CELERY_BROKER_URL') or 'redis://localhost:6379/0'
    CELERY_RESULT_BACKEND = os.environ.get('CELERY_RESULT_BACKEND') or 'redis://localhost:6379/0'
    # Integração MegaAPI (Segurança: Ler de variável de ambiente)
    MEGA_API_KEY = os.environ.get('MEGA_API_KEY') or 'sua_api_key_aqui'
    MEGA_API_URL = "https://api.megaapi.com.br/v1/messages/send"