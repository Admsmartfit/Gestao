from datetime import datetime
from app.extensions import db
from app.models.models import Usuario
from app.models.estoque_models import OrdemServico

class Terceirizado(db.Model):
    __tablename__ = 'terceirizados'
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(150), nullable=False)
    nome_empresa = db.Column(db.String(150))
    cnpj = db.Column(db.String(18))
    telefone = db.Column(db.String(20), nullable=False) # Formato 5511999999999
    email = db.Column(db.String(150))
    especialidades = db.Column(db.Text) # JSON array
    avaliacao_media = db.Column(db.Numeric(3, 2), default=0.00)
    total_servicos = db.Column(db.Integer, default=0)
    ativo = db.Column(db.Boolean, default=True)
    observacoes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # [Novo] Vinculação à Unidade (ou Null para Global)
    unidade_id = db.Column(db.Integer, db.ForeignKey('unidades.id'), nullable=True)
    unidade = db.relationship('Unidade', backref='terceirizados')

class ChamadoExterno(db.Model):
    __tablename__ = 'chamados_externos'
    id = db.Column(db.Integer, primary_key=True)
    numero_chamado = db.Column(db.String(20), unique=True, nullable=False)
    os_id = db.Column(db.Integer, db.ForeignKey('ordens_servico.id'), nullable=True)
    terceirizado_id = db.Column(db.Integer, db.ForeignKey('terceirizados.id'), nullable=False)
    
    titulo = db.Column(db.String(200), nullable=False)
    descricao = db.Column(db.Text, nullable=False)
    prioridade = db.Column(db.String(20), default='media')
    status = db.Column(db.String(20), default='aguardando') # aguardando, aceito, concluido...
    
    prazo_combinado = db.Column(db.DateTime, nullable=False)
    data_inicio = db.Column(db.DateTime)
    data_conclusao = db.Column(db.DateTime)
    
    valor_orcado = db.Column(db.Numeric(10, 2))
    valor_final = db.Column(db.Numeric(10, 2))
    
    avaliacao = db.Column(db.Integer)
    feedback = db.Column(db.Text)
    
    criado_por = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relacionamentos
    terceirizado = db.relationship('Terceirizado', backref='chamados')
    os_origem = db.relationship('OrdemServico', backref='chamados_externos')
    autor = db.relationship('Usuario', backref='chamados_criados')
    notificacoes = db.relationship('HistoricoNotificacao', backref='chamado', lazy=True)

class HistoricoNotificacao(db.Model):
    __tablename__ = 'historico_notificacoes'
    id = db.Column(db.Integer, primary_key=True)
    chamado_id = db.Column(db.Integer, db.ForeignKey('chamados_externos.id'), nullable=False)
    tipo = db.Column(db.String(20), nullable=False) # criacao, lembrete, cobranca
    destinatario = db.Column(db.String(20), nullable=False)
    mensagem = db.Column(db.Text, nullable=False)
    status_envio = db.Column(db.String(20), default='pendente') # pendente, enviado, falhou
    resposta_api = db.Column(db.Text) # JSON log
    tentativas = db.Column(db.Integer, default=0)
    enviado_em = db.Column(db.DateTime)