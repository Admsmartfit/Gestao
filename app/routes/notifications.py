from flask import Blueprint, jsonify
from flask_login import login_required, current_user
from app.models.estoque_models import OrdemServico, Estoque
from datetime import datetime, timedelta
from app.extensions import db

bp = Blueprint('notifications', __name__, url_prefix='/api')

@bp.route('/notifications', methods=['GET'])
@login_required
def get_notifications():
    alerts = []
    
    # 1. OSs Vencidas ou Vencendo Hoje/Amanhã
    # Consideramos "Urgente" se vencer em menos de 24h ou já venceu
    agora = datetime.utcnow()
    limite_urgencia = agora + timedelta(hours=24)
    
    oss_pendentes = OrdemServico.query.filter(
        OrdemServico.status != 'concluida',
        OrdemServico.prazo_conclusao <= limite_urgencia
    ).all()
    
    for os in oss_pendentes:
        delta = os.prazo_conclusao - agora
        if delta.total_seconds() < 0:
            msg = f"OS #{os.numero_os} está ATRASADA!"
            tipo = "urgent"
        else:
            horas = int(delta.total_seconds() // 3600)
            msg = f"OS #{os.numero_os} vence em {horas}h"
            tipo = "warning"
            
        alerts.append({
            "type": tipo,
            "message": msg,
            "url": f"/os/{os.id}/detalhes",
            "timestamp": os.prazo_conclusao.isoformat()
        })

    # 2. Estoque Baixo
    # Itens onde qtd_atual <= qtd_minima
    itens_baixo = Estoque.query.filter(Estoque.quantidade_atual <= Estoque.quantidade_minima).limit(10).all()
    
    for item in itens_baixo:
        alerts.append({
            "type": "warning",
            "message": f"Estoque baixo: {item.nome} ({item.quantidade_atual} {item.unidade_medida})",
            "url": "/os/painel-estoque",
            "timestamp": datetime.utcnow().isoformat()
        })

    return jsonify({
        "count": len(alerts),
        "alerts": alerts
    })
