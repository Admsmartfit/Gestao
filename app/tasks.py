from datetime import datetime, timedelta
from celery import shared_task
from celery.schedules import crontab
from flask import current_app
from app.extensions import db
from app.models.terceirizados_models import ChamadoExterno, HistoricoNotificacao
from app.services.whatsapp_service import WhatsAppService

@shared_task(bind=True, max_retries=3, default_retry_delay=60) # Retry exponencial simples (1m, 2m...)
def enviar_whatsapp_task(self, notificacao_id, telefone, mensagem):
    """
    Task assíncrona para envio de WhatsApp.
    Atualiza o status no banco de dados.
    """
    notificacao = HistoricoNotificacao.query.get(notificacao_id)
    if not notificacao:
        return

    sucesso, resposta = WhatsAppService.enviar_mensagem(telefone, mensagem)
    
    notificacao.tentativas += 1
    notificacao.resposta_api = str(resposta)
    
    if sucesso:
        notificacao.status_envio = 'enviado'
        notificacao.enviado_em = datetime.utcnow()
    else:
        notificacao.status_envio = 'falhou'
        # Retry em caso de falha (exceto erro de validação)
        if "error" in resposta and "inválido" in str(resposta):
            pass
        else:
            # Backoff exponencial manual ou via configuração do celery
            try:
                self.retry(countdown=60 * (2 ** self.request.retries))
            except Exception as e:
                current_app.logger.error(f"Max retries exceeded for {notificacao_id}")

    db.session.commit()

@shared_task
def lembretes_automaticos_task():
    """
    Executada diariamente às 9h (Configurar no Celery Beat)
    Busca chamados vencendo em até 2 dias.
    """
    hoje = datetime.utcnow()
    limite = hoje + timedelta(days=2)
    
    # Chamados 'aguardando' ou 'em_andamento' próximos do prazo
    chamados = ChamadoExterno.query.filter(
        ChamadoExterno.status.notin_(['concluido', 'cancelado']),
        ChamadoExterno.prazo_combinado <= limite,
        ChamadoExterno.prazo_combinado >= hoje
    ).all()
    
    for ch in chamados:
        msg = f"🔧 Lembrete GMM\n\nChamado: {ch.numero_chamado} vence em breve.\nPrazo: {ch.prazo_combinado.strftime('%d/%m %H:%M')}"
        
        # Cria registro
        notif = HistoricoNotificacao(
            chamado_id=ch.id,
            tipo='lembrete',
            destinatario=ch.terceirizado.telefone,
            mensagem=msg
        )
        db.session.add(notif)
        db.session.commit()
        
        # Dispara envio
        enviar_whatsapp_task.delay(notif.id, notif.destinatario, notif.mensagem)