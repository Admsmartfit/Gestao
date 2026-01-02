from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify
from flask_login import login_required, current_user
from datetime import datetime
from app.extensions import db
from app.models.models import Unidade, Usuario
from app.models.estoque_models import OrdemServico, Estoque, CategoriaEstoque, Equipamento, AnexosOS, PedidoCompra, EstoqueSaldo, MovimentacaoEstoque
from app.models.terceirizados_models import Terceirizado, ChamadoExterno
from app.services.os_service import OSService
from app.services.estoque_service import EstoqueService
from app.services.whatsapp_service import WhatsAppService # [Novo] Import

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
    
    # Carregar todas as peças para o modal de solicitação
    todas_pecas = Estoque.query.order_by(Estoque.nome).all()
    
    # Filtra terceirizados: Globais (abrangencia_global=True) OU que atendam a Unidade da OS
    terceirizados = Terceirizado.query.filter(
        (Terceirizado.abrangencia_global == True) | 
        (Terceirizado.unidades.any(id=os_obj.unidade_id))
    ).filter_by(ativo=True).order_by(Terceirizado.nome).all()

    # [Novo] Carrega usuários para o select de notificação na transferência
    usuarios = Usuario.query.filter_by(ativo=True).order_by(Usuario.nome).all()
    
    return render_template('os_detalhes.html', 
                         os=os_obj, 
                         categorias=categorias,
                         todas_pecas=todas_pecas,
                         terceirizados=terceirizados,
                         usuarios=usuarios)

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
        # Atualizado para receber o flag de alerta
        novo_saldo, alerta_minimo = EstoqueService.consumir_item(
            os_id=id,
            estoque_id=data['estoque_id'],
            quantidade=data['quantidade'],
            usuario_id=current_user.id
        )
        os_obj = OrdemServico.query.get(id)
        
        msg = "Peça adicionada."
        if alerta_minimo:
            msg += " ATENÇÃO: Item atingiu estoque mínimo!"

        return jsonify({
            'success': True, 
            'novo_estoque': float(novo_saldo), 
            'custo_total_os': float(os_obj.custo_total),
            'mensagem': msg,
            'alerta': alerta_minimo
        })
    except Exception as e:
        erro_msg = str(e)
        os_obj = OrdemServico.query.get(id)
        
        # Se o erro sugerir transferência ou compra, retornamos dados extras
        if os_obj:
            estoque_id = data.get('estoque_id')
            qtd_pedida = float(data.get('quantidade', 0))
            item = Estoque.query.get(estoque_id)
            
            if item:
                if "Solicite transferência" in erro_msg or "Solicite compra" in erro_msg:
                    # Busca distribuição
                    saldos = EstoqueSaldo.query.filter(
                        EstoqueSaldo.estoque_id == estoque_id,
                        EstoqueSaldo.quantidade > 0
                    ).all()
                    
                    sugestoes = []
                    for s in saldos:
                        if s.unidade_id != os_obj.unidade_id:
                            sugestoes.append({
                                'unidade_id': s.unidade_id,
                                'unidade_nome': s.unidade.nome,
                                'saldo': float(s.quantidade)
                            })
                    
                    return jsonify({
                        'success': False,
                        'erro': erro_msg,
                        'sugestoes_transferencia': sugestoes,
                        'unidade_destino_id': os_obj.unidade_id,
                        'unidade_destino_nome': os_obj.unidade.nome,
                        'quantidade_solicitada': qtd_pedida
                    }), 400
                
        return jsonify({'success': False, 'erro': erro_msg}), 400

@bp.route('/<int:id>/solicitar-compra-peca', methods=['POST'])
@login_required
def solicitar_compra_peca(id):
    """Cria uma solicitação de compra (PedidoCompra) vinculada à peça."""
    data = request.get_json()
    try:
        estoque_id = data.get('estoque_id')
        quantidade = data.get('quantidade')
        
        if not estoque_id or not quantidade or float(quantidade) <= 0:
            return jsonify({'success': False, 'erro': 'Quantidade deve ser maior que zero.'}), 400

        item = Estoque.query.get(estoque_id)
        if not item:
            return jsonify({'success': False, 'erro': 'Item não encontrado.'}), 404

        from app.models.estoque_models import CatalogoFornecedor, Fornecedor
        
        # 1. Tenta buscar no catálogo vinculado
        cat = CatalogoFornecedor.query.filter_by(estoque_id=estoque_id).first()
        if cat:
            fornecedor_id = cat.fornecedor_id
        else:
            # 2. Tenta buscar qualquer fornecedor disponível
            f = Fornecedor.query.first()
            if not f:
                return jsonify({'success': False, 'erro': 'Nenhum fornecedor cadastrado no sistema.'}), 400
            fornecedor_id = f.id

        novo_pedido = PedidoCompra(
            fornecedor_id=fornecedor_id,
            estoque_id=estoque_id,
            quantidade=quantidade,
            status='pendente',
            data_solicitacao=datetime.utcnow(),
            solicitante_id=current_user.id
        )
        
        db.session.add(novo_pedido)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'mensagem': f'Pedido #{novo_pedido.id} criado'
        })

    except Exception as e:
        return jsonify({'success': False, 'erro': str(e)}), 400

# [NOVA ROTA] Entrada de Estoque (Restock)
@bp.route('/api/estoque/entrada', methods=['POST'])
@login_required
def entrada_estoque():
    """Registra entrada de novas peças (compra/reposição)."""
    if current_user.tipo not in ['admin', 'gerente', 'tecnico', 'comprador']:
         return jsonify({'success': False, 'erro': 'Acesso negado'}), 403

    data = request.get_json()
    try:
        estoque_id = data.get('estoque_id')
        quantidade = data.get('quantidade')
        unidade_id = data.get('unidade_id')
        motivo = data.get('motivo')
        valor_novo = data.get('valor_novo')

        if not estoque_id or not quantidade:
            return jsonify({'success': False, 'erro': 'Dados incompletos'}), 400

        novo_saldo = EstoqueService.repor_estoque(
            estoque_id=estoque_id,
            quantidade=quantidade,
            usuario_id=current_user.id,
            motivo=motivo,
            unidade_id=unidade_id,
            valor_novo=valor_novo
        )
        return jsonify({'success': True, 'novo_saldo': float(novo_saldo)})
    except ValueError as e:
        return jsonify({'success': False, 'erro': str(e)}), 400
    except Exception as e:
        return jsonify({'success': False, 'erro': f"Erro interno: {str(e)}"}), 500

# [NOVA ROTA] Upload de Anexos em OS Aberta
@bp.route('/<int:id>/anexos', methods=['POST'])
@login_required
def upload_anexos(id):
    os_obj = OrdemServico.query.get_or_404(id)
    if os_obj.status in ['concluida', 'cancelada']:
        flash('Não é possível anexar arquivos a uma OS fechada.', 'warning')
        return redirect(url_for('os.detalhes', id=id))

    fotos = request.files.getlist('fotos')
    if fotos:
        try:
            OSService.processar_fotos(fotos, os_obj.id, tipo='documento') # ou 'foto_extra'
            db.session.commit()
            flash('Arquivos anexados com sucesso!', 'success')
        except ValueError as e:
            flash(str(e), 'danger')
        except Exception as e:
            flash(f'Erro no upload: {str(e)}', 'danger')
            
    return redirect(url_for('os.detalhes', id=id))
    
@bp.route('/api/estoque/<int:id>/disponibilidade')
@login_required
def disponibilidade_estoque(id):
    """
    API para verificar saldo global e distribuição por unidade de um item.
    """
    item = Estoque.query.get_or_404(id)
    saldos = EstoqueSaldo.query.filter_by(estoque_id=id).all()
    
    distribuicao = []
    for s in saldos:
        if s.quantidade > 0:
            distribuicao.append({
                'unidade_id': s.unidade_id,
                'unidade_nome': s.unidade.nome,
                'saldo': float(s.quantidade),
                'localizacao': s.localizacao or '-'
            })
            
    saldo_global = float(item.quantidade_atual)
    
    return jsonify({
        'item_id': item.id,
        'item_nome': item.nome,
        'saldo_global': saldo_global,
        'unidade_medida': item.unidade_medida,
        'distribuicao': distribuicao,
        'recomendacao': 'transferencia' if saldo_global > 0 else 'compra'
    })

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
    unidades = Unidade.query.order_by(Unidade.nome).all()
    return render_template('estoque.html', estoque=itens, unidades=unidades)

@bp.route('/api/estoque/solicitar-compra', methods=['POST'])
@login_required
def solicitar_compra():
    data = request.get_json()
    try:
        estoque_id = data.get('estoque_id')
        quantidade = data.get('quantidade')
        
        if not estoque_id or not quantidade or float(quantidade) <= 0:
            return jsonify({'success': False, 'erro': 'Quantidade deve ser maior que zero.'}), 400

        item = Estoque.query.get(estoque_id)
        if not item:
            return jsonify({'success': False, 'erro': 'Item não encontrado.'}), 404

        from app.models.estoque_models import CatalogoFornecedor, Fornecedor
        
        # 1. Tenta buscar no catálogo vinculado
        vinculo = CatalogoFornecedor.query.filter_by(estoque_id=estoque_id).first()
        if vinculo:
            fornecedor_id = vinculo.fornecedor_id
        else:
            # 2. Tenta buscar qualquer fornecedor disponível
            primeiro_forn = Fornecedor.query.first()
            if primeiro_forn:
                fornecedor_id = primeiro_forn.id
            else:
                return jsonify({'success': False, 'erro': 'Nenhum fornecedor cadastrado no sistema.'}), 400

        pedido = PedidoCompra(
            estoque_id=estoque_id,
            fornecedor_id=fornecedor_id,
            quantidade=quantidade,
            status='pendente',
            data_solicitacao=datetime.utcnow(),
            solicitante_id=current_user.id
        )

        db.session.add(pedido)
        db.session.commit()
        return jsonify({
            'success': True, 
            'mensagem': f'Pedido #{pedido.id} criado'
        })
    except Exception as e:
        return jsonify({'success': False, 'erro': str(e)}), 400

# [MODIFICADO] Solicitar Transferência entre Unidades (com notificação)
@bp.route('/api/estoque/transferir', methods=['POST'])
@login_required
def solicitar_transferencia():
    data = request.get_json()
    try:
        estoque_id = data.get('estoque_id')
        qtd = data.get('quantidade')
        unidade_origem_id = data.get('unidade_origem_id')
        unidade_destino_id = data.get('unidade_destino_id')
        
        # Novos campos para notificação
        notificar_responsavel_id = data.get('notificar_responsavel_id')
        enviar_whats = data.get('enviar_whats')
        
        if not all([estoque_id, qtd, unidade_origem_id, unidade_destino_id]):
             return jsonify({'success': False, 'erro': 'Dados incompletos'}), 400
        
        # Define se aprova automaticamente baseado no cargo
        aprovacao_automatica = current_user.tipo in ['admin', 'gerente']

        solicitacao = EstoqueService.transferir_entre_unidades(
            estoque_id=estoque_id,
            unidade_origem_id=unidade_origem_id,
            unidade_destino_id=unidade_destino_id,
            quantidade=qtd,
            solicitante_id=current_user.id,
            observacao=data.get('observacao'),
            aprovacao_automatica=aprovacao_automatica
        )
        
        # [Novo] Enviar notificação WhatsApp se solicitado
        if enviar_whats and notificar_responsavel_id:
            responsavel = Usuario.query.get(notificar_responsavel_id)
            if responsavel and responsavel.telefone:
                # Busca objetos para montar mensagem
                item = Estoque.query.get(estoque_id)
                origem = Unidade.query.get(unidade_origem_id)
                destino = Unidade.query.get(unidade_destino_id)
                
                msg = (f"📦 *Solicitação de Transferência*\n\n"
                       f"Item: {item.nome}\n"
                       f"Qtd: {qtd} {item.unidade_medida}\n"
                       f"De: {origem.nome}\n"
                       f"Para: {destino.nome}\n\n"
                       f"Solicitante: {current_user.nome}\n"
                       f"Status: {solicitacao.status.upper()}")

                WhatsAppService.enviar_mensagem(responsavel.telefone, msg)
        
        msg = 'Transferência realizada com sucesso!' if solicitacao.status == 'concluida' else 'Solicitação criada'
        return jsonify({'success': True, 'msg': msg})

    except ValueError as e:
        return jsonify({'success': False, 'erro': str(e)}), 400
    except Exception as e:
        return jsonify({'success': False, 'erro': f"Erro interno: {str(e)}"}), 500

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

@bp.route('/<int:id>/adicionar-tarefa-externa', methods=['POST'])
@login_required
def adicionar_tarefa_externa(id):
    os_obj = OrdemServico.query.get_or_404(id)
    
    terceirizado_id = request.form.get('terceirizado_id')
    descricao = request.form.get('descricao')
    prazo_str = request.form.get('prazo')
    valor_str = request.form.get('valor')
    
    if not terceirizado_id or not descricao:
        flash('Preencha os campos obrigatórios.', 'danger')
        return redirect(url_for('os.detalhes', id=id))

    try:
        prazo_dt = datetime.strptime(prazo_str, '%Y-%m-%dT%H:%M')
        
        # Gera sufixo baseado na quantidade atual de chamados
        count = len(os_obj.chamados_externos) + 1
        num_chamado = f"EXT-{os_obj.numero_os}-{count}"

        novo_chamado = ChamadoExterno(
            numero_chamado=num_chamado,
            os_id=os_obj.id,
            terceirizado_id=int(terceirizado_id),
            titulo=f"Serviço Adicional OS {os_obj.numero_os}",
            descricao=descricao,
            prioridade=os_obj.prioridade,
            prazo_combinado=prazo_dt,
            criado_por=current_user.id,
            valor_orcado=valor_str if valor_str else None,
            status='aguardando'
        )
        
        db.session.add(novo_chamado)
        db.session.commit()
        
        flash('Tarefa externa criada com sucesso!', 'success')
        
    except ValueError:
        flash('Formato de data inválido.', 'danger')
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao criar tarefa: {str(e)}', 'danger')

    return redirect(url_for('os.detalhes', id=id))

@bp.route('/api/estoque/historico')
@login_required
def historico_estoque():
    """Retorna as últimas 30 movimentações de estoque."""
    movs = MovimentacaoEstoque.query.order_by(MovimentacaoEstoque.data_movimentacao.desc()).limit(30).all()
    
    return jsonify([{
        'data': m.data_movimentacao.strftime('%d/%m/%Y %H:%M'),
        'item': m.estoque.nome,
        'tipo': m.tipo_movimentacao.capitalize(),
        'qtd': float(m.quantidade),
        'unidade': m.unidade.nome if m.unidade else 'N/A',
        'usuario': m.usuario.nome if m.usuario else 'Sistema',
        'motivo': m.observacao or '-'
    } for m in movs])

@bp.route('/<int:id>/editar-os', methods=['POST'])
@login_required
def editar_os(id):
    os_obj = OrdemServico.query.get_or_404(id)
    
    if os_obj.status == 'concluida':
        flash('Não é possível editar uma OS concluída.', 'warning')
        return redirect(url_for('os.detalhes', id=id))
        
    try:
        prazo_str = request.form.get('prazo_conclusao')
        prioridade = request.form.get('prioridade')
        descricao = request.form.get('descricao_problema')
        
        if prazo_str:
            os_obj.prazo_conclusao = datetime.strptime(prazo_str, '%Y-%m-%dT%H:%M')
            
        if prioridade:
            os_obj.prioridade = prioridade
            
        if descricao:
            os_obj.descricao_problema = descricao
            
        db.session.commit()
        flash('Ordem de Serviço atualizada.', 'success')
        
    except ValueError:
        flash('Formato de data inválido.', 'danger')
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao atualizar OS: {str(e)}', 'danger')
        
    return redirect(url_for('os.detalhes', id=id))

@bp.route('/<int:id>/cancelar', methods=['POST'])
@login_required
def cancelar_os_route(id):
    try:
        EstoqueService.cancelar_os(id, current_user.id)
        flash('Ordem de Serviço cancelada e estoque estornado.', 'success')
    except ValueError as e:
        flash(str(e), 'warning')
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao cancelar OS: {str(e)}', 'danger')
        
    return redirect(url_for('os.detalhes', id=id))