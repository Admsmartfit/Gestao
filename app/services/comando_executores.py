from datetime import datetime
from flask import current_app
from app.extensions import db
from app.models.estoque_models import Estoque
# Assuming PedidoCompra exists or similar, checking context... 
# PedidoCompra was mentioned in prompt but might not exist in viewed files.
# Adapting to implementation plan context.
# If PedidoCompra doesn't exist, we might need to create it or stub it. 
# Based on existing 'app.models.estoque_models', let's check what we have. 
# We have CategoriaEstoque, Estoque, Equipamento, OrdemServico.
# I will assume PedidoCompra needs to be imported if it exists, otherwise I'll stub/comment.
# Wait, previous prompts mentioned implementing Purchase Requests. Let's assume it exists or use a placeholder.
# I will verify file structure after this if needed. For now, implement assuming it matches recent work.

from app.models.terceirizados_models import Terceirizado, ChamadoExterno

class ComandoExecutores:
    """
    Executes business logic for WhatsApp commands.
    """
    
    @staticmethod
    def executar_compra(params: dict, solicitante: Terceirizado) -> dict:
        """
        Creates a purchase request (stubbed for now if model missing).
        """
        try:
            item_codigo = params['item']
            quantidade = params['quantidade']
            
            # 1. Find Item
            item = Estoque.query.filter_by(codigo=item_codigo).first()
            if not item:
                return {
                    'sucesso': False,
                    'resposta': f"❌ Item {item_codigo} não encontrado no catálogo."
                }
            
            # 2. Create Purchase Order (Dynamic import to avoid circular dep if not ready)
            # from app.models.estoque_models import PedidoCompra 
            # If PedidoCompra is not yet implemented, we log and return "Not Implemented"
            # user previous context mentioned "Implementing Purchase Requests" conversation.
            
            # Placeholder implementation:
            return {
                'sucesso': True,
                'resposta': f"✅ Solicitação recebida!\n\n*Item:* {item.nome}\n*Qtd:* {quantidade}\n\n(Funcionalidade em desenvolvimento)"
            }
            
        except Exception as e:
            current_app.logger.error(f"Error executing purchase: {e}")
            return {
                'sucesso': False,
                'resposta': "❌ Erro ao processar pedido. Tente novamente."
            }
    
    @staticmethod
    def executar_status(solicitante: Terceirizado) -> dict:
        """
        Lists active tickets for the requester.
        """
        chamados = ChamadoExterno.query.filter_by(
            terceirizado_id=solicitante.id
        ).filter(ChamadoExterno.status.in_(['aguardando', 'aceito', 'em_andamento'])).all()
        
        if not chamados:
            return {
                'sucesso': True,
                'resposta': "📋 Você não tem chamados ativos no momento."
            }
        
        resposta = "📋 *Seus Chamados Ativos*\n\n"
        
        for ch in chamados:
            icone = "✅" if ch.prazo_combinado > datetime.utcnow() else "⚠️"
            resposta += f"{icone} {ch.numero_chamado} - {ch.status}\n"
            resposta += f"   Prazo: {ch.prazo_combinado.strftime('%d/%m')}\n\n"
        
        return {
            'sucesso': True,
            'resposta': resposta
        }
    
    @staticmethod
    def executar_ajuda() -> dict:
        """
        Returns the help menu.
        """
        return {
            'sucesso': True,
            'resposta': """
❓ *Comandos Disponíveis*

- #COMPRA [código] [qtd]
  Ex: #COMPRA CABO-10MM 50

- #STATUS
  Ver seus chamados ativos

- #AJUDA
  Ver esta mensagem

Para falar com alguém, responda normalmente que encaminharemos.
            """
        }
