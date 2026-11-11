"""Verify exact fixture values and successful Fabric IQ calls through the saved Foundry agent."""

import argparse
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
import json
import math
from pathlib import Path

from openai import APIError

from manage_agent import AGENT_NAME, CONNECTION_NAME, FABRIC_URL, ROOT, invoke, project_client


def validate_binding(saved: dict) -> None:
    definition = saved["versions"]["latest"]["definition"]
    tools = definition.get("tools", [])
    if definition.get("kind") != "prompt" or len(tools) != 1:
        raise ValueError("The saved prompt agent must have exactly one Fabric IQ tool")
    tool = tools[0]
    if (
        tool.get("type") != "fabric_iq_preview"
        or tool.get("server_url") != FABRIC_URL
        or tool.get("server_label") != "ge_vernova_fleet"
        or not tool.get("project_connection_id", "").endswith("/connections/" + CONNECTION_NAME)
    ):
        raise ValueError("The saved tool binding does not target the expected Fabric data agent")


def compare_data(actual: object, expected: object, path: str = "data") -> None:
    if isinstance(expected, dict):
        if not isinstance(actual, dict) or actual.keys() != expected.keys():
            raise ValueError(f"{path}: result keys do not match the required shape")
        for key in expected:
            compare_data(actual[key], expected[key], f"{path}.{key}")
    elif isinstance(expected, list):
        if not isinstance(actual, list) or len(actual) != len(expected):
            raise ValueError(f"{path}: result row count does not match")
        for index, value in enumerate(expected):
            compare_data(actual[index], value, f"{path}[{index}]")
    elif isinstance(expected, (int, float)):
        if isinstance(actual, bool) or not isinstance(actual, (int, float)) or not math.isfinite(actual):
            raise ValueError(f"{path}: a finite JSON number is required")
        if Decimal(str(actual)) != Decimal(str(expected)):
            raise ValueError(f"{path}: got {actual}, expected {expected}")
    elif actual != expected:
        raise ValueError(f"{path}: got {actual!r}, expected {expected!r}")


def validate_response(response: dict, expected: object) -> dict:
    if response.get("status") != "completed" or response.get("error"):
        raise ValueError("The Foundry response failed or did not complete")
    outputs = response.get("output", [])
    calls = [
        item for item in outputs
        if item.get("type") in {"mcp_call", "fabric_iq_call"}
        and item.get("server_label") == "ge_vernova_fleet"
    ]
    if not calls:
        raise ValueError("No Fabric IQ tool-call evidence for ge_vernova_fleet")
    if any(call.get("error") or call.get("status") != "completed" or not call.get("output") for call in calls):
        raise ValueError("The Fabric IQ tool did not return a successful result")
    text = "".join(
        part["text"]
        for item in outputs if item.get("type") == "message"
        for part in item.get("content", []) if part.get("type") == "output_text"
    )
    answer = json.loads(text)
    if not isinstance(answer, dict) or set(answer) != {"source", "data"}:
        raise ValueError("The answer must contain exactly source and data")
    if not isinstance(answer["source"], str) or "GE Vernova Fleet Advisor" not in answer["source"]:
        raise ValueError("The answer must identify the Fabric data agent")
    compare_data(answer["data"], expected)
    return {
        "responseId": response["id"],
        "toolCalls": [
            {key: call[key] for key in ("type", "server_label", "name", "status", "arguments", "output") if key in call}
            for call in calls
        ],
        "answer": answer,
    }


def cases() -> list[tuple[str, str, object]]:
    fixture = json.loads((ROOT.parent / "expected-answers.json").read_text(encoding="utf-8"))
    percentages = {
        site: float((Decimal(str(value)) * 100).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP))
        for site, value in fixture["capacity_factor_by_site"].items()
    }
    return [
        (
            "generation",
            "Execute Total Generation MWh for January 1 through March 31, 2026 inclusive. "
            'Return data as {"generation_mwh": number}.',
            {"generation_mwh": fixture["fleet"]["Total Generation MWh"]},
        ),
        (
            "january-generation-by-site",
            "Execute Total Generation MWh by Site Name for January 1 through January 31, 2026 inclusive. "
            "Return all six sites as data: an object mapping exact site names to generation MWh numbers.",
            fixture["january_generation_by_site"],
        ),
        (
            "january-top-downtime",
            "Which five turbines had the most Downtime Hours for January 1 through January 31, 2026 inclusive? "
            "Sort downtime descending, then turbine name ascending for ties. "
            'Return data as an array of objects with exactly "Turbine Name" and "Downtime Hours".',
            fixture["january_top_downtime_turbines"],
        ),
        (
            "maintenance",
            "Execute Maintenance Cost in USD and Maintenance Event Count by site and for the fleet "
            "for January 1 through March 31, 2026 inclusive. Include open and completed events. "
            'Return data as {"sites": {site_name: {"Maintenance Cost": number, '
            '"Maintenance Event Count": number}}, "fleet": {"Maintenance Cost": number, '
            '"Maintenance Event Count": number}}. Include all six sites.',
            {
                "sites": fixture["maintenance_by_site"],
                "fleet": {key: fixture["fleet"][key] for key in ("Maintenance Cost", "Maintenance Event Count")},
            },
        ),
        (
            "capacity-factors",
            "Execute the model's existing Capacity Factor % measure by site for January 1 through March 31, "
            "2026 inclusive. Pass this DAX query verbatim to Fabric to override the measure's "
            "two-decimal display format: EVALUATE SUMMARIZECOLUMNS('Site'[Site Name], "
            "DATESBETWEEN('Date'[Date], DATE(2026,1,1), DATE(2026,3,31)), "
            "\"Capacity Factor Percent\", FORMAT([Capacity Factor %] * 100, \"0.000000\")) "
            "ORDER BY 'Site'[Site Name] ASC. Parse the six-decimal query values as JSON numbers. "
            "Do not average percentages or pad already rounded display values with zeros. "
            "Return data as an object mapping all six exact "
            "site names to percentage-unit JSON numbers rounded to six decimal places, not fractions.",
            percentages,
        ),
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", choices=[name for name, _, _ in cases()])
    parser.add_argument("--output", type=Path, default=ROOT / ".foundry" / "verification.json")
    args = parser.parse_args()
    report = {
        "verifiedAtUtc": datetime.now(timezone.utc).isoformat(),
        "agent": AGENT_NAME,
        "fabricEndpoint": FABRIC_URL,
        "passed": False,
        "cases": [],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    with project_client() as project:
        saved = project.agents.get(AGENT_NAME).as_dict()
        report["savedAgent"] = saved
        validate_binding(saved)
        for name, question, expected in cases():
            if args.case and args.case != name:
                continue
            prompt = (
                "Use the published GE Vernova Fleet Advisor Fabric data agent, executing a fresh query. "
                + question
                + ' Return only a JSON object with exactly "source" and "data", without markdown or other text. '
                'The source string must contain the exact name "GE Vernova Fleet Advisor" and identify '
                'the data as synthetic. Put the requested result structure in data.'
            )
            print(f"Running {name}", flush=True)
            response = None
            try:
                response = invoke(project, prompt)
                result = validate_response(response, expected)
            except (ValueError, KeyError, RuntimeError, APIError) as exc:
                report["cases"].append({"name": name, "passed": False, "error": str(exc)})
                args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
                if response is not None and not any(
                    item.get("type") == "oauth_consent_request" for item in response.get("output", [])
                ):
                    debug = ROOT / ".foundry" / "last-failed-response.json"
                    debug.parent.mkdir(parents=True, exist_ok=True)
                    debug.write_text(json.dumps(response, indent=2) + "\n", encoding="utf-8")
                raise
            report["cases"].append({"name": name, "passed": True, **result})
            args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    report["passed"] = bool(report["cases"]) and all(case["passed"] for case in report["cases"])
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"Passed {len(report['cases'])} case(s). Evidence: {args.output}")


if __name__ == "__main__":
    main()
