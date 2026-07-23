SELECT * FROM bronze_apolices;
SELECT * FROM bronze_sinistros;
SELECT * FROM dim_segurados;

SELECT
    (SELECT COUNT(*) FROM bronze_apolices) AS total_linhas_bronze_apolices,
    (SELECT COUNT(*) FROM bronze_sinistros) AS total_linhas_bronze_sinistros,
    (SELECT COUNT(*) FROM dim_segurados) AS total_linhas_dim_segurados;

SELECT
    (SELECT COUNT(DISTINCT id_apolice) FROM bronze_apolices) AS total_apolices_distintas,
    (SELECT COUNT(DISTINCT id_apolice) FROM bronze_sinistros) AS total_apolices_distintas_sinistros;

DROP TABLE IF EXISTS stg_sinistros_validados;
CREATE TABLE stg_sinistros_validados AS
SELECT s.*
FROM bronze_sinistros s
LEFT JOIN bronze_apolices a ON s.id_apolice = a.id_apolice
WHERE a.id_apolice IS NOT NULL;

DROP TABLE IF EXISTS stg_apolices_validadas;
CREATE TABLE stg_apolices_validadas AS
SELECT s.*
FROM bronze_apolices s
LEFT JOIN dim_segurados a ON s.id_segurado = a.id_segurado
WHERE a.id_segurado IS NOT NULL;

DROP TABLE IF EXISTS silver_sinistros;
CREATE TABLE silver_sinistros AS
WITH tratada_sinistros as(
SELECT
    id_sinistro,
    id_apolice,
    CASE
        WHEN LOWER(TRIM(tipo_sinistro)) = 'colisao'    THEN 'COLISAO'
        WHEN LOWER(TRIM(tipo_sinistro)) = 'roubo'      THEN 'ROUBO'
        WHEN LOWER(TRIM(tipo_sinistro)) = 'incendio'   THEN 'INCENDIO'
        WHEN LOWER(TRIM(tipo_sinistro)) = 'alagamento' THEN 'ALAGAMENTO'
        WHEN LOWER(TRIM(tipo_sinistro)) = 'furto'      THEN 'FURTO'
        ELSE UPPER(TRIM(tipo_sinistro))
    END AS tipo_sinistro,
    valor_pedido,
    CASE WHEN valor_pago < 0 THEN NULL ELSE valor_pago END AS valor_pago,
    CASE
        WHEN data_ocorrencia IS NULL THEN 'INCOSISTENTE: DATA NULA'
        WHEN data_ocorrencia = '0000-00-00' THEN 'INCOSISTENTE: DATA ZERADA'
        WHEN data_ocorrencia LIKE '____-__-__ %' AND date(substr(data_ocorrencia,1,10)) IS NOT NULL THEN date(substr(data_ocorrencia,1,10))
        WHEN data_ocorrencia LIKE '____-__-__'   AND date(data_ocorrencia) IS NOT NULL THEN date(data_ocorrencia)
        WHEN data_ocorrencia LIKE '__/__/____'   AND date(substr(data_ocorrencia,7,4)||'-'||substr(data_ocorrencia,4,2)||'-'||substr(data_ocorrencia,1,2)) IS NOT NULL THEN date(substr(data_ocorrencia,7,4)||'-'||substr(data_ocorrencia,4,2)||'-'||substr(data_ocorrencia,1,2))
        WHEN data_ocorrencia LIKE '__-__-____'   AND date(substr(data_ocorrencia,7,4)||'-'||substr(data_ocorrencia,4,2)||'-'||substr(data_ocorrencia,1,2)) IS NOT NULL THEN date(substr(data_ocorrencia,7,4)||'-'||substr(data_ocorrencia,4,2)||'-'||substr(data_ocorrencia,1,2))
        ELSE 'INCOSISTENTE: ' || data_ocorrencia
    END AS data_ocorrencia,
    CASE
        WHEN data_aviso IS NULL THEN 'INCOSISTENTE: DATA NULA'
        WHEN data_aviso = '0000-00-00' THEN 'INCOSISTENTE: DATA ZERADA'
        WHEN data_aviso LIKE '____-__-__ %' AND date(substr(data_aviso,1,10)) IS NOT NULL THEN date(substr(data_aviso,1,10))
        WHEN data_aviso LIKE '____-__-__'   AND date(data_aviso) IS NOT NULL THEN date(data_aviso)
        WHEN data_aviso LIKE '__/__/____'   AND date(substr(data_aviso,7,4)||'-'||substr(data_aviso,4,2)||'-'||substr(data_aviso,1,2)) IS NOT NULL THEN date(substr(data_aviso,7,4)||'-'||substr(data_aviso,4,2)||'-'||substr(data_aviso,1,2))
        WHEN data_aviso LIKE '__-__-____'   AND date(substr(data_aviso,7,4)||'-'||substr(data_aviso,4,2)||'-'||substr(data_aviso,1,2)) IS NOT NULL THEN date(substr(data_aviso,7,4)||'-'||substr(data_aviso,4,2)||'-'||substr(data_aviso,1,2))
        ELSE 'INCOSISTENTE: ' || data_aviso
    END AS data_aviso,
    CASE
        WHEN valor_pago < 0 THEN 'INCOSISTENTE: VALOR PAGO NEGATIVO'
        WHEN LOWER(TRIM(status_sinistro)) = 'pago'  AND valor_pago <= 1 THEN 'INCOSISTENTE: PAGO COM VALOR PAGO <= 1'
        WHEN LOWER(TRIM(status_sinistro)) != 'pago' AND valor_pago >  1 THEN 'INCOSISTENTE: NAO PAGO COM VALOR PAGO > 1'
        WHEN LOWER(TRIM(status_sinistro)) = 'em_analise' THEN 'EM ANALISE'
        WHEN LOWER(TRIM(status_sinistro)) = 'aberto'     THEN 'ABERTO'
        WHEN LOWER(TRIM(status_sinistro)) = 'pago'       THEN 'PAGO'
        WHEN LOWER(TRIM(status_sinistro)) = 'negado'     THEN 'NEGADO'
        ELSE UPPER(TRIM(status_sinistro))



    END AS status_sinistro,
    data_ingestao,
    ROW_NUMBER() OVER (PARTITION BY id_sinistro ORDER BY data_ingestao DESC) AS row_num
    FROM stg_sinistros_validados
)
SELECT
    id_sinistro,
    id_apolice,
    tipo_sinistro,
    valor_pedido,
    valor_pago,
    data_ocorrencia,
    data_aviso,
    status_sinistro,
    data_ingestao
FROM tratada_sinistros
WHERE row_num = 1;

DROP TABLE IF EXISTS silver_apolices;
CREATE TABLE silver_apolices AS
WITH tratada_apolice as(
SELECT
    id_apolice,
    id_segurado,
    CASE
        WHEN LOWER(TRIM(tipo)) IN ('auto')        THEN 'AUTO'
        WHEN LOWER(TRIM(tipo)) IN ('vida')        THEN 'VIDA'
        WHEN LOWER(TRIM(tipo)) IN ('residencial') THEN 'RESIDENCIAL'
        WHEN LOWER(TRIM(tipo)) IN ('empresarial') THEN 'EMPRESARIAL'
        ELSE UPPER(TRIM(tipo))
    END AS tipo,
    CASE WHEN premio_mensal <= 0 THEN NULL ELSE premio_mensal END AS premio_mensal,
    valor_segurado,
    CASE
        WHEN data_inicio LIKE '____-__-__ %' THEN date(substr(data_inicio,1,10))
        WHEN data_inicio LIKE '____-__-__'   THEN date(data_inicio)
        WHEN data_inicio LIKE '__/__/____'   THEN date(substr(data_inicio,7,4)||'-'||substr(data_inicio,4,2)||'-'||substr(data_inicio,1,2))
        WHEN data_inicio LIKE '__-__-____'   THEN date(substr(data_inicio,7,4)||'-'||substr(data_inicio,4,2)||'-'||substr(data_inicio,1,2))
        ELSE NULL
    END AS data_inicio,
    CASE
        WHEN data_fim LIKE '____-__-__ %' THEN date(substr(data_fim,1,10))
        WHEN data_fim LIKE '____-__-__'   THEN date(data_fim)
        WHEN data_fim LIKE '__/__/____'   THEN date(substr(data_fim,7,4)||'-'||substr(data_fim,4,2)||'-'||substr(data_fim,1,2))
        WHEN data_fim LIKE '__-__-____'   THEN date(substr(data_fim,7,4)||'-'||substr(data_fim,4,2)||'-'||substr(data_fim,1,2))
        ELSE NULL
    END AS data_fim,
    CASE
        WHEN LOWER(TRIM(status)) IN ('ativa','vigente') THEN 'ATIVA'
        WHEN LOWER(TRIM(status)) = 'cancelada'          THEN 'CANCELADA'
        WHEN LOWER(TRIM(status)) = 'suspensa'           THEN 'SUSPENSA'
        WHEN LOWER(TRIM(status)) = 'pendente'           THEN 'PENDENTE'
        ELSE UPPER(TRIM(status))
    END AS status,
    data_ingestao,
    ROW_NUMBER() OVER (PARTITION BY id_apolice ORDER BY data_ingestao DESC) AS row_num
    FROM stg_apolices_validadas
)
SELECT
    id_apolice,
    id_segurado,
    tipo,
    premio_mensal,
    valor_segurado,
    data_inicio,
    data_fim,
    status,
    data_ingestao
FROM tratada_apolice
WHERE row_num = 1;

SELECT * FROM silver_sinistros;
SELECT * FROM silver_apolices;

-- 1. View da Camada Silver (Visão Unificada de Sinistros + Apólices)
DROP VIEW IF EXISTS vw_silver_sinistros_completos;
CREATE VIEW vw_silver_sinistros_completos AS
SELECT 
    s.id_sinistro,
    s.id_apolice,
    a.id_segurado,
    a.tipo AS tipo_apolice,
    s.tipo_sinistro,
    s.valor_pedido,
    s.valor_pago,
    a.premio_mensal,
    a.valor_segurado,
    s.data_ocorrencia,
    s.data_aviso,
    s.status_sinistro,
    COALESCE(a.status, 'INCOSISTENTE: APOLICE NAO ENCONTRADA') AS status_apolice
FROM silver_sinistros s
LEFT JOIN silver_apolices a ON s.id_apolice = a.id_apolice;


-- 2. View da Camada Gold (KPIs de Sinistralidade para Negócio)
DROP VIEW IF EXISTS vw_gold_kpi_sinistralidade;
CREATE VIEW vw_gold_kpi_sinistralidade AS
SELECT 
    tipo_apolice,
    COUNT(DISTINCT id_apolice) AS total_apolices_com_sinistro,
    COUNT(DISTINCT id_sinistro) AS total_sinistros,
    ROUND(SUM(valor_pedido), 2) AS total_valor_pedido,
    ROUND(SUM(valor_pago), 2) AS total_valor_pago,
    ROUND(AVG(valor_pago), 2) AS ticket_medio_pago
FROM vw_silver_sinistros_completos
WHERE status_sinistro = 'PAGO'
GROUP BY tipo_apolice;

DROP TABLE IF EXISTS teste_datas;

