from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from app.extensions import db

class Unidade(db.Model):
    __tablename__ = 'unidades'
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), unique=True, nullable=False)
    endereco = db.Column(db.String(255), nullable=True)
    faixa_ip_permitida = db.Column(db.String(255), nullable=False)
    ssid_wifi = db.Column(db.String(50), nullable=True) # [Novo PRD 3.1.1]
    ativa = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    registros = db.relationship('RegistroPonto', backref='unidade', lazy=True)

class Usuario(UserMixin, db.Model):
    __tablename__ = 'usuarios'
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    username = db.Column(db.String(50), unique=True, nullable=False)
    telefone = db.Column(db.String(20), nullable=True)
    email = db.Column(db.String(120), unique=True, nullable=True)
    senha_hash = db.Column(db.String(255), nullable=False)
    tipo = db.Column(db.String(20), nullable=False)
    foto_perfil = db.Column(db.String(255), nullable=True) # [Novo PRD 3.1.1]
    unidade_padrao_id = db.Column(db.Integer, db.ForeignKey('unidades.id'), nullable=True)
    ativo = db.Column(db.Boolean, default=True)
    ultimo_acesso = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    registros = db.relationship('RegistroPonto', backref='usuario', lazy=True)

    def set_senha(self, senha):
        self.senha_hash = generate_password_hash(senha)

    def check_senha(self, senha):
        return check_password_hash(self.senha_hash, senha)

class RegistroPonto(db.Model):
    __tablename__ = 'registros_ponto'
    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    unidade_id = db.Column(db.Integer, db.ForeignKey('unidades.id'), nullable=False)
    data_hora_entrada = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    data_hora_saida = db.Column(db.DateTime, nullable=True)
    ip_origem_entrada = db.Column(db.String(45), nullable=False)
    ip_origem_saida = db.Column(db.String(45), nullable=True)
    
    # [Novo PRD 3.1.1] Geolocalização
    latitude = db.Column(db.Numeric(10, 8), nullable=True)
    longitude = db.Column(db.Numeric(11, 8), nullable=True)
    
    observacoes = db.Column(db.Text, nullable=True)

    __table_args__ = (
        db.Index('idx_usuario_data', 'usuario_id', 'data_hora_entrada'),
        db.Index('idx_unidade_data', 'unidade_id', 'data_hora_entrada'),
    )