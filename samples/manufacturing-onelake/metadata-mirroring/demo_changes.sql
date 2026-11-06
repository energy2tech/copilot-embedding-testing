-- Databricks SQL only. Verify the baseline value before updating.
SELECT customer_id, customer_name
FROM dbw_contoso_mfg_demo_eus2.manufacturing_managed_demo.customers
WHERE customer_id = 1;

UPDATE dbw_contoso_mfg_demo_eus2.manufacturing_managed_demo.customers
SET customer_name = 'Metadata Mirror Demo - Managed Update'
WHERE customer_id = 1 AND customer_name = 'Fictional Customer 001';

-- Fabric SQL: SELECT customer_id, customer_name FROM manufacturing_managed_demo.customers WHERE customer_id = 1;
-- Restore after verifying both the managed update and unchanged foreign original.
UPDATE dbw_contoso_mfg_demo_eus2.manufacturing_managed_demo.customers
SET customer_name = 'Fictional Customer 001'
WHERE customer_id = 1 AND customer_name = 'Metadata Mirror Demo - Managed Update';

-- Run separately: demonstrate automatic table metadata discovery in Fabric.
CREATE TABLE dbw_contoso_mfg_demo_eus2.manufacturing_managed_demo.metadata_sync_probe
(probe_id INT NOT NULL, description STRING NOT NULL) USING DELTA;

INSERT INTO dbw_contoso_mfg_demo_eus2.manufacturing_managed_demo.metadata_sync_probe
VALUES (1, 'Automatic metadata sync from Databricks managed storage');

-- After verifying Fabric discovery and exact row, remove only this demo probe.
DROP TABLE dbw_contoso_mfg_demo_eus2.manufacturing_managed_demo.metadata_sync_probe;
