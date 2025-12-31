from datetime import datetime, timedelta
from celery import shared_task
from app.extensions import db
from app.models.terceirizados_models import ChamadoExterno, HistoricoNotificacao
from app.tasks.whatsapp_tasks import enviar_whatsapp_task

@shared_task
def lembretes_automaticos_task():
    """
    Periodic task to check for upcoming deadlines and send WhatsApp reminders.
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
        
        # Cria registro de notificação
        notif = HistoricoNotificacao(
            chamado_id=ch.id,
            tipo='lembrete',
            destinatario=ch.terceirizado.telefone,
            mensagem=msg,
            prioridade=1 # Alta prioridade para lembretes
        )
        db.session.add(notif)
        db.session.commit()
        
        # Dispara envio assíncrono (nova versão que usa apenas o ID)
        enviar_whatsapp_task.delay(notif.id)
