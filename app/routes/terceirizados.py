from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify
from flask_login import login_required, current_user
from datetime import datetime
from app.extensions import db
from app.models.terceirizados_models import Terceirizado, ChamadoExterno, HistoricoNotificacao
from app.models.estoque_models import OrdemServico
from app.tasks import enviar_whatsapp_task

bp = Blueprint('terceirizados', __name__, url_prefix='/terceirizados')

@bp.route('/chamados', methods=['GET'])
@login_required
def listar_chamados():
    # Filtros opcionais (ex: ?filtro=atrasados)
    filtro = request.args.get('filtro', 'todos')
    
    query = ChamadoExterno.query.order_by(ChamadoExterno.prazo_combinado.asc())
    
    if filtro == 'atrasados':
        query = query.filter(
            ChamadoExterno.prazo_combinado < datetime.utcnow(),
            ChamadoExterno.status != 'concluido'
        )
    
    chamados = query.all()
    
    # Carrega a lista de prestadores para preencher o <select> do Modal
    lista_terceirizados = Terceirizado.query.filter_by(ativo=True).order_by(Terceirizado.nome).all()
    
    return render_template('chamados.html', 
                         chamados=chamados, 
                         terceirizados=lista_terceirizados,
                         hoje=datetime.utcnow())

@bp.route('/chamados/criar', methods=['POST'])
@login_required
def criar_chamado():
    try:
        # Validação básica
        prazo_str = request.form.get('prazo')
        terceirizado_id = request.form.get('terceirizado_id')
        enviar_whats = request.form.get('enviar_whatsapp') == 'on' # Checkbox do formulário
        
        if not prazo_str or not terceirizado_id:
            raise ValueError("Preencha todos os campos obrigatórios.")

        terceirizado = Terceirizado.query.get(terceirizado_id)
        if not terceirizado:
            raise ValueError("Prestador não encontrado.")

        prazo = datetime.strptime(prazo_str, '%Y-%m-%dT%H:%M')
        
        # Gera número do chamado (Ex: CH-2024-17012345)
        num_chamado = f"CH-{datetime.now().year}-{int(datetime.now().timestamp())}"
        
        # Cria o Chamado
        novo_chamado = ChamadoExterno(
            numero_chamado=num_chamado,
            terceirizado_id=terceirizado.id,
            os_id=request.form.get('os_id') or None, # Opcional: vincular a uma OS interna
            titulo=request.form.get('titulo'),
            descricao=request.form.get('descricao'),
            prioridade=request.form.get('prioridade'),
            prazo_combinado=prazo,
            criado_por=current_user.id,
            status='aguardando'
        )
        db.session.add(novo_chamado)
        db.session.commit()
        
        # Lógica de Envio de WhatsApp
        if enviar_whats:
            detalhes_os = ""
            if novo_chamado.os_id:
                os_origem = OrdemServico.query.get(novo_chamado.os_id)
                if os_origem:
                    equipamento = os_origem.equipamento_rel.nome if os_origem.equipamento_rel else 'Geral'
                    detalhes_os = (
                        f"\n📋 *Dados da OS #{os_origem.numero_os}*\n"
                        f"Local: {os_origem.unidade.nome}\n"
                        f"Endereço: {os_origem.unidade.endereco or 'Não informado'}\n"
                        f"Equipamento: {equipamento}\n"
                    )

            msg = (f"🔧 *Solicitação de Serviço GMM*\n\n"
                   f"Chamado: {novo_chamado.numero_chamado}\n"
                   f"Título: {novo_chamado.titulo}\n"
                   f"Prazo: {prazo.strftime('%d/%m %H:%M')}\n"
                   f"{detalhes_os}\n"
                   f"📝 *Descrição:*\n{novo_chamado.descricao}")
            
            # Registra no Histórico
            notif = HistoricoNotificacao(
                chamado_id=novo_chamado.id,
                tipo='criacao',
                destinatario=terceirizado.telefone,
                mensagem=msg,
                status_envio='pendente',
                direcao='outbound'
            )
            db.session.add(notif)
            db.session.commit()
            
            # Envia assíncrono
            enviar_whatsapp_task.delay(notif.id)
            flash('Chamado criado e notificação enviada.', 'success')
        else:
            flash('Chamado criado com sucesso.', 'success')
        
    except ValueError as ve:
        db.session.rollback()
        flash(str(ve), 'warning')
    except Exception as e:
        db.session.rollback()
        flash(f'Erro interno ao criar chamado: {str(e)}', 'danger')
        
    return redirect(url_for('terceirizados.listar_chamados'))

@bp.route('/chamados/<int:id>', methods=['GET'])
@login_required
def detalhes_chamado(id):
    """Exibe detalhes e timeline de comunicação do chamado"""
    chamado = ChamadoExterno.query.get_or_404(id)
    
    # Carregar histórico de mensagens (ordenado por data)
    mensagens = HistoricoNotificacao.query.filter_by(chamado_id=id)\
        .order_by(HistoricoNotificacao.criado_em.asc()).all()
    
    return render_template('chamado_detalhe.html', 
                         chamado=chamado, 
                         mensagens=mensagens)

@bp.route('/chamados/<int:id>/cobrar', methods=['POST'])
@login_required
def cobrar_terceirizado(id):
    """
    Botão de Cobrança: Envia mensagem padrão perguntando sobre a conclusão.
    """
    chamado = ChamadoExterno.query.get_or_404(id)
    
    msg = (f"⏰ *Prazo Vencido*\n\n"
           f"Chamado: {chamado.numero_chamado}\n"
           f"Título: {chamado.titulo}\n"
           f"Previsão de conclusão?")
    
    notif = HistoricoNotificacao(
        chamado_id=chamado.id,
        tipo='cobranca',
        destinatario=chamado.terceirizado.telefone,
        mensagem=msg,
        status_envio='pendente',
        direcao='outbound'
    )
    db.session.add(notif)
    db.session.commit()
    
    try:
        enviar_whatsapp_task.delay(notif.id)
        return jsonify({'success': True, 'msg': 'Cobrança enviada com sucesso!'})
    except Exception as e:
        return jsonify({'success': False, 'msg': f'Erro ao enviar: {str(e)}'}), 500

@bp.route('/chamados/<int:id>/responder', methods=['POST'])
@login_required
def responder_manual(id):
    """
    Permite enviar mensagem manual no chat do chamado.
    """
    chamado = ChamadoExterno.query.get_or_404(id)
    mensagem = request.form.get('mensagem')
    
    if not mensagem:
        return jsonify({'success': False, 'msg': 'Mensagem vazia.'}), 400

    try:
        notif = HistoricoNotificacao(
            chamado_id=chamado.id,
            tipo='manual_outbound',
            remetente=current_user.nome,
            destinatario=chamado.terceirizado.telefone,
            mensagem=mensagem,
            status_envio='pendente',
            direcao='outbound'
        )
        db.session.add(notif)
        db.session.commit()
        
        enviar_whatsapp_task.delay(notif.id)
        
        return jsonify({
            'success': True, 
            'msg': 'Mensagem enviada!',
            'data': datetime.utcnow().strftime('%H:%M'),
            'texto': mensagem
        })
    except Exception as e:
        return jsonify({'success': False, 'msg': str(e)}), 500