-- Fabric: run in the manufacturing_lh SQL endpoint.
-- Databricks: select contoso_mfg_onelake as the current catalog first.
SELECT 'customers' AS table_name, COUNT(*) AS row_count FROM manufacturing_demo.customers
UNION ALL SELECT 'products', COUNT(*) FROM manufacturing_demo.products
UNION ALL SELECT 'plants', COUNT(*) FROM manufacturing_demo.plants
UNION ALL SELECT 'sales_orders', COUNT(*) FROM manufacturing_demo.sales_orders
UNION ALL SELECT 'sales_order_lines', COUNT(*) FROM manufacturing_demo.sales_order_lines
UNION ALL SELECT 'work_orders', COUNT(*) FROM manufacturing_demo.work_orders
UNION ALL SELECT 'shipments', COUNT(*) FROM manufacturing_demo.shipments
UNION ALL SELECT 'shipment_lines', COUNT(*) FROM manufacturing_demo.shipment_lines;

SELECT
    SUM(ordered_quantity) AS ordered_quantity,
    SUM(line_amount) AS order_amount
FROM manufacturing_demo.sales_order_lines;

SELECT SUM(shipped_quantity) AS shipped_quantity
FROM manufacturing_demo.shipment_lines;

SELECT status, COUNT(*) AS order_count
FROM manufacturing_demo.sales_orders
GROUP BY status
ORDER BY status;

SELECT c.customer_id, c.customer_name, SUM(l.line_amount) AS order_amount
FROM manufacturing_demo.customers c
JOIN manufacturing_demo.sales_orders o ON o.customer_id = c.customer_id
JOIN manufacturing_demo.sales_order_lines l ON l.order_id = o.order_id
GROUP BY c.customer_id, c.customer_name
ORDER BY c.customer_id;

SELECT p.plant_id, p.plant_name,
       SUM(w.planned_quantity) AS planned_quantity,
       SUM(w.produced_quantity) AS produced_quantity
FROM manufacturing_demo.plants p
JOIN manufacturing_demo.work_orders w ON w.plant_id = p.plant_id
GROUP BY p.plant_id, p.plant_name
ORDER BY p.plant_id;

SELECT l.order_line_id, l.ordered_quantity,
       COALESCE(s.shipped_quantity, 0) AS shipped_quantity,
       l.ordered_quantity - COALESCE(s.shipped_quantity, 0) AS backlog_quantity
FROM manufacturing_demo.sales_order_lines l
LEFT JOIN (
    SELECT order_line_id, SUM(shipped_quantity) AS shipped_quantity
    FROM manufacturing_demo.shipment_lines
    GROUP BY order_line_id
) s ON s.order_line_id = l.order_line_id
ORDER BY l.order_line_id;

SELECT customer_id, customer_name
FROM manufacturing_demo.customers
WHERE customer_id = 1;
