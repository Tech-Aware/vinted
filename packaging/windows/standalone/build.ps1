[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$PythonPath,

    [string]$OutputDirectory
)

$ErrorActionPreference = "Stop"

$projectRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..\..")
$specPath = Join-Path $PSScriptRoot "vinted_standalone.spec"

if (-not (Test-Path $PythonPath)) {
    throw "Python introuvable à l'emplacement spécifié: $PythonPath"
}

if (-not $OutputDirectory) {
    $OutputDirectory = Join-Path $projectRoot "dist"
}

Write-Host "Utilisation de Python: $PythonPath"
Write-Host "Installation des dépendances et de PyInstaller"
& $PythonPath -m pip install --upgrade pip | Out-Null
& $PythonPath -m pip install -r (Join-Path $projectRoot "requirements.txt") PyInstaller

Push-Location $projectRoot
try {
    Write-Host "Construction de l'exécutable autonome"
    & $PythonPath -m PyInstaller $specPath --clean
} finally {
    Pop-Location
}

$standaloneDir = Join-Path $projectRoot "dist\VintedAssistant"
if (-not (Test-Path $standaloneDir)) {
    throw "Le dossier généré par PyInstaller est introuvable: $standaloneDir"
}

if (-not (Test-Path $OutputDirectory)) {
    New-Item -ItemType Directory -Path $OutputDirectory | Out-Null
}

$archivePath = Join-Path $OutputDirectory "VintedAssistant-win64.zip"
if (Test-Path $archivePath) {
    Remove-Item $archivePath -Force
}

Write-Host "Compression du dossier standalone"
Compress-Archive -Path (Join-Path $standaloneDir '*') -DestinationPath $archivePath -Force

Write-Host "Archive prête: $archivePath"
