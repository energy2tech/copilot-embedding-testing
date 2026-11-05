"""Deterministic fictional manufacturing orders; no external dependencies."""

from collections import Counter
from datetime import date, timedelta
from decimal import Decimal
from random import Random


EXPECTED_COUNTS = {
    "customers": 100,
    "products": 20,
    "plants": 3,
    "sales_orders": 1000,
    "sales_order_lines": 3000,
    "work_orders": 2000,
    "shipments": 800,
    "shipment_lines": 2400,
}

# The writer translates these portable type names into explicit Arrow schemas.
SCHEMAS = {
    "customers": [
        ("customer_id", "int"), ("customer_name", "string"),
        ("industry", "string"), ("region", "string"),
    ],
    "products": [
        ("product_id", "int"), ("sku", "string"), ("product_name", "string"),
        ("unit_price", "decimal"),
    ],
    "plants": [
        ("plant_id", "int"), ("plant_name", "string"), ("region", "string"),
    ],
    "sales_orders": [
        ("order_id", "int"), ("customer_id", "int"), ("order_date", "date"),
        ("requested_date", "date"), ("status", "string"),
    ],
    "sales_order_lines": [
        ("order_line_id", "int"), ("order_id", "int"), ("product_id", "int"),
        ("ordered_quantity", "int"), ("unit_price", "decimal"),
        ("line_amount", "decimal"),
    ],
    "work_orders": [
        ("work_order_id", "int"), ("order_line_id", "int"), ("plant_id", "int"),
        ("planned_quantity", "int"), ("produced_quantity", "int"),
        ("status", "string"),
    ],
    "shipments": [
        ("shipment_id", "int"), ("order_id", "int"), ("ship_date", "date"),
        ("delivery_date", "date"),
    ],
    "shipment_lines": [
        ("shipment_line_id", "int"), ("shipment_id", "int"),
        ("order_line_id", "int"), ("shipped_quantity", "int"),
    ],
}

PRIMARY_KEYS = {
    "customers": "customer_id", "products": "product_id", "plants": "plant_id",
    "sales_orders": "order_id", "sales_order_lines": "order_line_id",
    "work_orders": "work_order_id", "shipments": "shipment_id",
    "shipment_lines": "shipment_line_id",
}


def generate(seed=42):
    rng = Random(seed)
    regions = ("Americas", "EMEA", "APAC")
    industries = ("Industrial equipment", "Automotive components", "Electronics")
    data = {
        "customers": [
            {"customer_id": i, "customer_name": f"Fictional Customer {i:03d}",
             "industry": industries[(i - 1) % 3], "region": regions[(i - 1) % 3]}
            for i in range(1, 101)
        ],
        "products": [
            {"product_id": i, "sku": f"MFG-{i:04d}",
             "product_name": f"Precision Component {i:02d}",
             "unit_price": Decimal(1000 + i * 275) / 100}
            for i in range(1, 21)
        ],
        "plants": [
            {"plant_id": i, "plant_name": f"Fictional Plant {i}",
             "region": regions[i - 1]} for i in range(1, 4)
        ],
        "sales_orders": [], "sales_order_lines": [], "work_orders": [],
        "shipments": [], "shipment_lines": [],
    }
    for order_id in range(1, 1001):
        order_date = date(2026, 7, 1) + timedelta(days=(order_id - 1) % 90)
        status = "fulfilled" if order_id <= 600 else (
            "partially_fulfilled" if order_id <= 800 else "open"
        )
        data["sales_orders"].append({
            "order_id": order_id, "customer_id": (order_id - 1) % 100 + 1,
            "order_date": order_date, "requested_date": order_date + timedelta(days=14),
            "status": status,
        })
        if order_id <= 800:
            data["shipments"].append({
                "shipment_id": order_id, "order_id": order_id,
                "ship_date": order_date + timedelta(days=7),
                "delivery_date": order_date + timedelta(days=10),
            })
        for offset in range(3):
            line_id = (order_id - 1) * 3 + offset + 1
            product_id = rng.randrange(1, 21)
            quantity = 2 * rng.randrange(2, 22)
            price = data["products"][product_id - 1]["unit_price"]
            data["sales_order_lines"].append({
                "order_line_id": line_id, "order_id": order_id,
                "product_id": product_id, "ordered_quantity": quantity,
                "unit_price": price, "line_amount": price * quantity,
            })
            if line_id <= 2000:
                complete = order_id <= 600
                data["work_orders"].append({
                    "work_order_id": line_id, "order_line_id": line_id,
                    "plant_id": (line_id - 1) % 3 + 1,
                    "planned_quantity": quantity,
                    "produced_quantity": quantity if complete else quantity // 2,
                    "status": "complete" if complete else "in_progress",
                })
            if order_id <= 800:
                data["shipment_lines"].append({
                    "shipment_line_id": line_id, "shipment_id": order_id,
                    "order_line_id": line_id,
                    "shipped_quantity": quantity if order_id <= 600 else quantity // 2,
                })
    validate(data)
    return data


def validate(data):
    if set(data) != set(EXPECTED_COUNTS):
        raise ValueError("Unexpected table set")
    indexed = {}
    for name, count in EXPECTED_COUNTS.items():
        rows = data[name]
        if len(rows) != count:
            raise ValueError(f"{name}: expected {count} rows")
        columns = {column for column, _ in SCHEMAS[name]}
        key = PRIMARY_KEYS[name]
        if any(set(row) != columns for row in rows):
            raise ValueError(f"{name}: column mismatch")
        indexed[name] = {row[key]: row for row in rows}
        if len(indexed[name]) != count or any(
            not isinstance(row[key], int) or row[key] <= 0 for row in rows
        ):
            raise ValueError(f"{name}: invalid or duplicate primary key")
        for row in rows:
            for column, kind in SCHEMAS[name]:
                value = row[column]
                valid = {
                    "int": lambda: type(value) is int,
                    "string": lambda: isinstance(value, str) and bool(value),
                    "date": lambda: type(value) is date,
                    "decimal": lambda: isinstance(value, Decimal)
                    and value.is_finite()
                    and value == value.quantize(Decimal("0.01")),
                }[kind]()
                if not valid:
                    raise ValueError(f"{name}.{column}: invalid type or value")

    def require(table, key):
        if key not in indexed[table]:
            raise ValueError(f"Invalid foreign key into {table}")
        return indexed[table][key]

    line_counts = Counter()
    ordered = Counter()
    shipped = Counter()
    allocated = Counter()
    for product in data["products"]:
        if product["unit_price"] <= 0:
            raise ValueError("Invalid product price")
    for order in data["sales_orders"]:
        require("customers", order["customer_id"])
        if order["requested_date"] < order["order_date"]:
            raise ValueError("Invalid order dates")
    for line in data["sales_order_lines"]:
        require("sales_orders", line["order_id"])
        product = require("products", line["product_id"])
        quantity = line["ordered_quantity"]
        if (quantity <= 0 or line["unit_price"] != product["unit_price"]
                or line["line_amount"] != line["unit_price"] * quantity):
            raise ValueError("Invalid line quantity or amount")
        line_counts[line["order_id"]] += 1
        ordered[line["order_id"]] += quantity
    if any(line_counts[order_id] != 3 for order_id in indexed["sales_orders"]):
        raise ValueError("Each order must have three lines")
    for work in data["work_orders"]:
        line = require("sales_order_lines", work["order_line_id"])
        require("plants", work["plant_id"])
        allocated[line["order_line_id"]] += work["planned_quantity"]
        if (not 0 <= work["produced_quantity"] <= work["planned_quantity"]
                or work["planned_quantity"] <= 0
                or allocated[line["order_line_id"]] > line["ordered_quantity"]):
            raise ValueError("Invalid work order quantities")
        expected = "complete" if work["produced_quantity"] == work["planned_quantity"] else "in_progress"
        if work["status"] != expected:
            raise ValueError("Invalid work order status")
    for shipment in data["shipments"]:
        order = require("sales_orders", shipment["order_id"])
        if not order["order_date"] <= shipment["ship_date"] <= shipment["delivery_date"]:
            raise ValueError("Invalid shipment dates")
    shipped_lines = Counter()
    shipment_counts = Counter()
    for detail in data["shipment_lines"]:
        shipment = require("shipments", detail["shipment_id"])
        line = require("sales_order_lines", detail["order_line_id"])
        if shipment["order_id"] != line["order_id"]:
            raise ValueError("Shipment/order line mismatch")
        quantity = detail["shipped_quantity"]
        shipped_lines[line["order_line_id"]] += quantity
        if quantity <= 0 or shipped_lines[line["order_line_id"]] > line["ordered_quantity"]:
            raise ValueError("Invalid shipped quantity")
        shipment_counts[shipment["shipment_id"]] += 1
        shipped[line["order_id"]] += quantity
    if any(shipment_counts[key] == 0 for key in indexed["shipments"]):
        raise ValueError("Empty shipment")
    for order in data["sales_orders"]:
        quantity = shipped[order["order_id"]]
        expected = "fulfilled" if quantity == ordered[order["order_id"]] else (
            "partially_fulfilled" if quantity else "open"
        )
        if order["status"] != expected:
            raise ValueError("Order fulfillment status mismatch")


def summary(data):
    validate(data)
    return {
        "counts": {name: len(rows) for name, rows in data.items()},
        "order_amount": str(sum(
            (row["line_amount"] for row in data["sales_order_lines"]), Decimal("0.00")
        )),
        "ordered_quantity": sum(row["ordered_quantity"] for row in data["sales_order_lines"]),
        "shipped_quantity": sum(row["shipped_quantity"] for row in data["shipment_lines"]),
        "order_statuses": dict(sorted(Counter(
            row["status"] for row in data["sales_orders"]
        ).items())),
    }
