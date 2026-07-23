# Vivaz Chatbot — Insurtech RAG + SQL via MCP

Assistente de IA para uma seguradora fictícia que combina duas fontes de contexto —
documentos em PDF e um banco de dados estruturado — através do **MCP (Model Context Protocol)**.

## Estrutura do projeto

- [`mcp-server/`](mcp-server/) — servidor MCP: RAG sobre PDFs (embeddings locais) + consultas SQL de leitura.
- [`data-pipeline/`](data-pipeline/) — pipeline de dados em arquitetura Medallion (Bronze → Silver → Gold)
  e o banco `seguros.db` que o servidor consulta.

Veja o README de cada pasta para detalhes de setup e uso.

*(Todo o dado — apólices, sinistros e condições contratuais — é 100% sintético/fictício, criado para fins de estudo.)*
