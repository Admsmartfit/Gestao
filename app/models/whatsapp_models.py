from datetime import datetime, timedelta
import uuid
import json
from app.extensions import db
from cryptography.fernet import Fernet
from flask import current_app

class RegrasAutomacao(db.Model):
    __tablename__ = 'whatsapp_regras_automacao'
    id = db.Column(db.Integer, primary_key=True)
    palavra_chave = db.Column(db.String(50), nullable=False, index=True)
    tipo_correspondencia = db.Column(db.String(20), default='exata') # exata, contem
    acao = db.Column(db.String(50), nullable=False) # responder, criar_os, transbordar
    resposta_texto = db.Column(db.Text)
    encaminhar_para_perfil = db.Column(db.String(50), nullable=True) # admin, comprador, gerente
    funcao_sistema = db.Column(db.String(50), nullable=True) # Nome da função a executar
    prioridade = db.Column(db.Integer, default=0)
    ativo = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<RegraAutomacao {self.palavra_chave}>'

    @db.validates('palavra_chave')
    def validate_palavra_chave(self, key, value):
        if ' ' in value:
            raise ValueError("A palavra-chave não pode conter espaços.")
        return value

class TokenAcesso(db.Model):
    __tablename__ = 'whatsapp_tokens_acesso'
    id = db.Column(db.Integer, primary_key=True)
    token = db.Column(db.String(36), default=lambda: str(uuid.uuid4()), unique=True, index=True)
    entidade_tipo = db.Column(db.String(50), nullable=False) # 'ordem_servico', 'compra'
    entidade_id = db.Column(db.Integer, nullable=False)
    acao = db.Column(db.String(50), nullable=False) # 'aprovar', 'rejeitar'
    expira_em = db.Column(db.DateTime, nullable=False, index=True)
    usado = db.Column(db.Boolean, default=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def is_valid(self):
        return not self.usado and self.expira_em > datetime.utcnow()

class EstadoConversa(db.Model):
    __tablename__ = 'whatsapp_estados_conversa'
    id = db.Column(db.Integer, primary_key=True)
    telefone = db.Column(db.String(20), nullable=False, index=True)
    chamado_id = db.Column(db.Integer, db.ForeignKey('chamados_externos.id'), nullable=True)
    estado_atual = db.Column(db.String(50), default='inicio')
    contexto = db.Column(db.Text) # JSON String
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def set_contexto(self, data):
        self.contexto = json.dumps(data)

    def get_contexto(self):
        return json.loads(self.contexto) if self.contexto else {}

class ConfiguracaoWhatsApp(db.Model):
    __tablename__ = 'whatsapp_configuracao'
    id = db.Column(db.Integer, primary_key=True)
    api_key_encrypted = db.Column(db.LargeBinary(200))
    circuit_breaker_threshold = db.Column(db.Integer, default=5)
    rate_limit = db.Column(db.Integer, default=60) # msg por minuto
    status_saude = db.Column(db.String(20), default='ok') # ok, degradado, offline
    ultima_verificacao = db.Column(db.DateTime, nullable=True)
    ativo = db.Column(db.Boolean, default=True)

    def decrypt_key(self, fernet_key):
        f = Fernet(fernet_key)
        return f.decrypt(self.api_key_encrypted).decode()

class MetricasWhatsApp(db.Model):
    __tablename__ = 'whatsapp_metricas'
    id = db.Column(db.Integer, primary_key=True)
    data_hora = db.Column(db.DateTime, nullable=False, index=True) # Particionado por hora
    periodo = db.Column(db.String(10), default='hora') # hora, dia
    total_enviadas = db.Column(db.Integer, default=0)
    taxa_entrega = db.Column(db.Numeric(5, 2), default=0.0)
    tempo_medio_resposta = db.Column(db.Integer, default=0) # Segundos
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
