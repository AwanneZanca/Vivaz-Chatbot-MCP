import json

import server


class TestChunkText:
    """chunk_text e uma funcao pura, sem I/O -- testa o algoritmo de
    chunking isolado, sem precisar de um PDF de verdade nem do modelo
    de embeddings."""

    def test_respects_size_and_overlap(self):
        text = "a" * 2000
        chunks = server.chunk_text(text, size=800, overlap=150)

        assert all(len(c) <= 800 for c in chunks)
        assert len(chunks) > 1

    def test_drops_empty_chunks(self):
        assert server.chunk_text("   \n\n   ") == []


class TestRunSqlQuerySecurity:
    """Unica camada de seguranca do servidor: a LLM escreve a query
    sozinha (tool calling), entao precisa existir uma trava contra
    DROP/DELETE/etc antes de a query chegar no banco de verdade."""

    def test_blocks_drop(self):
        result = server.run_sql_query("DROP TABLE silver_sinistros")
        assert "Erro de Seguran" in result

    def test_blocks_delete(self):
        result = server.run_sql_query("DELETE FROM silver_sinistros")
        assert "Erro de Seguran" in result


class TestSqlReadQueries:
    """Confirma que consultas de leitura legitimas continuam
    funcionando -- um teste que so bloqueia escrita, sem confirmar que
    a leitura ainda passa, poderia 'aprovar' uma trava boa demais que
    quebrasse tudo."""

    def test_select_works(self):
        result = server.run_sql_query("SELECT 1 AS um")
        data = json.loads(result)
        assert data == [{"um": 1}]

    def test_with_cte_works(self):
        result = server.run_sql_query("WITH t AS (SELECT 1 AS x) SELECT x FROM t")
        data = json.loads(result)
        assert data == [{"x": 1}]

    def test_schema_includes_silver_and_gold(self):
        result = server.list_database_schema()
        assert "silver_sinistros" in result
        assert "vw_gold_kpi_sinistralidade" in result


class TestPdfToolsWithoutIndex:
    """Antes do primeiro add_pdf, chunks/embeddings nao existem em
    disco. Usa monkeypatch para apontar CHUNKS_PATH/EMBEDDINGS_PATH
    para uma pasta temporaria vazia, simulando esse estado sem
    precisar rodar o modelo de embeddings (lento e desnecessario
    aqui)."""

    def test_search_returns_hint(self, monkeypatch, tmp_path):
        monkeypatch.setattr(server, "CHUNKS_PATH", tmp_path / "chunks.json")
        monkeypatch.setattr(server, "EMBEDDINGS_PATH", tmp_path / "embeddings.npy")

        result = server.search_pdfs("qualquer pergunta")
        assert "Nenhum PDF foi indexado" in result

    def test_list_documents_returns_hint(self, monkeypatch, tmp_path):
        monkeypatch.setattr(server, "CHUNKS_PATH", tmp_path / "chunks.json")
        monkeypatch.setattr(server, "EMBEDDINGS_PATH", tmp_path / "embeddings.npy")

        result = server.list_documents()
        assert "Nenhum PDF foi indexado" in result
