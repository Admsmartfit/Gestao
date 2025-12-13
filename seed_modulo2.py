from decimal import Decimal
from app import create_app, db
from app.models.estoque_models import CategoriaEstoque, Estoque

app = create_app()

with app.app_context():
    print("Populando Categorias e Estoque...")
    
    cats = ['Elétrica', 'Hidráulica', 'Mecânica', 'Eletrônica', 'Acabamento']
    cat_objs = {}
    
    for c in cats:
        cat = CategoriaEstoque.query.filter_by(nome=c).first()
        if not cat:
            cat = CategoriaEstoque(nome=c)
            db.session.add(cat)
            db.session.commit()
        cat_objs[c] = cat.id

    itens = [
        ('CAB-001', 'Cabo de Aço 3mm', 'Mecânica', 'MT', 50.000, 2.50),
        ('ROL-001', 'Rolamento 608ZZ', 'Mecânica', 'UN', 20.000, 15.90),
        ('LUB-001', 'Silicone Spray Esteira', 'Mecânica', 'UN', 10.000, 45.00),
        ('ELE-001', 'Fusível 10A', 'Elétrica', 'UN', 100.000, 1.50),
        ('HID-001', 'Válvula Hydra 1.1/2', 'Hidráulica', 'UN', 5.000, 120.00),
        # ... Adicione mais itens conforme necessário
    ]

    for codigo, nome, cat_nome, und, qtd, val in itens:
        if not Estoque.query.filter_by(codigo=codigo).first():
            item = Estoque(
                codigo=codigo,
                nome=nome,
                categoria_id=cat_objs[cat_nome],
                unidade_medida=und,
                quantidade_atual=Decimal(str(qtd)),
                quantidade_minima=Decimal('5.000'),
                valor_unitario=Decimal(str(val))
            )
            db.session.add(item)
    
    db.session.commit()
    print("Estoque populado com sucesso!")