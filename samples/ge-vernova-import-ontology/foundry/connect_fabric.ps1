[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$tenant = '21ddafdf-7740-4439-9b4a-6246817b2dfc'
$connectionName = 'ge-vernova-fabric'
$target = 'https://api.fabric.microsoft.com/v1/mcp/workspaces/aeeddd08-ac34-4681-b9cd-c84424c97f3e/dataagents/664cedb7-472e-485c-a77b-70b47a18f878/agent'
$audience = 'https://analysis.windows.net/powerbi/api'
$previousUserAgent = $env:AZURE_DEV_USER_AGENT
$env:AZURE_DEV_USER_AGENT = 'microsoft_foundry_skill'
try {
    $projectId = & azd env get-value AZURE_AI_PROJECT_ID --cwd (Join-Path $PSScriptRoot 'infrastructure') -e ge-vernova-foundry
    if ($LASTEXITCODE -ne 0 -or -not $projectId) { throw 'Provision the Foundry project first.' }
    if ($projectId -notlike '/subscriptions/c2eaee16-e4b6-4608-b937-9005553d66f7/*') {
        throw 'The azd project does not belong to the approved subscription.'
    }
    $token = & az account get-access-token --tenant $tenant --resource 'https://management.azure.com/' --query accessToken -o tsv
    if ($LASTEXITCODE -ne 0) { throw 'Unable to acquire a tenant-scoped ARM token.' }
    $headers = @{ Authorization = "Bearer $token" }
    $base = "https://management.azure.com$projectId/connections/$connectionName"
    $uri = "${base}?api-version=2025-10-01-preview"
    $existing = Invoke-WebRequest -Uri $uri -Headers $headers -SkipHttpErrorCheck
    if ($existing.StatusCode -notin @(200, 404)) {
        throw "Connection lookup failed (HTTP $($existing.StatusCode)): $($existing.Content)"
    }
    if ($existing.StatusCode -eq 200) {
        $current = $existing.Content | ConvertFrom-Json
        if ($current.properties.target -ne $target -or $current.properties.category -ne 'RemoteTool') {
            throw 'The existing connection belongs to a different tool; refusing to replace it.'
        }
        if ($current.properties.authType -notin @('UserEntraToken', 'OAuth2')) {
            throw 'The existing connection uses an unexpected authentication method.'
        }
    }
    Write-Host "Configuring $connectionName with the approved incoming Entra user context."
    $body = @{
        properties = @{
            authType = 'UserEntraToken'
            category = 'RemoteTool'
            target = $target
            audience = $audience
            scopes = @("$audience/DataAgent.Execute.All")
            metadata = @{ type = 'generic_mcp'; audience = $audience }
            isSharedToAll = $true
        }
    } | ConvertTo-Json -Depth 6
    Invoke-RestMethod -Uri $uri -Method Put -Headers $headers -ContentType 'application/json' -Body $body | Out-Null
    $saved = Invoke-RestMethod -Uri $uri -Headers $headers
    if ($saved.properties.target -ne $target -or $saved.properties.authType -ne 'UserEntraToken' -or
        $saved.properties.audience -ne $audience) {
        throw 'The saved connection differs from the intended Fabric delegated-user connection.'
    }
    $saved | Select-Object id, name, @{ Name = 'target'; Expression = { $_.properties.target } },
        @{ Name = 'authType'; Expression = { $_.properties.authType } } | ConvertTo-Json
} finally {
    $token = $null
    $env:AZURE_DEV_USER_AGENT = $previousUserAgent
}
