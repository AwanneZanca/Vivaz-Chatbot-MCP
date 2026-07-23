# 🛡️ Data Pipeline (Vivaz_Chatbot)

Pipeline de Engenharia de Dados para o setor de Insurtech/Seguros, seguindo a arquitetura
**Medallion** (Bronze, Silver e Gold) em **SQLite** (`seguros.db`).

Faz parte do projeto `Vivaz_Chatbot`, junto com a pasta [`../mcp-server`](../mcp-server) (servidor
MCP que expõe esse banco e os PDFs de regras para um assistente de IA).

---

## 🏗️ Arquitetura de Dados (Medallion)

A pipeline transforma dados brutos e não estruturados em visões prontas para negócio:

1. **[ Dados Brutos / CSV ]**
2. **🥉 Camada Bronze (Raw):** `bronze_apolices`, `bronze_sinistros`, `dim_segurados`
3. **⚙️ Validação e Integridade Referencial:** `stg_apolices_validadas`, `stg_sinistros_validados`
4. **🥈 Camada Silver (Clean & Deduplicated):** `silver_apolices`, `silver_sinistros`
5. **🥇 Camada Gold (Views & KPIs):** `vw_silver_sinistros_completos`, `vw_gold_kpi_sinistralidade`

O script que gera essas camadas está em [`Insurtech_DB.session.sql`](Insurtech_DB.session.sql).

---

## 📊 Estrutura e Conteúdo do Banco de Dados (`seguros.db`)

### 🥉 Camada Bronze (Ingestão / Raw)
Guarda os dados brutos exatamente como chegam dos sistemas legados ou arquivos de ingestão, sem alterações.
* **`bronze_apolices`**: Registros brutos das apólices contratadas (status, datas, tipos e valores originais).
* **`bronze_sinistros`**: Registros brutos dos acionamentos de seguro (eventos, valores pedidos/pagos e status originais).
* **`dim_segurados`**: Tabela dimensional com cadastro e dados dos clientes/segurados.

### ⚙️ Camada de Staging (Integridade Referencial)
Tabelas intermediárias responsáveis por filtrar inconsistências antes do tratamento.
* **`stg_apolices_validadas`**: Apólices filtradas que possuem um segurado válido na `dim_segurados`.
* **`stg_sinistros_validados`**: Sinistros filtrados que pertencem a uma apólice existente na `bronze_apolices`.

### 🥈 Camada Silver (Tratada e Deduplicada)
Tabelas físicas higienizadas, com padronização de datas (ISO `YYYY-MM-DD`), conversão/sanitização de caracteres,
tratamento de inconsistências financeiras e deduplicadas via `ROW_NUMBER() OVER (PARTITION BY ... ORDER BY data_ingestao DESC)`.
Inconsistências não são descartadas silenciosamente — ficam marcadas com o prefixo `INCOSISTENTE: ...` no
próprio campo (`status_sinistro`, `data_ocorrencia`, `data_aviso`, `status_apolice`), pra ficar auditável de onde vieram.
* **`silver_apolices`**: Apólices tratadas por tipo (`AUTO`, `VIDA`, `RESIDENCIAL`, `EMPRESARIAL`), status sanitizado e deduplicado.
* **`silver_sinistros`**: Sinistros tratados com nomenclatura padronizada (`COLISAO`, `ROUBO`, etc.), mapeamento de inconsistências de pagamento/data e deduplicação por ingestão.

### 🥇 Camada Gold / Views (Visões de Negócio & Consumo)
Tabelas virtuais prontas para consumo por dashboards (Power BI) ou agentes autônomos de IA.
* **`vw_silver_sinistros_completos`**: Visão analítica consolidada unindo os dados da `silver_sinistros` com os detalhes da `silver_apolices`.
* **`vw_gold_kpi_sinistralidade`**: Agregação de KPIs financeiros e operacionais (quantidade de sinistros, total do valor pedido/pago e ticket médio) por tipo de cobertura para sinistros pagos.

---

## 🛠️ Tecnologias Utilizadas

* **Linguagem:** Python 3.10+
* **Banco de Dados:** SQLite3
* **IDE & Ferramentas SQL:** VS Code + extensão SQLTools
* **Arquitetura de Dados:** Medallion (Bronze / Silver / Gold) & Dimensional
