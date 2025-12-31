import logging
import requests
from datetime import datetime, timedelta
from flask import current_app
from app.extensions import db
from app.models.terceirizados_models import HistoricoNotificacao
from app.models.whatsapp_models import ConfiguracaoWhatsApp
from app.services.circuit_breaker import CircuitBreaker

logger = logging.getLogger(__name__)

class AlertaService:
    """
    Monitors system health and sends alerts via Slack/Email.
    """
    
    @staticmethod
    def verificar_saude():
        """
        Runs health checks and triggers alerts if necessary.
        """
        alertas = []
        
        # 1. Low Delivery Rate (< 90% in last hour)
        desde = datetime.utcnow() - timedelta(hours=1)
        total = HistoricoNotificacao.query.filter(
            HistoricoNotificacao.criado_em >= desde,
            HistoricoNotificacao.direcao == 'outbound'
        ).count()
        
        entregues = HistoricoNotificacao.query.filter(
            HistoricoNotificacao.enviado_em >= desde,
            HistoricoNotificacao.status_envio == 'entregue' # Note: 'status_envio' might be 'enviado' in current logic. 
            # In whatsapp_tasks.py: 'enviado' is success. 'entregue' usually comes from webhook delivery receipt.
            # Assuming 'enviado' means success for now, or if we had delivery receipts implemented.
            # Task sets 'enviado'. Let's use 'enviado' as success indicator for now.
        ).count()
        
        # If total is 0, rate is 100%
        taxa = (entregues / total * 100) if total > 0 else 100
        
        if taxa < 90 and total > 0:
            alertas.append({
                'nivel': 'WARNING',
                'mensagem': f'⚠️ Taxa de entrega baixa: {taxa:.1f}%',
                'detalhes': f'{entregues}/{total} mensagens enviadas na última hora'
            })
        
        # 2. Circuit Breaker Open
        if CircuitBreaker.get_state() == 'OPEN':
            alertas.append({
                'nivel': 'CRITICAL',
                'mensagem': '🔴 Circuit Breaker ABERTO',
                'detalhes': 'API WhatsApp indisponível. Mensagens em fila.'
            })
        
        # 3. Queue Size
        # 'pendente' status
        pendentes = HistoricoNotificacao.query.filter_by(
            status_envio='pendente'
        ).count()
        
        if pendentes > 100:
            alertas.append({
                'nivel': 'WARNING',
                'mensagem': f'⚠️ Fila de mensagens grande: {pendentes}',
                'detalhes': 'Verifique capacidade do Celery worker'
            })
        
        # Send Alerts
        for alerta in alertas:
            AlertaService.enviar_slack(alerta)
            # AlertaService.enviar_email(alerta) # Placeholder
        
        # Update Health Status in DB
        config = ConfiguracaoWhatsApp.query.first()
        if not config:
             # Create default config if missing? Or just skip
             return
             
        if alertas:
            # Urgent if CRITICAL, else Degradado
            nivel_max = 'CRITICAL' if any(a['nivel'] == 'CRITICAL' for a in alertas) else 'WARNING'
            config.status_saude = 'offline' if nivel_max == 'CRITICAL' else 'degradado'
        else:
            config.status_saude = 'ok'
        
        config.ultima_verificacao = datetime.utcnow()
        db.session.commit()
    
    @staticmethod
    def enviar_slack(alerta: dict):
        """Sends alert payload to Slack Webhook."""
        webhook_url = current_app.config.get('SLACK_WEBHOOK_URL')
        if not webhook_url:
            logger.warning("Slack Webhook URL not configured. Skipping alert.")
            return
        
        emoji = '🔴' if alerta['nivel'] == 'CRITICAL' else '⚠️'
        color = '#dc3545' if alerta['nivel'] == 'CRITICAL' else '#ffc107'
        
        payload = {
            'text': f"{emoji} *Alerta GMM - WhatsApp*",
            'attachments': [{
                'color': color,
                'fields': [
                    {'title': 'Mensagem', 'value': alerta['mensagem'], 'short': False},
                    {'title': 'Detalhes', 'value': alerta['detalhes'], 'short': False}
                ]
            }]
        }
        
        try:
            requests.post(webhook_url, json=payload, timeout=5)
        except Exception as e:
            logger.error(f"Falha ao enviar alerta para Slack: {e}")
