from flask import Blueprint, render_template, request, abort
from flask_login import login_required
from app.models.estoque_models import Equipamento, OrdemServico, MovimentacaoEstoque
from sqlalchemy import desc

bp = Blueprint('equipamentos', __name__, url_prefix='/equipamentos')

@bp.route('/')
@login_required
def listar():
    """Lista todos os equipamentos com busca simples"""
    q = request.args.get('q', '')
    query = Equipamento.query
    if q:
        query = query.filter(Equipamento.nome.ilike(f'%{q}%'))
    
    equipamentos = query.order_by(Equipamento.nome).all()
    return render_template('equipamentos_lista.html', equipamentos=equipamentos)

@bp.route('/<int:id>')
@login_required
def detalhes(id):
    """Dossiê completo do equipamento (RF-004)"""
    equipamento = Equipamento.query.get_or_404(id)
    
    # 1. Histórico de Manutenções
    historico_os = OrdemServico.query.filter_by(equipamento_id=id)\
        .order_by(OrdemServico.data_abertura.desc()).all()
    
    # 2. Peças Trocadas (Via Movimentações ligadas às OSs do equipamento)
    pecas_trocadas = MovimentacaoEstoque.query.join(OrdemServico)\
        .filter(OrdemServico.equipamento_id == id, MovimentacaoEstoque.tipo_movimentacao == 'consumo')\
        .order_by(MovimentacaoEstoque.data_movimentacao.desc()).all()
    
    # 3. KPIs Locais
    total_custo_pecas = sum([m.quantidade * (m.estoque.valor_unitario or 0) for m in pecas_trocadas])
    qtd_os = len(historico_os)
    
    # MTBF Simplificado (Tempo total / Qtd falhas corretivas)
    corretivas = [os for os in historico_os if os.tipo_manutencao == 'corretiva']
    mtbf = "N/A"
    if len(corretivas) > 1:
        # Pega a data da primeira e da última OS corretiva
        delta = corretivas[0].data_abertura - corretivas[-1].data_abertura
        dias = delta.days
        # Evita divisão por zero
        divisor = len(corretivas) - 1 if len(corretivas) > 1 else 1
        media_dias = dias // divisor
        mtbf = f"{media_dias} dias"

    return render_template('equipamento_detalhe.html', 
                         eq=equipamento,
                         historico_os=historico_os,
                         pecas=pecas_trocadas,
                         kpis={
                             'custo_total': total_custo_pecas,
                             'qtd_os': qtd_os,
                             'mtbf': mtbf
                         })