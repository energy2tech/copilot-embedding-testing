# Databricks notebook source
# MAGIC %pip install -r /Workspace/Shared/contoso-mfg-customer-orders/requirements.txt

# COMMAND ----------
dbutils.library.restartPython()

# COMMAND ----------
import json
import sys
from uuid import UUID

import pyarrow as pa
from deltalake import DeltaTable, write_deltalake
from msal import ConfidentialClientApplication

sys.path.insert(0, "/Workspace/Shared/contoso-mfg-customer-orders")
from sample_data import EXPECTED_COUNTS, SCHEMAS, generate, summary

dbutils.widgets.text("workspace_id", "")
dbutils.widgets.text("lakehouse_id", "")
dbutils.widgets.text("secret_scope", "contoso-mfg-onelake")
dbutils.widgets.dropdown("operation", "load", ["load", "verify", "probe", "restore"])

workspace_id = str(UUID(dbutils.widgets.get("workspace_id")))
lakehouse_id = str(UUID(dbutils.widgets.get("lakehouse_id")))
scope = dbutils.widgets.get("secret_scope")
operation = dbutils.widgets.get("operation")
schema_name = "manufacturing_demo"
root = f"abfss://{workspace_id}@onelake.dfs.fabric.microsoft.com/{lakehouse_id}/Tables"
tenant = dbutils.secrets.get(scope=scope, key="tenant-id")
client = ConfidentialClientApplication(
    dbutils.secrets.get(scope=scope, key="client-id"),
    authority=f"https://login.microsoftonline.com/{tenant}",
    client_credential=dbutils.secrets.get(scope=scope, key="client-secret"),
)


def storage_options():
    token = client.acquire_token_for_client(
        scopes=["https://onelake.fabric.microsoft.com/.default"]
    )
    if "access_token" not in token:
        raise RuntimeError(f"OneLake authentication failed: {token.get('error', 'unknown_error')}")
    return {"bearer_token": token["access_token"], "use_fabric_endpoint": "true"}


def path(name):
    return f"{root}/{schema_name}/{name}"


types = {
    "int": pa.int32(), "string": pa.string(), "date": pa.date32(),
    "decimal": pa.decimal128(12, 2),
}
data = generate()
marker = "contoso-mfg-customer-orders-v1-seed42"

if operation == "load":
    # Check every target before the first write, including non-Delta folders.
    from urllib.error import HTTPError
    from urllib.request import Request, urlopen

    for name in EXPECTED_COUNTS:
        url = (
            f"https://onelake.dfs.fabric.microsoft.com/{workspace_id}/"
            f"{lakehouse_id}/Tables/{schema_name}/{name}?action=getStatus"
        )
        try:
            with urlopen(Request(url, method="HEAD", headers={
                "Authorization": f"Bearer {storage_options()['bearer_token']}",
                "x-ms-version": "2023-11-03",
            })):
                raise ValueError(f"Refusing existing target: {name}")
        except HTTPError as error:
            if error.code != 404:
                raise RuntimeError(f"Target preflight failed for {name}: HTTP {error.code}") from error
    for name, rows in data.items():
        arrow_schema = pa.schema([
            pa.field(column, types[kind], nullable=False)
            for column, kind in SCHEMAS[name]
        ])
        write_deltalake(
            path(name), pa.Table.from_pylist(rows, schema=arrow_schema),
            mode="error", storage_options=storage_options(),
            description=marker,
        )
elif operation in ("probe", "restore"):
    table = DeltaTable(path("customers"), storage_options=storage_options())
    if table.metadata().description != marker:
        raise ValueError("Refusing to update an unowned table")
    expected_name = "Fictional Customer 001"
    original = table.to_pyarrow_table().to_pylist()
    current = next(row["customer_name"] for row in original if row["customer_id"] == 1)
    allowed = (expected_name,) if operation == "probe" else (expected_name + " - verified",)
    if current not in allowed:
        raise ValueError("Probe customer is not in the expected state")
    replacement = expected_name + " - verified" if operation == "probe" else expected_name
    table.update(predicate="customer_id = 1", new_values={"customer_name": replacement})

actual = {}
for name in EXPECTED_COUNTS:
    table = DeltaTable(path(name), storage_options=storage_options())
    if table.metadata().description != marker:
        raise ValueError(f"Unexpected ownership marker: {name}")
    rows = table.to_pyarrow_table().to_pylist()
    if operation == "probe" and name == "customers":
        rows = [
            {**row, "customer_name": "Fictional Customer 001"}
            if row["customer_id"] == 1 else row for row in rows
        ]
    key = SCHEMAS[name][0][0]
    if sorted(rows, key=lambda row: row[key]) != sorted(data[name], key=lambda row: row[key]):
        raise ValueError(f"Persisted values differ from deterministic input: {name}")
    actual[name] = len(rows)
    print(f"{name}: {len(rows)} rows; OneLake Delta version {table.version()}")

result = {"operation": operation, "counts": actual, "expected": summary(data)}
print(json.dumps(result, sort_keys=True))
dbutils.notebook.exit(json.dumps(result, sort_keys=True))
