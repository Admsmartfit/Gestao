from datetime import datetime, timedelta
from sqlalchemy import func, and_, or_
from decimal import Decimal
from app.extensions import db
from app.models.models import Usuario, Unidade, RegistroPonto
from app.models.estoque_models import OrdemServico, MovimentacaoEstoque, Estoque, EstoqueSaldo
from app.models.terceirizados_models import ChamadoExterno

class AnalyticsService:
    @staticmethod
    def get_kpi_geral(unidade_id=None, days=30):
        start_date = datetime.utcnow() - timedelta(days=days)
        
        # Filtros base
        os_filter = [OrdemServico.data_abertura >= start_date]
        mov_filter = [MovimentacaoEstoque.data_movimentacao >= start_date, MovimentacaoEstoque.tipo_movimentacao == 'consumo']
        chamado_filter = [ChamadoExterno.criado_em >= start_date]
        
        if unidade_id:
            os_filter.append(OrdemServico.unidade_id == unidade_id)
            mov_filter.append(MovimentacaoEstoque.unidade_id == unidade_id)
            # Chamados externos podem estar vinculados a uma OS que tem unidade
            chamado_filter.append(OrdemServico.unidade_id == unidade_id)

        # 1. MTTR (Mean Time To Repair)
        # Média de (data_conclusao - data_abertura) para OS concluídas
        mttr_query = db.session.query(
            func.avg(OrdemServico.data_conclusao - OrdemServico.data_abertura)
        ).filter(
            OrdemServico.status == 'concluida',
            OrdemServico.data_conclusao.isnot(None),
            *os_filter
        ).scalar()
        
        mttr_hours = 0
        if mttr_query:
            mttr_hours = mttr_query.total_seconds() / 3600

        # 2. Custos (Peças + Serviços)
        # Peças: sum(mov.quantidade * estoque.valor_unitario)
        custo_pecas = db.session.query(
            func.sum(MovimentacaoEstoque.quantidade * Estoque.valor_unitario)
        ).join(Estoque).filter(*mov_filter).scalar() or Decimal('0.00')

        # Serviços: sum(chamado.valor_final)
        custo_servicos = db.session.query(
            func.sum(ChamadoExterno.valor_final)
        ).join(OrdemServico, ChamadoExterno.os_id == OrdemServico.id).filter(*chamado_filter).scalar() or Decimal('0.00')

        total_custo = custo_pecas + custo_servicos

        # 3. Backlog e Eficiência
        total_os = OrdemServico.query.filter(*os_filter).count()
        concluidas = OrdemServico.query.filter(OrdemServico.status == 'concluida', *os_filter).count()
        taxa_conclusao = (concluidas / total_os * 100) if total_os > 0 else 0
        
        # OS abertas há mais de 7 dias
        sete_dias_atras = datetime.utcnow() - timedelta(days=7)
        backlog_critico = OrdemServico.query.filter(
            OrdemServico.status == 'aberta',
            OrdemServico.data_abertura <= sete_dias_atras,
            *([OrdemServico.unidade_id == unidade_id] if unidade_id else [])
        ).count()

        return {
            'mttr': round(mttr_hours, 1),
            'custo_total': float(total_custo),
            'custo_pecas': float(custo_pecas),
            'custo_servicos': float(custo_servicos),
            'total_os': total_os,
            'taxa_conclusao': round(taxa_conclusao, 1),
            'backlog_critico': backlog_critico
        }

    @staticmethod
    def get_performance_tecnicos(start_date, end_date, unidade_id=None):
        # Query base para usuários que são técnicos
        tecnicos_query = Usuario.query.filter(Usuario.tipo == 'tecnico')
        if unidade_id:
            tecnicos_query = tecnicos_query.filter(Usuario.unidade_padrao_id == unidade_id)
        
        tecnicos = tecnicos_query.all()
        result = []

        for t in tecnicos:
            # 1. Horas totais de Ponto (Check-in até Check-out)
            # Para SQLite, precisamos usar julianday. Para Postgres, a subtração direta funciona.
            # Verificamos o dialeto se necessário, mas aqui usaremos uma abordagem segura.
            registros = RegistroPonto.query.filter(
                RegistroPonto.usuario_id == t.id,
                RegistroPonto.data_hora_entrada >= start_date,
                RegistroPonto.data_hora_entrada <= end_date,
                RegistroPonto.data_hora_saida.isnot(None)
            ).all()
            
            total_horas_ponto = 0
            for r in registros:
                diff = r.data_hora_saida - r.data_hora_entrada
                total_horas_ponto += diff.total_seconds() / 3600

            # 2. Horas totais em OS
            ordens = OrdemServico.query.filter(
                OrdemServico.tecnico_id == t.id,
                OrdemServico.status == 'concluida',
                OrdemServico.data_conclusao >= start_date,
                OrdemServico.data_conclusao <= end_date
            ).all()

            total_horas_os = 0
            for o in ordens:
                if o.data_conclusao and o.data_abertura:
                    diff = o.data_conclusao - o.data_abertura
                    total_horas_os += diff.total_seconds() / 3600

            # 3. Consumo de Peças por técnico
            custo_pecas = db.session.query(
                func.sum(MovimentacaoEstoque.quantidade * Estoque.valor_unitario)
            ).join(Estoque).filter(
                MovimentacaoEstoque.usuario_id == t.id,
                MovimentacaoEstoque.tipo_movimentacao == 'consumo',
                MovimentacaoEstoque.data_movimentacao >= start_date,
                MovimentacaoEstoque.data_movimentacao <= end_date
            ).scalar() or 0

            os_concluidas = OrdemServico.query.filter(
                OrdemServico.tecnico_id == t.id,
                OrdemServico.status == 'concluida',
                OrdemServico.data_conclusao >= start_date,
                OrdemServico.data_conclusao <= end_date
            ).count()

            ociosidade = 0
            if total_horas_ponto > 0:
                ociosidade = max(0, (total_horas_ponto - total_horas_os) / total_horas_ponto * 100)

            result.append({
                'tecnico_id': t.id,
                'tecnico_nome': t.nome,
                'horas_ponto': round(total_horas_ponto, 1),
                'horas_os': round(total_horas_os, 1),
                'ociosidade_percentual': round(ociosidade, 1),
                'custo_pecas': float(custo_pecas),
                'os_concluidas': os_concluidas
            })
            
        return result

    @staticmethod
    def get_daily_logs(usuario_id, start_date, end_date):
        registros = RegistroPonto.query.filter(
            RegistroPonto.usuario_id == usuario_id,
            RegistroPonto.data_hora_entrada >= start_date,
            RegistroPonto.data_hora_entrada <= end_date
        ).order_by(RegistroPonto.data_hora_entrada.desc()).all()
        
        result = []
        for r in registros:
            total_horas = 0
            if r.data_hora_saida:
                diff = r.data_hora_saida - r.data_hora_entrada
                total_horas = diff.total_seconds() / 3600
                
            result.append({
                'data': r.data_hora_entrada.strftime('%d/%m/%Y'),
                'entrada': r.data_hora_entrada.strftime('%H:%M'),
                'saida': r.data_hora_saida.strftime('%H:%M') if r.data_hora_saida else '--:--',
                'total_horas': round(total_horas, 2),
                'status': 'normal' if 7.8 <= total_horas <= 8.5 else ('insuficiente' if total_horas < 7.8 else 'extra')
            })
            
        return result

    @staticmethod
    def get_stock_metrics(unidade_id=None):
        # Valor Imobilizado: sum(saldo.quantidade * estoque.valor_unitario)
        query_valor = db.session.query(
            func.sum(EstoqueSaldo.quantidade * Estoque.valor_unitario)
        ).join(Estoque)
        
        if unidade_id:
            query_valor = query_valor.filter(EstoqueSaldo.unidade_id == unidade_id)
        
        valor_imobilizado = query_valor.scalar() or 0

        # Itens Críticos (abaixo do mínimo)
        query_criticos = Estoque.query.filter(Estoque.quantidade_atual <= Estoque.quantidade_minima)
        if unidade_id:
            # Aqui é mais complexo pois quantidade_minima é global no modelo atual
            # Mas podemos filtrar itens que tenham saldo < algum patamar na unidade
            pass
        
        criticos_count = query_criticos.count()

        return {
            'valor_imobilizado': float(valor_imobilizado),
            'itens_criticos': criticos_count
        }

    @staticmethod
    def get_cost_evolution(unidade_id=None, days=30):
        # Retorna dados agrupados por dia para o gráfico
        start_date = datetime.utcnow() - timedelta(days=days)
        
        # Peças
        pecas_evo = db.session.query(
            func.date(MovimentacaoEstoque.data_movimentacao).label('dia'),
            func.sum(MovimentacaoEstoque.quantidade * Estoque.valor_unitario)
        ).join(Estoque).filter(
            MovimentacaoEstoque.tipo_movimentacao == 'consumo',
            MovimentacaoEstoque.data_movimentacao >= start_date
        )
        if unidade_id:
            pecas_evo = pecas_evo.filter(MovimentacaoEstoque.unidade_id == unidade_id)
        
        pecas_data = pecas_evo.group_by('dia').all()

        # Serviços
        servicos_evo = db.session.query(
            func.date(ChamadoExterno.data_conclusao).label('dia'),
            func.sum(ChamadoExterno.valor_final)
        ).join(OrdemServico, ChamadoExterno.os_id == OrdemServico.id).filter(
            ChamadoExterno.status == 'concluido',
            ChamadoExterno.data_conclusao >= start_date
        )
        if unidade_id:
            servicos_evo = servicos_evo.filter(OrdemServico.unidade_id == unidade_id)
        
        servicos_data = servicos_evo.group_by('dia').all()

        # Merge data
        all_days = {}
        for d, v in pecas_data:
            all_days[d] = {'pecas': float(v), 'servicos': 0}
        for d, v in servicos_data:
            if d in all_days:
                all_days[d]['servicos'] = float(v)
            else:
                all_days[d] = {'pecas': 0, 'servicos': float(v)}
        
        # Sort and format
        sorted_days = sorted(all_days.keys())
        labels = [datetime.strptime(d, '%Y-%m-%d').strftime('%d/%m') for d in sorted_days]
        dataset_pecas = [all_days[d]['pecas'] for d in sorted_days]
        dataset_servicos = [all_days[d]['servicos'] for d in sorted_days]

        return {
            'labels': labels,
            'pecas': dataset_pecas,
            'servicos': dataset_servicos
        }
