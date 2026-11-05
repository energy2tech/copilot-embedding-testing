"""Deterministic, fictional manufacturing data; standard library only."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from hashlib import sha256
from random import Random
from typing import NamedTuple


class Plant(NamedTuple):
    plant_id: int
    plant_name: str
    region: str
    timezone: str


class Machine(NamedTuple):
    machine_id: int
    plant_id: int
    machine_type: str
    rated_units_per_hour: int


class Product(NamedTuple):
    product_id: int
    sku: str
    product_family: str
    standard_cycle_seconds: int


class CalendarDay(NamedTuple):
    date_key: int
    calendar_date: date
    week_start: date
    month: int


class WorkOrder(NamedTuple):
    work_order_id: int
    machine_id: int
    product_id: int
    date_key: int
    start_utc: datetime
    end_utc: datetime
    planned_units: int


class Production(NamedTuple):
    production_id: int
    work_order_id: int
    start_utc: datetime
    end_utc: datetime
    total_units: int
    good_units: int
    scrap_units: int


class Inspection(NamedTuple):
    inspection_id: int
    work_order_id: int
    inspected_utc: datetime
    measurement: float
    lower_limit: float
    upper_limit: float
    passed: bool


class Downtime(NamedTuple):
    downtime_id: int
    machine_id: int
    work_order_id: int
    start_utc: datetime
    end_utc: datetime
    reason_code: str


class Tables(NamedTuple):
    dim_plant: list[Plant]
    dim_machine: list[Machine]
    dim_product: list[Product]
    dim_date: list[CalendarDay]
    fact_work_order: list[WorkOrder]
    fact_production: list[Production]
    fact_quality_inspection: list[Inspection]
    fact_downtime: list[Downtime]


EXPECTED_COUNTS = dict(zip(Tables._fields, (3, 24, 12, 90, 2160, 64800, 30000, 3000)))
SCHEMAS = {
    "dim_plant": "plant_id INT, plant_name STRING, region STRING, timezone STRING",
    "dim_machine": "machine_id INT, plant_id INT, machine_type STRING, rated_units_per_hour INT",
    "dim_product": "product_id INT, sku STRING, product_family STRING, standard_cycle_seconds INT",
    "dim_date": "date_key INT, calendar_date DATE, week_start DATE, month INT",
    "fact_work_order": (
        "work_order_id INT, machine_id INT, product_id INT, date_key INT, "
        "start_utc TIMESTAMP, end_utc TIMESTAMP, planned_units INT"
    ),
    "fact_production": (
        "production_id INT, work_order_id INT, start_utc TIMESTAMP, end_utc TIMESTAMP, "
        "total_units INT, good_units INT, scrap_units INT"
    ),
    "fact_quality_inspection": (
        "inspection_id INT, work_order_id INT, inspected_utc TIMESTAMP, "
        "measurement DOUBLE, lower_limit DOUBLE, upper_limit DOUBLE, passed BOOLEAN"
    ),
    "fact_downtime": (
        "downtime_id INT, machine_id INT, work_order_id INT, start_utc TIMESTAMP, "
        "end_utc TIMESTAMP, reason_code STRING"
    ),
}


def generate(seed: int = 42) -> Tables:
    rng = Random(seed)
    tables = Tables([], [], [], [], [], [], [], [])
    for plant_id, region in enumerate(("North", "Central", "South"), 1):
        tables.dim_plant.append(Plant(plant_id, f"Contoso {region} Works", region, "UTC"))
    for machine_id in range(1, 25):
        tables.dim_machine.append(
            Machine(machine_id, (machine_id - 1) // 8 + 1, ("CNC", "Press", "Assembly")[machine_id % 3], 240)
        )
    for product_id in range(1, 13):
        tables.dim_product.append(
            Product(product_id, f"CPM-{product_id:04d}", ("Housing", "Bracket", "Shaft")[product_id % 3], 15)
        )
    for day_index in range(90):
        day = date(2026, 7, 1) + timedelta(days=day_index)
        date_key = int(day.strftime("%Y%m%d"))
        tables.dim_date.append(CalendarDay(date_key, day, day - timedelta(days=day.weekday()), day.month))
        for machine_id in range(1, 25):
            order_id = day_index * 24 + machine_id
            start = datetime(day.year, day.month, day.day)
            tables.fact_work_order.append(
                WorkOrder(order_id, machine_id, (order_id - 1) % 12 + 1, date_key,
                          start, start + timedelta(hours=20), 3000)
            )
            for interval in range(30):
                total = rng.randint(60, 100)
                scrap = rng.randint(0, 6)
                interval_start = start + timedelta(minutes=interval * 30)
                tables.fact_production.append(
                    Production(len(tables.fact_production) + 1, order_id, interval_start,
                               interval_start + timedelta(minutes=30), total, total - scrap, scrap)
                )
            for inspection in range(14 if order_id <= 1920 else 13):
                measurement = rng.randint(950, 1050) / 100
                tables.fact_quality_inspection.append(
                    Inspection(len(tables.fact_quality_inspection) + 1, order_id,
                               start + timedelta(minutes=inspection * 60 + 15),
                               measurement, 9.8, 10.2, 9.8 <= measurement <= 10.2)
                )
            for event in range(2 if order_id <= 840 else 1):
                event_start = start + timedelta(hours=16 + event * 2)
                tables.fact_downtime.append(
                    Downtime(len(tables.fact_downtime) + 1, machine_id, order_id,
                             event_start, event_start + timedelta(minutes=rng.randint(5, 30)),
                             ("Maintenance", "Material shortage", "Changeover")[rng.randrange(3)])
                )
    return tables


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def validate(tables: Tables) -> None:
    for name, rows in tables._asdict().items():
        require(len(rows) == EXPECTED_COUNTS[name], f"{name}: unexpected row count")
        require(len({row[0] for row in rows}) == len(rows), f"{name}: duplicate primary key")
    plants = {row.plant_id for row in tables.dim_plant}
    machines = {row.machine_id for row in tables.dim_machine}
    products = {row.product_id for row in tables.dim_product}
    dates = {row.date_key for row in tables.dim_date}
    orders = {row.work_order_id: row for row in tables.fact_work_order}
    for machine in tables.dim_machine:
        require(machine.plant_id in plants, "Machine references missing plant")
    for order in tables.fact_work_order:
        require(order.machine_id in machines and order.product_id in products
                and order.date_key in dates, "Work order references missing dimension")
        require(order.start_utc < order.end_utc and order.planned_units >= 0, "Invalid work order")
    for production in tables.fact_production:
        require(production.work_order_id in orders, "Production references missing order")
        order = orders[production.work_order_id]
        require(order.start_utc <= production.start_utc < production.end_utc <= order.end_utc,
                "Production outside work order")
        require(production.good_units >= 0 and production.scrap_units >= 0
                and production.good_units + production.scrap_units == production.total_units,
                "Invalid production quantities")
    for inspection in tables.fact_quality_inspection:
        require(inspection.work_order_id in orders, "Inspection references missing order")
        order = orders[inspection.work_order_id]
        require(order.start_utc <= inspection.inspected_utc <= order.end_utc,
                "Inspection outside work order")
        require(inspection.passed ==
                (inspection.lower_limit <= inspection.measurement <= inspection.upper_limit),
                "Inspection pass flag disagrees with measurement")
    previous_end: dict[int, datetime] = {}
    for event in sorted(tables.fact_downtime, key=lambda row: (row.machine_id, row.start_utc)):
        require(event.work_order_id in orders, "Downtime references missing order")
        order = orders[event.work_order_id]
        require(event.machine_id == order.machine_id, "Downtime references wrong machine")
        require(order.start_utc <= event.start_utc < event.end_utc <= order.end_utc,
                "Downtime outside work order")
        require(event.machine_id not in previous_end
                or previous_end[event.machine_id] <= event.start_utc, "Overlapping downtime")
        previous_end[event.machine_id] = event.end_utc


def fingerprint(tables: Tables) -> str:
    return sha256(repr(tables).encode("ascii")).hexdigest()


if __name__ == "__main__":
    data = generate()
    validate(data)
    print(f"Validated {sum(EXPECTED_COUNTS.values()):,} rows; SHA-256 {fingerprint(data)}")
