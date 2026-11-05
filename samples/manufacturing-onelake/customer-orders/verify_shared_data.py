"""Compare the same read-only SQL queries through Fabric and Unity Catalog."""

import argparse
import hashlib
import json
import shutil
import struct
import subprocess
from decimal import Decimal, InvalidOperation
from pathlib import Path

import pyodbc

from sample_data import EXPECTED_COUNTS, generate, summary


def command(args):
    result = subprocess.run(args, capture_output=True, text=True)
    if result.returncode:
        details = result.stderr.strip()
        if not details and result.stdout.strip():
            response = json.loads(result.stdout)
            details = json.dumps([
                {"state": item.get("state"), "error": item.get("error")}
                for item in response if item.get("state") != "SUCCEEDED"
            ])
        raise RuntimeError(f"{args[0]} failed: {details}")
    return json.loads(result.stdout)


def normalize(value):
    if value is None:
        return None
    text = str(value)
    try:
        number = Decimal(text)
    except InvalidOperation:
        return text
    return str(number.normalize()) if number.is_finite() else text


def canonical(rows):
    return sorted(tuple(normalize(value) for value in row) for row in rows)


def verify(args):
    cli = shutil.which("databricks") or args.databricks_cli
    az = shutil.which("az")
    if not cli or not az:
        raise RuntimeError("Both Azure CLI and Databricks CLI are required")
    driver = "ODBC Driver 18 for SQL Server"
    if driver not in pyodbc.drivers():
        raise RuntimeError(f"{driver} is required")
    if any(character in args.fabric_server + args.database for character in ";{}"):
        raise ValueError("Invalid SQL connection target")
    source = Path(__file__).with_name("validate.sql").read_text()
    queries = [part.strip() for part in source.split(";") if part.strip()]
    foreign_queries = [
        query.replace("manufacturing_demo.", "contoso_mfg_onelake.manufacturing_demo.")
        for query in queries
    ]
    results = command([
        cli, "experimental", "aitools", "tools", "query",
        "--warehouse", args.warehouse_id, "--profile", args.profile,
        "--output", "json", "--", *foreign_queries,
    ])
    if len(results) != len(queries) or any(row["state"] != "SUCCEEDED" for row in results):
        raise RuntimeError("Databricks validation queries did not all succeed")
    access_token = command([
        az, "account", "get-access-token", "--resource", "https://database.windows.net/",
        "--query", "accessToken", "-o", "json",
    ])
    encoded = access_token.encode("utf-16-le")
    packed = struct.pack("<I", len(encoded)) + encoded
    connection_string = (
        f"Driver={{{driver}}};Server={args.fabric_server},1433;"
        f"Database={args.database};Encrypt=yes;TrustServerCertificate=no;"
    )
    snapshots = []
    with pyodbc.connect(connection_string, attrs_before={1256: packed}, timeout=30) as connection:
        connection.timeout = 120
        for index, (query, remote) in enumerate(zip(queries, results)):
            cursor = connection.cursor()
            cursor.execute(query)
            columns = [column[0].lower() for column in cursor.description]
            rows = cursor.fetchall()
            if columns != [column.lower() for column in remote["columns"]]:
                raise AssertionError(f"Query {index + 1}: column mismatch")
            actual = canonical(rows)
            if actual != canonical(remote["rows"]):
                raise AssertionError(f"Query {index + 1}: Fabric/Databricks row mismatch")
            snapshots.append({
                "query": index + 1, "rows": len(rows),
                "sha256": hashlib.sha256(json.dumps(actual).encode()).hexdigest(),
            })
    counts = {row[0]: int(row[1]) for row in results[0]["rows"]}
    expected = summary(generate())
    if counts != EXPECTED_COUNTS:
        raise AssertionError(f"Unexpected persisted counts: {counts}")
    quantity, amount = results[1]["rows"][0]
    if int(quantity) != expected["ordered_quantity"] or Decimal(str(amount)) != Decimal(expected["order_amount"]):
        raise AssertionError("Order aggregates differ from deterministic input")
    if int(results[2]["rows"][0][0]) != expected["shipped_quantity"]:
        raise AssertionError("Shipment aggregate differs from deterministic input")
    statuses = {row[0]: int(row[1]) for row in results[3]["rows"]}
    if statuses != expected["order_statuses"]:
        raise AssertionError("Order statuses differ from deterministic input")
    if canonical(results[7]["rows"]) != canonical([[1, args.expected_customer_name]]):
        raise AssertionError("Customer value does not match the requested probe/restore state")
    print(json.dumps({"counts": counts, "expected": expected, "comparisons": snapshots}, sort_keys=True))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", required=True)
    parser.add_argument("--warehouse-id", required=True)
    parser.add_argument("--fabric-server", required=True)
    parser.add_argument("--database", default="manufacturing_lh")
    parser.add_argument("--databricks-cli", help="Explicit CLI path if not on PATH")
    parser.add_argument("--expected-customer-name", default="Fictional Customer 001")
    verify(parser.parse_args())
