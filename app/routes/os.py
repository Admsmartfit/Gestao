from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify
from flask_login import login_required, current_user
from datetime import datetime
from app.extensions import db
from app.models.models import Unidade, Usuario
from app.models.estoque_models import OrdemServico, Estoque, CategoriaEstoque, Equipamento
from app.services.os_service import OSService
from app.services.estoque_service import EstoqueService

bp = Blueprint('os', __name__, url_prefix='/os')

@bp.route('/nova', methods=['GET', 'POST'])
@login_required
def nova_os():
    if request.method == 'POST':
        try:
            prazo_str = request.form.get('prazo_conclusao')
            prazo_dt = datetime.strptime(prazo_str, '%Y-%m-%dT%H:%M') if prazo_str else None
            
            nova_os = OrdemServico(
                numero_os=OSService.gerar_numero_os(),
                tecnico_id=request.form.get('tecnico_id'),
                unidade_id=request.form.get('unidade_id'),
                equipamento_id=request.form.get('equipamento_id'),
                prazo_conclusao=prazo_dt,
                tipo_manutencao=request.form.get('tipo_manutencao'),
                prioridade=request.form.get('prioridade'),
                descricao_problema=request.form.get('descricao_problema'),
                status='aberta'
            )
            
            db.session.add(nova_os)
            db.session.commit() # Commit para gerar o ID da OS
            
            # Processar Fotos (Agora salva na tabela anexos_os e retorna lista pro JSON)
            fotos = request.files.getlist('fotos_antes')
            if fotos and fotos[0].filename != '':
                caminhos = OSService.processar_fotos(fotos, nova_os.id, tipo='foto_antes')
                nova_os.fotos_antes = caminhos
                db.session.commit()

            flash(f'OS {nova_os.numero_os} criada com sucesso!', 'success')
            return redirect(url_for('os.detalhes', id=nova_os.id))
            
        except ValueError:
            db.session.rollback()
            flash('Erro no formato da data do prazo.', 'danger')
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao criar OS: {str(e)}', 'danger')

    unidades = Unidade.query.filter_by(ativa=True).all()
    tecnicos = Usuario.query.filter(Usuario.tipo.in_(['tecnico', 'admin'])).all()
    return render_template('os_nova.html', unidades=unidades, tecnicos=tecnicos)
    
@bp.route('/<int:id>', methods=['GET'])
@login_required
def detalhes(id):
    os_obj = OrdemServico.query.get_or_404(id)
    categorias = CategoriaEstoque.query.all()
    
    # CORREÇÃO DO ERRO 1: Carregar todas as peças para o modal de solicitação
    todas_pecas = Estoque.query.order_by(Estoque.nome).all()
    
    return render_template('os_detalhes.html', 
                         os=os_obj, 
                         categorias=categorias,
                         todas_pecas=todas_pecas) # Passando a variável aqui

# CORREÇÃO DO ERRO 2: Nova rota para concluir a OS
@bp.route('/<int:id>/concluir', methods=['POST'])
@login_required
def concluir_os(id):
    os_obj = OrdemServico.query.get_or_404(id)
    
    if os_obj.status == 'concluida':
        flash('Esta OS já está concluída.', 'warning')
        return redirect(url_for('os.detalhes', id=id))

    solucao = request.form.get('descricao_solucao')
    
    # Processar fotos do "Depois"
    fotos = request.files.getlist('fotos_depois')
    if fotos and fotos[0].filename != '':
        caminhos = OSService.processar_fotos(fotos, os_obj.id, tipo='foto_depois')
        os_obj.fotos_depois = caminhos

    os_obj.descricao_solucao = solucao
    os_obj.status = 'concluida'
    os_obj.data_conclusao = datetime.utcnow()
    
    db.session.commit()
    flash('Ordem de Serviço concluída com sucesso!', 'success')
    return redirect(url_for('os.detalhes', id=id))

@bp.route('/<int:id>/adicionar-peca', methods=['POST'])
@login_required
def adicionar_peca(id):
    data = request.get_json()
    try:
        novo_saldo = EstoqueService.consumir_item(
            os_id=id,
            estoque_id=data['estoque_id'],
            quantidade=data['quantidade'],
            usuario_id=current_user.id
        )
        os_obj = OrdemServico.query.get(id)
        return jsonify({'success': True, 'novo_estoque': float(novo_saldo), 'custo_total_os': float(os_obj.custo_total)})
    except Exception as e:
        return jsonify({'success': False, 'erro': str(e)}), 400

@bp.route('/api/pecas/buscar')
@login_required
def buscar_pecas():
    termo = request.args.get('q', '')
    if len(termo) < 2: return jsonify([])
    pecas = Estoque.query.filter(Estoque.nome.ilike(f'%{termo}%')).limit(10).all()
    return jsonify([{'id': p.id, 'nome': p.nome, 'unidade': p.unidade_medida, 'saldo': float(p.quantidade_atual)} for p in pecas])

@bp.route('/estoque/painel')
@login_required
def painel_estoque():
    itens = Estoque.query.order_by(Estoque.nome).all()
    return render_template('estoque.html', estoque=itens)

# --- ROTA QUE ESTAVA FALTANDO ---
@bp.route('/api/equipamentos/filtro')
@login_required
def filtrar_equipamentos():
    """
    API para filtrar equipamentos por unidade e categoria via AJAX
    """
    unidade_id = request.args.get('unidade_id')
    categoria = request.args.get('categoria')
    
    query = Equipamento.query.filter_by(ativo=True)
    
    if unidade_id:
        query = query.filter_by(unidade_id=unidade_id)
        
    if categoria and categoria != 'todos':
        query = query.filter_by(categoria=categoria)
        
    equipamentos = query.order_by(Equipamento.nome).all()
    
    return jsonify([{
        'id': e.id,
        'nome': e.nome
    } for e in equipamentos])