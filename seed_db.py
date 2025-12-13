from app import create_app, db
from app.models.models import Unidade, Usuario

app = create_app()

with app.app_context():
    print("Criando tabelas...")
    db.create_all()

    # Verificar se já existem dados
    if not Usuario.query.first():
        print("Criando Usuários Iniciais...")
        
        # Admin Master
        admin = Usuario(
            nome="Administrador Master",
            username="admin", # LOGIN NOVO
            email="admin@gmm.com",
            telefone="2799999999",
            tipo="admin"
        )
        admin.set_senha("admin123")

        # Técnico Teste
        tec = Usuario(
            nome="Técnico João",
            username="joao", # LOGIN NOVO
            email="joao@gmm.com",
            tipo="tecnico",
            unidade_padrao_id=1
        )
        tec.set_senha("senha123")

        db.session.add(admin)
        db.session.add(tec)

    if not Usuario.query.first():
        print("Criando Usuário de Teste...")
        tec = Usuario(
            nome="Técnico João",
            email="tecnico@gmm.com",
            tipo="tecnico",
            unidade_padrao_id=1
        )
        tec.set_senha("senha123") # [cite: 100]
        
        admin = Usuario(
            nome="Admin Master",
            email="admin@gmm.com",
            tipo="admin"
        )
        admin.set_senha("admin123")

        db.session.add(tec)
        db.session.add(admin)

    db.session.commit()
    print("Banco de dados inicializado com sucesso!")