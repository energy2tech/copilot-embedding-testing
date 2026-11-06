# Databricks writes to a Fabric OneLake Lakehouse

This sample uses **Databricks compute as the sole data writer**. It writes Delta
tables physically into a normal Fabric Lakehouse, then exposes the same tables
to Databricks SQL through OneLake catalog federation. Fabric reads those same
Delta files through Spark or the Lakehouse SQL analytics endpoint. No replication,
ADLS shortcuts, copied Databricks tables, or substitute views are involved.

The Unity Catalog entries are **read-only foreign tables**. To modify their data,
run the Databricks writer against the OneLake path, not `INSERT` or `MERGE` against
the foreign table name. A writable Unity Catalog external-location design uses
an **Azure Databricks Storage** item instead; see the [parent sample](../README.md).

For a **one-time copy into native Databricks managed Delta tables followed by
Fabric metadata mirroring**, see the separate
[managed-table metadata-mirroring sample](../metadata-mirroring/README.md).
Its eight managed copies are verified; mirroring currently awaits metastore-admin
external-access enablement. The foreign tables in this sample are unchanged.

## Provisioned demo

- [Fabric workspace: contoso-mfg-demo](https://app.fabric.microsoft.com/groups/cb9f8a41-6acf-454f-a01d-b04576c90889/list), assigned to existing F64 capacity `f64centralus001`.
- [OneLake Lakehouse: manufacturing_lh](https://app.fabric.microsoft.com/groups/cb9f8a41-6acf-454f-a01d-b04576c90889/lakehouses/77aed7cf-0543-4aea-8a20-50aaa3a8f5f0).
- [Unity Catalog: contoso_mfg_onelake](https://adb-7405616494524712.12.azuredatabricks.net/explore/data/contoso_mfg_onelake?o=7405616494524712).
- Databricks writer notebook: `/Shared/contoso-mfg-customer-orders/write_onelake`.

The Databricks writer verified every persisted row. **Unity Catalog and Fabric
SQL reads are verified:** all eight result sets match, including all table counts
(**9,323 rows**), the order amount **2,738,129.00**, ordered quantity **70,270**,
and shipped quantity **49,213**. A fresh Databricks-written customer update was
visible through both SQL engines. The original value was restored, every persisted
row was checked by the writer, and all eight SQL comparisons passed again. All
eight foreign table entries have the expected OneLake locations.

The OneLake SAS HTTP 401 was resolved by inspecting the actual demo workspace:
**Workspace settings > Delegated Settings > OneLake settings > Authenticate with
OneLake user-delegated SAS tokens** was **Off**. Turning it **On** and confirming
the workspace scope resolved both fresh SAS reads (HTTP 200) and existing Unity
Catalog SQL reads. No tenant-wide policy change, wider reader permissions, catalog
recreation, or data-copy workaround was needed.

The dedicated demo writer credential expires **December 5, 2026 (UTC)**; rotate
or remove it as appropriate. Its secret is stored only in Databricks secrets.

To query the shared customer table in Databricks (expected count: **100**):

```sql
SELECT COUNT(*)
FROM contoso_mfg_onelake.manufacturing_demo.customers;
```

Run the complete cross-engine comparison:

```powershell
python samples\manufacturing-onelake\customer-orders\verify_shared_data.py `
  --profile contoso-mfg-demo `
  --warehouse-id 26fbcb4ef42cecd7 `
  --fabric-server 36x52ikao44ujg2kmjdic6zn7q-igfj7s6pnjhulia5wbcxnsiire.datawarehouse.fabric.microsoft.com
```

The existing SQL warehouse retains its 10-minute idle auto-stop. The F64 capacity
was not paused or replaced.

## Tables

Fabric and Unity Catalog both expose the `manufacturing_demo` schema.

| Table | Rows |
| --- | ---: |
| customers | 100 |
| products | 20 |
| plants | 3 |
| sales_orders | 1,000 |
| sales_order_lines | 3,000 |
| work_orders | 2,000 |
| shipments | 800 |
| shipment_lines | 2,400 |
| **Total** | **9,323** |

Names and records are entirely fictional. Generation uses seed 42, fixed dates
starting July 1, 2026, integer quantities, and decimal prices/amounts. There are
600 fulfilled orders, 200 partially fulfilled orders, and 200 open orders.
Each order has three lines. Work orders represent a subset of production demand;
some shipment demand can be met from stock rather than a work order in this sample.

## Prerequisites and permissions

- An approved Fabric workspace on an existing active capacity and a **schema-enabled**
  Lakehouse. Create these only after checking name collisions and capacity permissions.
- An authenticated, explicitly selected Databricks CLI profile and Unity Catalog
  privileges to create storage credentials, connections, and foreign catalogs.
- Supported Databricks serverless notebook compute. The notebook uses the documented
  MSAL/`deltalake` alternative because serverless cannot set custom `fs.azure.*`
  Spark properties. Dependencies are declared in [requirements.txt](requirements.txt).
- A writer Entra service principal with Contributor access to the **dedicated demo
  workspace**, not unrelated workspaces. Store its `tenant-id`, `client-id`, and
  `client-secret` in the Databricks secret scope `contoso-mfg-onelake`. Restrict scope
  access to the operator; never grant all workspace users secret access.
- A separate read identity, preferably an existing Access Connector managed identity:
  workspace Viewer plus a Lakehouse-scoped OneLake `Read` role. Preserve existing
  OneLake roles. Create a read-only Unity Catalog storage credential named
  `contoso_mfg_onelake_read_credential` for it.
- OneLake federation-compatible query compute (DBR 18.0+ standard access mode or
  SQL warehouse 2025.40+) and the documented Fabric tenant/workspace settings:
  service principal public API access, external OneLake access, user-delegated SAS,
  and workspace user-delegated SAS authentication. Obtain administrator action if
  required; do not silently change tenant-wide settings.
  In the actual target workspace's **Delegated Settings > OneLake settings**, turn
  **Authenticate with OneLake user-delegated SAS tokens** **On**, confirm **The
  entire workspace users**, and verify the saved state says **On** and **Enabled
  for all users**. If the UI instead shows **Override tenant admin selection**,
  select it before enabling and applying the setting. Verify an actual SQL data
  read, not only visible table metadata.

Do not enable metastore-wide external data access for this inbound federation
scenario merely because the separate outbound mirroring sample requires it.
Do not assume compute that supports federation also supports direct ABFS writes.

## Execution

1. Assign the dedicated workspace to the approved existing capacity and verify
   the persisted capacity ID. Create `manufacturing_lh` with `enableSchemas=true`.
2. Import [fabric_schema.ipynb](fabric_schema.ipynb) into Fabric, bind its default
   Lakehouse to `manufacturing_lh`, and run it **once**. It creates only schema
   metadata, never sample rows. `CREATE SCHEMA` intentionally fails on a collision.
   Verify the schema's location uses `Tables/manufacturing_demo`.
3. Configure the writer secrets and reader permissions described above.
4. Upload [sample_data.py](sample_data.py) and [requirements.txt](requirements.txt)
   as **raw workspace files** under `/Shared/contoso-mfg-customer-orders`.
   Import [write_onelake.py](write_onelake.py) there as a Python source notebook.
   This fixed workspace folder keeps module imports and `%pip` paths consistent.
5. Run the Databricks notebook on serverless with `workspace_id` and `lakehouse_id`
   set to the discovered Fabric GUIDs, and `operation=load`. The ID-based table path is:

   ```text
   abfss://<workspace-id>@onelake.dfs.fabric.microsoft.com/<lakehouse-id>/Tables/manufacturing_demo/<table>
   ```

   Verify this matches the Lakehouse's returned OneLake path and schema metadata.
   The notebook authenticates using secrets, preflights **all** target folders,
   refuses existing targets, writes Delta with explicit Arrow schemas, and compares
   every persisted row with the deterministic input.
6. Confirm all eight tables appear in Fabric and its SQL analytics endpoint.
   Use [setup.sql](setup.sql), replacing its GUID placeholders, to create the
   OneLake connection and `contoso_mfg_onelake` foreign catalog. Existing names
   deliberately fail rather than being overwritten.
7. In Databricks Catalog Explorer, verify:

   ```text
   contoso_mfg_onelake
     manufacturing_demo
       customers
       products
       plants
       sales_orders
       sales_order_lines
       work_orders
       shipments
       shipment_lines
   ```

8. Run [validate.sql](validate.sql) in both engines (select the foreign catalog
   in Databricks and the Lakehouse database in Fabric). Compare counts, exact
   decimal/quantity totals, customer sales, plant demand, and backlog.
9. Run the Databricks writer with `operation=probe`. This changes only customer 1
   to `Fictional Customer 001 - verified`. Query the customer through both Unity
   Catalog and Fabric SQL to prove shared-file visibility. Then run `operation=restore`,
   query both readers again, and use `operation=verify` to confirm all original rows.
   Allow documented metadata/cache synchronization before comparing fresh reads.

### Fabric SQL synchronization after a write

The Fabric SQL analytics endpoint can lag behind a successful Databricks write.
During the verified probe, Unity Catalog saw the new customer name while Fabric
SQL still returned the old name. A scoped
[SQL endpoint metadata refresh](https://learn.microsoft.com/rest/api/fabric/sqlendpoint/items/refresh-sql-endpoint-metadata)
resolved this without changing or copying the Delta data:

```http
POST https://api.fabric.microsoft.com/v1/workspaces/<workspace-id>/sqlEndpoints/<sql-endpoint-id>/refreshMetadata
Content-Type: application/json

{
  "recreateTables": false,
  "tables": [
    {"schema": "manufacturing_demo", "tableNames": ["customers"]}
  ]
}
```

Use the SQL analytics endpoint ID, not the Lakehouse ID. Authenticate with an
authorized Fabric token; the API requires Contributor or higher and, for delegated
authentication, `Item.ReadWrite.All`. Check the returned table sync status. For
HTTP 202, follow the documented long-running operation until completion before
rerunning the comparison. The same scoped refresh was used after restoring the
original customer name. Do not reload data or recreate tables to bypass sync lag.

## Safety and operations

- Never enable simultaneous writers from Fabric and Databricks on these paths.
- `load` refuses every existing target, including non-Delta folders. A partial
  failure is not automatically retried or overwritten. Inspect partial results
  before deciding how to recover.
- `verify` performs reads only. `probe` and `restore` require this sample's Delta
  description marker and the expected original/probe customer value.
- Do not delete unknown tables or schemas, provision extra capacities, or run the
  parent sample's infrastructure template.
- Notebook jobs and SQL queries consume compute. Use existing approved resources,
  avoid duplicate runs, and stop only task-owned idle compute. Cross-region
  Databricks/OneLake access may add latency and transfer charges.
- Demo writer credentials should be short-lived. Rotate before expiration or
  remove the dedicated app credential after the demo. Never place secrets in
  notebook code, request files, logs, or this repository.
- A successful notebook upload is not a successful load. Verify actual persisted
  counts, Delta paths, Fabric SQL visibility, and Unity Catalog table entries.

## Local validation

From the repository root:

```powershell
python -m unittest discover -s samples\manufacturing-onelake\customer-orders -p test_sample_data.py -v
```

These standard-library tests validate counts, determinism, keys, prices, quantities,
shipment/order relationships, dates, and fulfillment status without cloud compute.
They do not substitute for remote two-engine verification.

For automated remote SQL comparison, install
[requirements-validation.txt](requirements-validation.txt) and Microsoft ODBC
Driver 18 for SQL Server. Run [verify_shared_data.py](verify_shared_data.py) with
`--profile`, `--warehouse-id`, and `--fabric-server` for your approved environment.
It uses Azure CLI authentication for Fabric SQL, executes all queries against
both engines, compares every result row, and checks exact expected aggregates.
Use `--databricks-cli` if the executable is not on PATH.

The verifier also accepts `--catalog` and `--schema` for the managed-copy demo,
and `--full-tables` to compare every row of all eight tables. Defaults preserve
this original foreign-table demo.

## Official integration references

- [Databricks direct writes to a OneLake Lakehouse](https://learn.microsoft.com/fabric/onelake/onelake-azure-databricks)
- [OneLake catalog federation](https://learn.microsoft.com/azure/databricks/query-federation/onelake)
- [Lakehouse schemas](https://learn.microsoft.com/fabric/data-engineering/lakehouse-schemas)
