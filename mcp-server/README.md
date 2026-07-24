# mcp-server (Vivaz_Chatbot)

Servidor MCP local que combina duas fontes de contexto para um assistente de Insurtech:

- **RAG sobre PDFs**: ingere PDFs (condições gerais, manuais), extrai texto, divide em chunks e gera
  embeddings locais (sentence-transformers) para busca semântica.
- **Consulta SQL**: lê o banco `seguros.db` (pipeline Bronze/Silver/Gold) na pasta irmã
  [`../data-pipeline`](../data-pipeline), permitindo consultas de leitura (`SELECT`) diretas às
  tabelas e views de negócio.

Faz parte do projeto `Vivaz_Chatbot`, junto com a pasta `data-pipeline/` (ETL e banco de dados).

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate      # Windows
pip install -r requirements.txt
```

## Tools expostas

### RAG em PDFs
- `add_pdf(path)` — ingere um PDF: extrai texto, faz chunking, embeda e adiciona ao índice.
- `search_pdfs(query, top_k=5)` — busca semântica nos PDFs indexados, retorna os trechos mais relevantes.
- `list_documents()` — lista os PDFs já indexados e quantos blocos cada um tem.

### SQL (seguros.db)
- `list_database_schema()` — lista tabelas e views do banco com seus comandos `CREATE`.
- `run_sql_query(query)` — executa uma consulta de leitura (`SELECT`/`WITH`) e retorna o resultado em JSON. Consultas de escrita (`DROP`, `DELETE`, etc.) são bloqueadas.

## Rodando localmente (dev)

```bash
mcp dev server.py
```

Isso abre o MCP Inspector no navegador para testar as tools manualmente.

## Conectando ao Claude Desktop / Claude Code

Adicione ao `claude_desktop_config.json` (ou config MCP equivalente):

```json
{
  "mcpServers": {
    "vivaz-chatbot": {
      "command": "/caminho/para/Vivaz-Chatbot-MCP/mcp-server/.venv/Scripts/python.exe",
      "args": ["/caminho/para/Vivaz-Chatbot-MCP/mcp-server/server.py"]
    }
  }
}
```

## Uso

1. Peça ao Claude para chamar `add_pdf` com o caminho de um PDF (ex: condições gerais, manual do segurado).
2. Faça perguntas normalmente — o Claude pode chamar `search_pdfs` para buscar contexto nos PDFs, ou
   `run_sql_query` para consultar dados estruturados de apólices e sinistros.

Exemplos:
* **Pergunta de Regra/Manual:** *"Segundo o manual em PDF, o que acontece em caso de sinistro por alagamento?"*
  → o agente faz busca semântica (RAG) nos PDFs indexados em `pdfs/`.
* **Pergunta de Negócio:** *"Qual o valor total pago em sinistros de apólices de Auto?"*
  → o agente executa uma consulta SQL direta na view `vw_gold_kpi_sinistralidade`.

## Como funciona (RAG)

1. **Extração**: `pypdf` lê o texto de cada página do PDF.
2. **Chunking**: o texto é dividido em blocos de ~800 caracteres com sobreposição de 150 (evita cortar contexto no meio).
3. **Embedding**: cada chunk é convertido em vetor com o modelo local `all-MiniLM-L6-v2`.
4. **Índice**: embeddings e chunks são persistidos em `data/index/` (numpy + json).
5. **Busca**: a query também é embedada, e a similaridade de cosseno contra todos os chunks retorna o top-k mais relevante.

## Como funciona (SQL)

O `seguros.db` segue a arquitetura Medallion (ver [`../data-pipeline/README.md`](../data-pipeline/README.md)):
Bronze (raw) → Staging (`stg_*`, validação referencial) → Silver (tratado/deduplicado) → Gold (views de KPI).

## Testes

```bash
pip install -r requirements-dev.txt
pytest -v
```

Dois níveis de teste:
- `tests/test_server_tools.py` — comportamento das tools (bloqueio de escrita SQL, chunking, respostas sem índice carregado).
- `tests/test_data_quality.py` — invariantes de qualidade de dado direto no `seguros.db` (nenhum `NULL`/valor negativo escapa sem ser sinalizado como `INCOSISTENTE:`, KPIs da camada Gold nunca incluem dado inconsistente).

Roda automaticamente a cada push via GitHub Actions ([`.github/workflows/ci.yml`](../.github/workflows/ci.yml)).

## Observabilidade

Cada chamada de tool é logada em `stderr` (nunca `stdout`, que é reservado pelo protocolo MCP via stdio) com nome, argumentos, duração e tamanho da resposta — útil para depurar quais ferramentas o agente está chamando e quanto tempo cada uma leva.
