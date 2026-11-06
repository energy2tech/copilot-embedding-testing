"""Copy actual foreign-table rows into an empty native managed schema."""

import argparse
import json
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent / "customer-orders"))

from sample_data import PRIMARY_KEYS
from verify_shared_data import canonical, command


def identifier(name):
    if not isinstance(name, str) or not name or any(char in name for char in "\r\n\x00"):
        raise ValueError(f"Invalid identifier: {name!r}")
    return "`" + name.replace("`", "``") + "`"


def qualified(catalog, schema, table):
    return ".".join(identifier(part) for part in (catalog, schema, table))


def signature(table):
    return [(column["name"], column["type_text"].lower(), column["nullable"])
            for column in table["columns"]]


def create_sql(source, destination, table):
    columns = []
    for name, kind, nullable in signature(table):
        if not re.fullmatch(r"(int|bigint|smallint|tinyint|boolean|string|date|timestamp|"
                            r"float|double|decimal\(\d+,\d+\))", kind):
            raise ValueError(f"Unsupported source type for {table['name']}.{name}: {kind}")
        columns.append(f"    {identifier(name)} {kind.upper()}"
                       + ("" if nullable else " NOT NULL"))
    fields = ", ".join(identifier(column["name"]) for column in table["columns"])
    return [
        f"CREATE TABLE {destination} (\n" + ",\n".join(columns) + "\n) USING DELTA",
        f"INSERT INTO {destination} ({fields}) SELECT {fields} FROM {source}",
    ]


def query(cli, profile, warehouse, statements):
    if not statements:
        raise ValueError("No SQL statements supplied")
    sql = list(statements)
    if len(sql) == 1:
        sql.append("SELECT 1 AS execution_guard")
    result = command([cli, "experimental", "aitools", "tools", "query",
                      "--profile", profile, "--warehouse", warehouse,
                      "--output", "json", "--", *sql])
    if (not isinstance(result, list) or len(result) != len(sql)
            or any(item.get("state") != "SUCCEEDED" for item in result)):
        raise RuntimeError(f"SQL execution did not complete successfully: {result}")
    return result[:len(statements)]


def validate_location(source, destination):
    parsed = urlparse(destination["storage_location"])
    if (parsed.scheme != "abfss"
            or not parsed.hostname
            or not parsed.hostname.endswith(".dfs.core.windows.net")
            or destination["storage_location"] == source["storage_location"]):
        raise ValueError(f"Not a distinct native ADLS managed location: {parsed.geturl()}")
    if destination["table_type"] != "MANAGED" or destination["data_source_format"] != "DELTA":
        raise ValueError(f"Not a managed Delta table: {destination['full_name']}")


def run(args):
    cli = shutil.which("databricks")
    if not cli:
        raise RuntimeError("Databricks CLI is required")
    if (args.source_catalog, args.source_schema) == (args.catalog, args.schema):
        raise ValueError("Source and destination must differ")
    catalog = command([cli, "catalogs", "get", args.catalog,
                       "--profile", args.profile, "--output", "json"])
    if catalog["catalog_type"] != "MANAGED_CATALOG":
        raise ValueError("Destination must be a native managed catalog")
    source = command([cli, "tables", "list", args.source_catalog, args.source_schema,
                      "--profile", args.profile, "--output", "json"])
    if not source or len({table["name"] for table in source}) != len(source):
        raise ValueError("Source schema is empty or contains duplicate names")
    source.sort(key=lambda table: table["name"])
    if any(table["table_type"] != "FOREIGN" or table["data_source_format"] != "DELTA"
           for table in source):
        raise ValueError("Every source must be a foreign Delta table")
    existing = command([cli, "tables", "list", args.catalog, args.schema,
                        "--profile", args.profile, "--output", "json"])
    if existing and not args.verify_only:
        raise ValueError("Destination is not empty; refusing to overwrite or skip tables")
    source_names = {table["name"] for table in source}
    if args.verify_only and {table["name"] for table in existing} != source_names:
        raise ValueError("Destination table set does not match the complete source schema")
    ddl, inserts, diffs, counts, keys = [], [], [], [], []
    for table in source:
        name = table["name"]
        old = qualified(args.source_catalog, args.source_schema, name)
        new = qualified(args.catalog, args.schema, name)
        create, insert = create_sql(old, new, table)
        ddl.append(create)
        inserts.append(insert)
        diffs.append(f"SELECT '{name}' AS table_name, "
                     f"(SELECT COUNT(*) FROM (SELECT * FROM {old} EXCEPT ALL SELECT * FROM {new})) "
                     "AS source_only, "
                     f"(SELECT COUNT(*) FROM (SELECT * FROM {new} EXCEPT ALL SELECT * FROM {old})) "
                     "AS destination_only")
        counts.append(f"SELECT '{name}' AS table_name, COUNT(*) AS row_count FROM {new}")
        if name in PRIMARY_KEYS:
            key = identifier(PRIMARY_KEYS[name])
            keys.append(f"SELECT '{name}' AS table_name, COUNT(*) - COUNT(DISTINCT {key}) "
                        f"AS duplicate_or_null_keys FROM {new}")
    ROOT.joinpath("copy_managed.sql").write_text(
        "-- Requires an existing empty destination schema; never rerun INSERTs on populated tables.\n"
        + ";\n\n".join(ddl + inserts) + ";\n", encoding="utf-8")
    baseline_sql = (ROOT.parent / "customer-orders" / "validate.sql").read_text(encoding="utf-8")
    baseline_sql = "\n".join(line for line in baseline_sql.splitlines()
                             if not line.lstrip().startswith("--"))
    template = baseline_sql.replace("manufacturing_demo.", args.schema + ".")
    ROOT.joinpath("validate.sql").write_text(
        "-- Fabric SQL: run against the mirrored catalog endpoint.\n" + template, encoding="utf-8")
    baseline_queries = [sql.strip() for sql in baseline_sql.split(";") if sql.strip()]
    source_queries = [sql.replace("manufacturing_demo.",
                                  f"{identifier(args.source_catalog)}.{identifier(args.source_schema)}.")
                      for sql in baseline_queries]
    destination_queries = [sql.replace("manufacturing_demo.",
                                       f"{identifier(args.catalog)}.{identifier(args.schema)}.")
                           for sql in baseline_queries]
    before = query(cli, args.profile, args.warehouse, source_queries)
    if not args.verify_only:
        query(cli, args.profile, args.warehouse, ddl)
        query(cli, args.profile, args.warehouse, inserts)
    destination = command([cli, "tables", "list", args.catalog, args.schema,
                           "--profile", args.profile, "--output", "json"])
    mapped = {table["name"]: table for table in destination}
    if set(mapped) != source_names:
        raise ValueError("Destination must contain exactly the source table set")
    for table in source:
        target = mapped[table["name"]]
        validate_location(table, target)
        if signature(table) != signature(target):
            raise ValueError(f"Full source/destination schema mismatch: {table['name']}")
    differences = query(cli, args.profile, args.warehouse, diffs)
    for result in differences:
        if len(result["rows"]) != 1 or any(int(value) != 0 for value in result["rows"][0][1:]):
            raise ValueError(f"Duplicate-sensitive row comparison failed: {result}")
    key_results = query(cli, args.profile, args.warehouse, keys)
    if any(int(result["rows"][0][1]) != 0 for result in key_results):
        raise ValueError("Managed copies contain invalid primary keys")
    relationships = [
        ("sales_orders", "customer_id", "customers", "customer_id"),
        ("sales_order_lines", "order_id", "sales_orders", "order_id"),
        ("sales_order_lines", "product_id", "products", "product_id"),
        ("work_orders", "order_line_id", "sales_order_lines", "order_line_id"),
        ("work_orders", "plant_id", "plants", "plant_id"),
        ("shipments", "order_id", "sales_orders", "order_id"),
        ("shipment_lines", "shipment_id", "shipments", "shipment_id"),
        ("shipment_lines", "order_line_id", "sales_order_lines", "order_line_id"),
    ]
    relationship_queries = [
        f"SELECT COUNT(*) AS orphan_rows FROM {qualified(args.catalog, args.schema, child)} c "
        f"LEFT ANTI JOIN {qualified(args.catalog, args.schema, parent)} p "
        f"ON c.{identifier(child_key)} = p.{identifier(parent_key)}"
        for child, child_key, parent, parent_key in relationships
    ]
    relationship_results = query(cli, args.profile, args.warehouse, relationship_queries)
    if any(int(result["rows"][0][0]) != 0 for result in relationship_results):
        raise ValueError("Managed copies contain orphaned foreign keys")
    after = query(cli, args.profile, args.warehouse, source_queries)
    actual = query(cli, args.profile, args.warehouse, destination_queries)
    for original, refreshed, copied in zip(before, after, actual):
        if (original["columns"] != refreshed["columns"] or original["columns"] != copied["columns"]
                or canonical(original["rows"]) != canonical(refreshed["rows"])
                or canonical(original["rows"]) != canonical(copied["rows"])):
            raise ValueError("Source changed during copying or managed aggregate/join results differ")
    row_counts = query(cli, args.profile, args.warehouse, counts)
    evidence = {
        "verifiedAtUtc": datetime.now(timezone.utc).isoformat(),
        "sourceCatalog": args.source_catalog, "sourceSchema": args.source_schema,
        "managedCatalog": args.catalog, "managedSchema": args.schema,
        "scope": "Actual foreign rows copied to native managed Delta; Fabric mirroring verified separately",
        "tables": [{
            "name": table["name"], "columns": signature(table),
            "sourceType": table["table_type"], "sourceLocation": table["storage_location"],
            "managedType": mapped[table["name"]]["table_type"],
            "managedLocation": mapped[table["name"]]["storage_location"],
            "sourceOnlyRows": int(differences[index]["rows"][0][1]),
            "managedOnlyRows": int(differences[index]["rows"][0][2]),
            "rowCount": int(row_counts[index]["rows"][0][1]),
        } for index, table in enumerate(source)],
        "primaryKeyChecksPassed": len(key_results),
        "relationshipChecksPassed": len(relationship_results),
        "sourceStableDuringCopy": True,
        "aggregateAndJoinChecksPassed": len(actual),
        "validationQueries": actual,
    }
    args.output.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    print(f"PASS: {len(source)} managed tables; "
          f"{sum(table['rowCount'] for table in evidence['tables'])} rows; "
          f"full schemas, bidirectional EXCEPT ALL, {len(relationship_results)} relationships "
          f"and {len(actual)} aggregate/join checks")
    print(f"Saved {args.output}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", required=True)
    parser.add_argument("--warehouse", required=True)
    parser.add_argument("--source-catalog", default="contoso_mfg_onelake")
    parser.add_argument("--source-schema", default="manufacturing_demo")
    parser.add_argument("--catalog", default="dbw_contoso_mfg_demo_eus2")
    parser.add_argument("--schema", default="manufacturing_managed_demo")
    parser.add_argument("--verify-only", action="store_true")
    parser.add_argument("--output", type=Path, default=ROOT / "copy-verification.json")
    run(parser.parse_args())
