from datetime import datetime
from decimal import Decimal
from sqlalchemy import event
from app.extensions import db
from app.models.models import Usuario, Unidade

class CategoriaEstoque(db.Model):
    __tablename__ = 'categorias_estoque'
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(50), unique=True, nullable=False)
    descricao = db.Column(db.Text, nullable=True)

class Estoque(db.Model):
    __tablename__ = 'estoque'
    id = db.Column(db.Integer, primary_key=True)
    codigo = db.Column(db.String(20), unique=True, nullable=False)
    nome = db.Column(db.String(150), nullable=False)
    categoria_id = db.Column(db.Integer, db.ForeignKey('categorias_estoque.id'))
    unidade_medida = db.Column(db.String(5), nullable=False)
    quantidade_atual = db.Column(db.Numeric(10, 3), nullable=False, default=0)
    quantidade_minima = db.Column(db.Numeric(10, 3), nullable=False, default=5)
    valor_unitario = db.Column(db.Numeric(10, 2), nullable=True)
    localizacao = db.Column(db.String(100), nullable=True)
    unidade_id = db.Column(db.Integer, db.ForeignKey('unidades.id'), nullable=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    categoria = db.relationship('CategoriaEstoque', backref='itens')
    unidade = db.relationship('Unidade', backref='estoque_itens')

class Equipamento(db.Model):
    __tablename__ = 'equipamentos'
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(150), nullable=False)
    categoria = db.Column(db.String(50), nullable=False)
    unidade_id = db.Column(db.Integer, db.ForeignKey('unidades.id'), nullable=False)
    ativo = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    unidade = db.relationship('Unidade', backref='lista_equipamentos')

class OrdemServico(db.Model):
    __tablename__ = 'ordens_servico'
    id = db.Column(db.Integer, primary_key=True)
    numero_os = db.Column(db.String(20), unique=True, nullable=False)
    tecnico_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    unidade_id = db.Column(db.Integer, db.ForeignKey('unidades.id'), nullable=False)
    equipamento_id = db.Column(db.Integer, db.ForeignKey('equipamentos.id'), nullable=True)
    
    tipo_manutencao = db.Column(db.String(20), nullable=False)
    prioridade = db.Column(db.String(20), default='media')
    descricao_problema = db.Column(db.Text, nullable=False)
    descricao_solucao = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(20), default='aberta')
    prazo_conclusao = db.Column(db.DateTime, nullable=False)
    
    # Mantemos JSON como legado ou backup, mas usaremos a tabela AnexosOS
    fotos_antes = db.Column(db.JSON, nullable=True)
    fotos_depois = db.Column(db.JSON, nullable=True)
    
    data_abertura = db.Column(db.DateTime, default=datetime.utcnow)
    data_conclusao = db.Column(db.DateTime, nullable=True)
    
    tecnico = db.relationship('Usuario', backref='ordens_servico')
    unidade = db.relationship('Unidade', backref='ordens_servico')
    equipamento_rel = db.relationship('Equipamento', backref='ordens')
    movimentacoes = db.relationship('MovimentacaoEstoque', backref='os', lazy=True)
    
    # [cite_start]NOVO RELACIONAMENTO (PRD 3.2.1) [cite: 1093-1103]
    anexos_list = db.relationship('AnexosOS', backref='os', lazy=True, cascade="all, delete-orphan")

    @property
    def custo_total(self):
        total = Decimal('0.00')
        for mov in self.movimentacoes:
            if mov.tipo_movimentacao == 'consumo' and mov.estoque.valor_unitario:
                total += (mov.quantidade * mov.estoque.valor_unitario)
        return total

# [cite_start]NOVA TABELA (PRD 3.2.1) [cite: 1094]
class AnexosOS(db.Model):
    __tablename__ = 'anexos_os'
    id = db.Column(db.Integer, primary_key=True)
    os_id = db.Column(db.Integer, db.ForeignKey('ordens_servico.id'), nullable=False)
    tipo = db.Column(db.String(20), default='foto_antes') # foto_antes, foto_depois
    nome_arquivo = db.Column(db.String(255), nullable=False)
    caminho_arquivo = db.Column(db.String(500), nullable=False)
    tamanho_kb = db.Column(db.Integer)
    upload_em = db.Column(db.DateTime, default=datetime.utcnow)

class MovimentacaoEstoque(db.Model):
    __tablename__ = 'movimentacoes_estoque'
    id = db.Column(db.Integer, primary_key=True)
    os_id = db.Column(db.Integer, db.ForeignKey('ordens_servico.id'), nullable=True)
    estoque_id = db.Column(db.Integer, db.ForeignKey('estoque.id'), nullable=False)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    tipo_movimentacao = db.Column(db.String(20), nullable=False)
    quantidade = db.Column(db.Numeric(10, 3), nullable=False)
    observacao = db.Column(db.String(255), nullable=True)
    data_movimentacao = db.Column(db.DateTime, default=datetime.utcnow)

    estoque = db.relationship('Estoque', backref='historico')
    usuario = db.relationship('Usuario')

class Fornecedor(db.Model):
    __tablename__ = 'fornecedores'
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(150), nullable=False)
    endereco = db.Column(db.String(255), nullable=True)
    email = db.Column(db.String(120), nullable=False)
    telefone = db.Column(db.String(20), nullable=True)
    prazo_medio_entrega_dias = db.Column(db.Float, default=7.0)
    total_pedidos_entregues = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class CatalogoFornecedor(db.Model):
    __tablename__ = 'catalogo_fornecedores'
    id = db.Column(db.Integer, primary_key=True)
    fornecedor_id = db.Column(db.Integer, db.ForeignKey('fornecedores.id'), nullable=False)
    estoque_id = db.Column(db.Integer, db.ForeignKey('estoque.id'), nullable=False)
    preco_atual = db.Column(db.Numeric(10, 2), nullable=True)
    prazo_estimado_dias = db.Column(db.Integer, default=7)
    
    fornecedor = db.relationship('Fornecedor', backref='catalogo')
    peca = db.relationship('Estoque', backref='fornecedores')

class PedidoCompra(db.Model):
    __tablename__ = 'pedidos_compra'
    id = db.Column(db.Integer, primary_key=True)
    fornecedor_id = db.Column(db.Integer, db.ForeignKey('fornecedores.id'), nullable=False)
    estoque_id = db.Column(db.Integer, db.ForeignKey('estoque.id'), nullable=False)
    quantidade = db.Column(db.Numeric(10, 3), nullable=False)
    data_solicitacao = db.Column(db.DateTime, default=datetime.utcnow)
    data_chegada = db.Column(db.DateTime, nullable=True)
    status = db.Column(db.String(20), default='pendente')
    fornecedor = db.relationship('Fornecedor', backref='pedidos')
    peca = db.relationship('Estoque')

@event.listens_for(MovimentacaoEstoque, 'after_insert')
def atualizar_saldo_estoque(mapper, connection, target):
    tabela_estoque = Estoque.__table__
    fator = 1
    if target.tipo_movimentacao in ['consumo', 'saida']:
        fator = -1
    qtd_ajuste = target.quantidade * fator
    connection.execute(
        tabela_estoque.update()
        .where(tabela_estoque.c.id == target.estoque_id)
        .values(quantidade_atual=tabela_estoque.c.quantidade_atual + qtd_ajuste)
    )