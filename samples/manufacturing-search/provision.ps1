[CmdletBinding()]
param(
    [Parameter(Mandatory)][string]$SubscriptionId,
    [string]$ResourceGroup = 'manufacturing-search-demo',
    [switch]$Preview
)

$ErrorActionPreference = 'Stop'
function Invoke-Az {
    param([string[]]$Arguments)
    $result = & az @Arguments --subscription $SubscriptionId --only-show-errors
    if ($LASTEXITCODE -ne 0) { throw "Azure CLI failed: $($Arguments[0..1] -join ' ')" }
    return $result
}

$account = Invoke-Az @('account', 'show', '-o', 'json') | ConvertFrom-Json
$principalId = & az ad signed-in-user show --query id -o tsv --only-show-errors
if ($LASTEXITCODE -ne 0) { throw 'Sign in as a user with resource provisioning and role assignment permissions.' }
$hash = [System.Security.Cryptography.SHA256]::Create()
try {
    $suffix = ([BitConverter]::ToString($hash.ComputeHash(
        [Text.Encoding]::UTF8.GetBytes("$SubscriptionId/$ResourceGroup")))).Replace('-', '').Substring(0, 10).ToLowerInvariant()
} finally { $hash.Dispose() }
$searchName = "srch-mfg-$suffix"
$openaiName = "aoai-mfg-$suffix"

$existing = Invoke-Az @('group', 'exists', '-n', $ResourceGroup, '-o', 'tsv')
if ($existing -eq 'true') {
    $group = Invoke-Az @('group', 'show', '-n', $ResourceGroup, '-o', 'json') | ConvertFrom-Json
    if ($group.tags.sample -ne 'manufacturing-search' -or $group.location -ne 'eastus') {
        throw 'Existing resource group is not owned by this East US sample.'
    }
}
$services = @(Invoke-Az @('resource', 'list', '--resource-type', 'Microsoft.Search/searchServices',
    '-o', 'json') | ConvertFrom-Json | ForEach-Object { $_ })
foreach ($service in $services) {
    if ($service.sku.name -eq 'free' -and
        ($service.name -ne $searchName -or $service.resourceGroup -ne $ResourceGroup)) {
        throw 'A Free Search service already exists. No paid fallback is permitted.'
    }
}
$usage = Invoke-Az @('cognitiveservices', 'usage', 'list', '--location', 'eastus',
    '-o', 'json') | ConvertFrom-Json
$quota = $usage | Where-Object { $_.name.value -eq 'OpenAI.Standard.text-embedding-3-small' }
if (-not $quota -or ($quota.limit - $quota.currentValue) -lt 10) {
    throw 'Insufficient unallocated Standard embedding quota (10 required); no region/SKU fallback.'
}
foreach ($provider in @('Microsoft.Search', 'Microsoft.CognitiveServices')) {
    $state = Invoke-Az @('provider', 'show', '-n', $provider, '--query', 'registrationState', '-o', 'tsv')
    if ($state -ne 'Registered') {
        Invoke-Az @('provider', 'register', '-n', $provider, '--wait') | Out-Host
    }
}
if ($existing -ne 'true') {
    Invoke-Az @('group', 'create', '-n', $ResourceGroup, '-l', 'eastus',
        '--tags', 'sample=manufacturing-search', '-o', 'none')
}
$arguments = @('--resource-group', $ResourceGroup, '--name', 'manufacturing-search',
    '--template-file', (Join-Path $PSScriptRoot 'infra\main.json'), '--parameters',
    "searchName=$searchName", "openaiName=$openaiName", "principalId=$principalId")
Invoke-Az (@('deployment', 'group', 'validate') + $arguments + @('-o', 'none'))
Invoke-Az (@('deployment', 'group', 'what-if') + $arguments) | Out-Host
if ($Preview) {
    Write-Host 'Preview complete. Provider registration and an empty tagged resource group may have been created.'
    return
}
$deployment = Invoke-Az (@('deployment', 'group', 'create') + $arguments + @('-o', 'json')) | ConvertFrom-Json
if ($deployment.properties.provisioningState -ne 'Succeeded') { throw 'Deployment did not succeed.' }
$config = @{
    subscriptionId = $SubscriptionId
    tenantId = $account.tenantId
    resourceGroup = $ResourceGroup
    searchName = $searchName
    openaiName = $openaiName
}
foreach ($output in $deployment.properties.outputs.PSObject.Properties) {
    $config[$output.Name] = $output.Value.value
}
$config | ConvertTo-Json | Set-Content -Encoding utf8 (Join-Path $PSScriptRoot 'config.local.json')
Write-Host 'Deployed Free Search and usage-billed embeddings. Local config saved without credentials.'
