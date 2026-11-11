[CmdletBinding()]
param(
    [switch]$Preview
)

$ErrorActionPreference = 'Stop'
$subscription = 'c2eaee16-e4b6-4608-b937-9005553d66f7'
$tenant = '21ddafdf-7740-4439-9b4a-6246817b2dfc'
$location = 'centralus'
$resourceGroup = 'rg-ge-vernova-foundry'
$accountName = 'ai-ge-vernova-c2eaee16'
$projectName = 'ge-vernova-fleet'
$environment = 'ge-vernova-foundry'
$infra = Join-Path $PSScriptRoot 'infrastructure'
$parameters = Get-Content -Raw (Join-Path $infra 'infra\main.parameters.json') | ConvertFrom-Json
$deployment = @($parameters.parameters.aiProjectDeploymentsJson.value | ConvertFrom-Json)[0]
$modelName = $deployment.model.name
$modelVersion = $deployment.model.version
$skuName = $deployment.sku.name
$capacity = $deployment.sku.capacity

function Invoke-Az {
    param([string[]]$Arguments)
    $result = & az @Arguments --subscription $subscription --only-show-errors
    if ($LASTEXITCODE -ne 0) {
        throw "Azure CLI failed: $($Arguments[0..([Math]::Min(2, $Arguments.Length - 1))] -join ' ')"
    }
    return $result
}

function Invoke-Azd {
    param([string[]]$Arguments)
    & azd @Arguments --cwd $infra --environment $environment --no-prompt
    if ($LASTEXITCODE -ne 0) {
        throw "azd failed: $($Arguments[0])"
    }
}

$previousUserAgent = $env:AZURE_DEV_USER_AGENT
$previousConfigDirectory = $env:AZD_CONFIG_DIR
$env:AZURE_DEV_USER_AGENT = 'microsoft_foundry_skill'
$env:AZD_CONFIG_DIR = Join-Path $env:LOCALAPPDATA 'ge-vernova-foundry\azd'
try {
    Invoke-Azd @('config', 'set', 'auth.useAzCliAuth', 'true')
    $context = Invoke-Az @('account', 'show', '-o', 'json') | ConvertFrom-Json
    if ($context.tenantId -ne $tenant) {
        throw "The selected subscription must belong to tenant $tenant."
    }
    $providerState = Invoke-Az @('provider', 'show', '--namespace', 'Microsoft.CognitiveServices',
        '--query', 'registrationState', '-o', 'tsv')
    if ($providerState -ne 'Registered') {
        Invoke-Az @('provider', 'register', '--namespace', 'Microsoft.CognitiveServices', '--wait')
    }

    $models = Invoke-Az @('cognitiveservices', 'model', 'list', '--location', $location, '-o', 'json') |
        ConvertFrom-Json
    $model = $models | Where-Object {
        $_.model.name -eq $modelName -and $_.model.version -eq $modelVersion
    } | Select-Object -First 1
    if (-not $model -or $model.model.capabilities.agentsV2 -ne 'true') {
        throw "$modelName $modelVersion is not available for prompt agents in $location."
    }
    $sku = $model.model.skus | Where-Object {
        $_.name -eq $skuName -and $_.usageName -notlike '*finetune*'
    } | Select-Object -First 1
    if (-not $sku) { throw "$skuName is not supported by $modelName in $location." }

    $usage = Invoke-Az @('cognitiveservices', 'usage', 'list', '--location', $location, '-o', 'json') |
        ConvertFrom-Json
    $quota = $usage | Where-Object { $_.name.value -eq $sku.usageName }
    $groupExists = Invoke-Az @('group', 'exists', '--name', $resourceGroup, '-o', 'tsv')
    $existing = @()
    if ($groupExists -eq 'true') {
        $group = Invoke-Az @('group', 'show', '--name', $resourceGroup, '-o', 'json') | ConvertFrom-Json
        if ($group.tags.'azd-env-name' -ne $environment -or $group.location -ne $location) {
            throw 'The existing resource group is not owned by this sample environment.'
        }
        $existing = @(Invoke-Az @('resource', 'list', '--resource-group', $resourceGroup,
            '--resource-type', 'Microsoft.CognitiveServices/accounts', '-o', 'json') |
            ConvertFrom-Json | ForEach-Object { $_ })
    }
    if ($existing.Count -gt 0 -and @($existing | Where-Object { $_.name -ne $accountName }).Count -gt 0) {
        throw 'The target resource group contains an unexpected Foundry account.'
    }
    $allocated = 0
    if ($existing.Count -gt 0) {
        $deployments = Invoke-Az @('cognitiveservices', 'account', 'deployment', 'list',
            '--resource-group', $resourceGroup, '--name', $accountName, '-o', 'json') | ConvertFrom-Json
        $current = $deployments | Where-Object { $_.name -eq $modelName }
        if ($current) {
            if ($current.properties.model.name -ne $modelName -or
                $current.properties.model.version -ne $modelVersion -or $current.sku.name -ne $skuName) {
                throw 'An existing model deployment conflicts with this sample.'
            }
            $allocated = $current.sku.capacity
        }
    }
    if (-not $quota -or ($quota.limit - $quota.currentValue + $allocated) -lt $capacity) {
        throw "Insufficient or unknown quota for $($sku.usageName). Do not change region/SKU without approval."
    }
    if (-not (Test-Path (Join-Path $infra ".azure\$environment\.env"))) {
        Invoke-Azd @('env', 'new', $environment, '--subscription', $subscription, '--location', $location)
    }
    $principalId = & az ad signed-in-user show --query id -o tsv --only-show-errors
    if ($LASTEXITCODE -ne 0) { throw 'Unable to resolve the signed-in user for scoped RBAC.' }

    $settings = @{
        AZURE_SUBSCRIPTION_ID = $subscription
        AZURE_TENANT_ID = $tenant
        AZURE_LOCATION = $location
        AZURE_RESOURCE_GROUP = $resourceGroup
        AZURE_AI_ACCOUNT_NAME = $accountName
        AZURE_AI_PROJECT_NAME = $projectName
        AZURE_AI_DEPLOYMENTS_LOCATION = $location
        AZURE_PRINCIPAL_ID = $principalId
        AZURE_PRINCIPAL_TYPE = 'User'
        AI_PROJECT_CONNECTIONS = '[]'
        AI_PROJECT_CONNECTION_CREDENTIALS = '{}'
        AI_PROJECT_DEPENDENT_RESOURCES = '[]'
        ENABLE_HOSTED_AGENTS = 'false'
        ENABLE_CAPABILITY_HOST = 'false'
        ENABLE_MONITORING = 'false'
        USE_EXISTING_AI_PROJECT = 'false'
        AZD_AGENT_SKIP_ACR = 'true'
    }
    foreach ($setting in $settings.GetEnumerator()) {
        Invoke-Azd @('env', 'set', $setting.Key, $setting.Value)
    }
    Write-Host "Target: $resourceGroup / $accountName / $projectName ($location)"
    Write-Host "Model: $modelName $modelVersion / $skuName / capacity $capacity (usage billed separately)"
    if ($Preview) {
        Invoke-Azd @('provision', '--preview')
    } else {
        Invoke-Azd @('provision')
        Invoke-Az @('cognitiveservices', 'account', 'deployment', 'show', '--resource-group',
            $resourceGroup, '--name', $accountName, '--deployment-name', $modelName,
            '--query', '{name:name,state:properties.provisioningState,model:properties.model,sku:sku}', '-o', 'json')
    }
} finally {
    $env:AZURE_DEV_USER_AGENT = $previousUserAgent
    $env:AZD_CONFIG_DIR = $previousConfigDirectory
}
