import re

class ComandoParser:
    """
    Parses structured commands from text messages.
    Supports:
    - #COMPRA [CODE] [QUANTITY]
    - #STATUS
    - #AJUDA
    """
    
    COMANDOS = {
        '#COMPRA': r'#COMPRA\s+([A-Z0-9\-]+)\s+(\d+\.?\d*)',
        '#STATUS': r'#STATUS',
        '#AJUDA': r'#AJUDA'
    }
    
    @staticmethod
    def parse(texto: str) -> dict:
        """
        Parses the text and returns a dictionary with the command and parameters.
        Returns None if no command is found.
        Example return:
        {
            'comando': 'COMPRA',
            'params': {'item': 'CABO-10MM', 'quantidade': 50.0},
            'texto_original': '#COMPRA ...'
        }
        """
        if not texto:
            return None
            
        texto = texto.strip().upper()
        
        for cmd, pattern in ComandoParser.COMANDOS.items():
            match = re.match(pattern, texto)
            if match:
                resultado = {
                    'comando': cmd.replace('#', ''),
                    'texto_original': texto
                }
                
                if cmd == '#COMPRA':
                    resultado['params'] = {
                        'item': match.group(1),
                        'quantidade': float(match.group(2))
                    }
                else:
                    resultado['params'] = {}
                
                return resultado
        
        return None
