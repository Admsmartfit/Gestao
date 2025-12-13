from functools import wraps
from flask import request, abort, flash, redirect, url_for
from flask_login import current_user
from app.models.models import Unidade

def require_unit_ip(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if current_user.is_authenticated and current_user.tipo == 'admin':
            return f(*args, **kwargs)

        unidade_id = request.form.get('unidade_id') or request.args.get('unidade_id')
        if not unidade_id:
            return f(*args, **kwargs)

        unidade = Unidade.query.get(unidade_id)
        if not unidade:
            abort(404)

        user_ip = request.remote_addr
        
        # --- LÓGICA DE RANGE ATUALIZADA ---
        # Aceita "192.168.1, 10.0.0, 172.16"
        # Remove espaços e cria uma lista
        faixas_permitidas = [ip.strip() for ip in unidade.faixa_ip_permitida.split(',')]
        
        ip_valido = False
        for faixa in faixas_permitidas:
            if user_ip.startswith(faixa):
                ip_valido = True
                break
        
        if not ip_valido:
            flash(f"Acesso Negado: IP {user_ip} fora das faixas permitidas ({unidade.faixa_ip_permitida}).", "danger")
            return redirect(url_for('ponto.index'))

        return f(*args, **kwargs)
    return decorated_function