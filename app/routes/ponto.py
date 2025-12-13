from flask import Blueprint, render_template, request, flash, redirect, url_for
from flask_login import login_required, current_user
from app.extensions import db
from app.models.models import Unidade, RegistroPonto
from app.models.estoque_models import OrdemServico # Importar model de OS
from app.utils.decorators import require_unit_ip
from datetime import datetime

bp = Blueprint('ponto', __name__, url_prefix='/dashboard') # Mudamos prefixo para ficar mais semântico

@bp.route('/')
@login_required
def index():
    # 1. Dados para o Ponto (Apenas se não for admin, mas carregamos para lógica do template)
    unidades = Unidade.query.filter_by(ativa=True).all()
    registro_aberto = RegistroPonto.query.filter_by(
        usuario_id=current_user.id, 
        data_hora_saida=None
    ).first()
    # 2. Dados para Ordens de Serviço (OS)
    # Se for técnico, vê as suas. Se for admin/gerente, vê todas (ou lógica específica)
    if current_user.tipo == 'tecnico':
        minhas_os = OrdemServico.query.filter_by(tecnico_id=current_user.id).order_by(OrdemServico.prioridade.desc()).all()
    else:
        minhas_os = OrdemServico.query.order_by(OrdemServico.data_abertura.desc()).limit(20).all()

    return render_template('dashboard.html', 
                         unidades=unidades, 
                         registro_aberto=registro_aberto,
                         minhas_os=minhas_os)
                         
    # Histórico dos últimos 7 dias [cite: 146]
    historico = RegistroPonto.query.filter_by(usuario_id=current_user.id)\
        .order_by(RegistroPonto.data_hora_entrada.desc())\
        .limit(10).all()

    return render_template('ponto.html', unidades=unidades, registro_aberto=registro_aberto, historico=historico)

@bp.route('/checkin', methods=['POST']) # [cite: 112]
@login_required
@require_unit_ip # RN-001 [cite: 80]
def checkin():
    unidade_id = request.form.get('unidade_id')
    
    # RN-002: Controle de Ponto Duplicado [cite: 87]
    ponto_existente = RegistroPonto.query.filter_by(
        usuario_id=current_user.id, 
        data_hora_saida=None
    ).first()

    if ponto_existente:
        flash('Você já possui um registro de entrada aberto. Faça o checkout primeiro.', 'warning')
        return redirect(url_for('ponto.index'))

    novo_ponto = RegistroPonto(
        usuario_id=current_user.id,
        unidade_id=unidade_id,
        ip_origem_entrada=request.remote_addr, # [cite: 82]
        data_hora_entrada=datetime.utcnow()
    )
    
    db.session.add(novo_ponto)
    db.session.commit()
    
    flash('Entrada registrada com sucesso!', 'success')
    return redirect(url_for('ponto.index'))

@bp.route('/checkout', methods=['POST']) # [cite: 131]
@login_required
def checkout():
    registro_id = request.form.get('registro_id')
    registro = RegistroPonto.query.get(registro_id)

    if registro and registro.usuario_id == current_user.id and registro.data_hora_saida is None:
        registro.data_hora_saida = datetime.utcnow()
        registro.ip_origem_saida = request.remote_addr
        db.session.commit()
        flash('Saída registrada com sucesso!', 'success')
    else:
        flash('Erro ao registrar saída.', 'danger')

    return redirect(url_for('ponto.index'))