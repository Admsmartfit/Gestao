from flask import Blueprint, render_template, jsonify, request, send_file
from flask_login import login_required, current_user
from app.services.analytics_service import AnalyticsService
from app.models.models import Unidade, Usuario
from datetime import datetime, timedelta
import csv
import io

bp = Blueprint('analytics', __name__, url_prefix='/analytics')

@bp.route('/dashboard')
@login_required
def dashboard():
    if current_user.tipo not in ['admin', 'gerente', 'comprador']:
        return render_template('errors/403.html'), 403
    
    unidades = Unidade.query.filter_by(ativa=True).all()
    return render_template('analytics/dashboard.html', unidades=unidades)

@bp.route('/desempenho-tecnico')
@login_required
def desempenho_tecnico():
    if current_user.tipo not in ['admin', 'gerente', 'comprador']:
        return render_template('errors/403.html'), 403
    
    unidades = Unidade.query.filter_by(ativa=True).all()
    # Passamos a data de início padrão calculada no backend
    data_inicio = (datetime.utcnow() - timedelta(days=30)).strftime('%Y-%m-%d')
    return render_template('analytics/performance_tecnica.html', 
                         unidades=unidades, 
                         data_inicio_padrao=data_inicio)

@bp.route('/api/kpi/geral')
@login_required
def api_kpi_geral():
    unidade_id = request.args.get('unidade_id', type=int)
    days = request.args.get('days', default=30, type=int)
    
    if current_user.tipo == 'gerente' and not unidade_id:
        unidade_id = current_user.unidade_padrao_id
        
    kpis = AnalyticsService.get_kpi_geral(unidade_id, days)
    stock = AnalyticsService.get_stock_metrics(unidade_id)
    kpis.update(stock)
    
    return jsonify(kpis)

@bp.route('/api/charts/custos')
@login_required
def api_charts_custos():
    unidade_id = request.args.get('unidade_id', type=int)
    days = request.args.get('days', default=30, type=int)
    
    data = AnalyticsService.get_cost_evolution(unidade_id, days)
    return jsonify(data)

@bp.route('/api/tecnicos/performance')
@login_required
def api_tecnicos_performance():
    unidade_id = request.args.get('unidade_id', type=int)
    start_str = request.args.get('start_date')
    end_str = request.args.get('end_date')
    
    if start_str and end_str:
        start_date = datetime.strptime(start_str, '%Y-%m-%d')
        end_date = datetime.strptime(end_str, '%Y-%m-%d') + timedelta(days=1)
    else:
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=30)
        
    data = AnalyticsService.get_performance_tecnicos(start_date, end_date, unidade_id)
    return jsonify(data)

@bp.route('/api/tecnicos/<int:usuario_id>/logs-diarios')
@login_required
def api_tecnico_logs_diarios(usuario_id):
    start_str = request.args.get('start_date')
    end_str = request.args.get('end_date')
    
    if start_str and end_str:
        start_date = datetime.strptime(start_str, '%Y-%m-%d')
        end_date = datetime.strptime(end_str, '%Y-%m-%d') + timedelta(days=1)
    else:
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=30)
        
    data = AnalyticsService.get_daily_logs(usuario_id, start_date, end_date)
    return jsonify(data)

@bp.route('/api/export/csv')
@login_required
def export_csv():
    # Similar ao performance técnicos mas retorna arquivo
    unidade_id = request.args.get('unidade_id', type=int)
    start_str = request.args.get('start_date')
    end_str = request.args.get('end_date')
    
    if start_str and end_str:
        start_date = datetime.strptime(start_str, '%Y-%m-%d')
        end_date = datetime.strptime(end_str, '%Y-%m-%d')
    else:
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=30)
        
    data = AnalyticsService.get_performance_tecnicos(start_date, end_date, unidade_id)
    
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Técnico', 'Horas Ponto', 'Horas OS', 'Ociosidade %', 'Custo Peças', 'OS Concluídas'])
    
    for row in data:
        writer.writerow([
            row['tecnico_nome'],
            row['horas_ponto'],
            row['horas_os'],
            row['ociosidade_percentual'],
            row['custo_pecas'],
            row['os_concluidas']
        ])
    
    output.seek(0)
    return send_file(
        io.BytesIO(output.getvalue().encode('utf-8-sig')),
        mimetype='text/csv',
        as_attachment=True,
        download_name=f'performance_tecnica_{start_date.strftime("%Y%m%d")}.csv'
    )
