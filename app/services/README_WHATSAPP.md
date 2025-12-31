# Módulo WhatsApp GMM

Este módulo habilita a comunicação automatizada e manual via WhatsApp através da MegaAPI.

## Requisitos
- Redis (Broker do Celery e Estado do Circuit Breaker)
- Celery
- MegaAPI Token & URL

## Instalação
1. Instale as novas dependências:
   ```bash
   pip install -r requirements.txt
   ```
2. Execute a migração do banco de dados:
   ```bash
   flask db upgrade
   ```

## Configuração (.env ou config.py)
- `MEGA_API_URL`: URL da API (ex: https://api.megaapi.com.br/v1/messages/send)
- `MEGA_API_KEY`: Token da MegaAPI
- `FERNET_KEY`: Chave de 32 bytes para criptografia (gerada via `Fernet.generate_key()`)
- `CELERY_BROKER_URL`: URL do Redis (ex: redis://localhost:6379/0)

## Componentes
- **WhatsAppService**: Camada de serviço com validação de telefone (13 dígitos) e Circuit Breaker (abre após 5 falhas consecutivas).
- **Celery Tasks**:
  - `enviar_whatsapp_task`: Envio assíncrono com retry exponencial.
  - `limpar_estados_expirados`: Cleanup de conversas inativas (24h).
  - `agregar_metricas_horarias`: Cálculo de performance.

## Testes
Execute os testes unitários:
```bash
$env:PYTHONPATH="."
python tests/unit/test_whatsapp_service.py
```
