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
            try:
                sequencial = int(ultima_os.numero_os.split('-')[-1]) + 1
            except ValueError:
                sequencial = 1
        else:
            sequencial = 1
            
        return f"{prefixo}{sequencial:04d}"

    @staticmethod
    def processar_fotos(files, os_id, tipo='foto_antes'):
        """RN-006: Upload com validação de limites e compressão."""
        caminhos_json = [] 
        
        # [RN006] Limite de quantidade (Máx 10 por lote)
        if len(files) > 10:
            raise ValueError("Máximo de 10 fotos permitidas por vez.")

        upload_folder = os.path.join(current_app.root_path, 'static/uploads/os', str(os_id))
        os.makedirs(upload_folder, exist_ok=True)

        processed_count = 0

        for file in files:
            if file and file.filename:
                # Validação de Extensão
                ext = file.filename.rsplit('.', 1)[1].lower()
                if ext not in ['jpg', 'jpeg', 'png', 'webp', 'heic']:
                    continue
                
                # [RN006] Validação de Tamanho (5MB)
                file.seek(0, os.SEEK_END)
                size = file.tell()
                file.seek(0)
                if size > 5 * 1024 * 1024:
                    continue # Pula arquivos muito grandes (ou poderia lançar erro)

                hash_name = secrets.token_hex(4)
                timestamp = int(datetime.now().timestamp())
                filename = f"{tipo}_{timestamp}_{hash_name}.{ext}"
                filepath = os.path.join(upload_folder, filename)
                
                try:
                    img = Image.open(file)
                    if img.mode in ("RGBA", "P"):
                        img = img.convert("RGB")
                    
                    # Salvar imagem otimizada
                    img.save(filepath, optimize=True, quality=85)
                    
                    # Gerar Thumbnail
                    thumb = img.copy()
                    thumb.thumbnail((300, 300))
                    thumb_filename = f"thumb_{filename}"
                    thumb_path = os.path.join(upload_folder, thumb_filename)
                    thumb.save(thumb_path)
                    
                    rel_path = f"uploads/os/{os_id}/{filename}"
                    
                    anexo = AnexosOS(
                        os_id=os_id,
                        nome_arquivo=filename,
                        caminho_arquivo=rel_path,
                        tipo=tipo,
                        tamanho_kb=size // 1024
                    )
                    db.session.add(anexo)
                    caminhos_json.append(rel_path)
                    processed_count += 1
                    
                except Exception as e:
                    print(f"Erro ao processar imagem {file.filename}: {e}")
                    continue
        
        return caminhos_json