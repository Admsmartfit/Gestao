import hashlib
import secrets
from datetime import datetime, timedelta
from flask import Blueprint, jsonify, request, render_template, current_app
from flask_login import login_required, current_user
from app.extensions import db
from app.models.terceirizados_models import ChamadoExterno, HistoricoNotificacao
from app.models.whatsapp_models import TokenAcesso
from app.services.template_service import TemplateService
from app.tasks.whatsapp_tasks import enviar_whatsapp_task

bp = Blueprint('whatsapp', __name__)

def gerar_link_aceite(chamado: ChamadoExterno) -> str:
    """
    Gera link único com token que expira em 7 dias.
    Salva no banco de dados para validação posterior.
    """
    token = secrets.token_urlsafe(32)
    
    token_obj = TokenAcesso(
        token=token,
        entidade_tipo='chamado_externo',
        entidade_id=chamado.id,
        acao='aceitar',
        expira_em=datetime.utcnow() + timedelta(days=7)
    )
    db.session.add(token_obj)
    db.session.commit()
    
    # URL base deve ser configurada ou pega do request
    base_url = request.host_url.rstrip('/')
    return f"{base_url}/api/link/{token}"

@bp.route('/api/chamados/<int:id>/notificar', methods=['POST'])
@login_required
def notificar_terceirizado(id):
    """
    Dispara notificação para terceirizado
    - Cria registro em HistoricoNotificacao
    - Enfileira task Celery
    """
    chamado = ChamadoExterno.query.get_or_404(id)
    
    # Renderizar mensagem usando o TemplateService
    mensagem = TemplateService.render('novo_chamado',
        numero_chamado=chamado.numero_chamado,
        titulo=chamado.titulo,
        prazo=chamado.prazo_combinado.strftime('%d/%m %H:%M'),
        descricao=chamado.descricao,
        link_aceite=gerar_link_aceite(chamado)
    )
    
    # Criar registro de notificação
    notif = HistoricoNotificacao(
        chamado_id=chamado.id,
        tipo='criacao',
        destinatario=chamado.terceirizado.telefone,
        mensagem=mensagem,
        mensagem_hash=hashlib.sha256(mensagem.encode()).hexdigest(),
        status_envio='pendente',
        direcao='outbound'
    )
    db.session.add(notif)
    db.session.commit()
    
    # Enfileirar envio assíncrono
    enviar_whatsapp_task.delay(notif.id)
    
    return jsonify({
        'success': True, 
        'message': 'Notificação enfileirada com sucesso',
        'notificacao_id': notif.id
    })

@bp.route('/api/link/<token>')
def processar_link_acesso(token):
    """
    Processa clique no link de confirmação do WhatsApp
    """
    token_obj = TokenAcesso.query.filter_by(token=token, usado=False).first()
    
    if not token_obj:
        return render_template('whatsapp/erro.html', mensagem="Link inválido ou já utilizado."), 404
    
    if token_obj.expira_em < datetime.utcnow():
        return render_template('whatsapp/erro.html', mensagem="Este link expirou."), 410
    
    chamado = ChamadoExterno.query.get(token_obj.entidade_id)
    if not chamado:
        return render_template('whatsapp/erro.html', mensagem="Chamado não encontrado."), 404

    # Processar ação
    if token_obj.acao == 'aceitar':
        chamado.status = 'aceito'
        chamado.data_inicio = datetime.utcnow()
        
        # Opcional: Criar notificação de confirmação (outbound)
        conf_msg = f"✅ Chamado {chamado.numero_chamado} aceito com sucesso! Obrigado."
        # Aqui poderíamos disparar uma resposta automática simples
        
    token_obj.usado = True
    # token_obj.usado_em = datetime.utcnow() # Adicionar campo se necessário na migration
    # token_obj.ip_origem = request.remote_addr # Adicionar campo se necessário na migration
    
    db.session.commit()
    
    return render_template('whatsapp/confirmacao.html', chamado=chamado)
