import re
from datetime import datetime
from app.models.terceirizados_models import Terceirizado
from app.models.whatsapp_models import EstadoConversa, RegrasAutomacao
from app.services.comando_parser import ComandoParser
from app.services.comando_executores import ComandoExecutores
from app.services.estado_service import EstadoService

class RoteamentoService:
    """
    Decides how to process an incoming message.
    Flow: User Check -> Active State -> Command -> Auto Rule -> Fallback
    """
    
    @staticmethod
    def processar(remetente: str, texto: str) -> dict:
        """
        Main routing logic.
        Returns a dict with 'acao', 'resposta', etc.
        """
        
        # 1. Identify Sender
        terceirizado = Terceirizado.query.filter_by(telefone=remetente).first()
        if not terceirizado:
            # Could implement Stranger flow here
            return {
                'acao': 'ignorar',
                'motivo': 'Remetente não cadastrado'
            }
        
        # 2. Check Active Conversation State
        # Assuming activity window of 24h managed by 'updated_at' check
        # We find latest state
        estado = EstadoConversa.query.filter_by(telefone=remetente).order_by(EstadoConversa.updated_at.desc()).first()
        
        # Determine if state is still valid (e.g., < 24h)
        if estado and (datetime.utcnow() - estado.updated_at).total_seconds() < 86400: # 24h
            resultado_estado = EstadoService.processar_resposta_com_estado(estado, texto)
            if resultado_estado['sucesso']:
                return {'acao': 'responder', 'resposta': resultado_estado['resposta']}
            # If not processed successfully by state (e.g. invalid input), fall through or return help
            # For now, let's allow fallthrough to Commands if Input was not 'SIM'/'NAO'
        
        # 3. Parse Command
        comando = ComandoParser.parse(texto)
        if comando:
            cmd_key = comando['comando']
            if cmd_key == 'COMPRA':
                res = ComandoExecutores.executar_compra(comando['params'], terceirizado)
            elif cmd_key == 'STATUS':
                res = ComandoExecutores.executar_status(terceirizado)
            elif cmd_key == 'AJUDA':
                res = ComandoExecutores.executar_ajuda()
            else:
                res = {'sucesso': False, 'resposta': 'Comando desconhecido.'}
            
            return {'acao': 'responder', 'resposta': res['resposta']}
        
        # 4. Automation Rules
        regra = RegrasAutomacao.query.filter(
            RegrasAutomacao.ativo == True
        ).order_by(RegrasAutomacao.prioridade.desc()).all()
        
        for r in regra:
            if RoteamentoService._match_regra(r, texto):
                return {
                    'acao': r.acao, # responder, executar_funcao, encaminhar
                    'resposta': r.resposta_texto,
                    'encaminhar_para': r.encaminhar_para_perfil, # if acao=encaminhar
                    'funcao': r.funcao_sistema # if acao=executar_funcao
                }
        
        # 5. Fallback (Forward to Manager)
        return {
            'acao': 'encaminhar',
            'destino': 'gerente',
            'mensagem': f"Mensagem de {terceirizado.nome}: {texto}"
        }
    
    @staticmethod
    def _match_regra(regra: RegrasAutomacao, texto: str) -> bool:
        """Checks if text matches the rule pattern."""
        if not regra.palavra_chave:
            return False
            
        if regra.tipo_correspondencia == 'exata':
            return texto.strip().upper() == regra.palavra_chave.upper()
        
        elif regra.tipo_correspondencia == 'contem':
            return regra.palavra_chave.upper() in texto.upper()
        
        elif regra.tipo_correspondencia == 'regex':
            try:
                return re.search(regra.palavra_chave, texto, re.IGNORECASE) is not None
            except:
                return False
        
        return False
