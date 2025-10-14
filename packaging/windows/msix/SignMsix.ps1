param(
    [Parameter(Mandatory = $true)]
    [string]$MsixPath,
    [Parameter(Mandatory = $true)]
    [string]$CertificatePath,
    [Parameter(Mandatory = $true)]
    [string]$TimestampUrl,
    [Parameter(Mandatory = $false)]
    [string]$CertificatePassword
)

if (-not (Test-Path $MsixPath)) {
    throw "MSIX introuvable: $MsixPath"
}

if (-not (Test-Path $CertificatePath)) {
    throw "Certificat introuvable: $CertificatePath"
}

$signtoolArgs = @(
    "sign",
    "/fd", "SHA256",
    "/a",
    "/tr", $TimestampUrl,
    "/td", "SHA256",
    "/f", $CertificatePath,
    $MsixPath
)

if ($CertificatePassword) {
    $signtoolArgs += @("/p", $CertificatePassword)
}

$signtool = "${env:ProgramFiles(x86)}\Windows Kits\10\bin\x64\signtool.exe"
if (-not (Test-Path $signtool)) {
    $signtool = "${env:ProgramFiles(x86)}\Windows Kits\10\bin\10.0.19041.0\x64\signtool.exe"
}

if (-not (Test-Path $signtool)) {
    throw "signtool.exe introuvable. Installez le SDK Windows 10."
}

& $signtool @signtoolArgs
