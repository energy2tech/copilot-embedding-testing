"""Persist and invoke the GE Vernova Foundry prompt agent using tenant-scoped CLI auth."""

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess

from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import FabricIQPreviewTool, PromptAgentDefinition
from azure.identity import AzureCliCredential


ROOT = Path(__file__).resolve().parent
TENANT = "21ddafdf-7740-4439-9b4a-6246817b2dfc"
AGENT_NAME = "ge-vernova-fleet-advisor"
CONNECTION_NAME = "ge-vernova-fabric"
FABRIC_URL = (
    "https://api.fabric.microsoft.com/v1/mcp/workspaces/"
    "aeeddd08-ac34-4681-b9cd-c84424c97f3e/dataagents/"
    "664cedb7-472e-485c-a77b-70b47a18f878/agent"
)
INSTRUCTIONS = """You are the GE Vernova Fleet Advisor for a synthetic demonstration.
All sites, turbines, generation, downtime, and costs are fictional, not operational data.
For every fleet-data question, call the GE Vernova Fleet Advisor Fabric IQ tool.
It uses the published Fabric data agent and its existing ontology-connected Import model.
Never replace this tool with your own knowledge, a guessed result, or a direct data source.
Preserve the user's explicit date range, units, names, precision, and requested tie ordering.
Use existing model measures, including Capacity Factor %, rather than averaging percentages.
Maintenance costs include both open and completed events unless explicitly requested otherwise.
State the dates, units, and Fabric source in your answer, and identify the data as synthetic.
If the question lacks necessary dates or is ambiguous, ask for clarification.
If the tool fails, is unauthorized, or requires OAuth consent, state that clearly.
Do not present estimates or memorized values as query results.
"""


def azd_value(name: str) -> str:
    environment = {**os.environ, "AZURE_DEV_USER_AGENT": "microsoft_foundry_skill"}
    executable = shutil.which("azd")
    if not executable:
        raise RuntimeError("Azure Developer CLI is not installed")
    result = subprocess.run(
        [
            executable, "env", "get-value", name, "--cwd", str(ROOT / "infrastructure"),
            "--environment", "ge-vernova-foundry", "--no-prompt",
        ],
        env=environment, check=True, capture_output=True, text=True,
    )
    value = result.stdout.strip()
    if not value:
        raise ValueError(f"Missing azd value: {name}. Run provision.ps1 first.")
    return value


def project_client() -> AIProjectClient:
    endpoint = azd_value("AZURE_AI_PROJECT_ENDPOINT")
    if endpoint != "https://ai-ge-vernova-c2eaee16.services.ai.azure.com/api/projects/ge-vernova-fleet":
        raise ValueError("The azd endpoint does not match the approved deployment.")
    return AIProjectClient(
        endpoint=endpoint,
        credential=AzureCliCredential(tenant_id=TENANT),
    )


def ensure_runtime_access(principal_id: str) -> None:
    executable = shutil.which("az")
    if not executable:
        raise RuntimeError("Azure CLI is not installed")
    project_id = azd_value("AZURE_AI_PROJECT_ID")
    if not project_id.startswith("/subscriptions/c2eaee16-e4b6-4608-b937-9005553d66f7/"):
        raise ValueError("The project ID does not match the approved subscription")
    subprocess.run(
        [
            executable, "role", "assignment", "create",
            "--assignee-object-id", principal_id, "--assignee-principal-type", "ServicePrincipal",
            "--role", "53ca6127-db72-4b80-b1b0-d745d6d5456d", "--scope", project_id,
            "--subscription", "c2eaee16-e4b6-4608-b937-9005553d66f7",
            "--only-show-errors", "--output", "none",
        ],
        check=True,
    )


def create_agent(project: AIProjectClient) -> dict:
    connection = project.connections.get(CONNECTION_NAME)
    if connection.target != FABRIC_URL:
        raise ValueError("The project connection does not target the intended Fabric data agent.")
    definition = PromptAgentDefinition(
        model="gpt-4.1-mini",
        instructions=INSTRUCTIONS,
        temperature=0,
        tools=[
            FabricIQPreviewTool(
                project_connection_id=connection.id,
                server_label="ge_vernova_fleet",
                server_url=FABRIC_URL,
                require_approval="never",
            )
        ],
    )
    version = project.agents.create_version(
        agent_name=AGENT_NAME,
        definition=definition,
        description="Synthetic fleet analytics delegated to the published Fabric data agent.",
    )
    saved = project.agents.get_version(AGENT_NAME, version.version)
    if saved.definition.as_dict() != definition.as_dict():
        raise RuntimeError("The persisted agent definition differs from the submitted definition.")
    ensure_runtime_access(saved.instance_identity.principal_id)
    return {"name": saved.name, "version": saved.version, "id": saved.id}


def invoke(project: AIProjectClient, question: str) -> dict:
    with project.get_openai_client(agent_name=AGENT_NAME) as client:
        response = client.responses.create(input=question)
    result = response.model_dump(mode="json", exclude={"tools"})
    if result.get("status") != "completed" or result.get("error"):
        raise RuntimeError(f"Foundry response failed: {result.get('status')}: {result.get('error')}")
    for item in result.get("output", []):
        if item.get("type") in {"mcp_call", "fabric_iq_call"} and item.get("error"):
            raise RuntimeError(f"Fabric IQ tool failed: {item['error']}")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["create", "show", "ask"])
    parser.add_argument("--question")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.command == "ask" and not args.question:
        parser.error("--question is required for ask")
    with project_client() as project:
        if args.command == "create":
            result = create_agent(project)
        elif args.command == "show":
            result = project.agents.get(AGENT_NAME).as_dict()
        else:
            result = invoke(project, args.question)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    if args.command == "ask" and result.get("status") != "completed":
        raise RuntimeError(f"Foundry response did not complete: {result.get('status')}")


if __name__ == "__main__":
    main()
