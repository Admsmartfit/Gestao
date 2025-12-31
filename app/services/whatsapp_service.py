import requests
import json
import re
import time
import logging
from flask import current_app
from app.services.circuit_breaker import CircuitBreaker
from app.services.rate_limiter import RateLimiter

logger = logging.getLogger(__name__)

class WhatsAppService:

    @staticmethod
    def validar_telefone(telefone: str) -> bool:
        """Valida formato: 5511999999999 (13 dígitos)"""
        return bool(re.match(r'^55\d{11}$', str(telefone)))

    @classmethod
    def enviar_mensagem(cls, telefone: str, texto: str, prioridade: int = 0, notificacao_id: int = None):
        """
        Envia mensagem via MegaAPI com resiliência:
        1. Validação de Telefone
        2. Circuit Breaker check
        3. Rate Limiting check (exceto para prioridade 2/Urgente)
        4. API Request com Error Handling
        """
        # 1. Validação
        if not cls.validar_telefone(telefone):
            return False, {"error": "Telefone inválido"}

        # 2. Circuit Breaker
        if not CircuitBreaker.should_attempt():
            return False, {"error": "Circuit breaker OPEN", "code": "CIRCUIT_OPEN"}

        # 3. Rate Limit (ignorar se prioridade urgente >= 2)
        if prioridade < 2:
            pode_enviar, restantes = RateLimiter.check_limit()
            if not pode_enviar:
                logger.info(f"Rate limit reached. Enqueueing notification {notificacao_id} for later.")
                if notificacao_id:
                    # Circular import avoidance: import inside method
                    from app.tasks.whatsapp_tasks import enviar_whatsapp_task
                    enviar_whatsapp_task.apply_async(args=[notificacao_id], countdown=60)
                return True, {"status": "enfileirado"}

        # 4. Get Credentials
        from app.models.whatsapp_models import ConfiguracaoWhatsApp
        config = ConfiguracaoWhatsApp.query.filter_by(ativo=True).first()
        
        if config and config.api_key_encrypted:
            try:
                fernet_key = current_app.config.get('FERNET_KEY')
                api_key = config.decrypt_key(fernet_key)
                url = current_app.config.get('MEGA_API_URL')
            except Exception as e:
                logger.error(f"Error decrypting API Key: {str(e)}")
                return False, {"error": "Decryption failed"}
        else:
            url = current_app.config.get('MEGA_API_URL')
            api_key = current_app.config.get('MEGA_API_KEY')

        if not url or not api_key:
            return False, {"error": "MegaAPI configuration missing"}

        # 5. API Request
        try:
            response = requests.post(
                url,
                json={"phone": telefone, "message": texto},
                headers={"Authorization": f"Bearer {api_key}"},
                timeout=5
            )
            
            if response.status_code in [200, 201]:
                CircuitBreaker.record_success()
                RateLimiter.increment()
                return True, response.json()
            else:
                CircuitBreaker.record_failure()
                logger.warning(f"MegaAPI failure: {response.status_code} - {response.text}")
                return False, {"status": response.status_code, "text": response.text}
                
        except requests.exceptions.RequestException as e:
            CircuitBreaker.record_failure()
            logger.error(f"MegaAPI request exception: {str(e)}")
            return False, {"error": str(e)}