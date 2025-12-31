import hmac
import hashlib
import logging
from datetime import datetime
from flask import Blueprint, request, jsonify, current_app
from app.extensions import db
from app.models.terceirizados_models import HistoricoNotificacao
from app.tasks.whatsapp_tasks import processar_mensagem_inbound

bp = Blueprint('webhook', __name__)
logger = logging.getLogger(__name__)

def validar_webhook(req):
    """
    Valida origem do webhook:
    - IP na whitelist (Placeholder IPs)
    - Assinatura HMAC
    - Timestamp recente (max 5min)
    """
    # 1. IP Whitelist (Simulated/Placeholder ranges as per prompt)
    # In prod, check actual MegaAPI IPs
    # MEGAAPI_IPS = ['191.252.xxx.xxx', ...]
    # For now, we skip IP check or allow localhost/all for dev
    # if request.remote_addr not in MEGAAPI_IPS: ...
    
    # 2. Assinatura HMAC
    signature = req.headers.get('X-Webhook-Signature', '')
    payload = req.get_data()
    secret = current_app.config.get('WEBHOOK_SECRET', 'default-secret-dev')
    
    expected = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    
    # Using compare_digest to prevent timing attacks
    # Note: Prompt example format "sha256={expected}" depends on provider. 
    # MegaAPI usually sends just the hash or specific format. Adapting to prompt req.
    # If signature header is just the hash:
    if not hmac.compare_digest(signature, f"sha256={expected}") and not hmac.compare_digest(signature, expected):
         # Try both formats to be safe
         logger.warning(f"Invalid HMAC signature. Expected: {expected}, Got: {signature}")
         return False
    
    # 3. Timestamp (Replay Attack Prevention)
    try:
        data = req.json
        if not data: return False
        
        timestamp = data.get('timestamp')
        if not timestamp:
            # Some hooks might not send timestamp in body, check headers if needed
            return True # Skip if not present
            
        msg_time = datetime.fromtimestamp(int(timestamp))
        now = datetime.utcnow()
        
        if abs((now - msg_time).total_seconds()) > 300:  # 5 minutos
            logger.warning(f"Old message received: {msg_time}")
            return False
    except Exception as e:
        logger.error(f"Error validating timestamp: {e}")
        return False
    
    return True

@bp.route('/webhook/whatsapp', methods=['POST'])
def webhook_whatsapp():
    """
    Receives POSTs from MegaAPI
    """
    # 1. Validações de Segurança
    if not validar_webhook(request):
        return jsonify({'error': 'Unauthorized'}), 403
    
    # 2. Parse do payload
    try:
        data = request.json
        # Structure depends on MegaAPI actual payload. 
        # Prompt says: data['data']['from'], data['data']['text']
        payload_data = data.get('data', {})
        remetente = payload_data.get('from')
        texto = payload_data.get('text')
        timestamp = data.get('timestamp', datetime.utcnow().timestamp())
        
        if not remetente or not texto:
            return jsonify({'status': 'ignored', 'reason': 'no_text_or_sender'}), 200

    except KeyError:
        return jsonify({'error': 'Invalid payload'}), 400
    
    # 3. Registrar no banco (Auditoria Inbound)
    try:
        notif = HistoricoNotificacao(
            tipo='resposta_auto',
            direcao='inbound',
            remetente=remetente,
            destinatario='sistema',
            status_envio='recebido',
            mensagem=texto,
            mensagem_hash=hashlib.sha256(texto.encode()).hexdigest(),
            chamado_id=None # Now nullable
        )
        db.session.add(notif)
        db.session.commit()
        
    except Exception as e:
        logger.error(f"Error logging inbound: {e}")

    # 4. Processar assincronamente
    # We pass the heavy lifting to Celery
    processar_mensagem_inbound.delay(remetente, texto, timestamp)
    
    return jsonify({'success': True, 'processed_at': datetime.utcnow().isoformat()})
