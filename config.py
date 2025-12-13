import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'chave-super-secreta-dev'
    # Configuração SQLite para desenvolvimento [cite: 22]
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///gmm.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False