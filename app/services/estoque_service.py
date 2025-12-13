from decimal import Decimal
from app.extensions import db
from app.models.estoque_models import Estoque, MovimentacaoEstoque

class EstoqueService:
    @staticmethod
    def consumir_item(os_id, estoque_id, quantidade, usuario_id):
        """RN-004: Consumo fracionado com validação [cite: 342-345]"""
        item = Estoque.query.get(estoque_id)
        if not item:
            raise ValueError("Item não encontrado")
            
        qtd_decimal = Decimal(str(quantidade))
        
        if item.quantidade_atual < qtd_decimal:
            raise ValueError(f"Estoque insuficiente. Disponível: {item.quantidade_atual} {item.unidade_medida}")
            
        mov = MovimentacaoEstoque(
            os_id=os_id,
            estoque_id=estoque_id,
            usuario_id=usuario_id,
            tipo_movimentacao='consumo',
            quantidade=qtd_decimal,
            observacao=f"Consumo na OS #{os_id}"
        )
        
        db.session.add(mov)
        db.session.commit()
        # Trigger automático atualizará o saldo
        
        return item.quantidade_atual - qtd_decimal # Retorna saldo previsto