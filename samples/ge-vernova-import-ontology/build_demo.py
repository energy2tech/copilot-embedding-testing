"""Build a portable, synthetic Import-mode Power BI project using only the standard library."""

import argparse
import calendar
import json
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent
NAME = "GE Vernova Fleet Performance (Import)"
START = date(2026, 1, 1)
DAYS = 90
SITE_NAMES = (
    "Prairie Ridge",
    "Coastal Horizon",
    "Riverbend",
    "Highland Point",
    "Desert Vista",
    "Lakeside",
)


def generate(adjustment: int = 0) -> dict[str, list[dict]]:
    if not 0 <= adjustment <= 100:
        raise ValueError("Generation adjustment must be an integer from 0 to 100 MWh")
    tables = {
        "Site": [
            {"SiteId": i + 1, "Site Name": name, "Region": ("Central", "East", "West")[i % 3]}
            for i, name in enumerate(SITE_NAMES)
        ],
        "Turbine": [
            {
                "TurbineId": i,
                "SiteId": (i - 1) // 4 + 1,
                "Turbine Name": f"Turbine {i:02d}",
                "Technology": "Synthetic gas turbine",
                "Rated MW": 100 + (i % 4) * 25,
            }
            for i in range(1, 25)
        ],
        "Date": [
            {
                "DateKey": day + 1,
                "Date": (START + timedelta(days=day)).isoformat(),
                "Month": calendar.month_name[(START + timedelta(days=day)).month],
                "Month Number": (START + timedelta(days=day)).month,
                "Year": 2026,
            }
            for day in range(DAYS)
        ],
        "Daily Generation": [],
        "Maintenance Event": [],
    }
    for turbine in tables["Turbine"]:
        tid = turbine["TurbineId"]
        for day in range(DAYS):
            downtime = (tid + day) % 6
            tables["Daily Generation"].append(
                {
                    "GenerationId": (tid - 1) * DAYS + day + 1,
                    "TurbineId": tid,
                    "DateKey": day + 1,
                    "Generation MWh": turbine["Rated MW"]
                    * (24 - downtime)
                    * (45 + (tid * 7 + day * 3) % 45)
                    // 100
                    + (adjustment if tid == 1 and day == 0 else 0),
                    "Downtime Hours": downtime,
                }
            )
    for eid in range(1, 73):
        tables["Maintenance Event"].append(
            {
                "MaintenanceEventId": eid,
                "TurbineId": (eid - 1) % 24 + 1,
                "DateKey": (eid * 7) % DAYS + 1,
                "Category": ("Inspection", "Preventive", "Corrective")[eid % 3],
                "Status": "Open" if eid % 5 == 0 else "Completed",
                "Cost USD": 1000 + (eid * 137) % 9000,
            }
        )
    validate(tables)
    return tables


def validate(tables: dict[str, list[dict]]) -> None:
    counts = {"Site": 6, "Turbine": 24, "Date": 90, "Daily Generation": 2160, "Maintenance Event": 72}
    keys = ("SiteId", "TurbineId", "DateKey", "GenerationId", "MaintenanceEventId")
    for (name, count), key in zip(counts.items(), keys, strict=True):
        rows = tables[name]
        if len(rows) != count or len({r[key] for r in rows}) != count:
            raise ValueError(f"{name}: invalid count or duplicate keys")
    sites = {r["SiteId"] for r in tables["Site"]}
    turbines = {r["TurbineId"]: r for r in tables["Turbine"]}
    dates = {r["DateKey"] for r in tables["Date"]}
    if any(r["SiteId"] not in sites for r in turbines.values()):
        raise ValueError("Turbine has an invalid site foreign key")
    for name in ("Daily Generation", "Maintenance Event"):
        for row in tables[name]:
            if row["TurbineId"] not in turbines or row["DateKey"] not in dates:
                raise ValueError(f"{name}: invalid foreign key")
    for row in tables["Daily Generation"]:
        if not 0 <= row["Downtime Hours"] <= 24:
            raise ValueError("Invalid downtime")
        if not 0 <= row["Generation MWh"] <= turbines[row["TurbineId"]]["Rated MW"] * 24:
            raise ValueError("Invalid generation")
    if any(r["Cost USD"] < 0 for r in tables["Maintenance Event"]):
        raise ValueError("Invalid maintenance cost")


def expected_answers(tables: dict[str, list[dict]]) -> dict:
    turbines = {r["TurbineId"]: r for r in tables["Turbine"]}
    sites = {r["SiteId"]: r["Site Name"] for r in tables["Site"]}
    totals = defaultdict(lambda: {"Generation MWh": 0, "Capacity MWh": 0, "Downtime Hours": 0})
    january = defaultdict(int)
    turbine_downtime = defaultdict(int)
    maintenance = defaultdict(lambda: {"Maintenance Cost": 0, "Maintenance Event Count": 0})
    for row in tables["Daily Generation"]:
        turbine = turbines[row["TurbineId"]]
        site = sites[turbine["SiteId"]]
        totals[site]["Generation MWh"] += row["Generation MWh"]
        totals[site]["Capacity MWh"] += turbine["Rated MW"] * 24
        totals[site]["Downtime Hours"] += row["Downtime Hours"]
        if row["DateKey"] <= 31:
            january[site] += row["Generation MWh"]
            turbine_downtime[turbine["Turbine Name"]] += row["Downtime Hours"]
    for row in tables["Maintenance Event"]:
        site = sites[turbines[row["TurbineId"]]["SiteId"]]
        maintenance[site]["Maintenance Cost"] += row["Cost USD"]
        maintenance[site]["Maintenance Event Count"] += 1
    return {
        "period": {"from": "2026-01-01", "to": "2026-03-31"},
        "fleet": {
            "Total Generation MWh": sum(r["Generation MWh"] for r in tables["Daily Generation"]),
            "Downtime Hours": sum(r["Downtime Hours"] for r in tables["Daily Generation"]),
            "Maintenance Cost": sum(r["Cost USD"] for r in tables["Maintenance Event"]),
            "Maintenance Event Count": 72,
            "Turbine Count": 24,
        },
        "january_generation_by_site": dict(sorted(january.items())),
        "january_top_downtime_turbines": sorted(
            [{"Turbine Name": k, "Downtime Hours": v} for k, v in turbine_downtime.items()],
            key=lambda r: (-r["Downtime Hours"], r["Turbine Name"]),
        )[:5],
        "maintenance_by_site": dict(sorted(maintenance.items())),
        "capacity_factor_by_site": {
            site: values["Generation MWh"] / values["Capacity MWh"]
            for site, values in sorted(totals.items())
        },
    }


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8")


def quote(name: str) -> str:
    return "'" + name.replace("'", "''") + "'"


def m_queries(adjustment: int) -> dict[str, str]:
    return {
        "Site": '''let
    Source = #table(type table [SiteId=Int64.Type, #"Site Name"=text, Region=text], {
        {1,"Prairie Ridge","Central"}, {2,"Coastal Horizon","East"}, {3,"Riverbend","West"},
        {4,"Highland Point","Central"}, {5,"Desert Vista","East"}, {6,"Lakeside","West"}
    })
in
    Source''',
        "Turbine": '''let
    Rows = List.Transform({1..24}, (i) => {
        i, Number.IntegerDivide(i-1,4)+1, "Turbine " & Text.PadStart(Text.From(i),2,"0"),
        "Synthetic gas turbine", 100 + Number.Mod(i,4)*25
    }),
    Source = #table(type table [TurbineId=Int64.Type, SiteId=Int64.Type,
        #"Turbine Name"=text, Technology=text, #"Rated MW"=Int64.Type], Rows)
in
    Source''',
        "Date": '''let
    Rows = List.Transform({0..89}, (d) => let Day = Date.AddDays(#date(2026,1,1),d)
        in {d+1, Day, Date.MonthName(Day,"en-US"), Date.Month(Day), Date.Year(Day)}),
    Source = #table(type table [DateKey=Int64.Type, Date=date, Month=text,
        #"Month Number"=Int64.Type, Year=Int64.Type], Rows)
in
    Source''',
        "Daily Generation": f'''let
    AdjustmentMWh = {adjustment},
    Rows = List.Combine(List.Transform({{1..24}}, (t) =>
        List.Transform({{0..89}}, (d) => let
            Downtime = Number.Mod(t+d,6),
            RatedMW = 100 + Number.Mod(t,4)*25,
            LoadPercent = 45 + Number.Mod(t*7+d*3,45),
            Generation = Number.IntegerDivide(RatedMW*(24-Downtime)*LoadPercent,100)
                + (if t=1 and d=0 then AdjustmentMWh else 0)
        in {{(t-1)*90+d+1, t, d+1, Generation, Downtime}}))),
    Source = #table(type table [GenerationId=Int64.Type, TurbineId=Int64.Type,
        DateKey=Int64.Type, #"Generation MWh"=Int64.Type, #"Downtime Hours"=Int64.Type], Rows)
in
    Source''',
        "Maintenance Event": '''let
    Rows = List.Transform({1..72}, (e) => {
        e, Number.Mod(e-1,24)+1, Number.Mod(e*7,90)+1,
        {"Inspection","Preventive","Corrective"}{Number.Mod(e,3)},
        if Number.Mod(e,5)=0 then "Open" else "Completed", 1000+Number.Mod(e*137,9000)
    }),
    Source = #table(type table [MaintenanceEventId=Int64.Type, TurbineId=Int64.Type,
        DateKey=Int64.Type, Category=text, Status=text, #"Cost USD"=Int64.Type], Rows)
in
    Source''',
    }


MEASURES = {
    "Turbine": [
        ("Turbine Count", "COUNTROWS('Turbine')", "#,##0", "Number of synthetic fleet turbines in the current site/turbine scope."),
    ],
    "Daily Generation": [
        ("Total Generation MWh", "SUM('Daily Generation'[Generation MWh])", "#,##0", "Synthetic electrical generation in megawatt-hours for the selected turbine-days."),
        ("Downtime Hours", "SUM('Daily Generation'[Downtime Hours Raw])", "#,##0", "Aggregate turbine downtime hours over the selected turbine-days."),
        ("Capacity Factor %", "DIVIDE([Total Generation MWh], SUMX('Daily Generation', RELATED('Turbine'[Rated MW]) * 24))", "0.00%", "Generation divided by nameplate MW times 24 hours for each turbine-day in scope, including downtime."),
    ],
    "Maintenance Event": [
        ("Maintenance Cost", "SUM('Maintenance Event'[Cost USD])", "$#,##0", "Synthetic maintenance cost in USD, attributed to the event date, including open events."),
        ("Maintenance Event Count", "COUNTROWS('Maintenance Event')", "#,##0", "Number of synthetic maintenance events, including open events."),
    ],
}


def build_model(project: Path, tables: dict[str, list[dict]], adjustment: int) -> None:
    model = project / f"{NAME}.SemanticModel"
    write_json(model / "definition.pbism", {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/semanticModel/definitionProperties/1.0.0/schema.json",
        "version": "4.2", "settings": {"qnaEnabled": True},
    })
    write_text(model / "definition" / "database.tmdl", "database\n\tcompatibilityLevel: 1702\n")
    write_text(model / "definition" / "model.tmdl",
               "model Model\n\tculture: en-US\n\tdefaultPowerBIDataSourceVersion: powerBI_V3\n"
               "\tsourceQueryCulture: en-US\n\tdiscourageImplicitMeasures\n\n"
               + "\n".join(f"ref table {quote(name)}" for name in tables) + "\n")
    hidden = {"SiteId", "TurbineId", "DateKey", "GenerationId", "MaintenanceEventId",
              "Generation MWh", "Downtime Hours", "Cost USD", "Rated MW"}
    for name, rows in tables.items():
        lines = [f"/// Synthetic demo only. {len(rows)} rows; see README for grain and metric definitions.",
                 f"table {quote(name)}", ""]
        if name == "Date":
            lines += ["\tdataCategory: Time", ""]
        for measure, expression, fmt, description in MEASURES.get(name, []):
            lines += [f"\t/// {description}", f"\tmeasure {quote(measure)} = {expression}",
                      f"\t\tformatString: {fmt}", ""]
        for column, value in rows[0].items():
            dtype = "dateTime" if column == "Date" else "int64" if isinstance(value, int) else "string"
            model_column = "Downtime Hours Raw" if column == "Downtime Hours" else column
            lines += [f"\tcolumn {quote(model_column)}", f"\t\tdataType: {dtype}"]
            if column in hidden:
                lines += ["\t\tisHidden"]
            if column == "Date":
                lines += ["\t\tisKey", "\t\tformatString: yyyy-MM-dd"]
            if column == "Month":
                lines += ["\t\tsortByColumn: 'Month Number'"]
            lines += ["\t\tsummarizeBy: none", f"\t\tsourceColumn: {column}", ""]
            if column == "Date":
                lines += ["\t\tannotation UnderlyingDateTimeDataType = Date", ""]
        lines += [f"\tpartition {quote(name)} = m", "\t\tmode: import", "\t\tsource ="]
        lines += ["\t\t\t" + line for line in m_queries(adjustment)[name].splitlines()]
        write_text(model / "definition" / "tables" / f"{name}.tmdl", "\n".join(lines) + "\n")
    relationships = []
    for index, (fact, fk, dim, pk) in enumerate([
        ("Turbine", "SiteId", "Site", "SiteId"),
        ("Daily Generation", "TurbineId", "Turbine", "TurbineId"),
        ("Daily Generation", "DateKey", "Date", "DateKey"),
        ("Maintenance Event", "TurbineId", "Turbine", "TurbineId"),
        ("Maintenance Event", "DateKey", "Date", "DateKey"),
    ], start=1):
        relationships += [
            f"relationship FleetRelationship{index}",
            f"\tfromColumn: {quote(fact)}.{quote(fk)}",
            f"\ttoColumn: {quote(dim)}.{quote(pk)}",
            "\tcrossFilteringBehavior: oneDirection", "",
        ]
    write_text(model / "definition" / "relationships.tmdl", "\n".join(relationships))


SCHEMA_BASE = "https://developer.microsoft.com/json-schemas/fabric"


def field(table: str, column: str, measure: bool = False) -> dict:
    return {
        "field": {("Measure" if measure else "Column"): {
            "Expression": {"SourceRef": {"Entity": table}}, "Property": column}},
        "queryRef": f"{table}.{column}", "nativeQueryRef": column,
    }


def build_report(project: Path) -> None:
    report = project / f"{NAME}.Report"
    write_json(project / f"{NAME}.pbip", {
        "$schema": f"{SCHEMA_BASE}/pbip/pbipProperties/1.0.0/schema.json",
        "version": "1.0", "artifacts": [{"report": {"path": f"{NAME}.Report"}}],
        "settings": {"enableAutoRecovery": True},
    })
    write_json(report / "definition.pbir", {
        "$schema": f"{SCHEMA_BASE}/item/report/definitionProperties/2.0.0/schema.json",
        "version": "4.0", "datasetReference": {"byPath": {"path": f"../{NAME}.SemanticModel"}},
    })
    definition = report / "definition"
    write_json(definition / "version.json", {
        "$schema": f"{SCHEMA_BASE}/item/report/definition/versionMetadata/1.0.0/schema.json",
        "version": "2.0.0",
    })
    write_json(definition / "report.json", {
        "$schema": f"{SCHEMA_BASE}/item/report/definition/report/3.0.0/schema.json",
        "themeCollection": {},
    })
    pages = [("fleet", "Fleet Overview | SYNTHETIC DATA"),
             ("generation", "Generation & Availability | SYNTHETIC DATA"),
             ("maintenance", "Maintenance | SYNTHETIC DATA")]
    write_json(definition / "pages" / "pages.json", {
        "$schema": f"{SCHEMA_BASE}/item/report/definition/pagesMetadata/1.0.0/schema.json",
        "pageOrder": [name for name, _ in pages], "activePageName": "fleet",
    })
    configurations = {
        "fleet": [
            ("card", None, ("Daily Generation", "Total Generation MWh")),
            ("card", None, ("Daily Generation", "Capacity Factor %")),
            ("card", None, ("Turbine", "Turbine Count")),
            ("clusteredColumnChart", ("Site", "Site Name"), ("Daily Generation", "Total Generation MWh")),
        ],
        "generation": [
            ("card", None, ("Daily Generation", "Downtime Hours")),
            ("clusteredColumnChart", ("Date", "Month"), ("Daily Generation", "Total Generation MWh")),
            ("clusteredBarChart", ("Turbine", "Turbine Name"), ("Daily Generation", "Downtime Hours")),
        ],
        "maintenance": [
            ("card", None, ("Maintenance Event", "Maintenance Cost")),
            ("card", None, ("Maintenance Event", "Maintenance Event Count")),
            ("clusteredColumnChart", ("Site", "Site Name"), ("Maintenance Event", "Maintenance Cost")),
            ("clusteredColumnChart", ("Maintenance Event", "Category"), ("Maintenance Event", "Maintenance Event Count")),
        ],
    }
    for page_name, display in pages:
        page = definition / "pages" / page_name
        write_json(page / "page.json", {
            "$schema": f"{SCHEMA_BASE}/item/report/definition/page/2.0.0/schema.json",
            "name": page_name, "displayName": display, "displayOption": "FitToPage",
            "height": 720, "width": 1280,
        })
        visuals = configurations[page_name] + [
            ("slicer", ("Site", "Site Name"), None),
            ("slicer", ("Date", "Month"), None),
        ]
        for index, (visual_type, category, measure) in enumerate(visuals):
            visual_name = f"{page_name}{index:02d}"
            if visual_type == "slicer":
                state = {"Values": {"projections": [field(*category)]}}
                x, y, width, height = (20 + (index - len(configurations[page_name])) * 630, 15, 610, 100)
            elif visual_type == "card":
                state = {"Values": {"projections": [field(*measure, measure=True)]}}
                x, y, width, height = 20 + index * 400, 130, 380, 150
            else:
                state = {
                    "Category": {"projections": [field(*category)]},
                    "Y": {"projections": [field(*measure, measure=True)]},
                }
                chart_index = sum(1 for v, _, _ in visuals[:index] if v not in ("card", "slicer"))
                x, y, width, height = 20 + chart_index * 630, 305, 610, 390
                if page_name == "fleet":
                    width = 1240
            write_json(page / "visuals" / visual_name / "visual.json", {
                "$schema": f"{SCHEMA_BASE}/item/report/definition/visualContainer/2.5.0/schema.json",
                "name": visual_name,
                "position": {"x": x, "y": y, "z": index, "height": height, "width": width, "tabOrder": index},
                "visual": {"visualType": visual_type, "query": {"queryState": state},
                           "drillFilterOtherVisuals": True},
            })


def build(output: Path, adjustment: int = 0) -> None:
    tables = generate(adjustment)
    build_model(output, tables, adjustment)
    build_report(output)
    write_json(output.parent / "expected-answers.json", expected_answers(tables))
    print(f"Built {output} ({sum(map(len, tables.values()))} synthetic rows; all partitions Import)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "project")
    parser.add_argument("--generation-adjustment-mwh", type=int, default=0,
                        help="Add 0-100 MWh to turbine 1 on January 1 for the controlled data-change test")
    args = parser.parse_args()
    build(args.output, args.generation_adjustment_mwh)
