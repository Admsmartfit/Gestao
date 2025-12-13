from flask import Flask, redirect, url_for
from app.extensions import db, login_manager, migrate
from app.models.models import Usuario

def create_app():
    app = Flask(__name__)
    app.config.from_object('config.Config')

    # Inicializar extensões
    db.init_app(app)
    login_manager.init_app(app)
    migrate.init_app(app, db)

    # User Loader do Flask-Login
    @login_manager.user_loader
    def load_user(user_id):
        return Usuario.query.get(int(user_id))

    # Registrar Blueprints
    from app.routes import auth, ponto, admin, os
    
    app.register_blueprint(auth.bp)
    app.register_blueprint(ponto.bp)
    app.register_blueprint(admin.bp)
    app.register_blueprint(os.bp)

    # --- CORREÇÃO: ROTA RAIZ (ROOT) ---
    @app.route('/')
    def root():
        # Redireciona automaticamente para o login
        return redirect(url_for('auth.login'))

    return app