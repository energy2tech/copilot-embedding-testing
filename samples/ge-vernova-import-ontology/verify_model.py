"""Compare the published Import model's DAX results with independent Python fixtures."""

import argparse
import json
import math
import os
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from uuid import UUID

from build_demo import ROOT


def execute(workspace: str, model: str, query: str, token: str) -> list[dict]:
    url = f"https://api.powerbi.com/v1.0/myorg/groups/{workspace}/datasets/{model}/executeQueries"
    body = json.dumps({"queries": [{"query": query}], "serializerSettings": {"includeNulls": True}})
    request = Request(url, data=body.encode(), headers={
        "Authorization": f"Bearer {token}", "Content-Type": "application/json",
    })
    try:
        with urlopen(request, timeout=120) as response:
            result = json.load(response)
    except HTTPError as error:
        raise RuntimeError(f"Power BI query failed: HTTP {error.code}: {error.read().decode()}") from error
    if "error" in result or "error" in result["results"][0]:
        raise RuntimeError(json.dumps(result))
    table = result["results"][0]["tables"][0]
    if "error" in table:
        raise RuntimeError(json.dumps(table["error"]))
    return [{key.rsplit("[", 1)[-1].rstrip("]"): value for key, value in row.items()}
            for row in table["rows"]]


QUERIES = {
    "row_counts": """EVALUATE ROW(
        "Site", COUNTROWS('Site'), "Turbine", COUNTROWS('Turbine'),
        "Date", COUNTROWS('Date'), "Daily Generation", COUNTROWS('Daily Generation'),
        "Maintenance Event", COUNTROWS('Maintenance Event'))""",
    "fleet": """EVALUATE ROW(
        "Total Generation MWh", [Total Generation MWh], "Downtime Hours", [Downtime Hours],
        "Maintenance Cost", [Maintenance Cost], "Maintenance Event Count", [Maintenance Event Count],
        "Turbine Count", [Turbine Count])""",
    "january_generation_by_site": """EVALUATE SUMMARIZECOLUMNS(
        'Site'[Site Name], TREATAS({1}, 'Date'[Month Number]),
        "Generation MWh", [Total Generation MWh])
        ORDER BY 'Site'[Site Name] ASC""",
    "january_top_downtime_turbines": """EVALUATE TOPN(5, SUMMARIZECOLUMNS(
        'Turbine'[Turbine Name], TREATAS({1}, 'Date'[Month Number]),
        "Downtime Hours", [Downtime Hours]),
        [Downtime Hours], DESC, 'Turbine'[Turbine Name], ASC)
        ORDER BY [Downtime Hours] DESC, 'Turbine'[Turbine Name] ASC""",
    "maintenance_by_site": """EVALUATE SUMMARIZECOLUMNS('Site'[Site Name],
        "Maintenance Cost", [Maintenance Cost], "Maintenance Event Count", [Maintenance Event Count])
        ORDER BY 'Site'[Site Name] ASC""",
    "capacity_factor_by_site": """EVALUATE SUMMARIZECOLUMNS('Site'[Site Name],
        "Capacity Factor", [Capacity Factor %])
        ORDER BY 'Site'[Site Name] ASC""",
}


def compare(name: str, actual: list[dict], expected: dict) -> None:
    if name == "row_counts":
        wanted = {"Site": 6, "Turbine": 24, "Date": 90, "Daily Generation": 2160, "Maintenance Event": 72}
        if actual != [wanted]:
            raise ValueError(f"{name}: expected {wanted}, got {actual}")
    elif name == "fleet":
        if actual != [expected[name]]:
            raise ValueError(f"{name}: expected {expected[name]}, got {actual}")
    elif name == "january_top_downtime_turbines":
        if actual != expected[name]:
            raise ValueError(f"{name}: expected {expected[name]}, got {actual}")
    elif name == "january_generation_by_site":
        result = {row["Site Name"]: row["Generation MWh"] for row in actual}
        if result != expected[name]:
            raise ValueError(f"{name}: expected {expected[name]}, got {result}")
    elif name == "maintenance_by_site":
        result = {row["Site Name"]: {k: v for k, v in row.items() if k != "Site Name"} for row in actual}
        if result != expected[name]:
            raise ValueError(f"{name}: expected {expected[name]}, got {result}")
    elif name == "capacity_factor_by_site":
        result = {row["Site Name"]: row["Capacity Factor"] for row in actual}
        if result.keys() != expected[name].keys() or any(
            not math.isclose(result[site], value, rel_tol=1e-10, abs_tol=1e-12)
            for site, value in expected[name].items()
        ):
            raise ValueError(f"{name}: expected {expected[name]}, got {result}")
    else:
        raise ValueError(f"Unknown verification case: {name}")


def verify(workspace: str, model: str, expected_file: Path, output: Path) -> None:
    UUID(workspace)
    UUID(model)
    token = os.environ.get("POWERBI_ACCESS_TOKEN")
    if not token:
        executable = shutil.which("az")
        if not executable:
            raise RuntimeError("Azure CLI is required; alternatively supply POWERBI_ACCESS_TOKEN")
        token = subprocess.check_output(
            [executable, "account", "get-access-token", "--resource",
             "https://analysis.windows.net/powerbi/api", "--query", "accessToken", "-o", "tsv"],
            text=True,
        ).strip()
    expected = json.loads(expected_file.read_text(encoding="utf-8"))
    evidence = {"workspaceId": workspace, "modelId": model,
                "verifiedAtUtc": datetime.now(timezone.utc).isoformat(),
                "scope": "Direct semantic-model DAX only; NOT evidence of ontology or data-agent grounding.",
                "checks": {}}
    for name, query in QUERIES.items():
        actual = execute(workspace, model, query, token)
        compare(name, actual, expected)
        evidence["checks"][name] = {"status": "Pass", "query": query, "actual": actual}
        print(f"PASS {name}")
    output.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    print(f"Saved direct-model verification to {output}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--expected", type=Path, default=ROOT / "expected-answers.json")
    parser.add_argument("--output", type=Path, default=ROOT / "model-verification.json")
    args = parser.parse_args()
    verify(args.workspace, args.model, args.expected, args.output)
