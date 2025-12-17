from flask import Blueprint, render_template, request, flash, redirect, url_for, abort, jsonify
from flask_login import login_required, current_user
from werkzeug.security import generate_password_hash
from app.models.models import Unidade, Usuario
from app.models.estoque_models import Equipamento, Fornecedor, CatalogoFornecedor, Estoque, OrdemServico, PedidoCompra
from datetime import datetime
from app.models.terceirizados_models import Terceirizado
from app.extensions import db
from sqlalchemy import func

bp = Blueprint('admin', __name__, url_prefix='/admin')

@bp.before_request
def restrict_to_admin():
    """
    Middleware de segurança.
    Bloqueia acesso a não-admins, EXCETO para a API de busca de fornecedores
    que é usada pelos técnicos na tela de OS.
    """
    # Exceções (Rotas permitidas para não-admins)
    # 1. API usada por técnicos na OS
    if request.endpoint == 'admin.buscar_fornecedores_peca':
        return
        
    # 2. Compradores podem acessar painel de compras e APIs
    if current_user.is_authenticated and current_user.tipo == 'comprador':
        if request.endpoint in ['admin.compras_painel', 'admin.aprovar_pedido', 'admin.rejeitar_pedido', 'admin.receber_pedido']:
            return

    if not current_user.is_authenticated or current_user.tipo != 'admin':
        abort(403)

@bp.route('/configuracoes', methods=['GET'])
@login_required
def dashboard():
    # Captura a aba ativa para manter a navegação fluida
    active_tab = request.args.get('tab', 'tecnicos')
    
    # Carregamento de dados para todas as abas
    unidades = Unidade.query.all()
    # Carrega TODOS os usuários ordenados por nome
    funcionarios = Usuario.query.order_by(Usuario.nome).all()
    equipamentos = Equipamento.query.all()
    fornecedores = Fornecedor.query.all()
    estoque_itens = Estoque.query.all()
    # [Novo] Carrega prestadores de serviço
    terceirizados = Terceirizado.query.order_by(Terceirizado.nome).all()

    os_concluidas = OrdemServico.query.filter(
        OrdemServico.status == 'concluida',
        OrdemServico.tipo_manutencao == 'corretiva',
        OrdemServico.data_conclusao != None
    ).all()
    
    total_horas = 0
    qtd_os = len(os_concluidas)
    
    for os_obj in os_concluidas:
        diff = os_obj.data_conclusao - os_obj.data_abertura
        total_horas += diff.total_seconds() / 3600
        
    mttr = round(total_horas / qtd_os, 1) if qtd_os > 0 else 0
    
    return render_template('admin_config.html', 
                         unidades=unidades, 
                         funcionarios=funcionarios, 
                         equipamentos=equipamentos,
                         fornecedores=fornecedores,
                         estoque_itens=estoque_itens,
                         terceirizados=terceirizados,
                         kpi_mttr=mttr,
                         kpi_os_concluidas=qtd_os,
                         active_tab=active_tab)

# ==============================================================================
# GESTÃO DE USUÁRIOS (FUNCIONÁRIOS)
# ==============================================================================

@bp.route('/usuario/novo', methods=['POST'])
@login_required
def novo_usuario():
    username = request.form.get('username')
    email = request.form.get('email')
    
    # Validação de duplicidade (Username ou Email)
    if Usuario.query.filter((Usuario.username == username) | (Usuario.email == email)).first():
        flash('Erro: Nome de usuário ou Email já estão em uso.', 'danger')
        return redirect(url_for('admin.dashboard', tab='tecnicos'))
        
    novo_user = Usuario(
        nome=request.form.get('nome'), 
        username=username,
        email=email,
        telefone=request.form.get('telefone'),
        # Gera o hash seguro da senha
        senha_hash=generate_password_hash(request.form.get('senha')),
        tipo=request.form.get('tipo'), # tecnico, prestador, gerente, admin
        unidade_padrao_id=request.form.get('unidade_id') or None
    )
    
    db.session.add(novo_user)
    db.session.commit()
    flash('Funcionário cadastrado com sucesso!', 'success')
    return redirect(url_for('admin.dashboard', tab='tecnicos'))

@bp.route('/usuario/editar', methods=['POST'])
@login_required
def editar_tecnico(): # Mantive o nome da função para compatibilidade, mas serve para todos
    user_id = request.form.get('user_id')
    user = Usuario.query.get(user_id)
    
    if user:
        user.nome = request.form.get('nome')
        user.email = request.form.get('email')
        user.unidade_padrao_id = request.form.get('unidade_id') or None
        
        # Só altera a senha se o campo foi preenchido
        nova_senha = request.form.get('senha')
        if nova_senha:
            user.set_senha(nova_senha)
            
        db.session.commit()
        flash('Dados do usuário atualizados.', 'success')
    return redirect(url_for('admin.dashboard', tab='tecnicos'))

@bp.route('/usuario/excluir/<int:id>')
@login_required
def excluir_tecnico(id):
    user = Usuario.query.get(id)
    # Impede que o admin exclua a si mesmo acidentalmente
    if user.id == current_user.id:
        flash('Você não pode excluir seu próprio usuário.', 'danger')
        return redirect(url_for('admin.dashboard', tab='tecnicos'))

    if user:
        db.session.delete(user)
        db.session.commit()
        flash('Usuário removido com sucesso.', 'success')
    return redirect(url_for('admin.dashboard', tab='tecnicos'))

# ==============================================================================
# GESTÃO DE EQUIPAMENTOS
# ==============================================================================

@bp.route('/equipamento/novo', methods=['POST'])
@login_required
def novo_equipamento():
    novo_eq = Equipamento(
        nome=request.form.get('nome'),
        categoria=request.form.get('categoria'),
        unidade_id=request.form.get('unidade_id')
    )
    db.session.add(novo_eq)
    db.session.commit()
    flash('Equipamento cadastrado com sucesso!', 'success')
    return redirect(url_for('admin.dashboard', tab='equipamentos'))

# ==============================================================================
# GESTÃO DE UNIDADES
# ==============================================================================

@bp.route('/unidade/nova', methods=['POST'])
@login_required
def nova_unidade():
    nova_un = Unidade(
        nome=request.form.get('nome'), 
        endereco=request.form.get('endereco'), 
        faixa_ip_permitida=request.form.get('faixa_ip')
    )
    db.session.add(nova_un)
    db.session.commit()
    flash('Unidade criada com sucesso!', 'success')
    return redirect(url_for('admin.dashboard', tab='unidades'))

# ==============================================================================
# GESTÃO DE FORNECEDORES E ESTOQUE
# ==============================================================================

@bp.route('/fornecedor/novo', methods=['POST'])
@login_required
def novo_fornecedor():
    # Tratamento seguro para float
    try:
        prazo = float(request.form.get('prazo_inicial', 7))
    except ValueError:
        prazo = 7.0

    novo_forn = Fornecedor(
        nome=request.form.get('nome'),
        email=request.form.get('email'),
        telefone=request.form.get('telefone'),
        endereco=request.form.get('endereco'),
        prazo_medio_entrega_dias=prazo
    )
    db.session.add(novo_forn)
    db.session.commit()
    flash('Fornecedor cadastrado com sucesso!', 'success')
    return redirect(url_for('admin.dashboard', tab='fornecedores'))

@bp.route('/estoque/novo', methods=['POST'])
@login_required
def novo_item_estoque():
    """Cadastra uma nova peça no sistema."""
    codigo = request.form.get('codigo')
    
    if Estoque.query.filter_by(codigo=codigo).first():
        flash(f'Erro: O código {codigo} já existe.', 'danger')
        return redirect(url_for('admin.dashboard', tab='fornecedores'))

    nova_peca = Estoque(
        codigo=codigo,
        nome=request.form.get('nome'),
        unidade_medida=request.form.get('unidade_medida'),
        quantidade_atual=0, 
        quantidade_minima=5
    )
    
    db.session.add(nova_peca)
    db.session.commit()
    flash('Nova peça cadastrada no sistema!', 'success')
    return redirect(url_for('admin.dashboard', tab='fornecedores'))

@bp.route('/fornecedor/vincular-peca', methods=['POST'])
@login_required
def vincular_peca_fornecedor():
    """Vincula Peça ao Fornecedor com Preço e Prazo."""
    fornecedor_id = request.form.get('fornecedor_id')
    estoque_id = request.form.get('estoque_id')
    
    # TRATAMENTO DE ERROS: Evita crash se campos vierem vazios
    try:
        preco_str = request.form.get('preco', '')
        # Substitui vírgula por ponto e converte. Se vazio, vira 0.0
        preco = float(preco_str.replace(',', '.')) if preco_str else 0.0
    except ValueError:
        preco = 0.0

    try:
        prazo_str = request.form.get('prazo', '')
        prazo = int(prazo_str) if prazo_str else 0
    except ValueError:
        prazo = 0

    # Verifica se já existe o vínculo para atualizar
    existe = CatalogoFornecedor.query.filter_by(fornecedor_id=fornecedor_id, estoque_id=estoque_id).first()
    
    if existe:
        existe.preco_atual = preco
        existe.prazo_estimado_dias = prazo
        msg = 'Vínculo atualizado com sucesso!'
    else:
        vinculo = CatalogoFornecedor(
            fornecedor_id=fornecedor_id,
            estoque_id=estoque_id,
            preco_atual=preco,
            prazo_estimado_dias=prazo
        )
        db.session.add(vinculo)
        msg = 'Peça vinculada ao fornecedor!'
        
    db.session.commit()
    flash(msg, 'success')
    return redirect(url_for('admin.dashboard', tab='fornecedores'))

# ==============================================================================
# GESTÃO DE PRESTADORES (TERCEIRIZADOS)
# ==============================================================================

@bp.route('/terceirizado/novo', methods=['POST'])
@login_required
def novo_terceirizado():
    unidade_id = request.form.get('unidade_id')
    # Se vazio, é None (Global)
    if not unidade_id:
        unidade_id = None
        
    novo_terc = Terceirizado(
        nome=request.form.get('nome'),
        nome_empresa=request.form.get('nome_empresa'),
        cnpj=request.form.get('cnpj'),
        telefone=request.form.get('telefone'),
        email=request.form.get('email'),
        especialidades=request.form.get('especialidades'), # Salva como String simples
        unidade_id=unidade_id,
        ativo=True
    )
    
    db.session.add(novo_terc)
    db.session.commit()
    flash('Prestador de Serviço cadastrado com sucesso!', 'success')
    return redirect(url_for('admin.dashboard', tab='terceirizados'))

@bp.route('/terceirizado/excluir/<int:id>')
@login_required
def excluir_terceirizado(id):
    prestador = Terceirizado.query.get_or_404(id)
    # Exclusão lógica ou física? Como usuário pediu "Remover", vou deletar.
    # Mas se tiver vínculos, pode dar erro de FK. Melhor desativar ou try/catch
    try:
        db.session.delete(prestador)
        db.session.commit()
        flash('Prestador removido.', 'success')
    except:
        db.session.rollback()
        prestador.ativo = False
        db.session.commit()
        flash('Prestador desativado (possui histórico).', 'warning')
        
    return redirect(url_for('admin.dashboard', tab='terceirizados'))

# ==============================================================================
# APIs (JSON)
# ==============================================================================

@bp.route('/api/fornecedores/buscar-por-peca/<int:peca_id>')
@login_required
def buscar_fornecedores_peca(peca_id):
    """
    Retorna lista de fornecedores para uma peça específica,
    ordenada pelo menor prazo médio de entrega.
    """
    itens = CatalogoFornecedor.query.filter_by(estoque_id=peca_id).all()
    
    resultado = []
    for item in itens:
        resultado.append({
            'fornecedor_id': item.fornecedor.id,
            'nome': item.fornecedor.nome,
            'prazo_medio_geral': round(item.fornecedor.prazo_medio_entrega_dias, 1),
            'preco': float(item.preco_atual) if item.preco_atual else 0.0,
            'historico_entregas': item.fornecedor.total_pedidos_entregues
        })
    
    resultado.sort(key=lambda x: x['prazo_medio_geral'])
    
    return jsonify(resultado)

@bp.route('/api/fornecedores/<int:id>/pecas')
@login_required
def buscar_pecas_fornecedor(id):
    """
    Retorna lista de peças que um fornecedor específico fornece.
    """
    itens = CatalogoFornecedor.query.filter_by(fornecedor_id=id).all()
    resultado = []
    
    for item in itens:
        resultado.append({
            'codigo': item.peca.codigo,
            'nome': item.peca.nome,
            'preco': float(item.preco_atual) if item.preco_atual else 0.0,
            'prazo': item.prazo_estimado_dias
        })
    
    return jsonify(resultado)
@bp.route('/compras', methods=['GET'])
@login_required
def compras_painel():
    pendentes = PedidoCompra.query.filter_by(status='pendente').order_by(PedidoCompra.data_solicitacao.desc()).all()
    aprovados = PedidoCompra.query.filter(PedidoCompra.status.in_(['aprovado', 'encomendado', 'solicitado'])).all()
    # Histórico (concluidos ou cancelados)
    historico = PedidoCompra.query.filter(PedidoCompra.status.in_(['entregue', 'cancelado'])).order_by(PedidoCompra.data_solicitacao.desc()).limit(20).all()
    
    fornecedores = Fornecedor.query.all()
    
    return render_template('compras.html', pendentes=pendentes, aprovados=aprovados, historico=historico, fornecedores=fornecedores)

@bp.route('/api/compras/<int:id>/aprovar', methods=['POST'])
@login_required
def aprovar_pedido(id):
    pedido = PedidoCompra.query.get_or_404(id)
    data = request.get_json()
    
    pedido.status = 'aprovado'
    pedido.fornecedor_id = data.get('fornecedor_id')
    
    # Data de Chegada Estimada
    data_chegada_str = data.get('data_chegada')
    if data_chegada_str:
        from datetime import datetime
        pedido.data_chegada = datetime.strptime(data_chegada_str, '%Y-%m-%d')
        
    db.session.commit()
    return jsonify({'success': True})

@bp.route('/api/compras/<int:id>/rejeitar', methods=['POST'])
@login_required
def rejeitar_pedido(id):
    pedido = PedidoCompra.query.get_or_404(id)
    pedido.status = 'cancelado'
    db.session.commit()
    return jsonify({'success': True})

@bp.route('/api/compras/<int:id>/receber', methods=['POST'])
@login_required
def receber_pedido(id):
    pedido = PedidoCompra.query.get_or_404(id)
    if pedido.status == 'entregue':
        return jsonify({'success': False, 'erro': 'Já recebido'}), 400
        
    # Atualiza Status
    pedido.status = 'entregue'
    pedido.data_chegada = datetime.utcnow() # Data Real da Chegada
    
    # Atualiza Estoque
    estoque = Estoque.query.get(pedido.estoque_id)
    estoque.quantidade_atual += pedido.quantidade
    
    # Registra Movimentação (Opcional, mas ideal)
    # Precisaria importar MovimentacaoEstoque.
    # Vou deixar simples por agora, focando na atualização do saldo.
    
    db.session.commit()
    return jsonify({'success': True})