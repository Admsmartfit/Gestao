import os
import secrets
from datetime import datetime
from PIL import Image
from werkzeug.utils import secure_filename
from flask import current_app
from app.extensions import db
from app.models.estoque_models import OrdemServico

class OSService:
    @staticmethod
    def gerar_numero_os():
        """RN-005: Formato OS-{ANO}-{SEQUENCIAL} [cite: 347]"""
        ano_atual = datetime.now().year
        prefixo = f"OS-{ano_atual}-"
        
        ultima_os = OrdemServico.query.filter(
            OrdemServico.numero_os.like(f"{prefixo}%")
        ).order_by(OrdemServico.id.desc()).first()

        if ultima_os:
            sequencial = int(ultima_os.numero_os.split('-')[-1]) + 1
        else:
            sequencial = 1
            
        return f"{prefixo}{sequencial:04d}"

    @staticmethod
    def processar_fotos(files, os_id):
        """RN-006: Upload e compressão de fotos [cite: 350-357]"""
        caminhos = []
        upload_folder = os.path.join(current_app.root_path, 'static/uploads/os', 
                                   str(datetime.now().year), str(datetime.now().month))
        os.makedirs(upload_folder, exist_ok=True)

        for file in files:
            if file and file.filename:
                ext = file.filename.rsplit('.', 1)[1].lower()
                if ext not in ['jpg', 'jpeg', 'png', 'webp']:
                    continue

                # Nomenclatura segura
                hash_name = secrets.token_hex(4)
                filename = f"os_{os_id}_{int(datetime.now().timestamp())}_{hash_name}.{ext}"
                filepath = os.path.join(upload_folder, filename)
                
                # Compressão (Pillow)
                img = Image.open(file)
                img.thumbnail((1920, 1920)) # Mantém aspect ratio
                img.save(filepath, optimize=True, quality=85)
                
                # Caminho relativo para o banco
                rel_path = f"uploads/os/{datetime.now().year}/{datetime.now().month}/{filename}"
                caminhos.append(rel_path)
        
        return caminhos