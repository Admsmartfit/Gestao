from app import create_app, db
from app.models.estoque_models import EstoqueSaldo, SolicitacaoTransferencia
from sqlalchemy import text

app = create_app()

with app.app_context():
    print("Criando novas tabelas...")
    db.create_all()
    
    # Adicionar coluna unidade_id em movimentacoes_estoque se não existir
    try:
        with db.engine.connect() as conn:
            conn.execute(text("ALTER TABLE movimentacoes_estoque ADD COLUMN unidade_id INTEGER REFERENCES unidades(id)"))
            conn.commit()
            print("Coluna unidade_id adicionada.")
    except Exception as e:
        print(f"Nota: Coluna unidade_id provavelmente já existe ou erro: {e}")

    print("Schema atualizado.")
