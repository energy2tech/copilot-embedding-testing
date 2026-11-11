# Foundry agent for the synthetic GE Vernova fleet

This sample provisions a public, Microsoft Entra-authenticated Foundry project and a persistent prompt agent. Its only fleet-data tool is the existing published **GE Vernova Fleet Advisor** in Fabric. The web application is unchanged.

See [deployment status](./deployment-status.json) and [live verification evidence](./verification.json) for the actual verification state. Infrastructure and the persistent agent are deployed, and the Fabric connection works using the incoming Microsoft Entra user context.

**Synthetic demonstration, not production guidance.** Fabric IQ is preview. Fabric answers sent to Foundry leave the Fabric compliance boundary and follow Foundry's processing/storage policies.

## Resources

| Component | Value |
|---|---|
| Tenant | `21ddafdf-7740-4439-9b4a-6246817b2dfc` |
| Subscription | `ME-MngEnvMCAP617842-xujames-1` / `c2eaee16-e4b6-4608-b937-9005553d66f7` |
| Resource group | `rg-ge-vernova-foundry` |
| Region | Central US |
| Foundry account / project | `ai-ge-vernova-c2eaee16` / `ge-vernova-fleet` |
| Agent | `ge-vernova-fleet-advisor` |
| Model | `gpt-4.1-mini`, version `2025-04-14`, `DataZoneStandard`, capacity 10 |
| Fabric workspace | `aeeddd08-ac34-4681-b9cd-c84424c97f3e` |
| Fabric data agent | `664cedb7-472e-485c-a77b-70b47a18f878` |

Model capacity is a rate allocation (10,000 tokens/minute), **not a spending cap**. Model inference is billed by usage. No ACR, container hosting, AI Search, monitoring workspace, or additional Fabric capacity is deployed.

- [Foundry project](https://ai.azure.com/nextgen/r/c2eaee16-e4b6-4608-b937-9005553d66f7/rg-ge-vernova-foundry/ai-ge-vernova-c2eaee16/ge-vernova-fleet)
- [Azure resource group](https://portal.azure.com/#@21ddafdf-7740-4439-9b4a-6246817b2dfc/resource/subscriptions/c2eaee16-e4b6-4608-b937-9005553d66f7/resourceGroups/rg-ge-vernova-foundry/overview)
- [Fabric data agent](https://app.powerbi.com/groups/aeeddd08-ac34-4681-b9cd-c84424c97f3e/aiskills/664cedb7-472e-485c-a77b-70b47a18f878?ctid=21ddafdf-7740-4439-9b4a-6246817b2dfc)

## Provision

Use PowerShell 7, Azure CLI, Azure Developer CLI, and Python. Sign in to the same tenant/account used in Fabric:

```powershell
az login --tenant 21ddafdf-7740-4439-9b4a-6246817b2dfc
Set-Location .\samples\ge-vernova-import-ontology\foundry
.\provision.ps1 -Preview
.\provision.ps1
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r .\requirements.txt
```

The script checks provider registration, model catalog/SKU, quota (using the catalog's actual usage name), and ownership of existing resources before provisioning. It will not silently change region/model. The pinned model deployment specification is in [main.parameters.json](./infrastructure/infra/main.parameters.json).

Infrastructure is scaffolded from the official [azd-ai-starter-basic](https://github.com/Azure-Samples/azd-ai-starter-basic) template. The sample adds Central US to the template's outdated region allowlist and uses a literal model JSON parameter to avoid unescaped JSON environment substitution. Hosted agents, the Standard Setup capability host, monitoring, and dependent services are disabled.

The script uses supported Azure CLI credential reuse through `auth.useAzCliAuth` in an **isolated** azd configuration at `%LOCALAPPDATA%\ge-vernova-foundry\azd`; it does not change your global azd configuration. This also keeps azd's downloaded Bicep executable out of the OneDrive path containing spaces. Deployment outputs remain in the ignored `infrastructure\.azure\ge-vernova-foundry` environment.

## Fabric authentication

Only a **published** Fabric agent is usable. Both services must be in the same tenant. Each calling user must have a Fabric license and access to the data agent and its underlying sources. Foundry runtime access does not grant Fabric source access.

The project connection uses **`UserEntraToken`**: Foundry forwards the incoming Microsoft Entra user context to the published Fabric data agent. Configure it after provisioning and before creating the agent:

```powershell
.\connect_fabric.ps1
```

The script saves and reads back `ge-vernova-fabric` with the Power BI audience `https://analysis.windows.net/powerbi/api` and delegated scope `https://analysis.windows.net/powerbi/api/DataAgent.Execute.All`. It does not create an app registration, store credentials, grant tenant-wide consent, or replace the caller's Fabric permissions. Sharing the connection within the project does not share the underlying data permissions. Invoke with the same authorized user identity; unattended service-principal access is not established by this sample.

An earlier managed-OAuth connection could not establish gateway authorization. It was replaced, with user approval, by this working incoming-user-context connection; the old OAuth consent flow is not required.

The code uses the native `fabric_iq_preview` tool, not the legacy Fabric tool or direct access to the model. The exact data-agent MCP endpoint is:

```text
https://api.fabric.microsoft.com/v1/mcp/workspaces/aeeddd08-ac34-4681-b9cd-c84424c97f3e/dataagents/664cedb7-472e-485c-a77b-70b47a18f878/agent
```

## Agent management and verification

```powershell
.\.venv\Scripts\python.exe .\manage_agent.py show
.\.venv\Scripts\python.exe .\manage_agent.py create
.\.venv\Scripts\python.exe .\manage_agent.py ask --question "Using the Fabric data agent, what was total generation in MWh from January 1 through March 31, 2026?"
.\.venv\Scripts\python.exe .\verify_agent.py --case generation
.\.venv\Scripts\python.exe .\verify_agent.py
.\.venv\Scripts\python.exe -m unittest -v test_verify_agent
```

`create` saves a new persistent version and grants its runtime identity **Foundry User** only on this project. It does not delete the agent after testing. `show` and `ask` use tenant-scoped Azure CLI credentials rather than ambiguous cross-tenant default credentials.

The live verifier reads the existing independent [expected answers](../expected-answers.json). It asks five separate questions, requires successful Fabric tool-call evidence, and compares exact values, row order, all site keys, and six-decimal percentage-unit results. Correct-looking text without a successful tool call fails validation. Expected numbers are never embedded in agent instructions or sent in test questions.

For capacity factor, the question supplies a DAX projection of the existing measure with six-decimal formatting. This avoids Fabric returning only the measure's two-decimal display values; it does not change the model or bypass the Fabric data agent.

By default, live evidence is saved in ignored `.foundry\verification.json`. Do not publish OAuth links, tokens, or credential-bearing responses. A passing local unit test or a saved connection/agent is not proof of the complete integration.

## Capacity, costs, and cleanup

`f64centralus001` was already **Active** at execution start. This sample leaves it unchanged and does not change the workspace's capacity assignment. Running F64 remains billable. If it is suspended later, coordinate shared usage before resuming; resume only as needed and pause afterward only when your execution started it and it is safe for other users.

The new Foundry resources stay deployed for reuse. After reviewing the exact resource inventory, deleting only `rg-ge-vernova-foundry` removes this sample's account, project, model, connections, and agents. This is destructive and loses stored state. Never delete or pause the separate shared `rg-nonprod-centralus` resources as part of Foundry cleanup.

## References

- [Connect Fabric data agents to Foundry](https://learn.microsoft.com/fabric/data-science/data-agent-foundry-fabric-iq)
- [Fabric IQ tools and authentication](https://learn.microsoft.com/azure/foundry/agents/how-to/tools/fabric-iq)
- [Incoming user delegation](https://learn.microsoft.com/azure/foundry/agents/how-to/configure-user-delegation)
