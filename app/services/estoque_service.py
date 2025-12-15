from decimal import Decimal
from app.extensions import db
from app.models.estoque_models import Estoque, MovimentacaoEstoque, OrdemServico

class EstoqueService:
    @staticmethod
    def consumir_item(os_id, estoque_id, quantidade, usuario_id):
        """
        RN-004: Consumo com validação de saldo e alerta de mínimo.
        RN-007: Bloquear consumo em OS cancelada.
        """
        # [RN007] Validação de Status da OS
        os_obj = OrdemServico.query.get(os_id)
        if not os_obj:
            raise ValueError("Ordem de Serviço não encontrada.")
        
        if os_obj.status == 'cancelada':
            raise ValueError("Não é possível adicionar peças a uma OS cancelada.")

        if os_obj.status == 'concluida':
            raise ValueError("Não é possível adicionar peças a uma OS concluída.")

        # Validação do Item
        item = Estoque.query.get(estoque_id)
        if not item:
            raise ValueError("Item não encontrado")
            
        qtd_decimal = Decimal(str(quantidade))
        
        if qtd_decimal <= 0:
            raise ValueError("A quantidade deve ser maior que zero.")

        # [RN004] Bloqueio por saldo insuficiente
        if item.quantidade_atual < qtd_decimal:
            raise ValueError(f"Estoque insuficiente. Disponível: {item.quantidade_atual} {item.unidade_medida}")
            
        # Registro da Movimentação
        mov = MovimentacaoEstoque(
            os_id=os_id,
            estoque_id=estoque_id,
            usuario_id=usuario_id,
            tipo_movimentacao='consumo',
            quantidade=qtd_decimal,
            observacao=f"Consumo na OS #{os_obj.numero_os}"
        )
        
        db.session.add(mov)
        # O saldo é atualizado via Trigger (event listener no model)
        
        db.session.commit()
        
        # [RN004] Verificação de Alerta de Estoque Mínimo (Pós-consumo)
        alerta = False
        if item.quantidade_atual <= item.quantidade_minima:
            alerta = True
        
        return item.quantidade_atual, alerta

    @staticmethod
    def repor_estoque(estoque_id, quantidade, usuario_id, motivo=None):
        """
        Registra entrada de material no estoque (Reabastecimento).
        """
        item = Estoque.query.get(estoque_id)
        if not item:
            raise ValueError("Item não encontrado")

        qtd_decimal = Decimal(str(quantidade))
        if qtd_decimal <= 0:
            raise ValueError("A quantidade deve ser maior que zero.")

        mov = MovimentacaoEstoque(
            estoque_id=estoque_id,
            usuario_id=usuario_id,
            tipo_movimentacao='entrada',
            quantidade=qtd_decimal,
            observacao=motivo or "Entrada manual de estoque"
        )

        db.session.add(mov)
        db.session.commit()
        
        return item.quantidade_atual