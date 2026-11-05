# Databricks notebook source
# COMMAND ----------
from uuid import UUID

from sample_data import EXPECTED_COUNTS, SCHEMAS, fingerprint, generate, validate

dbutils.widgets.text("storage_workspace_id", "")
dbutils.widgets.text("storage_item_id", "")
dbutils.widgets.dropdown("reset_demo_tables", "false", ["false", "true"])

workspace_id = str(UUID(dbutils.widgets.get("storage_workspace_id")))
item_id = str(UUID(dbutils.widgets.get("storage_item_id")))
storage_root = f"abfss://{workspace_id}@onelake.dfs.fabric.microsoft.com/{item_id}/Files/"
catalog = "contoso_mfg_onelake_demo"
schema = f"{catalog}.manufacturing"
ownership_marker = "Contoso manufacturing OneLake demo; synthetic data; seed=42"

spark.conf.set("spark.sql.session.timeZone", "UTC")
data = generate()
validate(data)
spark.sql(f"DESCRIBE SCHEMA {schema}").collect()
catalog_details = spark.sql(f"DESCRIBE CATALOG EXTENDED {catalog}").collect()
if not any(storage_root.lower() in str(row).lower() for row in catalog_details):
    raise ValueError("Catalog metadata does not identify the expected OneLake managed storage root")

# COMMAND ----------
existing = []
for name in EXPECTED_COUNTS:
    full_name = f"{schema}.{name}"
    if spark.catalog.tableExists(full_name):
        detail = spark.sql(f"DESCRIBE DETAIL {full_name}").first().asDict()
        if (detail["properties"].get("manufacturing_demo.owner") != ownership_marker
                or not detail["location"].lower().startswith(storage_root.lower())):
            raise ValueError(f"Refusing to replace unowned or unexpected table: {full_name}")
        existing.append(full_name)

if existing and dbutils.widgets.get("reset_demo_tables") != "true":
    raise ValueError("Demo tables already exist. Review them, then explicitly enable reset_demo_tables.")

for full_name in existing:
    spark.sql(f"DROP TABLE {full_name}")

# COMMAND ----------
for name, rows in data._asdict().items():
    full_name = f"{schema}.{name}"
    frame = spark.createDataFrame([tuple(row) for row in rows], schema=SCHEMAS[name])
    frame.write.format("delta").mode("errorifexists").saveAsTable(full_name)
    spark.sql(
        f"ALTER TABLE {full_name} SET TBLPROPERTIES "
        f"('manufacturing_demo.owner' = '{ownership_marker}')"
    )
    detail = spark.sql(f"DESCRIBE DETAIL {full_name}").first().asDict()
    if not detail["location"].lower().startswith(storage_root.lower()):
        raise ValueError(f"Table is not physically in the intended OneLake storage item: {full_name}")
    actual = spark.table(full_name).count()
    if actual != EXPECTED_COUNTS[name]:
        raise ValueError(f"{full_name}: expected {EXPECTED_COUNTS[name]}, got {actual}")
    print(f"{full_name}: {actual} rows; verified OneLake location")

print(f"Generation complete. Local dataset SHA-256: {fingerprint(data)}")
