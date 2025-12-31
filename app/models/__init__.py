# Import all models here so Alembic can discover them
from app.models.models import Usuario, Unidade, RegistroPonto
from app.models.estoque_models import CategoriaEstoque, Estoque, Equipamento, OrdemServico
from app.models.terceirizados_models import Terceirizado, ChamadoExterno, HistoricoNotificacao
from app.models.whatsapp_models import RegrasAutomacao, TokenAcesso, EstadoConversa, ConfiguracaoWhatsApp, MetricasWhatsApp

__all__ = [
    'Usuario', 'Unidade', 'RegistroPonto',
    'CategoriaEstoque', 'Estoque', 'Equipamento', 'OrdemServico',
    'Terceirizado', 'ChamadoExterno', 'HistoricoNotificacao',
    'RegrasAutomacao', 'TokenAcesso', 'EstadoConversa', 'ConfiguracaoWhatsApp', 'MetricasWhatsApp'
]
