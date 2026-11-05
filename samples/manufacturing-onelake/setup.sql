-- Run in Databricks only after the README prerequisite and identity checks.
-- Create/test contoso_mfg_onelake_location in Catalog Explorer first.
-- Replace both GUID placeholders with the actual Azure Databricks Storage item IDs.
-- Deliberately fails rather than reusing an existing, possibly unrelated catalog.
CREATE CATALOG contoso_mfg_onelake_demo
MANAGED LOCATION 'abfss://<workspace-id>@onelake.dfs.fabric.microsoft.com/<storage-item-id>/Files/contoso_mfg_onelake_demo';

CREATE SCHEMA contoso_mfg_onelake_demo.manufacturing;
