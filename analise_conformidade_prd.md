# Análise de Conformidade: Sistema GMM vs PRD 2.0

Esta análise identifica as lacunas e divergências entre a implementação atual e os requisitos definidos no documento `prd 2.txt`.

## 📊 Resumo de Cobertura por Módulo

| Módulo | Status | Cobertura |
| :--- | :--- | :--- |
| **Módulo 1: Autenticação e Ponto** | Estável | ~85% |
| **Módulo 2: Manutenção e Estoque** | Funcional | ~90% |
| **Módulo 3: Terceirizados e WhatsApp** | Em Progresso | ~30% |
| **Módulo 4: Dashboard e Analytics** | Básico | ~40% |

---

## 📦 Módulo 1: Autenticação e Controle de Ponto

### ✅ Implementado
- Autenticação via Flask-Login e senhas com Hash.
- Geolocalização capturada no Check-in.
- Validação de IP da Unidade no Check-in (`@require_unit_ip`).

### ❌ Faltando / Diferente
- **IP no Checkout (RN001):** A validação de rede só ocorre na entrada, permitindo saída fora da rede da unidade.
- **Segurança de Senha (RN003):** Não há validação de complexidade (maiúsculas/números) nem política de expiração de 90 dias.
- **Modelo de Dados:** O PRD especifica o `tipo` de usuário como ENUM (atualmente String).

---

## 📦 Módulo 2: Gestão de Manutenção e Estoque

### ✅ Implementado
- Numeração automática de OS (`OS-2024-XXXX`).
- Controle de estoque com bloqueio de saldo insuficiente.
- Upload de múltiplas fotos com compressão e miniaturas (300x300).
- Saldo de estoque separado por Unidade.

### ❌ Faltando / Diferente
- **Metadados de Equipamentos (3.2.1):** Faltam campos como `fabricante`, `modelo`, `número_serie` e `data_aquisicao`.
- **Métricas de OS:** Faltam os campos `tempo_execucao` (em minutos) e `avaliacao` (1-5 estrelas) na Ordem de Serviço.
- **Status de Peças:** A medida em "METROS" aceita decimais, mas o controle de "ajuste/devolução" (RN004) está simplificado.

---

## 📦 Módulo 3: Terceirizados e Notificações (Ponto Crítico)

### ✅ Implementado
- Cadastro de Prestadores e Vínculo com Unidades.
- Criação de Chamados Externos vinculados a uma OS.

### ❌ Faltando / Diferente
- **Integração WhatsApp (MegaAPI - RN008):** O sistema não envia mensagens automáticas.
- **Lembretes Celery (RN009):** Não há automação para lembretes de prazo ou cobranças.
- **Avaliação (RN011):** Falta a lógica de atualizar a média de estrelas do prestador automaticamente após o serviço.

---

## 📦 Módulo 4: Dashboard Gerencial e Analytics

### ✅ Implementado
- Painel de Compras com aprovação e recebimento.
- Auditoria de quem solicitou/aprovou (campos adicionados recentemente).

### ❌ Faltando / Diferente
- **Indicadores de Performance (RN013):** Não existe a tabela de cache diário de métricas. Elas são calculadas "on-the-fly".
- **Gráficos (Chart.js):** O dashboard é textual; faltam os gráficos de pizza (por tipo) e barras (consumo).
- **Exportação CSV:** Requisito CA021 não implementado.
- **Alertas ao Gerente (RN014):** Automação de e-mails para estoque crítico ou atrasos não existe.
- **Estrutura de Pedidos (578):** O PRD sugere uma lista JSON de itens num único pedido. Atualmente, cada pedido vincula apenas 1 peça.

---

## 💡 Próximos Passos Sugeridos

1. **Prioridade 1:** Implementar o serviço de envio de WhatsApp (serviço base).
2. **Prioridade 2:** Adicionar campos de métricas em OS (tempo e avaliação).
3. **Prioridade 3:** Configurar Celery Beat para as tarefas de lembrete e cache de indicadores.
