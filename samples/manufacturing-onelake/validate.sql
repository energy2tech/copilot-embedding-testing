-- Fabric SQL analytics endpoint: use the schema names actually shown by the mirror.
-- Databricks: first USE CATALOG contoso_mfg_onelake_demo.
-- Run after all eight tables have been enabled and synchronized.
-- Each count must equal expected_rows.
SELECT 'dim_plant' AS table_name, COUNT(*) AS actual_rows, 3 AS expected_rows FROM manufacturing.dim_plant
UNION ALL SELECT 'dim_machine', COUNT(*), 24 FROM manufacturing.dim_machine
UNION ALL SELECT 'dim_product', COUNT(*), 12 FROM manufacturing.dim_product
UNION ALL SELECT 'dim_date', COUNT(*), 90 FROM manufacturing.dim_date
UNION ALL SELECT 'fact_work_order', COUNT(*), 2160 FROM manufacturing.fact_work_order
UNION ALL SELECT 'fact_production', COUNT(*), 64800 FROM manufacturing.fact_production
UNION ALL SELECT 'fact_quality_inspection', COUNT(*), 30000 FROM manufacturing.fact_quality_inspection
UNION ALL SELECT 'fact_downtime', COUNT(*), 3000 FROM manufacturing.fact_downtime;

-- Compare these aggregates between engines, not just row counts.
SELECT SUM(total_units) AS total_units, SUM(good_units) AS good_units,
       SUM(scrap_units) AS scrap_units
FROM manufacturing.fact_production;

SELECT COUNT(*) AS failures
FROM manufacturing.fact_production AS p
LEFT JOIN manufacturing.fact_work_order AS w ON w.work_order_id = p.work_order_id
WHERE w.work_order_id IS NULL OR p.good_units < 0 OR p.scrap_units < 0
   OR p.good_units + p.scrap_units <> p.total_units
   OR p.start_utc < w.start_utc OR p.end_utc > w.end_utc OR p.start_utc >= p.end_utc;

SELECT COUNT(*) AS failures
FROM manufacturing.fact_quality_inspection AS q
LEFT JOIN manufacturing.fact_work_order AS w ON w.work_order_id = q.work_order_id
WHERE w.work_order_id IS NULL OR q.inspected_utc < w.start_utc OR q.inspected_utc > w.end_utc
   OR (CAST(q.passed AS INT) = 1 AND (q.measurement < q.lower_limit OR q.measurement > q.upper_limit))
   OR (CAST(q.passed AS INT) = 0 AND q.measurement BETWEEN q.lower_limit AND q.upper_limit);

-- Yield by fictional plant; this is not full OEE.
SELECT d.plant_name, SUM(p.total_units) AS total_units, SUM(p.scrap_units) AS scrap_units,
       100.0 * SUM(p.good_units) / NULLIF(SUM(p.total_units), 0) AS yield_percent
FROM manufacturing.fact_production AS p
JOIN manufacturing.fact_work_order AS w ON w.work_order_id = p.work_order_id
JOIN manufacturing.dim_machine AS m ON m.machine_id = w.machine_id
JOIN manufacturing.dim_plant AS d ON d.plant_id = m.plant_id
GROUP BY d.plant_name;
