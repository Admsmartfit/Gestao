from app import create_app, db
from app.models.estoque_models import Estoque, EstoqueSaldo
from app.models.models import Unidade

app = create_app()

with app.app_context():
    print("Iniciando migração de saldos de estoque legado...")

    # 1. Buscar a primeira unidade ativa para atribuir o saldo inicial
    unidade_padrao = Unidade.query.filter_by(ativa=True).order_by(Unidade.id).first()

    if not unidade_padrao:
        print("ERRO: Nenhuma unidade ativa encontrada no sistema.")
        print("Crie uma unidade antes de rodar este script.")
        exit(1)

    print(f"Unidade padrão definida para migração: ID {unidade_padrao.id} - {unidade_padrao.nome}")

    # 2. Buscar todos os itens do estoque
    itens = Estoque.query.all()
    count_migrados = 0

    for item in itens:
        # Verifica se o item já tem algum registro de saldo (usando o relacionamento backref 'saldos')
        # Se a lista 'saldos' estiver vazia, significa que é um dado legado sem distribuição por unidade.
        if not item.saldos:
            print(f"Migrando item: {item.nome} (ID: {item.id}) -> Qtd: {item.quantidade_atual}")
            
            # 3. Cria o registro de saldo na unidade padrão com a quantidade total atual
            novo_saldo = EstoqueSaldo(
                estoque_id=item.id,
                unidade_id=unidade_padrao.id,
                quantidade=item.quantidade_atual,
                localizacao=item.localizacao # Copia localização se existir (opcional, mas útil)
            )
            
            db.session.add(novo_saldo)
            count_migrados += 1

    if count_migrados > 0:
        try:
            db.session.commit()
            print(f"\nSucesso! {count_migrados} itens foram migrados para a tabela de saldos na unidade '{unidade_padrao.nome}'.")
        except Exception as e:
            db.session.rollback()
            print(f"\nErro ao salvar alterações no banco de dados: {str(e)}")
    else:
        print("\nNenhum item precisou de migração (todos já possuem saldo definido).")

    print("Script finalizado.")