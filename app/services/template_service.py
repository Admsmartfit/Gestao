class TemplateService:
    """
    Renders message templates with provided variables.
    """
    
    TEMPLATES = {
        'novo_chamado': """
🔧 *Novo Chamado GMM*

*Número:* {numero_chamado}
*Título:* {titulo}
*Prazo:* {prazo}

{descricao}

Para aceitar: {link_aceite}
Ou responda: SIM
        """,
        
        'lembrete': """
⏰ *Lembrete GMM*

*Chamado:* {numero_chamado}
*Prazo:* {prazo} (em 48h)

Tudo certo? 👍
        """,
        
        'cobranca': """
🚨 *Prazo Vencido*

*Chamado:* {numero_chamado}
Precisamos de atualização urgente!

Qual a previsão?
        """
    }
    
    @staticmethod
    def render(template_name: str, **kwargs) -> str:
        """
        Renders a template by name using the provided keyword arguments.
        Returns the rendered string or the template name if not found.
        """
        template_text = TemplateService.TEMPLATES.get(template_name)
        if not template_text:
            return f"Template {template_name} not found."
            
        try:
            return template_text.strip().format(**kwargs)
        except KeyError as e:
            return f"Error: Missing variable {str(e)} for template {template_name}"
        except Exception as e:
            return f"Error rendering template: {str(e)}"
