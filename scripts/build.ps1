param(
    [string] $ReleaseDir
)

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$localPython = Join-Path $projectRoot '.venv\Scripts\python.exe'

$pythonCommand = $null
$pythonPrefix = @()

if (Test-Path -LiteralPath $localPython) {
    & $localPython -c 'import sys; print(sys.executable)' *> $null
    if ($LASTEXITCODE -eq 0) {
        $pythonCommand = $localPython
    }
}

if ($null -eq $pythonCommand -and (Get-Command py -ErrorAction SilentlyContinue)) {
    $pythonCommand = (Get-Command py).Source
    $pythonPrefix = @('-3')
    & $pythonCommand @pythonPrefix -c 'import sys; print(sys.executable)' *> $null
    if ($LASTEXITCODE -ne 0) {
        $pythonCommand = $null
        $pythonPrefix = @()
    }
}

if ($null -eq $pythonCommand -and (Get-Command python -ErrorAction SilentlyContinue)) {
    $pythonCommand = (Get-Command python).Source
    & $pythonCommand -c 'import sys; print(sys.executable)' *> $null
    if ($LASTEXITCODE -ne 0) {
        $pythonCommand = $null
    }
}

if ($null -eq $pythonCommand) {
    throw 'No usable Python 3 environment was found.'
}

function Invoke-Python {
    param([Parameter(ValueFromRemainingArguments = $true)][string[]] $Args)
    & $pythonCommand @pythonPrefix @Args
    if ($LASTEXITCODE -ne 0) {
        throw "Python command failed with exit code $LASTEXITCODE."
    }
}

Invoke-Python -c 'import sys; print(sys.executable); print(sys.version)'

try {
    Invoke-Python -c 'import PyInstaller; print("PyInstaller", PyInstaller.__version__)'
} catch {
    throw 'PyInstaller is required for packaging. Install it with: python -m pip install -r requirements-dev.txt'
}

Push-Location $projectRoot
try {
    if ([string]::IsNullOrWhiteSpace($ReleaseDir)) {
        $ReleaseDir = Join-Path (Split-Path -Parent $projectRoot) 'CodexQuotaMonitor_release'
    }
    New-Item -ItemType Directory -Path $ReleaseDir -Force | Out-Null
    Invoke-Python -m unittest discover -s tests -p 'test_*.py' -v
    Invoke-Python -m compileall -q src tests
    Invoke-Python (Join-Path $projectRoot 'scripts\create_icon.py')

    Invoke-Python -m PyInstaller `
        --noconfirm `
        --clean `
        --distpath $ReleaseDir `
        --workpath (Join-Path $projectRoot 'build') `
        (Join-Path $projectRoot 'CodexQuotaMonitor.spec')

    $exePath = Join-Path $ReleaseDir 'CodexQuotaMonitor_v1.4.exe'
    if (-not (Test-Path -LiteralPath $exePath)) {
        throw "Expected executable was not produced: $exePath"
    }

    Get-Item -LiteralPath $exePath | Select-Object FullName, Length, LastWriteTime
    Get-FileHash -Algorithm SHA256 -LiteralPath $exePath
} finally {
    Pop-Location
}
