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
            msg = f"Estoque insuficiente na unidade {os_obj.unidade.nome}. "
            msg += f"Disponível: {qtd_disponivel_local} {item.unidade_medida}. "
            total_global = item.quantidade_atual
            if total_global >= qtd_decimal:
                msg += f"(Há {total_global} {item.unidade_medida} no estoque global. Solicite transferência ou entrada nesta unidade)."
            else:
                msg += "Solicite compra ou entrada de estoque."
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
    def repor_estoque(estoque_id, quantidade, usuario_id, motivo=None, unidade_id=None):
        # ... (Manter o código existente do método repor_estoque)
        item = Estoque.query.get(estoque_id)
        if not item:
            raise ValueError("Item não encontrado")
            
        if not unidade_id:
            usuario = Usuario.query.get(usuario_id)
            if usuario.unidade_padrao_id:
                unidade_id = usuario.unidade_padrao_id
            else:
                 raise ValueError("É necessário informar a unidade para entrada de estoque.")

        qtd_decimal = Decimal(str(quantidade))
        if qtd_decimal <= 0:
            raise ValueError("A quantidade deve ser maior que zero.")

        saldo_local = EstoqueSaldo.query.filter_by(estoque_id=estoque_id, unidade_id=unidade_id).first()
        
        if not saldo_local:
            saldo_local = EstoqueSaldo(estoque_id=estoque_id, unidade_id=unidade_id, quantidade=0)
            db.session.add(saldo_local)
        
        saldo_local.quantidade += qtd_decimal

        mov = MovimentacaoEstoque(
            estoque_id=estoque_id,
            usuario_id=usuario_id,
            unidade_id=unidade_id,
            tipo_movimentacao='entrada',
            quantidade=qtd_decimal,
            observacao=motivo or "Entrada manual de estoque"
        )

        db.session.add(mov)
        db.session.commit()
        
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
            
            # Executa a Movimentação Física (Saída Origem)
            saldo_origem.quantidade -= qtd_decimal
            
            # Executa a Movimentação Física (Entrada Destino)
            saldo_destino = EstoqueSaldo.query.filter_by(
                estoque_id=estoque_id, 
                unidade_id=unidade_destino_id
            ).first()
            
            if not saldo_destino:
                saldo_destino = EstoqueSaldo(estoque_id=estoque_id, unidade_id=unidade_destino_id, quantidade=0)
                db.session.add(saldo_destino)
            
            saldo_destino.quantidade += qtd_decimal
            
            # Registra Histórico (Saída na Origem)
            mov_saida = MovimentacaoEstoque(
                estoque_id=estoque_id, 
                usuario_id=solicitante_id, 
                unidade_id=unidade_origem_id,
                tipo_movimentacao='saida', 
                quantidade=qtd_decimal, 
                observacao=f"Transferência para unidade {unidade_destino_id}"
            )
            db.session.add(mov_saida)

            # Registra Histórico (Entrada no Destino)
            mov_entrada = MovimentacaoEstoque(
                estoque_id=estoque_id, 
                usuario_id=solicitante_id, 
                unidade_id=unidade_destino_id,
                tipo_movimentacao='entrada', 
                quantidade=qtd_decimal, 
                observacao=f"Transferência de unidade {unidade_origem_id}"
            )
            db.session.add(mov_entrada)

        db.session.add(solicitacao)
        db.session.commit()
        
        return solicitacao