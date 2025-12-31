from flask import Blueprint, jsonify, request, render_template, abort
from flask_login import login_required, current_user
from app.extensions import db
from app.models.whatsapp_models import RegrasAutomacao

bp = Blueprint('admin_whatsapp', __name__)

@bp.route('/admin/whatsapp/regras', methods=['GET'])
@login_required
def listar_regras():
    """Tela de configuração de regras"""
    if current_user.tipo != 'admin':
        abort(403)
    
    regras = RegrasAutomacao.query.order_by(
        RegrasAutomacao.prioridade.desc()
    ).all()
    
    return render_template('admin/whatsapp_regras.html', regras=regras)

@bp.route('/admin/whatsapp/regras', methods=['POST'])
@login_required
def criar_regra():
    """Cria nova regra de automação"""
    if current_user.tipo != 'admin':
        return jsonify({'error': 'Unauthorized'}), 403
    
    data = request.json
    
    # Validações
    if not data.get('palavra_chave'):
        return jsonify({'error': 'Palavra-chave obrigatória'}), 400
    
    regra = RegrasAutomacao(
        palavra_chave=data['palavra_chave'],
        tipo_correspondencia=data.get('tipo_correspondencia', 'contem'),
        acao=data['acao'],
        resposta_texto=data.get('resposta_texto'),
        encaminhar_para_perfil=data.get('encaminhar_para_perfil'),
        funcao_sistema=data.get('funcao_sistema'),
        prioridade=data.get('prioridade', 0)
    )
    
    db.session.add(regra)
    db.session.commit()
    
    return jsonify({
        'success': True,
        'id': regra.id
    })

# --- Dashboard & Métricas ---

from datetime import datetime, timedelta
from app.models.whatsapp_models import ConfiguracaoWhatsApp
from app.models.terceirizados_models import HistoricoNotificacao
from app.services.circuit_breaker import CircuitBreaker
from app.services.rate_limiter import RateLimiter

@bp.route('/admin/whatsapp/dashboard')
@login_required
def dashboard():
    """Painel de saúde da integração"""
    if current_user.tipo != 'admin':
        abort(403)
    
    # Buscar configuração
    config = ConfiguracaoWhatsApp.query.filter_by(ativo=True).first()
    # Create dummy config if not exists to avoid crash
    if not config:
        config = ConfiguracaoWhatsApp(ativo=True) # transient

    # Métricas últimas 24h
    desde = datetime.utcnow() - timedelta(hours=24)
    
    total_enviadas = HistoricoNotificacao.query.filter(
        HistoricoNotificacao.direcao == 'outbound',
        HistoricoNotificacao.criado_em >= desde
    ).count()
    
    total_entregues = HistoricoNotificacao.query.filter(
        HistoricoNotificacao.direcao == 'outbound',
        HistoricoNotificacao.status_envio == 'enviado', # Using 'enviado' as proxy for delivered in this context
        HistoricoNotificacao.criado_em >= desde
    ).count()
    
    taxa_entrega = (total_entregues / total_enviadas * 100) if total_enviadas > 0 else 0
    
    # Estado do Circuit Breaker
    cb_state = CircuitBreaker.get_state()
    
    # Rate Limit
    pode_enviar, restantes = RateLimiter.check_limit()
    
    # Mensagens pendentes
    pendentes = HistoricoNotificacao.query.filter_by(
        status_envio='pendente'
    ).count()
    
    return render_template('admin/whatsapp_dashboard.html',
        config=config,
        total_enviadas=total_enviadas,
        total_entregues=total_entregues,
        taxa_entrega=round(taxa_entrega, 1),
        cb_state=cb_state,
        rate_limit_disponivel=restantes,
        mensagens_pendentes=pendentes
    )

@bp.route('/api/whatsapp/metricas-grafico')
@login_required
def metricas_grafico():
    """Dados para gráfico de envios"""
    periodo = request.args.get('periodo', 'dia')
    
    if periodo == 'dia':
        inicio = datetime.utcnow() - timedelta(days=1)
        intervalo = timedelta(hours=1)
        formato = '%H:00'
    else:
        inicio = datetime.utcnow() - timedelta(days=7)
        intervalo = timedelta(days=1)
        formato = '%d/%m'
    
    # Agregar por período (Simplified loop)
    labels = []
    enviadas = []
    entregues = []
    
    timestamp = inicio
    while timestamp < datetime.utcnow():
        labels.append(timestamp.strftime(formato))
        fim_periodo = timestamp + intervalo
        
        total_env = HistoricoNotificacao.query.filter(
            HistoricoNotificacao.criado_em >= timestamp,
            HistoricoNotificacao.criado_em < fim_periodo,
            HistoricoNotificacao.direcao == 'outbound'
        ).count()
        
        total_ent = HistoricoNotificacao.query.filter(
            HistoricoNotificacao.enviado_em >= timestamp,
            HistoricoNotificacao.enviado_em < fim_periodo,
            HistoricoNotificacao.status_envio == 'enviado'
        ).count()
        
        enviadas.append(total_env)
        entregues.append(total_ent)
        timestamp = fim_periodo
    
    return jsonify({
        'labels': labels,
        'enviadas': enviadas,
        'entregues': entregues
    })

@bp.route('/api/whatsapp/historico-recente')
@login_required
def historico_recente():
    """Últimas 20 notificações"""
    notifs = HistoricoNotificacao.query.order_by(
        HistoricoNotificacao.criado_em.desc()
    ).limit(20).all()
    
    return jsonify([{
        'hora': n.criado_em.strftime('%H:%M'),
        'direcao': n.direcao,
        'destinatario': (n.destinatario or '')[-4:],
        'tipo': n.tipo,
        'status': n.status_envio
    } for n in notifs])

# --- Configuração & Testes ---

@bp.route('/admin/whatsapp/config', methods=['GET', 'POST'])
@login_required
def configuracao():
    """Tela de configurações do WhatsApp"""
    if current_user.tipo != 'admin':
        abort(403)
        
    config = ConfiguracaoWhatsApp.query.filter_by(ativo=True).first()
    if not config:
        config = ConfiguracaoWhatsApp(ativo=True)
        db.session.add(config)
        db.session.commit()
    
    if request.method == 'POST':
        # Atualizar configurações
        from cryptography.fernet import Fernet
        
        # Rate Limit & Circuit Breaker
        config.rate_limit = int(request.form.get('rate_limit', 60))
        config.circuit_breaker_threshold = int(request.form.get('cb_threshold', 5))
        
        # API Key (Criptografada)
        api_key = request.form.get('api_key')
        if api_key and api_key.strip():
            fernet_key = current_app.config.get('FERNET_KEY')
            if fernet_key:
                f = Fernet(fernet_key)
                config.api_key_encrypted = f.encrypt(api_key.encode())
            else:
                # Fallback inseguro se chave não configurada (não ideal, mas evita crash)
                current_app.config['MEGA_API_KEY'] = api_key 
        
        db.session.commit()
        return render_template('admin/whatsapp_config.html', config=config, success=True)
        
    return render_template('admin/whatsapp_config.html', config=config)

@bp.route('/api/whatsapp/teste', methods=['POST'])
@login_required
def enviar_teste():
    """Envia mensagem de teste manual"""
    if current_user.tipo != 'admin':
        return jsonify({'error': 'Unauthorized'}), 403
        
    data = request.json
    telefone = data.get('telefone')
    mensagem = data.get('mensagem')
    
    if not telefone or not mensagem:
        return jsonify({'error': 'Dados incompletos'}), 400
        
    from app.services.whatsapp_service import WhatsAppService
    
    # Forçar prioridade máxima para teste
    sucesso, resposta = WhatsAppService.enviar_mensagem(
        telefone=telefone,
        texto=mensagem,
        prioridade=2 
    )
    
    # Registrar no histórico como 'teste_manual'
    if sucesso:
        hs = HistoricoNotificacao(
            tipo='teste_manual',
            destinatario=telefone,
            mensagem=mensagem,
            status_envio='enviado',
            direcao='outbound',
            enviado_em=datetime.utcnow()
        )
        db.session.add(hs)
        db.session.commit()
        
    return jsonify({
        'success': sucesso,
        'resposta': resposta
    })
