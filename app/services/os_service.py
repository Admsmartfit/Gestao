import os
import secrets
from datetime import datetime
from PIL import Image
from werkzeug.utils import secure_filename
from flask import current_app
from app.extensions import db
from app.models.estoque_models import OrdemServico, AnexosOS

class OSService:
    @staticmethod
    def gerar_numero_os():
        """RN-005: Formato OS-{ANO}-{SEQUENCIAL}"""
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
    def processar_fotos(files, os_id, tipo='foto_antes'):
        """RN-006: Upload, compressão e registro na tabela AnexosOS"""
        caminhos_json = [] # Para manter compatibilidade com campo JSON legado
        
        # Estrutura: static/uploads/os/ID/
        upload_folder = os.path.join(current_app.root_path, 'static/uploads/os', str(os_id))
        os.makedirs(upload_folder, exist_ok=True)

        for file in files:
            if file and file.filename:
                ext = file.filename.rsplit('.', 1)[1].lower()
                if ext not in ['jpg', 'jpeg', 'png', 'webp']:
                    continue

                # Nome seguro e único
                hash_name = secrets.token_hex(4)
                timestamp = int(datetime.now().timestamp())
                filename = f"{tipo}_{timestamp}_{hash_name}.{ext}"
                filepath = os.path.join(upload_folder, filename)
                
                # 1. Processamento com Pillow
                img = Image.open(file)
                # Converter para RGB se necessário (ex: PNG com transparência)
                if img.mode in ("RGBA", "P"):
                    img = img.convert("RGB")
                
                # Salvar imagem original otimizada
                img.save(filepath, optimize=True, quality=85)
                
                # 2. Gerar Thumbnail 300x300 (Requisito PRD)
                thumb = img.copy()
                thumb.thumbnail((300, 300))
                thumb_filename = f"thumb_{filename}"
                thumb_path = os.path.join(upload_folder, thumb_filename)
                thumb.save(thumb_path)
                
                # Caminho relativo para acesso web
                rel_path = f"uploads/os/{os_id}/{filename}"
                
                # 3. Salvar na Tabela AnexosOS
                anexo = AnexosOS(
                    os_id=os_id,
                    nome_arquivo=filename,
                    caminho_arquivo=rel_path,
                    tipo=tipo,
                    tamanho_kb=os.path.getsize(filepath) // 1024
                )
                db.session.add(anexo)
                
                caminhos_json.append(rel_path)
        
        return caminhos_json