from decimal import Decimal
from app.extensions import db
from app.models.estoque_models import Estoque, MovimentacaoEstoque, OrdemServico, EstoqueSaldo
from app.models.models import Usuario

class EstoqueService:
    @staticmethod
    def consumir_item(os_id, estoque_id, quantidade, usuario_id):
        """
        RN-004: Consumo com validação de saldo LOCAL e alerta.
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

        # [NOVO] Validação de Saldo LOCAL (Unidade da OS)
        unidade_id = os_obj.unidade_id
        saldo_local = EstoqueSaldo.query.filter_by(estoque_id=estoque_id, unidade_id=unidade_id).first()

        qtd_disponivel_local = saldo_local.quantidade if saldo_local else Decimal(0)

        # [RN004] Bloqueio por saldo insuficiente LOCAL
        if qtd_disponivel_local < qtd_decimal:
            msg = f"Estoque insuficiente na unidade {os_obj.unidade.nome}. Disponível: {qtd_disponivel_local} {item.unidade_medida}"
            # Opcional: Avisar se há em outras unidades
            total_global = item.quantidade_atual
            if total_global >= qtd_decimal:
                msg += f" (Há saldo global: {total_global}, solicite transferência)."
            raise ValueError(msg)
            
        # Atualizar Saldo Local
        saldo_local.quantidade -= qtd_decimal
        
        # Registro da Movimentação
        mov = MovimentacaoEstoque(
            os_id=os_id,
            estoque_id=estoque_id,
            usuario_id=usuario_id,
            unidade_id=unidade_id, # [NOVO]
            tipo_movimentacao='consumo',
            quantidade=qtd_decimal,
            observacao=f"Consumo na OS #{os_obj.numero_os}"
        )
        
        db.session.add(mov)
        # O saldo GLOBAL é atualizado via Trigger (event listener no model MovimentacaoEstoque)
        # O saldo LOCAL nós atualizamos manualmente acima
        
        db.session.commit()
        
        # [RN004] Verificação de Alerta de Estoque Mínimo (Pós-consumo)
        alerta = False
        if item.quantidade_atual <= item.quantidade_minima:
            alerta = True
        
        return item.quantidade_atual, alerta

    @staticmethod
    def repor_estoque(estoque_id, quantidade, usuario_id, motivo=None, unidade_id=None):
        """
        Registra entrada de material no estoque (Reabastecimento) em uma unidade específica.
        """
        item = Estoque.query.get(estoque_id)
        if not item:
            raise ValueError("Item não encontrado")
            
        # Se não informou unidade, tenta pegar a do usuário logado (se técnico/gerente) ou erro
        if not unidade_id:
            usuario = Usuario.query.get(usuario_id)
            if usuario.unidade_padrao_id:
                unidade_id = usuario.unidade_padrao_id
            else:
                 # Se for admin global e não escolheu, precisa escolher.
                 # Por fallback, vamos assumir a primeira unidade ativa ou erro.
                 # Aqui vou lançar erro para forçar envio da unidade.
                 raise ValueError("É necessário informar a unidade para entrada de estoque.")

        qtd_decimal = Decimal(str(quantidade))
        if qtd_decimal <= 0:
            raise ValueError("A quantidade deve ser maior que zero.")

        # Atualizar/Criar Saldo Local
        saldo_local = EstoqueSaldo.query.filter_by(estoque_id=estoque_id, unidade_id=unidade_id).first()
        if not saldo_local:
            saldo_local = EstoqueSaldo(estoque_id=estoque_id, unidade_id=unidade_id, quantidade=0)
            db.session.add(saldo_local)
        
        saldo_local.quantidade += qtd_decimal

        mov = MovimentacaoEstoque(
            estoque_id=estoque_id,
            usuario_id=usuario_id,
            unidade_id=unidade_id, # [NOVO]
            tipo_movimentacao='entrada',
            quantidade=qtd_decimal,
            observacao=motivo or "Entrada manual de estoque"
        )

        db.session.add(mov)
        db.session.commit()
        
        return item.quantidade_atual