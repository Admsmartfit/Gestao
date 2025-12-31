from flask import Flask, redirect, url_for
from app.extensions import db, login_manager, migrate
from app.models.models import Usuario
from celery import Celery
from config import Config
from datetime import datetime

def make_celery(app):
    celery = Celery(
        app.import_name,
        backend=app.config['CELERY_RESULT_BACKEND'],
        broker=app.config['CELERY_BROKER_URL']
    )
    celery.conf.update(app.config)
    class ContextTask(celery.Task):
        def __call__(self, *args, **kwargs):
            with app.app_context():
                return self.run(*args, **kwargs)
    celery.Task = ContextTask
    return celery

def create_app():
    app = Flask(__name__)
    app.config.from_object('config.Config')

    db.init_app(app)
    login_manager.init_app(app)
    migrate.init_app(app, db)

    # Inicializa Celery
    app.celery = make_celery(app)

    @app.context_processor
    def inject_now():
        return {'hoje': datetime.utcnow()}

    @login_manager.user_loader
    def load_user(user_id):
        return Usuario.query.get(int(user_id))

    # Registrar Blueprints
    # Importamos todos os módulos de rotas aqui para evitar erros de importação circular
    from app.routes import (
        auth, 
        ponto, 
        admin, 
        os, 
        terceirizados, 
        analytics, 
        whatsapp, 
        webhook, 
        admin_whatsapp, 
        equipamentos, 
        search, 
        notifications
    )
    
    app.register_blueprint(auth.bp)
    app.register_blueprint(ponto.bp)
    app.register_blueprint(admin.bp)
    app.register_blueprint(os.bp)
    app.register_blueprint(terceirizados.bp)
    app.register_blueprint(analytics.bp)
    app.register_blueprint(whatsapp.bp)
    app.register_blueprint(webhook.bp)
    app.register_blueprint(admin_whatsapp.bp)
    
    # Novo Módulo de Equipamentos
    app.register_blueprint(equipamentos.bp)
    
    # Módulos de Utilidade
    app.register_blueprint(search.bp)
    app.register_blueprint(notifications.bp)
    
    # Rota Raiz
    @app.route('/')
    def root():
        # Redireciona automaticamente para o login
        return redirect(url_for('auth.login'))

    return app