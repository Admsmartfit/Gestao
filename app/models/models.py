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
    ativa = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    registros = db.relationship('RegistroPonto', backref='unidade', lazy=True)
    # ... outros relacionamentos ...

class Usuario(UserMixin, db.Model):
    __tablename__ = 'usuarios'
    
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    
    # --- NOVOS CAMPOS ---
    username = db.Column(db.String(50), unique=True, nullable=False) # Login
    telefone = db.Column(db.String(20), nullable=True)
    # --------------------

    email = db.Column(db.String(120), unique=True, nullable=True) # Agora é apenas contato
    senha_hash = db.Column(db.String(255), nullable=False)
    
    # Tipos: 'tecnico', 'prestador', 'gerente', 'admin'
    tipo = db.Column(db.String(20), nullable=False) 
    
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
    __tablename__ = 'registros_ponto' #
    
    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    unidade_id = db.Column(db.Integer, db.ForeignKey('unidades.id'), nullable=False)
    data_hora_entrada = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    data_hora_saida = db.Column(db.DateTime, nullable=True)
    ip_origem_entrada = db.Column(db.String(45), nullable=False)
    ip_origem_saida = db.Column(db.String(45), nullable=True)
    observacoes = db.Column(db.Text, nullable=True)

    # Índices conforme especificado
    __table_args__ = (
        db.Index('idx_usuario_data', 'usuario_id', 'data_hora_entrada'),
        db.Index('idx_unidade_data', 'unidade_id', 'data_hora_entrada'),
    )