# Manufacturing managed tables and Databricks metadata mirroring

This sample snapshots the existing fictional manufacturing foreign tables into
**Databricks Unity Catalog managed Delta tables**, then uses **Fabric metadata
mirroring** to read those managed tables.

The snapshot is a one-time data copy. The subsequent Fabric metadata mirror uses
**Databricks shortcuts to the managed Delta files**, not another data replication
pipeline. Later foreign-source changes do not automatically refresh the copies.

## Current deployed state

**Managed copies are complete; Fabric mirroring is not yet configured.**

- [Databricks managed schema](https://adb-7405616494524712.12.azuredatabricks.net/explore/data/dbw_contoso_mfg_demo_eus2/manufacturing_managed_demo?o=7405616494524712)
- Destination: `dbw_contoso_mfg_demo_eus2.manufacturing_managed_demo`.
- Sources: `contoso_mfg_onelake.manufacturing_demo`, unchanged read-only foreign tables.
- Eight managed Delta tables, **9,323 rows**, on native ADLS managed storage.
- Source/copy column order, types, decimal precision/scale, and NOT NULL
  constraints match. Eight bidirectional `EXCEPT ALL` comparisons have zero
  differences; eight primary-key checks, eight foreign-key relationships and
  eight aggregate/join comparisons pass.
- See [actual copy evidence](copy-verification.json), including source and managed
  locations, actual counts, comparison results, and executed queries.
- Destination-only `USE_SCHEMA`, `SELECT`, and explicit `EXTERNAL_USE_SCHEMA`
  grants for the intended organizational principal were verified; the principal
  also has `USE_CATALOG`.
- Existing **f64centralus001** was resumed with permission and verified Active.
  It remains billable. Existing SQL warehouse retains 10-minute idle auto-stop.

### Remaining blocker

Metastore **metastore_azure_eastus2**, ID
`421b5c6c-9980-43d8-9d18-cafcdd0651be`, still reports
**`external_access_enabled: false`**.

The attempted enablement was rejected with **User is not a metastore admin**.
The user subsequently reported administrator enablement, but fresh CLI checks
still returned false for this exact metastore. No administrative identity
substitution or self-grant was attempted.

A metastore administrator must open **Catalog > gear > Metastore > Details >
External data access** in the selected Databricks workspace and enable it. This
is **not** Fabric's OneLake user-delegated SAS setting.

Verify before proceeding:

```powershell
databricks metastores summary --profile contoso-mfg-demo -o json
```

Only continue when this target metastore reports `external_access_enabled: true`.
The planned Fabric workspace, connection, and mirror have **not** been created;
the managed-update and automatic metadata-sync demonstrations have **not** run.
See [deployment status](deployment-status.json).

## Tables and baseline

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

Observed baseline order amount: **2,738,129.00**; ordered quantity: **70,270**;
shipped quantity: **49,213**. These are fictional records, not operational data.

Initial source reads failed while F64 was paused. After the authorized resume,
all eight tables and actual Delta reads became available. No source recreation,
data regeneration, or writer change was needed.

## Managed copy assets

[copy_managed.py](copy_managed.py) inspects all foreign Delta tables in the source
schema, refuses a populated destination, creates explicit managed Delta schemas,
and loads actual source rows. No `LOCATION`, external-table registration, cloning,
or `CREATE OR REPLACE` is used. It emits [copy_managed.sql](copy_managed.sql) and
[validate.sql](validate.sql).

For a new empty schema, first create it through an authorized principal:

```powershell
databricks schemas create manufacturing_managed_demo dbw_contoso_mfg_demo_eus2 --profile contoso-mfg-demo
python .\copy_managed.py --profile contoso-mfg-demo --warehouse 26fbcb4ef42cecd7
```

**The deployed schema already exists and is populated. Do not rerun its INSERTs.**
Instead, revalidate without writing:

```powershell
python .\copy_managed.py --profile contoso-mfg-demo --warehouse 26fbcb4ef42cecd7 --verify-only
```

Keep the source stable while snapshotting/comparing. Partial failures are explicit:
inspect existing tables and resolve the failed stage deliberately; the copier
does not silently skip or overwrite them. It rejects unsupported source types.

## Finish Fabric metadata mirroring after the admin gate

1. Confirm metastore external access and the actual Fabric connection principal's
   destination-only grants. Do not assume ownership or `ALL PRIVILEGES` includes
   `EXTERNAL_USE_SCHEMA`.
2. Create **Contoso Manufacturing - Databricks Metadata Mirroring Demo** and assign
   the existing **f64centralus001** capacity.
3. In Fabric, select **New item > Mirrored Azure Databricks catalog**.
4. Create **contoso_mfg_metadata_mirroring_connection** using **Organizational
   account**, signing into the selected Databricks workspace interactively.
5. Select native catalog `dbw_contoso_mfg_demo_eus2` and **only**
   `manufacturing_managed_demo`. Exclude `default`, unrelated schemas, and the
   original foreign tables. Keep future-table metadata sync enabled for this schema.
6. Create **contoso_mfg_managed_catalog_mirror**. Inspect the persisted selection,
   Databricks shortcuts, and generated SQL analytics endpoint.
7. Run [validate.sql](validate.sql) on that endpoint. For all table rows and all
   eight manufacturing aggregate/join result sets, reuse the shared verifier:

   ```powershell
   python ..\customer-orders\verify_shared_data.py `
     --profile contoso-mfg-demo `
     --warehouse-id 26fbcb4ef42cecd7 `
     --catalog dbw_contoso_mfg_demo_eus2 `
     --schema manufacturing_managed_demo `
     --fabric-server <new-mirror-sql-server> `
     --database contoso_mfg_managed_catalog_mirror `
     --full-tables
   ```

   Use the endpoint's actual returned database/server names, not an assumed
   connection string. Existing `pyodbc`, ODBC Driver 18 and Azure CLI provide
   authenticated SQL reads; no tokens are stored.

## Demo queries and reversible changes

Start with [validate.sql](validate.sql):

- Counts for each table and exact order/shipment totals.
- Orders grouped by fulfillment status.
- Order amount by customer and production quantity by plant.
- Ordered versus shipped quantity and backlog by order line.

Then run **individual statements** from [demo_changes.sql](demo_changes.sql),
not the entire file at once:

1. Confirm customer 1 is `Fictional Customer 001`.
2. Update only the managed copy to `Metadata Mirror Demo - Managed Update`.
3. Verify that Fabric SQL reads the updated value and the foreign original is
   unchanged. Propagation may take seconds to minutes.
4. Restore the original managed value and verify again.
5. Create and populate `metadata_sync_probe` in the managed schema. Verify it
   appears automatically in Fabric and returns the exact probe row without
   manually changing the mirror's table selection.
6. Drop only this known probe and verify automatic metadata removal. Leave all
   eight baseline managed tables.

Do not mark this demo complete from catalog metadata alone. Record actual query
results, shortcut source references, observed propagation, and restoration.

## Security, costs, and boundaries

- UC policies and permissions do not automatically propagate to Fabric. Configure
  Fabric permissions separately; the Databricks connection identity authorizes
  external reads.
- Lakehouse-federated source tables cannot themselves be mirrored; this sample
  first materializes real managed Delta copies.
- No new Azure resources, F64 capacity, SQL warehouse, continuous ingestion job,
  Databricks Storage item, or wider storage firewall change is included.
- Existing managed-copy storage, SQL queries, and resumed F64 incur costs.
  Do not pause a shared capacity or alter warehouse auto-stop automatically.
- Leave the metastore-wide switch and unrelated resources unchanged during
  cleanup. Any removal of baseline artifacts needs explicit approval.

## Local tests

```powershell
python -m unittest discover -s . -p "test_*.py" -v
```

These test managed DDL generation, schema preservation, storage/source separation,
and shared-verifier defaults and full-table mode. They are not Fabric proof.

**Validation performed:** 19 related unit tests passed. The updated shared
verifier also passed all 16 cross-engine comparisons on the **original**
OneLake/foreign-table demo, including every row from all eight source tables.
That regression check does not prove the still-uncreated managed-table mirror.

## References

- [Fabric metadata mirroring](https://learn.microsoft.com/fabric/mirroring/azure-databricks)
- [Configuration tutorial](https://learn.microsoft.com/fabric/mirroring/azure-databricks-tutorial)
- [External data access](https://learn.microsoft.com/azure/databricks/external-access/admin)
- [Limitations and supported regions](https://learn.microsoft.com/fabric/mirroring/azure-databricks-limitations)
- [Fabric security](https://learn.microsoft.com/fabric/mirroring/azure-databricks-security)
- [Original foreign-table demo](../customer-orders/README.md)
