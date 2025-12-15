from flask import Blueprint, render_template, request, flash, redirect, url_for
from flask_login import login_required, current_user
from app.extensions import db
from app.models.models import Unidade, RegistroPonto
from app.models.estoque_models import OrdemServico
from app.utils.decorators import require_unit_ip
from datetime import datetime, timedelta # Importar timedelta

bp = Blueprint('ponto', __name__, url_prefix='/dashboard')

@bp.route('/')
@login_required
def index():
    unidades = Unidade.query.filter_by(ativa=True).all()
    registro_aberto = RegistroPonto.query.filter_by(
        usuario_id=current_user.id, 
        data_hora_saida=None
    ).first()
    
    if current_user.tipo == 'tecnico':
        minhas_os = OrdemServico.query.filter_by(tecnico_id=current_user.id).order_by(OrdemServico.prioridade.desc()).all()
    else:
        minhas_os = OrdemServico.query.order_by(OrdemServico.data_abertura.desc()).limit(20).all()

    return render_template('dashboard.html', 
                         unidades=unidades, 
                         registro_aberto=registro_aberto,
                         minhas_os=minhas_os)

@bp.route('/checkin', methods=['POST'])
@login_required
@require_unit_ip
def checkin():
    unidade_id = request.form.get('unidade_id')
    lat = request.form.get('latitude')
    lon = request.form.get('longitude')
    
    ponto_existente = RegistroPonto.query.filter_by(
        usuario_id=current_user.id, 
        data_hora_saida=None
    ).first()

    if ponto_existente:
        flash('Você já possui um registro de entrada aberto.', 'warning')
        return redirect(url_for('ponto.index'))

    novo_ponto = RegistroPonto(
        usuario_id=current_user.id,
        unidade_id=unidade_id,
        ip_origem_entrada=request.remote_addr,
        data_hora_entrada=datetime.utcnow(),
        latitude=lat, # [Novo] Captura Geo
        longitude=lon # [Novo] Captura Geo
    )
    
    db.session.add(novo_ponto)
    db.session.commit()
    
    flash('Entrada registrada com sucesso!', 'success')
    return redirect(url_for('ponto.index'))

@bp.route('/checkout', methods=['POST'])
@login_required
def checkout():
    registro_id = request.form.get('registro_id')
    registro = RegistroPonto.query.get(registro_id)

    if registro and registro.usuario_id == current_user.id and registro.data_hora_saida is None:
        agora = datetime.utcnow()
        registro.data_hora_saida = agora
        registro.ip_origem_saida = request.remote_addr
        
        # [RN002] Alerta se intervalo < 2 horas
        duracao = agora - registro.data_hora_entrada
        if duracao < timedelta(hours=2):
            registro.observacoes = "Alerta: Turno inferior a 2 horas."
            flash('Saída registrada. Atenção: Turno menor que 2 horas.', 'warning')
        else:
            flash('Saída registrada com sucesso!', 'success')
            
        db.session.commit()
    else:
        flash('Erro ao registrar saída.', 'danger')

    return redirect(url_for('ponto.index'))