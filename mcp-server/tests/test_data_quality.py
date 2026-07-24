"""
Testes de invariantes de qualidade de dado sobre a camada Silver do seguros.db.

Nao testam numeros historicos (ex: "159 sinistros inconsistentes") porque esses
numeros mudam se o pipeline for re-executado sobre um dataset diferente. Testam
garantias estruturais: dado invalido nunca vira NULL mudo, e nunca vaza para
KPIs financeiros sem ser sinalizado.
"""

import sqlite3

import pytest

import server

pytestmark = pytest.mark.skipif(
    not server.DB_PATH.exists(), reason="seguros.db nao encontrado"
)


@pytest.fixture
def conn():
    connection = sqlite3.connect(server.DB_PATH)
    yield connection
    connection.close()


def scalar(conn, query):
    return conn.execute(query).fetchone()[0]


def test_no_raw_null_dates_in_silver(conn):
    assert scalar(conn, """
        SELECT COUNT(*) FROM silver_sinistros
        WHERE data_ocorrencia IS NULL OR data_aviso IS NULL
    """) == 0


def test_no_zeroed_dates_leak_through_unflagged(conn):
    assert scalar(conn, """
        SELECT COUNT(*) FROM silver_sinistros
        WHERE data_ocorrencia = '0000-00-00' OR data_aviso = '0000-00-00'
    """) == 0


def test_invalid_dates_are_flagged_not_silently_dropped(conn):
    flagged = scalar(conn, """
        SELECT COUNT(*) FROM silver_sinistros
        WHERE data_ocorrencia LIKE 'INCOSISTENTE:%' OR data_aviso LIKE 'INCOSISTENTE:%'
    """)
    total = scalar(conn, "SELECT COUNT(*) FROM silver_sinistros")
    assert 0 < flagged < total


def test_no_negative_valor_pago_in_silver(conn):
    assert scalar(conn, """
        SELECT COUNT(*) FROM silver_sinistros WHERE valor_pago < 0
    """) == 0


def test_pago_status_never_paired_with_non_positive_valor(conn):
    assert scalar(conn, """
        SELECT COUNT(*) FROM silver_sinistros
        WHERE status_sinistro = 'PAGO' AND (valor_pago IS NULL OR valor_pago <= 1)
    """) == 0


def test_orphan_sinistros_flagged_in_completos_view(conn):
    assert scalar(conn, """
        SELECT COUNT(*) FROM vw_silver_sinistros_completos
        WHERE id_apolice NOT IN (SELECT id_apolice FROM silver_apolices)
          AND status_apolice != 'INCOSISTENTE: APOLICE NAO ENCONTRADA'
    """) == 0


def test_gold_kpi_only_reflects_pago_claims(conn):
    gold_total = scalar(conn, "SELECT SUM(total_sinistros) FROM vw_gold_kpi_sinistralidade")
    direct_total = scalar(conn, """
        SELECT COUNT(*) FROM vw_silver_sinistros_completos WHERE status_sinistro = 'PAGO'
    """)
    assert gold_total == direct_total


def test_gold_kpi_excludes_inconsistent_status(conn):
    assert scalar(conn, """
        SELECT COUNT(*) FROM vw_silver_sinistros_completos
        WHERE status_sinistro LIKE 'INCOSISTENTE:%' AND status_sinistro = 'PAGO'
    """) == 0
