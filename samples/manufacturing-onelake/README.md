# Manufacturing on OneLake, governed from Databricks

For **Databricks writes into an ordinary Fabric Lakehouse**, with the same files
queried from Fabric and Unity Catalog foreign tables, use the separate
[customer/order sample](customer-orders/README.md). The architecture and status
below refer only to this original Azure Databricks Storage item sample.

For a **one-time foreign-to-managed Delta copy using existing native ADLS storage
and then Fabric metadata mirroring**, see
[the metadata-mirroring sample](metadata-mirroring/README.md). Its eight managed
tables are loaded and validated; Fabric mirror creation is blocked until a
metastore administrator enables external data access. This is separate from
both the original Databricks Storage design below and direct OneLake writes.

Fictional Contoso Precision Manufacturing: three plants, 24 machines, 12 products,
and 90 days (2026-07-01 through 2026-09-28). Eight tables contain exactly 100,089
rows: 129 dimension rows and 99,960 fact rows. No real customer information.

**Integration is not complete.** The dedicated Premium Databricks workspace and
access connector have been provisioned. The workspace API still reports
"Did not find workspace with specified org ID" after the user reported completing
onboarding; browser launch redirects to signup. Authenticated readiness remains
blocked and needs Azure/Databricks administrator investigation. No compute was
started by these assets; running compute could not be independently enumerated
while the API is inaccessible. No sample tables have been created remotely.
Eligible Fabric capacity remains unresolved.

## Architecture

Databricks creates Unity Catalog managed Delta tables physically inside an
**Azure Databricks Storage** item in OneLake. This is not an ordinary Lakehouse
with directly readable files. Its OneLake security role admits only the
Databricks storage identity. Tables are separately published from Databricks
Catalog Explorer to a Fabric mirrored catalog for read-only consumption.

Both [OneLake external locations](https://learn.microsoft.com/azure/databricks/connect/unity-catalog/cloud-storage/external-locations-onelake)
and [Publish to OneLake](https://learn.microsoft.com/azure/databricks/partners/bi/fabric-publish)
are public previews. Verify availability in the actual environment.

There is no assumed per-table "Visible in Fabric" property. Publication plus
Unity Catalog privileges govern what the Fabric connection identity can access.
Fabric consumer permissions are separate. A metastore-wide external-access
switch is not a per-table switch. Do not disable a shared metastore for this demo.

## Prerequisite gate

Before creating anything, verify:

1. An existing Unity Catalog-enabled Azure Databricks workspace and an explicitly
   selected authentication profile. The standalone Databricks CLI is different
   from the Azure CLI `databricks` extension. Do not select a profile implicitly.
2. Serverless compute or Runtime 18.1+, preview availability, and approval for
   compute consumption. Do not create paid compute or capacity.
3. An active Fabric capacity that supports the feature and region. West Central
   US was not listed in the [mirroring regions](https://learn.microsoft.com/fabric/mirroring/azure-databricks-limitations)
   checked during planning; do not assume the discovered trial is eligible.
4. Fabric tenant setting **Users can create Azure Databricks Storage items**
   and workspace setting **Authenticate with OneLake user-delegated SAS tokens**.
5. Administrative approval to enable metastore external data access if currently
   disabled; catalog-owner approval for `EXTERNAL USE SCHEMA`; privileges to
   create storage credentials, external locations, and managed storage.
6. An existing access connector managed identity, preferably, for storage; and
   a distinct Entra/Databricks identity for the Fabric connection. Never commit
   credentials or paste secrets into notebook source.

Stop if any gate fails. Do not substitute direct Lakehouse writes, ADLS storage,
or replication: those do not demonstrate the same storage/governance boundary.

## Optional Azure resource provisioning

[infra/main.json](infra/main.json) provisions a dedicated resource group, Premium
Databricks workspace, and system-assigned managed-identity Access Connector.
It also causes Databricks to create its service-managed resource group and
supporting storage/network infrastructure. Those resources can incur charges.
In particular, service-created NAT gateways and public IPs can incur charges
even without running Databricks compute.
No clusters, jobs, SQL warehouses, or Fabric capacities are declared or started.
Public workspace access uses Entra authentication; secure cluster connectivity
is enabled for future approved classic compute.

Only deploy after subscription, region, cost scope, name availability, and ARM
validation/what-if approval. From the repository root, using the explicitly
approved subscription:

```powershell
az deployment sub validate --subscription <subscription-id> --location eastus2 --template-file samples\manufacturing-onelake\infra\main.json
az deployment sub what-if --subscription <subscription-id> --location eastus2 --template-file samples\manufacturing-onelake\infra\main.json
az deployment sub create --subscription <subscription-id> --name contoso-mfg-databricks-demo --location eastus2 --template-file samples\manufacturing-onelake\infra\main.json
```

These are real provisioning commands, not local tests. Do not run `create` merely
to validate the template. The template outputs the workspace URL, resource IDs,
and connector principal ID; it does not automatically configure Unity Catalog,
OneLake security, previews, or Fabric connections.

## Names and configuration

| Resource | Name |
| --- | --- |
| Fabric workspace | Contoso Manufacturing - Databricks Governance Demo |
| Storage item | contoso_mfg_dbx_storage |
| Storage credential | contoso_mfg_onelake_credential |
| External location | contoso_mfg_onelake_location |
| Catalog | contoso_mfg_onelake_demo |
| Schema | manufacturing |
| Fabric connection | contoso_mfg_databricks_connection |
| Published catalog | contoso_mfg_published |

Use the fixed catalog/schema names only in a dedicated demo environment. If they
exist, inspect them and stop rather than overwriting unknown assets. Any name
change must be applied consistently to the notebook and SQL files.

Record the actual workspace URL, profile, capacity ID/region, Fabric workspace
ID, storage item ID, and identity application/access-connector IDs in your
private execution notes. All scripts contain placeholders or notebook inputs,
not environment-specific credentials.

## 1. Configure the storage boundary

Follow the [official external-location procedure](https://learn.microsoft.com/azure/databricks/connect/unity-catalog/cloud-storage/external-locations-onelake):

1. Create the dedicated Fabric workspace, assign the approved existing capacity,
   and create an **Azure Databricks Storage** item.
2. Give the storage managed identity workspace **Viewer** access. In the storage
   item's **Manage OneLake security**, create a **ReadWrite** role with **only
   that identity**. Do not add human readers or the publication/connection
   identity. Workspace roles alone do not unlock this storage item.
3. In Databricks Catalog Explorer, create the managed-identity storage credential
   referencing the existing access connector.
4. Create an external location with storage type **OneLake**, that credential,
   and the ID-based URL:

   ```text
   abfss://<workspace-id>@onelake.dfs.fabric.microsoft.com/<storage-item-id>/Files/
   ```

5. Test the connection. In Databricks, replace the two GUID placeholders in
   [setup.sql](setup.sql), review the managed path, and run it.

Some preview operations require the portal. These assets do not assume an
undocumented API can provision or publish the preview.

## 2. Generate and validate tables

Keep [sample_data.py](sample_data.py) alongside the notebook as a Databricks
workspace file (for example, in the same Git folder). Import
[generate_notebook.py](generate_notebook.py) as a Databricks Python source
notebook, not as a plain job script. Its sibling module must be importable.
Attach approved compute, enter the actual storage workspace/item GUIDs, and run.

The notebook:

- Validates the complete deterministic dataset before writing.
- Requires the expected OneLake managed catalog location.
- Creates ordinary managed Delta tables with explicit schemas and UTC timestamps.
- Checks actual table locations and exact persisted counts.
- Refuses existing tables by default.
- Allows an explicit `reset_demo_tables=true` only for tables bearing the exact
  demo ownership marker and residing under the expected OneLake storage root.

Reset drops only the eight known tables, then regenerates them. It is not
transactional across tables; failed runs can leave a partial dataset. Rerun with
explicit reset after investigation. Reset also removes grants on dropped tables;
reapply the reviewed permissions afterward. Do not run reset concurrently.

| Table | Rows |
| --- | ---: |
| dim_plant | 3 |
| dim_machine | 24 |
| dim_product | 12 |
| dim_date | 90 |
| fact_work_order | 2,160 |
| fact_production | 64,800 |
| fact_quality_inspection | 30,000 |
| fact_downtime | 3,000 |

Run the dependency-free local generator tests from this repository's root:

```powershell
python -B -m unittest discover -s samples\manufacturing-onelake -p "test_*.py" -v
python -B samples\manufacturing-onelake\sample_data.py
```

These prove sample generation, exact counts, keys, quantities, event windows,
inspection flags, downtime nonoverlap, and reproducibility. They do **not** prove
remote Spark execution, preview eligibility, physical storage, or Fabric access.

## 3. Publish from Databricks

1. Inspect effective grants and group memberships for the dedicated connection
   identity. It must not inherit broad table SELECT or direct storage access.
2. Replace the application-ID placeholder in [permissions.sql](permissions.sql).
   Execute only its **INITIAL ENABLE** block, leaving quality inspections
   withheld. Do not execute the entire file at once.
3. In Fabric **Manage connections and gateways**, create an **Azure Databricks
   workspace** connection with the exact workspace URL and the intended identity.
   Configure credentials securely in the UI. The official publication workflow
   requires Contributor or higher for the publishing identity in the Fabric
   workspace; keep this distinct from ordinary demo readers.
4. In Databricks Catalog Explorer select the demo catalog, then **Share >
   Publish to OneLake**. Authenticate to Entra ID, choose the connection and
   workspace, and publish with display name `contoso_mfg_published`.
5. Open the Fabric mirrored catalog, inspect selected schemas/tables, and grant
   the intended Fabric readers only the required consumer permissions. Never
   unlock the storage item to resolve a mirror-access failure.

See the [publication walkthrough](https://learn.microsoft.com/azure/databricks/partners/bi/fabric-publish)
for exact permissions and preview UI. Fabric mirrors catalog metadata and reads
the same underlying data; these assets do not create a second data copy.

## 4. Acceptance and admin-control demonstration

Use a non-administrator Fabric test reader. Record timestamp, identity, selected
tables, refresh action, query result/error, and whether an existing session or
fresh session was used.

1. Before publication, confirm that reader cannot directly access the storage
   item. A successful administrator test is not a valid negative-access test.
2. After publication with quality withheld, test both table discovery and a
   query of `manufacturing.fact_quality_inspection`. Presence in metadata and
   successful data access are different outcomes.
3. Execute **ENABLE QUALITY** in [permissions.sql](permissions.sql). Refresh as
   needed and verify reads. Run [validate.sql](validate.sql) in the Fabric SQL
   endpoint and in Databricks after selecting the demo catalog. All counts must
   match, all `failures` values must be zero, and aggregates must match.
4. Execute **DISABLE QUALITY**. Test fresh reads and metadata separately, checking
   effective inherited grants. Record the observed delay. Short-lived credentials
   are refreshed hourly; do not promise instantaneous denial or disappearance.
   Agree a bounded expiry/refresh observation window before testing. If it is
   exceeded, report the test as failed/unverified rather than treating stale
   metadata as proof of enforcement.
5. Execute **RESTORE QUALITY** and verify reads return.
6. In Databricks, update one bounded row:

   ```sql
   UPDATE contoso_mfg_onelake_demo.manufacturing.fact_work_order
   SET planned_units = 3001 WHERE work_order_id = 1 AND planned_units = 3000;
   ```

   Query that row in Fabric until the change appears, recording delay, then
   restore `planned_units = 3000` for that same row and verify again.

Unity Catalog grants authorize the connection identity, not each downstream
Fabric user. [Fabric permissions](https://learn.microsoft.com/fabric/mirroring/azure-databricks-security)
must separately protect the published data. Independent direct-storage grants
bypass that control path and are intentionally excluded.

Fabric Spark reads are not part of this demo. Catalog commits can prevent them;
do not disable catalog commits automatically to make notebook access work.
No custom per-table flag, RLS/column masking demonstration, Power BI model/report,
continuous job, or embedding-app change is included.

## Cleanup

Review the resource/grant inventory first. Remove only this demo's mirrored item,
connection (if newly created and unused elsewhere), catalog/tables, external
location, credential, storage item, and dedicated workspace after explicit
approval. Preserve existing identities, access connectors, capacities, shared
metastore settings, and unrelated storage. No automatic broad-delete script is
provided.
