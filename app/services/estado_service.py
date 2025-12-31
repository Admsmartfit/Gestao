import json
from datetime import datetime, timedelta
from app.extensions import db
from app.models.whatsapp_models import EstadoConversa
from app.models.terceirizados_models import ChamadoExterno

class EstadoService:
    """
    Manages conversation lifecycle and context.
    """
    
    @staticmethod
    def criar_estado(telefone: str, chamado_id: int, estado_inicial: str):
        """Creates a new conversation state."""
        # Clean existing state
        EstadoConversa.query.filter_by(telefone=telefone).delete()
        
        estado = EstadoConversa(
            telefone=telefone,
            chamado_id=chamado_id,
            estado_atual=estado_inicial,
            contexto=json.dumps({}), # Empty context initially
            # expira_em handled by cleanup task logic (updated_at)
        )
        db.session.add(estado)
        db.session.commit()
        return estado
    
    @staticmethod
    def atualizar_estado(estado: EstadoConversa, novo_estado: str, contexto_update: dict = None):
        """Updates the state and context."""
        estado.estado_atual = novo_estado
        estado.updated_at = datetime.utcnow()
        
        if contexto_update:
            ctx = estado.get_contexto()
            ctx.update(contexto_update)
            estado.set_contexto(ctx)
        
        db.session.commit()
    
    @staticmethod
    def processar_resposta_com_estado(estado: EstadoConversa, texto: str) -> dict:
        """
        Process user response based on current state.
        """
        if estado.estado_atual == 'aguardando_aceite':
            clean_text = texto.strip().upper()
            
            if clean_text in ['SIM', 'ACEITO', 'OK', 'CONFIRMO']:
                # Accept Ticket
                chamado = ChamadoExterno.query.get(estado.chamado_id)
                if chamado:
                    chamado.status = 'aceito'
                    chamado.data_inicio = datetime.utcnow()
                    
                    EstadoService.atualizar_estado(estado, 'aguardando_conclusao')
                    return {
                        'sucesso': True,
                        'resposta': f"✅ Chamado {chamado.numero_chamado} aceito! Contamos com você."
                    }
            
            elif clean_text in ['NAO', 'RECUSO', 'NÃO', 'CANCELAR']:
                # Reject Ticket
                chamado = ChamadoExterno.query.get(estado.chamado_id)
                if chamado:
                    chamado.status = 'recusado' # Or back to 'aberto' depending on logic
                
                # Close conversation
                db.session.delete(estado)
                db.session.commit()
                
                return {
                    'sucesso': True,
                    'resposta': "Chamado recusado. Obrigado pelo retorno."
                }
        
        return {
            'sucesso': False,
            'resposta': "Não entendi sua resposta. Responda SIM ou NÃO, ou digite #AJUDA."
        }
