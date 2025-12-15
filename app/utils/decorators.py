from functools import wraps
from flask import request, abort, flash, redirect, url_for
from flask_login import current_user
from app.models.models import Unidade

def get_real_ip():
    """
    Obtém o IP real do cliente, considerando proxies (X-Forwarded-For).
    """
    if request.headers.getlist("X-Forwarded-For"):
        # Pega o primeiro IP da lista (o do cliente original)
        return request.headers.getlist("X-Forwarded-For")[0].split(',')[0].strip()
    return request.remote_addr

def require_unit_ip(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if current_user.is_authenticated and current_user.tipo == 'admin':
            return f(*args, **kwargs)

        unidade_id = request.form.get('unidade_id') or request.args.get('unidade_id')
        
        # Se não enviou unidade_id, deixa passar (pode ser lógica de outra rota)
        # Mas para checkin é obrigatório.
        if not unidade_id:
             return f(*args, **kwargs)

        unidade = Unidade.query.get(unidade_id)
        if not unidade:
            abort(404)

        user_ip = get_real_ip()
        
        # Lógica de Range
        faixas_permitidas = [ip.strip() for ip in unidade.faixa_ip_permitida.split(',')]
        
        ip_valido = False
        for faixa in faixas_permitidas:
            # Suporta correspondência exata ou sub-rede simples (startswith)
            if user_ip.startswith(faixa):
                ip_valido = True
                break
        
        # Permite localhost para testes se configurado
        if user_ip in ['127.0.0.1', '::1']:
            ip_valido = True

        if not ip_valido:
            flash(f"Acesso Negado: Seu IP ({user_ip}) não está autorizado nesta unidade.", "danger")
            return redirect(url_for('ponto.index'))

        return f(*args, **kwargs)
    return decorated_function