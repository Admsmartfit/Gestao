from flask import Blueprint, jsonify, request
from flask_login import login_required
from app.models.models import Usuario
from app.models.estoque_models import OrdemServico, Equipamento, Estoque
from sqlalchemy import or_

bp = Blueprint('search', __name__, url_prefix='/api')

@bp.route('/global-search', methods=['GET'])
@login_required
def global_search():
    query = request.args.get('q', '').strip()
    if not query or len(query) < 2:
        return jsonify({})

    # 1. Buscar em Ordens de Serviço (ID ou Descrição)
    # Tenta converter para int para busca por ID
    os_results = []
    try:
        os_id = int(query)
        os_por_id = OrdemServico.query.get(os_id)
        if os_por_id:
            os_results.append({
                'id': os_por_id.id,
                'titulo': f'OS #{os_por_id.id} - {os_por_id.equipamento_rel.nome if os_por_id.equipamento_rel else "Sem Equipamento"}',
                'subtitulo': f'Status: {os_por_id.status} | Técnico: {os_por_id.tecnico.nome}',
                'url': f'/os/{os_por_id.id}/detalhes',
                'tipo': 'Ordem de Serviço'
            })
    except ValueError:
        pass

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
                'titulo': f'OS #{os.id} - {os.equipamento_rel.nome if os.equipamento_rel else "Geral"}',
                'subtitulo': f'{os.descricao_problema[:50]}...',
                'url': f'/os/{os.id}/detalhes',
                'tipo': 'Ordem de Serviço'
            })

    # 2. Buscar Equipamentos
    equipamentos = Equipamento.query.filter(Equipamento.nome.ilike(f'%{query}%')).limit(5).all()
    equip_results = [{
        'id': e.id,
        'titulo': e.nome,
        'subtitulo': f'Categoria: {e.categoria} | Unidade: {e.unidade.nome}',
        'url': f'/admin/configuracoes?tab=equipamentos', # Idealmente teria uma pág de detalhes
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
        'url': '/os/painel-estoque', # Redireciona para painel
        'tipo': 'Peça'
    } for p in pecas]

    # 4. Buscar Técnicos/Usuários
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
        'usuarios': user_results
    })
