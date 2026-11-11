# Manufacturing PDF hybrid search deployment

Status: Deployed and verified

## Approved Search scope (2026-11-11)

- Current CLI subscription, East US, resource group manufacturing-search-demo.
- Free Azure AI Search only; stop before any paid Search SKU.
- New Azure OpenAI account with text-embedding-3-small version 1,
  Standard capacity 10. Pay-per-token embedding charges approved.
- Five fictional product PDF datasheets, local extraction, chunking, and upload
  into a hybrid keyword/vector index with source filename and page metadata.
- Entra-only authentication and resource-scoped Search Service Contributor,
  Search Index Data Contributor, and Cognitive Services OpenAI User roles
  for the deploying user.
- Standalone sample under samples/manufacturing-search. No Blob Storage,
  chat model, semantic ranker, or modifications to the existing Foundry demo.
- User approved reusable scripts, README, and this deployment plan.

## Approach and gates

Recipe: AZCLI with an incremental resource-group ARM JSON template.
Use explicit subscription selection and validate/what-if before deployment.
Stop on Free-tier unavailability, insufficient quota, or policy denial.
Model availability and 350 Standard capacity quota were confirmed in East US;
current usage is zero. No Search services currently exist in this subscription.
Microsoft.Search requires provider registration.

Generate PDFs and test extraction/chunking locally. Deploy only the approved
resources, ingest text and embeddings, then verify keyword, vector-only, and
hybrid queries against expected product IDs and persist nonsecret evidence.
Search stays Free; embedding estimates are not a hard budget cap.
Public HTTPS endpoints require Entra authorization; no secrets are saved.
No automatic deletion or modification of pre-existing resources.

## Search preparation verification

Three local tests passed: five actual two-page PDF extraction roundtrips with
unique keys and source metadata, chunk overlap/boundaries, and empty corpus
failure. Generated five PDFs and ten page chunks. PowerShell parser and ARM
JSON parser passed. Dependencies are isolated in the sample's ignored venv.
ARM provider validation and what-if remain gates before resource creation.

## All validation checks pass

- Core validation: Azure CLI/authentication, ARM JSON parse, provider validation,
  and what-if. Bicep compilation is not applicable to this ARM JSON source.
- Docker build: not applicable (no container or application deployment).
- Azure Policy validation: ARM validation and what-if must report no denials.
- Roles: deploying user must be allowed to create resources and role assignments.
- Runtime: no Node.js runtime is deployed; this is a local Python ingestion tool.

## 7. Search Validation Proof

- Three focused local tests and PDF generation passed.
- PowerShell and ARM JSON parsing passed.
- Azure group-scope ARM validation succeeded.
- What-if: exactly six Create operations (Search, OpenAI, embedding deployment,
  three resource-scoped role assignments); no Modify or Delete operations.
- Microsoft.Search registered; dedicated tagged East US resource group created
  for provider validation. No Search/OpenAI resources created by preview.
- No policy denial reported by ARM provider validation/what-if.
- Commands: sample venv `python -m unittest -v`, `search_demo.py generate`,
  PowerShell Parser.ParseFile, ConvertFrom-Json, and
  `provision.ps1 -SubscriptionId <approved-subscription> -Preview` (includes
  `az deployment group validate` and `az deployment group what-if`).
- Resource-group permissions API confirms wildcard resource and authorization
  permissions. Three role IDs verified using `az role definition list`;
  assignments are scoped only to the two new services.
- Initial deployment exposed a provider-only validation error: Search requires
  authOptions to be absent when disableLocalAuth is true. Removed authOptions;
  Entra-only authentication remains enabled. Revalidation required before retry.
- Corrected ARM validation and what-if passed on 2026-11-11. Incremental retry
  creates only Search and its two roles; existing approved OpenAI resources
  remain. Embedding what-if differences are provider-populated currentCapacity
  and default policy fields, not changes to model, tier, or capacity.

## Search deployment result

- Search srch-mfg-45b8aab5e6: Succeeded, running, Free, East US.
- OpenAI aoai-mfg-45b8aab5e6 and text-embedding-3-small: Succeeded,
  Standard capacity 10, model version 1. Both services disable local key auth.
- Actual resource-scoped role assignments read back and confirmed.
- Five PDFs generated, ten chunks extracted from their pages and uploaded into
  manufacturing-products with 1,536-dimensional embeddings.
- Fifteen live rank-1 product checks passed: five queries in each of keyword,
  vector-only, and hybrid modes. Source filename and page metadata verified.
- Extra natural-language hybrid query returned SENSOR-500, source PDF page 1.
- Nonsecret deployment-status.json and verification.json persisted in sample.
- No dependencies or source in the existing embedding app were changed.

---

# Previous Databricks manufacturing demo deployment (preserved)

Status: Provisioned; authenticated workspace readiness blocked

## Approved scope

Create one dedicated resource group, one Azure Databricks Premium workspace,
and one system-assigned managed-identity Access Connector in East US 2.
The user explicitly selected the Azure subscription at execution time.
Do not start compute, create clusters or SQL warehouses, provision Fabric
capacity, create service principal secrets, or grant broad storage access.

## Approach

Use an ARM JSON template deployed with Azure CLI. Keep infrastructure alongside
the isolated manufacturing demo and leave the embedding application unchanged.
Pass subscription and resource names explicitly at execution time; do not commit
environment-specific credentials or resource identifiers.

Template: `samples\manufacturing-onelake\infra\main.json`, subscription scope,
with an incremental nested resource-group deployment. Parameters have demo
defaults; no compute resources or credentials are declared.

The user approved this scope, subscription, and East US 2 through the provisioning
confirmation form. This supersedes the earlier prohibition on new Databricks
resources, not the prohibition on compute or Fabric capacity.

## Planned names

- Resource group: rg-contoso-mfg-dbx-demo-eus2
- Workspace: dbw-contoso-mfg-demo-eus2
- Managed resource group: rg-contoso-mfg-dbx-managed-eus2
- Access Connector: ac-contoso-mfg-onelake-eus2

## Gates and verification

1. Verify account context, resource provider availability, regional support,
   resource counts/limits, permissions, and name collisions.
2. Generate and validate the ARM template and inspect a deployment what-if.
3. Deploy only the approved resources.
4. Verify workspace provisioning, Premium SKU, access-connector managed identity,
   and absence of started compute where data-plane permissions permit.
5. Record actual deployment results privately in the session workspace.

## Validation steps

- All validation checks pass:
  - Azure CLI is installed and authenticated to the explicitly selected subscription.
  - ARM JSON parses and declares only the approved resource types; Bicep compilation
    is not applicable because the source template is ARM JSON.
  - Subscription-scope ARM validation succeeds.
  - Subscription-scope what-if shows only the intended creations and no deletions.
  - Existing policy assignments and provider validation allow the deployment.
  - Docker/application build is not applicable: no application code is deployed.
  - Subscription principal has provisioning permissions.

Recipe: AZCLI, adapted for an ARM JSON source rather than a Bicep source. Run the
same authentication, provider validation, and what-if checks directly; do not
misreport a skipped Bicep compiler as a successful compilation.

## Preparation findings

- Subscription is enabled and current principal has subscription provisioning
  permissions. Both requested resource-group names were absent.
- Microsoft.Databricks supports workspaces and access connectors in East US 2
  with stable API version 2026-01-01. The initially unregistered provider has
  been registered successfully.
- Existing Databricks workspace and access-connector counts are zero in the
  subscription. Existing East US 2 storage-account count is zero.
- The quota CLI extension was missing, then installed into the isolated extension
  directory. Databricks quota discovery returned BadRequest; that API does not
  provide a usable limit here. Do not interpret that as unlimited quota.
  Provider-side ARM validation is required before actual deployment.
- Existing policy assignments cover Defender protection rather than a discovered
  regional restriction; ARM validation/what-if remains authoritative for denials.
- No VM, cluster, or warehouse quota is requested because no compute is deployed.

## Cost and security

Workspace creation also creates a Databricks-managed resource group containing
service-managed infrastructure such as storage/network resources. Storage can
incur charges even without compute. No hard budget cap is implied.
Use Entra authentication and the access connector's managed identity; do not
generate PATs or client secrets. Keep secure cluster connectivity enabled.

## Remaining integration prerequisites

Unity Catalog assignment and administrator rights, OneLake external-location
and publication previews, and a compatible Fabric capacity remain separate
gates. Creating a workspace does not establish that these prerequisites pass.

## Deployment result

- Subscription deployment and nested resource-group deployment: Succeeded.
- Premium workspace and dedicated access connector: Succeeded in East US 2.
- Secure cluster connectivity: enabled (`enableNoPublicIp=true`).
- Connector has a system-assigned managed identity.
- The service-managed resource group contains storage, identity/access connector,
  VNet/NSG, NAT gateway, and public IP resources; no VM was listed.
- No compute-start or Fabric-capacity creation operation was issued.
- Authenticated workspace API currently reports "Did not find workspace with
  specified org ID." A browser launch redirects to Databricks account signup.
  The user reports completing onboarding, but verification still fails.
  Requests with an explicit Azure workspace resource-ID header and with Azure
  management bootstrap authentication returned the same error.
- This is an unresolved data-plane readiness/account-association issue, not a
  confirmed provisioning failure or a confirmed missing onboarding action.
  Further investigation requires Databricks/Azure administration or support;
  do not recreate or delete the successfully provisioned resources automatically.
- Do not claim authenticated workspace usability, zero active serverless compute,
  Unity Catalog setup, or preview availability until subsequent checks succeed.
- Actual URLs and identity/resource IDs are recorded privately in the session
  plan rather than committed to the reusable sample source.
- Local validation: nine tests passed, including explicit infrastructure
  resource-type allowlist and Premium/managed-identity/connectivity settings.

## 7. Validation Proof

The following checks ran against the explicitly user-approved subscription:

- Azure CLI authentication: passed; subscription enabled.
- Subscription permissions API: principal has resource provisioning permissions.
- ARM JSON parsing and explicit resource-type allowlist: passed.
- `az deployment sub validate --location eastus2 --name contoso-mfg-databricks-demo
  --template-file samples\manufacturing-onelake\infra\main.json`: Succeeded,
  error null (explicit subscription flag supplied).
- `az deployment sub what-if` with the same scope/name/template:
  Succeeded, error null, exactly three Create results (dedicated resource group,
  workspace, and access connector); zero Modify and zero Delete results.
- Static identity review: system-assigned identity only; no role assignments,
  secrets, clusters, warehouses, or Fabric resources in the template.
- Application/Docker build and Bicep compilation: not applicable to ARM JSON
  infrastructure-only deployment. Existing application remains unchanged.

The Databricks-managed resource group is created by the workspace resource
provider and is not a separately declared template resource.
