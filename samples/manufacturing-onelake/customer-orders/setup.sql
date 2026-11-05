-- Create the read-only managed-identity storage credential in Catalog Explorer
-- or with `databricks storage-credentials create` before running this file.
-- Replace both GUID placeholders. Fail rather than reuse unknown objects.
CREATE CONNECTION contoso_mfg_onelake_connection TYPE onelake
OPTIONS (
  workspace '<fabric-workspace-id>',
  credential 'contoso_mfg_onelake_read_credential'
);

CREATE FOREIGN CATALOG contoso_mfg_onelake
USING CONNECTION contoso_mfg_onelake_connection
OPTIONS (
  data_item '<lakehouse-id>',
  item_type 'Lakehouse',
  create_volume_for_lakehouse_files 'false'
);
