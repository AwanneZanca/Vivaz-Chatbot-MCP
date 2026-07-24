"""
Servidor MCP que expõe ferramentas de RAG (PDFs) e Consultas SQL (SQLite).
"""

# region [1] Imports e Configurações de Ambiente
import json
import logging
import os
import sqlite3
import sys
import time
from functools import wraps
from pathlib import Path

# Configurações de variáveis de ambiente para evitar congelamentos no Windows
os.environ["TOKENIZERS_PARALLELISM"] = "false"
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"

import numpy as np
from mcp.server.fastmcp import FastMCP
from pypdf import PdfReader
# endregion

# region [2] Definindo Caminhos e Constantes
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data" / "index"
DATA_DIR.mkdir(parents=True, exist_ok=True)

# Aponta para o banco seguros.db na pasta irmã 'data-pipeline' (dentro de Vivaz_Chatbot)
DB_PATH = BASE_DIR.parent / "data-pipeline" / "seguros.db"

EMBEDDINGS_PATH = DATA_DIR / "embeddings.npy"
CHUNKS_PATH = DATA_DIR / "chunks.json"

CHUNK_SIZE = 800
CHUNK_OVERLAP = 150

# Inicialização do servidor MCP
mcp = FastMCP("insurtech-rag-sql")
_model = None

# Log vai para stderr, nunca stdout: o transporte stdio do MCP usa stdout
# para o protocolo JSON-RPC, e qualquer texto solto ali quebra o cliente.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger("insurtech-rag-sql")
# endregion

# region [3] Funções Auxiliares (Lazy Loading e Storage)
def get_model():
    """Carrega o modelo de embeddings na memória apenas sob demanda (Lazy Loading)."""
    global _model
    if _model is None:
        import torch
        torch.set_num_threads(1)
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer("all-MiniLM-L6-v2", device="cpu")
    return _model


def load_index():
    """Carrega do disco o índice atual contendo os chunks de texto e os vetores de embeddings."""
    if CHUNKS_PATH.exists() and EMBEDDINGS_PATH.exists():
        chunks = json.loads(CHUNKS_PATH.read_text(encoding="utf-8"))
        embeddings = np.load(EMBEDDINGS_PATH)
        return chunks, embeddings
    return [], np.zeros((0, 384), dtype=np.float32)


def save_index(chunks, embeddings):
    """Salva os chunks e a matriz de embeddings atualizados nos arquivos locais."""
    CHUNKS_PATH.write_text(json.dumps(chunks, ensure_ascii=False, indent=2), encoding="utf-8")
    np.save(EMBEDDINGS_PATH, embeddings)


def chunk_text(text, size=CHUNK_SIZE, overlap=CHUNK_OVERLAP):
    """Divide um texto longo em blocos menores com sobreposição."""
    chunks = []
    start = 0
    while start < len(text):
        end = start + size
        chunks.append(text[start:end])
        start += size - overlap
    return [c.strip() for c in chunks if c.strip()]


def log_tool_call(func):
    """Loga início, duração e tamanho do resultado de cada chamada de tool."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        start = time.monotonic()
        logger.info("tool=%s chamada kwargs=%s", func.__name__, kwargs or dict(zip(func.__code__.co_varnames, args)))
        try:
            result = func(*args, **kwargs)
            duration_ms = (time.monotonic() - start) * 1000
            logger.info("tool=%s concluida em %.1fms (%d chars retornados)", func.__name__, duration_ms, len(result))
            return result
        except Exception:
            duration_ms = (time.monotonic() - start) * 1000
            logger.exception("tool=%s falhou apos %.1fms", func.__name__, duration_ms)
            raise
    return wrapper
# endregion

# region [4] Ferramentas MCP (RAG em PDFs)
@mcp.tool()
@log_tool_call
def add_pdf(path: str) -> str:
    """Processa e indexa um arquivo PDF local."""
    pdf_path = Path(path).expanduser().resolve()
    if not pdf_path.exists():
        return f"Erro: arquivo não encontrado em {pdf_path}"
    if pdf_path.suffix.lower() != ".pdf":
        return f"Erro: o arquivo {pdf_path} não é um PDF válido."

    reader = PdfReader(str(pdf_path))
    new_chunks = []
    for page_num, page in enumerate(reader.pages, start=1):
        page_text = page.extract_text() or ""
        for chunk in chunk_text(page_text):
            new_chunks.append({
                "source": pdf_path.name,
                "page": page_num,
                "text": chunk,
            })

    if not new_chunks:
        return f"Nenhum texto extraível foi encontrado no arquivo {pdf_path.name}"

    import torch
    model = get_model()
    
    with torch.no_grad():
        new_embeddings = model.encode(
            [c["text"] for c in new_chunks],
            batch_size=16,
            normalize_embeddings=True,
            show_progress_bar=False
        )

    chunks, embeddings = load_index()
    chunks.extend(new_chunks)
    embeddings = np.vstack([embeddings, new_embeddings]) if embeddings.shape[0] else np.array(new_embeddings)
    save_index(chunks, embeddings)

    return f"Sucesso: {pdf_path.name} indexado! {len(new_chunks)} blocos adicionados."


@mcp.tool()
@log_tool_call
def search_pdfs(query: str, top_k: int = 5) -> str:
    """Realiza busca semântica nos PDFs indexados."""
    chunks, embeddings = load_index()
    if not chunks:
        return "Nenhum PDF foi indexado ainda. Use a ferramenta 'add_pdf' primeiro."

    import torch
    model = get_model()
    with torch.no_grad():
        query_embedding = model.encode([query], normalize_embeddings=True, show_progress_bar=False)[0]
    
    scores = embeddings @ query_embedding
    top_indices = np.argsort(scores)[::-1][:top_k]

    results = []
    for idx in top_indices:
        chunk = chunks[idx]
        results.append(
            f"[{chunk['source']} pág.{chunk['page']}, relevância={scores[idx]:.3f}]\n{chunk['text']}"
        )
    return "\n\n---\n\n".join(results)


@mcp.tool()
@log_tool_call
def list_documents() -> str:
    """Lista todos os documentos PDF cadastrados."""
    chunks, _ = load_index()
    if not chunks:
        return "Nenhum PDF foi indexado até o momento."

    counts = {}
    for chunk in chunks:
        counts[chunk["source"]] = counts.get(chunk["source"], 0) + 1
    return "\n".join(f"{name}: {count} blocos" for name, count in counts.items())
# endregion

# region [5] Ferramentas MCP (SQL / SQLite)
@mcp.tool()
@log_tool_call
def list_database_schema() -> str:
    """
    Lista todas as tabelas e VIEWS disponíveis no banco de dados seguros.db,
    exibindo os comandos DDL (CREATE TABLE/VIEW) de cada uma.

    O banco segue arquitetura Medallion: bronze_* e stg_* são camadas brutas/internas
    de ingestão e staging (dado sujo, sem tratamento). Para responder perguntas de
    negócio, prefira sempre silver_* e as views vw_* — já vêm tratadas, deduplicadas
    e com inconsistências sinalizadas (prefixo 'INCOSISTENTE: ...' nos campos).
    """
    if not DB_PATH.exists():
        return f"Erro: Banco de dados não encontrado em '{DB_PATH}'."

    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Consulta sqlite_master buscando tabelas e views
        cursor.execute("""
            SELECT type, name, sql 
            FROM sqlite_master 
            WHERE type IN ('table', 'view') 
              AND name NOT LIKE 'sqlite_%'
            ORDER BY type, name;
        """)
        rows = cursor.fetchall()
        conn.close()

        if not rows:
            return "O banco de dados está vazio."

        output = ["=== ESTRUTURA DO BANCO DE DADOS (TABELAS E VIEWS) ==="]
        for item_type, name, sql in rows:
            output.append(f"\n-- [{item_type.upper()}] {name}\n{sql};")

        return "\n".join(output)
    except Exception as e:
        return f"Erro ao ler o schema: {str(e)}"


@mcp.tool()
@log_tool_call
def run_sql_query(query: str) -> str:
    """
    Executa uma consulta SQL (SELECT) de leitura no banco seguros.db.
    Pode consultar tanto tabelas físicas quanto views (ex: vw_gold_kpi_sinistralidade).

    Para perguntas de negócio, use silver_* e vw_* (dado tratado e sinalizado).
    Só consulte bronze_*/stg_* se a pergunta for especificamente sobre dado bruto/lineage.
    """
    if not DB_PATH.exists():
        return f"Erro: Banco de dados não encontrado em '{DB_PATH}'."

    # Trava de segurança simples para evitar mutações indesejadas pelo LLM
    clean_query = query.strip().lower()
    if not clean_query.startswith("select") and not clean_query.startswith("with"):
        return "Erro de Segurança: Apenas consultas de leitura (SELECT) são permitidas."

    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(query)
        
        columns = [description[0] for description in cursor.description] if cursor.description else []
        rows = cursor.fetchall()
        conn.close()

        if not rows:
            return "Consulta executada com sucesso. Nenhum resultado retornado."

        # Retorna formatado em JSON estruturado para facilitação da leitura do LLM
        result_data = [dict(zip(columns, row)) for row in rows]
        return json.dumps(result_data, ensure_ascii=False, indent=2)

    except Exception as e:
        return f"Erro ao executar SQL: {str(e)}"
# endregion

# region [6] Ponto de Entrada (Execution)
if __name__ == "__main__":
    mcp.run(transport="stdio")
# endregion