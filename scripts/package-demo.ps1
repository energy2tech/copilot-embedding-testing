param(
    [string]$OutputPath = "",
    [switch]$Force
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest
$root = Split-Path -Parent $PSScriptRoot
if ([string]::IsNullOrWhiteSpace($OutputPath)) {
    $OutputPath = Join-Path $root "release\pbie-copilot-demo.zip"
}
$OutputPath = [System.IO.Path]::GetFullPath($OutputPath)
if ([System.IO.Path]::GetExtension($OutputPath) -ne ".zip") {
    throw "OutputPath must end in .zip."
}

# A fixed allowlist prevents local configuration and diagnostic files entering the ZIP.
$files = @(
    "package.json", "package-lock.json", "tsconfig.json", "vite.config.ts",
    "index.html", ".gitignore", "README.md",
    "public\config.example.json", "public\auth.html",
    "src\main.ts", "src\auth.ts", "src\config.ts", "src\embed.ts",
    "src\diagnostics.ts", "src\style.css",
    "tests\auth.test.ts", "tests\config-diagnostics.test.ts", "tests\embed.test.ts",
    "scripts\package-demo.ps1"
)
foreach ($file in $files) {
    if (-not (Test-Path -LiteralPath (Join-Path $root $file) -PathType Leaf)) {
        throw "Required distribution file is missing: $file. Run npm install to generate the lockfile if needed."
    }
}
if (Test-Path -LiteralPath $OutputPath) {
    if (-not $Force) { throw "ZIP already exists. Use -Force or choose another -OutputPath." }
    if (-not (Test-Path -LiteralPath $OutputPath -PathType Leaf)) { throw "OutputPath is not a file." }
    Remove-Item -LiteralPath $OutputPath -Force
}
[System.IO.Directory]::CreateDirectory((Split-Path -Parent $OutputPath)) | Out-Null
Add-Type -AssemblyName System.IO.Compression
Add-Type -AssemblyName System.IO.Compression.FileSystem
$stream = [System.IO.File]::Open($OutputPath, [System.IO.FileMode]::CreateNew)
try {
    $zip = [System.IO.Compression.ZipArchive]::new($stream, [System.IO.Compression.ZipArchiveMode]::Create)
    try {
        foreach ($file in $files) {
            $entry = $file.Replace("\", "/")
            [System.IO.Compression.ZipFileExtensions]::CreateEntryFromFile(
                $zip, (Join-Path $root $file), $entry, [System.IO.Compression.CompressionLevel]::Optimal
            ) | Out-Null
        }
    } finally { $zip.Dispose() }
} finally { $stream.Dispose() }
Write-Output "Created $OutputPath"
Write-Output "Includes source, tests, lockfile and placeholder configuration only. Review the ZIP before sharing."
