import sys
import os
sys.path.append(os.getcwd())

from app import create_app
from app.extensions import db
from sqlalchemy import text

app = create_app()

with app.app_context():
    # Helper to check if column exists (naive check for SQLite/Postgres compatibility)
    # Using simple try/catch with ALTER TABLE
    
    commands = [
        "ALTER TABLE unidades ADD COLUMN razao_social VARCHAR(150)",
        "ALTER TABLE unidades ADD COLUMN cnpj VARCHAR(20)",
        "ALTER TABLE unidades ADD COLUMN telefone VARCHAR(20)"
    ]
    
    with db.engine.connect() as conn:
        for cmd in commands:
            try:
                conn.execute(text(cmd))
                print(f"Executed: {cmd}")
            except Exception as e:
                # Likely column already exists
                print(f"Skipped (or error): {cmd} | Detail: {str(e)}")
        
        conn.commit()
    
    print("Database update complete.")
