import requests
import json
import re
import time
from datetime import datetime, timedelta
from flask import current_app
# Assumindo uso de redis-py para persistência do estado do Circuit Breaker
import redis

class WhatsAppService:
    _redis_client = None

    @classmethod
    def _get_redis(cls):
        if cls._redis_client is None:
            cls._redis_client = redis.from_url(current_app.config['CELERY_BROKER_URL'])
        return cls._redis_client

    @staticmethod
    def validar_telefone(telefone):
        # Regex: ^\d{13}$ (ex: 5511999999999)
        return bool(re.match(r'^\d{13}$', telefone))

    @classmethod
    def check_circuit_breaker(cls):
        r = cls._get_redis()
        # Verifica se o circuito está aberto (pausado)
        open_until = r.get('whatsapp_circuit_open_until')
        if open_until and float(open_until) > time.time():
            return False, f"Circuito aberto. Pausado até {datetime.fromtimestamp(float(open_until))}"
        return True, "OK"

    @classmethod
    def record_failure(cls):
        r = cls._get_redis()
        # Incrementa falhas
        failures = r.incr('whatsapp_api_failures')
        if failures == 1:
            r.expire('whatsapp_api_failures', 300) # Reset após 5 min se não atingir limite
        
        # Se 5 falhas seguidas, abre o circuito por 10 minutos
        if failures >= 5:
            r.set('whatsapp_circuit_open_until', time.time() + 600) # 10 min
            r.delete('whatsapp_api_failures') # Reseta contagem
            current_app.logger.critical("Circuit Breaker do WhatsApp ATIVADO por 10 minutos.")

    @classmethod
    def record_success(cls):
        r = cls._get_redis()
        r.delete('whatsapp_api_failures')

    @classmethod
    def enviar_mensagem(cls, telefone, texto):
        """
        Envia mensagem via MegaAPI com validação e Circuit Breaker.
        Retorna (sucesso: bool, resposta: dict/str)
        """
        if not cls.validar_telefone(telefone):
            return False, {"error": "Número de telefone inválido. Formato: 5511999999999"}

        # 1. Verificar Circuit Breaker
        status, msg = cls.check_circuit_breaker()
        if not status:
            return False, {"error": msg, "code": "CIRCUIT_OPEN"}

        url = current_app.config['MEGA_API_URL']
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {current_app.config['MEGA_API_KEY']}"
        }
        payload = {
            "phone": telefone,
            "message": texto
        }

        try:
            # 2. POST com Timeout de 5s
            response = requests.post(url, json=payload, headers=headers, timeout=5)
            
            if response.status_code == 200:
                cls.record_success()
                return True, response.json()
            else:
                cls.record_failure()
                return False, {"status": response.status_code, "text": response.text}

        except requests.exceptions.RequestException as e:
            cls.record_failure()
            return False, {"error": str(e)}