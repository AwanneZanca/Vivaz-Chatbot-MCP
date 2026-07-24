import json

import server


def test_chunk_text_respects_size_and_overlap():
    text = "a" * 2000
    chunks = server.chunk_text(text, size=800, overlap=150)

    assert all(len(c) <= 800 for c in chunks)
    assert len(chunks) > 1


def test_chunk_text_drops_empty_chunks():
    assert server.chunk_text("   \n\n   ") == []


def test_run_sql_query_blocks_non_select():
    result = server.run_sql_query("DROP TABLE silver_sinistros")
    assert "Erro de Seguran" in result


def test_run_sql_query_blocks_delete():
    result = server.run_sql_query("DELETE FROM silver_sinistros")
    assert "Erro de Seguran" in result


def test_run_sql_query_allows_select():
    result = server.run_sql_query("SELECT 1 AS um")
    data = json.loads(result)
    assert data == [{"um": 1}]


def test_run_sql_query_allows_with_cte():
    result = server.run_sql_query("WITH t AS (SELECT 1 AS x) SELECT x FROM t")
    data = json.loads(result)
    assert data == [{"x": 1}]


def test_list_database_schema_includes_silver_and_gold():
    result = server.list_database_schema()
    assert "silver_sinistros" in result
    assert "vw_gold_kpi_sinistralidade" in result


def test_search_pdfs_without_index_returns_hint(monkeypatch, tmp_path):
    monkeypatch.setattr(server, "CHUNKS_PATH", tmp_path / "chunks.json")
    monkeypatch.setattr(server, "EMBEDDINGS_PATH", tmp_path / "embeddings.npy")

    result = server.search_pdfs("qualquer pergunta")
    assert "Nenhum PDF foi indexado" in result


def test_list_documents_without_index_returns_hint(monkeypatch, tmp_path):
    monkeypatch.setattr(server, "CHUNKS_PATH", tmp_path / "chunks.json")
    monkeypatch.setattr(server, "EMBEDDINGS_PATH", tmp_path / "embeddings.npy")

    result = server.list_documents()
    assert "Nenhum PDF foi indexado" in result
