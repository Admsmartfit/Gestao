from flask import Blueprint, jsonify, request
from flask_login import login_required
from app.models.models import Usuario
from app.models.estoque_models import OrdemServico, Equipamento, Estoque, Fornecedor
from app.models.terceirizados_models import Terceirizado
from sqlalchemy import or_

bp = Blueprint('search', __name__, url_prefix='/api')

@bp.route('/global-search', methods=['GET'])
@login_required
def global_search():
    query = request.args.get('q', '').strip()
    if not query or len(query) < 2:
        return jsonify({})

    # 1. Buscar em Ordens de Serviço (ID ou Descrição)
    os_results = []
    # Busca por ID
    if query.isdigit():
        os_por_id = OrdemServico.query.get(int(query))
        if os_por_id:
            os_results.append({
                'id': os_por_id.id,
                'titulo': f'OS #{os_por_id.numero_os} - {os_por_id.equipamento_rel.nome if os_por_id.equipamento_rel else "Sem Equipamento"}',
                'subtitulo': f'Status: {os_por_id.status} | Técnico: {os_por_id.tecnico.nome}',
                'url': f'/os/{os_por_id.id}/detalhes',
                'tipo': 'Ordem de Serviço'
            })

    # Busca textual em OS
    os_text = OrdemServico.query.filter(
        or_(
            OrdemServico.descricao_problema.ilike(f'%{query}%'),
            OrdemServico.descricao_solucao.ilike(f'%{query}%')
        )
    ).limit(5).all()

    for os in os_text:
        # Evita duplicação se achou por ID
        if not any(r['id'] == os.id for r in os_results):
            os_results.append({
                'id': os.id,
                'titulo': f'OS #{os.numero_os} - {os.equipamento_rel.nome if os.equipamento_rel else "Geral"}',
                'subtitulo': f'{os.descricao_problema[:50]}...',
                'url': f'/os/{os.id}/detalhes',
                'tipo': 'Ordem de Serviço'
            })

    # 2. Buscar Equipamentos
    equipamentos = Equipamento.query.filter(
        or_(
            Equipamento.nome.ilike(f'%{query}%'),
            Equipamento.categoria.ilike(f'%{query}%')
        )
    ).limit(5).all()
    
    equip_results = [{
        'id': e.id,
        'titulo': e.nome,
        'subtitulo': f'Categoria: {e.categoria} | Unidade: {e.unidade.nome}',
        'url': f'/admin/configuracoes?tab=equipamentos', # Link genérico pois não há pg detalhe
        'tipo': 'Equipamento'
    } for e in equipamentos]

    # 3. Buscar Peças (Estoque)
    pecas = Estoque.query.filter(
        or_(
            Estoque.nome.ilike(f'%{query}%'),
            Estoque.codigo.ilike(f'%{query}%')
        )
    ).limit(5).all()
    
    pecas_results = [{
        'id': p.id,
        'titulo': f'{p.nome} ({p.codigo})',
        'subtitulo': f'Saldo: {p.quantidade_atual} {p.unidade_medida}',
        'url': '/os/painel-estoque', 
        'tipo': 'Peça'
    } for p in pecas]

    # 4. Buscar Fornecedores
    fornecedores = Fornecedor.query.filter(
        or_(
            Fornecedor.nome.ilike(f'%{query}%'),
            Fornecedor.email.ilike(f'%{query}%')
        )
    ).limit(3).all()
    
    forn_results = [{
        'id': f.id,
        'titulo': f.nome,
        'subtitulo': f'Fornecedor | {f.email}',
        'url': '/admin/configuracoes?tab=modalFornecedor', # Tentar abrir modal?
        'tipo': 'Fornecedor'
    } for f in fornecedores]
    
    # 5. Buscar Terceirizados
    terceiros = Terceirizado.query.filter(
        or_(
            Terceirizado.nome.ilike(f'%{query}%'),
            Terceirizado.nome_empresa.ilike(f'%{query}%'),
            Terceirizado.especialidades.ilike(f'%{query}%')
        )
    ).limit(3).all()
    
    terc_results = [{
        'id': t.id,
        'titulo': t.nome_empresa or t.nome,
        'subtitulo': f'Terceirizado | {t.especialidades[:30] if t.especialidades else "Geral"}',
        'url': '/terceirizados/painel', 
        'tipo': 'Terceirizado'
    } for t in terceiros]

    # 6. Buscar Técnicos/Usuários
    usuarios = Usuario.query.filter(Usuario.nome.ilike(f'%{query}%')).limit(3).all()
    user_results = [{
        'id': u.id,
        'titulo': u.nome,
        'subtitulo': f'{u.tipo.capitalize()} | {u.email}',
        'url': '/admin/configuracoes?tab=tecnicos',
        'tipo': 'Usuário'
    } for u in usuarios]

    return jsonify({
        'os': os_results,
        'equipamentos': equip_results,
        'pecas': pecas_results,
        'fornecedores': forn_results,
        'terceirizados': terc_results,
        'usuarios': user_results
    })
