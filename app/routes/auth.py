from datetime import datetime
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required
from app.models.models import Usuario
from app.extensions import db

bp = Blueprint('auth', __name__, url_prefix='/auth')

# ... imports ...

@bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        # MUDANÇA: Recebe username em vez de email
        username = request.form.get('username')
        senha = request.form.get('senha')
        
        # Busca por username
        user = Usuario.query.filter_by(username=username).first()

        if user and user.check_senha(senha):
            login_user(user)
            user.ultimo_acesso = datetime.utcnow()
            db.session.commit()
            return redirect(url_for('ponto.index'))
        
        flash('Usuário ou senha incorretos.', 'danger')
    
    return render_template('login.html')

@bp.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('auth.login'))