from decimal import Decimal
from datetime import datetime
from app.extensions import db
from app.models.estoque_models import Estoque, MovimentacaoEstoque, OrdemServico, EstoqueSaldo, SolicitacaoTransferencia
from app.models.models import Usuario

class EstoqueService:
    @staticmethod
    def consumir_item(os_id, estoque_id, quantidade, usuario_id):
        # ... (Manter o código existente do método consumir_item corrigido anteriormente)
        os_obj = OrdemServico.query.get(os_id)
        if not os_obj:
            raise ValueError("Ordem de Serviço não encontrada.")
        
        if os_obj.status == 'cancelada':
            raise ValueError("Não é possível adicionar peças a uma OS cancelada.")

        if os_obj.status == 'concluida':
            raise ValueError("Não é possível adicionar peças a uma OS concluída.")

        item = Estoque.query.get(estoque_id)
        if not item:
            raise ValueError("Item não encontrado")
            
        qtd_decimal = Decimal(str(quantidade))
        if qtd_decimal <= 0:
            raise ValueError("A quantidade deve ser maior que zero.")

        unidade_id = os_obj.unidade_id
        saldo_local = EstoqueSaldo.query.filter_by(
            estoque_id=estoque_id, 
            unidade_id=unidade_id
        ).first()

        qtd_disponivel_local = saldo_local.quantidade if saldo_local else Decimal(0)

        if saldo_local is None or qtd_disponivel_local < qtd_decimal:
            total_global = item.quantidade_atual
            
            if total_global >= qtd_decimal:
                msg = f"Estoque insuficiente na unidade {os_obj.unidade.nome}. "
                msg += f"Disponível aqui: {qtd_disponivel_local}. "
                msg += f"Estoque global: {total_global}. "
                msg += "Solicite transferência de outra unidade."
            else:
                msg = f"Item indisponível em todas as unidades. "
                msg += f"Saldo global: {total_global}. "
                msg += "Solicite compra."
            
            raise ValueError(msg)
            
        saldo_local.quantidade -= qtd_decimal
        
        mov = MovimentacaoEstoque(
            os_id=os_id,
            estoque_id=estoque_id,
            usuario_id=usuario_id,
            unidade_id=unidade_id,
            tipo_movimentacao='consumo',
            quantidade=qtd_decimal,
            observacao=f"Consumo na OS #{os_obj.numero_os}"
        )
        
        db.session.add(mov)
        db.session.commit()
        
        alerta = False
        if item.quantidade_atual <= item.quantidade_minima:
            alerta = True
        
        return item.quantidade_atual, alerta

    @staticmethod
    def repor_estoque(estoque_id, quantidade, usuario_id, motivo=None, unidade_id=None, valor_novo=None):
        item = Estoque.query.get(estoque_id)
        if not item:
            raise ValueError("Item não encontrado")
            
        if not unidade_id:
            usuario = Usuario.query.get(usuario_id)
            if usuario and usuario.unidade_padrao_id:
                unidade_id = usuario.unidade_padrao_id
            else:
                 raise ValueError("É necessário informar a unidade para entrada de estoque.")

        qtd_decimal = Decimal(str(quantidade))
        # Removemos a trava de <= 0 para permitir ajustes negativos (perda/furto)
        
        # Se valor_novo informado, atualizar Estoque.valor_unitario
        if valor_novo is not None:
            item.valor_unitario = Decimal(str(valor_novo))

        saldo_local = EstoqueSaldo.query.filter_by(estoque_id=estoque_id, unidade_id=unidade_id).first()
        
        if not saldo_local:
            saldo_local = EstoqueSaldo(estoque_id=estoque_id, unidade_id=unidade_id, quantidade=0)
            db.session.add(saldo_local)
        
        saldo_local.quantidade += qtd_decimal

        # Define tipo de movimentação: se negativo ou se motivo contiver "Ajuste", vira 'ajuste'
        # Caso contrário, se for positivo e manual, mantemos 'entrada'
        tipo = 'entrada'
        if qtd_decimal < 0 or (motivo and "ajuste" in motivo.lower()):
            tipo = 'ajuste'

        mov = MovimentacaoEstoque(
            estoque_id=estoque_id,
            usuario_id=usuario_id,
            unidade_id=unidade_id,
            tipo_movimentacao=tipo,
            quantidade=qtd_decimal, # Passamos o valor assinado (positivo ou negativo)
            observacao=motivo or ("Entrada manual" if qtd_decimal > 0 else "Ajuste de estoque")
        )

        db.session.add(mov)
        db.session.commit()
        
        # Refresh para garantir que o saldo global atualizado pelo evento seja retornado
        db.session.refresh(item)
        
        return item.quantidade_atual

    @staticmethod
    def transferir_entre_unidades(estoque_id, unidade_origem_id, unidade_destino_id, quantidade, solicitante_id, observacao=None, aprovacao_automatica=False):
        """
        Realiza a lógica de transferência de estoque entre unidades.
        """
        qtd_decimal = Decimal(str(quantidade))
        
        if qtd_decimal <= 0:
             raise ValueError("A quantidade deve ser maior que zero.")

        if str(unidade_origem_id) == str(unidade_destino_id):
             raise ValueError("Origem e Destino devem ser diferentes.")

        # Verificar Disponibilidade na Origem
        saldo_origem = EstoqueSaldo.query.filter_by(
            estoque_id=estoque_id, 
            unidade_id=unidade_origem_id
        ).first()
        
        if not saldo_origem or saldo_origem.quantidade < qtd_decimal:
             raise ValueError('Saldo insuficiente na unidade de origem.')

        solicitacao = SolicitacaoTransferencia(
            estoque_id=estoque_id,
            unidade_origem_id=unidade_origem_id,
            unidade_destino_id=unidade_destino_id,
            solicitante_id=solicitante_id,
            quantidade=qtd_decimal,
            status='pendente',
            observacao=observacao
        )
        
        # Se for aprovada automaticamente (Admin/Gerente)
        if aprovacao_automatica:
            solicitacao.status = 'concluida'
            solicitacao.data_conclusao = datetime.utcnow()
            
            # 1. Executa a Movimentação Física (Saída Origem)
            saldo_origem.quantidade -= qtd_decimal
            
            # 2. Executa a Movimentação Física (Entrada Destino)
            saldo_destino = EstoqueSaldo.query.filter_by(
                estoque_id=estoque_id, 
                unidade_id=unidade_destino_id
            ).first()
            
            if not saldo_destino:
                saldo_destino = EstoqueSaldo(estoque_id=estoque_id, unidade_id=unidade_destino_id, quantidade=0)
                db.session.add(saldo_destino)
            
            saldo_destino.quantidade += qtd_decimal
            
            # 3. Registra Histórico (Saída na Origem)
            mov_saida = MovimentacaoEstoque(
                estoque_id=estoque_id, 
                usuario_id=solicitante_id, 
                unidade_id=unidade_origem_id,
                tipo_movimentacao='saida', 
                quantidade=qtd_decimal, 
                observacao=f"Transferência (Saída) p/ Unidade #{unidade_destino_id}. {observacao or ''}"
            )
            db.session.add(mov_saida)

            # 4. Registra Histórico (Entrada no Destino)
            mov_entrada = MovimentacaoEstoque(
                estoque_id=estoque_id, 
                usuario_id=solicitante_id, 
                unidade_id=unidade_destino_id,
                tipo_movimentacao='entrada', 
                quantidade=qtd_decimal, 
                observacao=f"Transferência (Entrada) de Unidade #{unidade_origem_id}. {observacao or ''}"
            )
            db.session.add(mov_entrada)

        db.session.add(solicitacao)
        db.session.commit()
        
        return solicitacao

    @staticmethod
    def aprovar_solicitacao_transferencia(solicitacao_id, aprovador_id):
        """
        Aprova uma solicitação pendente e executa a movimentação de estoque.
        """
        sol = SolicitacaoTransferencia.query.get(solicitacao_id)
        if not sol:
            raise ValueError("Solicitação não encontrada.")
        
        if sol.status != 'pendente':
            raise ValueError(f"Esta solicitação já está {sol.status}.")

        # Vínculo do saldo de origem
        saldo_origem = EstoqueSaldo.query.filter_by(
            estoque_id=sol.estoque_id, 
            unidade_id=sol.unidade_origem_id
        ).first()

        if not saldo_origem or saldo_origem.quantidade < sol.quantidade:
            raise ValueError("Saldo insuficiente na origem para aprovação.")

        # Executa Transferência
        sol.status = 'concluida'
        sol.data_conclusao = datetime.utcnow()
        # Nota: SolicitacaoTransferencia não tem campo aprovador_id no seu modelo atual, 
        # mas poderíamos adicionar se necessário. Por agora apenas concluímos.

        # Movimentação Física
        saldo_origem.quantidade -= sol.quantidade
        
        saldo_destino = EstoqueSaldo.query.filter_by(
            estoque_id=sol.estoque_id, 
            unidade_id=sol.unidade_destino_id
        ).first()
        
        if not saldo_destino:
            saldo_destino = EstoqueSaldo(estoque_id=sol.estoque_id, unidade_id=sol.unidade_destino_id, quantidade=0)
            db.session.add(saldo_destino)
            
        saldo_destino.quantidade += sol.quantidade
        
        # Histórico
        mov_saida = MovimentacaoEstoque(
            estoque_id=sol.estoque_id, 
            usuario_id=aprovador_id, 
            unidade_id=sol.unidade_origem_id,
            tipo_movimentacao='saida', 
            quantidade=sol.quantidade, 
            observacao=f"Transferência Aprovada p/ Unidade #{sol.unidade_destino_id}"
        )
        db.session.add(mov_saida)

        mov_entrada = MovimentacaoEstoque(
            estoque_id=sol.estoque_id, 
            usuario_id=aprovador_id, 
            unidade_id=sol.unidade_destino_id,
            tipo_movimentacao='entrada', 
            quantidade=sol.quantidade, 
            observacao=f"Transferência Aprovada de Unidade #{sol.unidade_origem_id}"
        )
        db.session.add(mov_entrada)

        db.session.commit()
        return sol

    @staticmethod
    def rejeitar_solicitacao_transferencia(solicitacao_id, aprovador_id):
        """
        Rejeita uma solicitação de transferência.
        """
        sol = SolicitacaoTransferencia.query.get(solicitacao_id)
        if not sol:
            raise ValueError("Solicitação não encontrada.")
        
        if sol.status != 'pendente':
            raise ValueError(f"Esta solicitação já está {sol.status}.")

        sol.status = 'rejeitada'
        sol.data_conclusao = datetime.utcnow()
        db.session.commit()
        return sol

    @staticmethod
    def cancelar_os(os_id, usuario_id):
        """
        Cancela uma OS e estorna as peças consumidas de volta ao estoque da unidade.
        """
        os_obj = OrdemServico.query.get(os_id)
        if not os_obj:
            raise ValueError("Ordem de Serviço não encontrada.")
        
        if os_obj.status == 'concluida':
            raise ValueError("Não é possível cancelar uma OS já concluída.")
            
        if os_obj.status == 'cancelada':
            return os_obj

        # 1. Identifica movimentações de consumo vinculadas a esta OS
        consumos = [m for m in os_obj.movimentacoes if m.tipo_movimentacao == 'consumo']

        for mov in consumos:
            # 2. Localiza o saldo da peça na unidade da OS
            saldo_local = EstoqueSaldo.query.filter_by(
                estoque_id=mov.estoque_id, 
                unidade_id=mov.unidade_id
            ).first()

            if saldo_local:
                # 3. Estorna a quantidade para o saldo local
                saldo_local.quantidade += mov.quantidade
            else:
                # Caso raro: se o registro de saldo desapareceu, recria
                saldo_local = EstoqueSaldo(
                    estoque_id=mov.estoque_id, 
                    unidade_id=mov.unidade_id, 
                    quantidade=mov.quantidade
                )
                db.session.add(saldo_local)

            # 4. Registra a devolução no histórico geral (MovimentacaoEstoque)
            # Nota: O trigger after_insert de MovimentacaoEstoque atualizará o Estoque.quantidade_atual (global)
            estorno = MovimentacaoEstoque(
                os_id=os_id,
                estoque_id=mov.estoque_id,
                usuario_id=usuario_id,
                unidade_id=mov.unidade_id,
                tipo_movimentacao='entrada', # Ou 'devolucao' se o modelo suportar
                quantidade=mov.quantidade,
                observacao=f"Estorno por cancelamento da OS #{os_obj.numero_os}"
            )
            db.session.add(estorno)

        # 5. Atualiza o status da OS
        os_obj.status = 'cancelada'
        db.session.commit()
        
        return os_obj