param(
    [Parameter(Mandatory=$true)]
    [string]$Email,
    [string]$Name = "Administrador"
)

$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$Backend = Join-Path $Root "BackEnd\Python"
$VenvPython = Join-Path $Backend ".venv\Scripts\python.exe"
$Python = if (Test-Path $VenvPython) { $VenvPython } else { "python" }

$SecurePassword = Read-Host "Senha do administrador" -AsSecureString
$Ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($SecurePassword)
$PlainPassword = $null

try {
    $PlainPassword = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($Ptr)
    if ([string]::IsNullOrWhiteSpace($PlainPassword)) {
        throw "A senha nao pode ser vazia."
    }

    $oldEmail = $env:ADMIN_EMAIL
    $oldPassword = $env:ADMIN_PASSWORD
    $oldName = $env:ADMIN_NAME
    $oldReset = $env:ADMIN_RESET_PASSWORD

    try {
        $env:ADMIN_EMAIL = $Email
        $env:ADMIN_PASSWORD = $PlainPassword
        $env:ADMIN_NAME = $Name
        $env:ADMIN_RESET_PASSWORD = "true"

        Push-Location $Backend
        & $Python scripts/create_admin.py
        if ($LASTEXITCODE -ne 0) {
            throw "Falha ao criar/promover o administrador (exit code $LASTEXITCODE)."
        }
        Pop-Location
    }
    finally {
        $env:ADMIN_EMAIL = $oldEmail
        $env:ADMIN_PASSWORD = $oldPassword
        $env:ADMIN_NAME = $oldName
        $env:ADMIN_RESET_PASSWORD = $oldReset
    }
}
finally {
    if ($Ptr -ne [IntPtr]::Zero) {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($Ptr)
    }
    $PlainPassword = $null
}
