param(
    [string] $ReleaseDir
)

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$localPython = Join-Path $projectRoot '.venv\Scripts\python.exe'
$tempDirPrefix = 'CodexQuotaMonitor_build_'

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
    param([Parameter(ValueFromRemainingArguments = $true)][string[]] $PythonArgs)
    & $pythonCommand @pythonPrefix @PythonArgs
    if ($LASTEXITCODE -ne 0) {
        throw "Python command failed with exit code $LASTEXITCODE."
    }
}

function New-IsolatedTempDir {
    param([string] $Prefix)

    $base = [System.IO.Path]::GetTempPath()
    for ($attempt = 0; $attempt -lt 32; $attempt++) {
        $candidate = Join-Path $base ($Prefix + [guid]::NewGuid().ToString('N'))
        if (-not (Test-Path -LiteralPath $candidate)) {
            New-Item -ItemType Directory -Path $candidate -Force | Out-Null
            return (Get-Item -LiteralPath $candidate).FullName
        }
    }
    throw 'Unable to create an isolated temporary working directory.'
}

function Remove-IsolatedTempDir {
    param([string] $Path, [string] $Prefix)

    if ([string]::IsNullOrWhiteSpace($Path)) {
        return
    }

    $item = Get-Item -LiteralPath $Path -ErrorAction SilentlyContinue
    if ($null -eq $item -or -not $item.PSIsContainer) {
        return
    }

    # Safety: only remove a directory that this run created, that resolves to the
    # system temp directory, and whose leaf name carries our unique prefix.
    $tempBase = [System.IO.Path]::GetFullPath([System.IO.Path]::GetTempPath()).TrimEnd([char]'\')
    $fullPath = [System.IO.Path]::GetFullPath($item.FullName).TrimEnd([char]'\')
    $leaf = Split-Path -Leaf $fullPath

    if (-not $fullPath.StartsWith($tempBase + '\', [System.StringComparison]::OrdinalIgnoreCase)) {
        Write-Warning "Skipped cleanup, path is not under the system temp directory: $fullPath"
        return
    }
    if (-not $leaf.StartsWith($Prefix, [System.StringComparison]::OrdinalIgnoreCase)) {
        Write-Warning "Skipped cleanup, unexpected directory name: $fullPath"
        return
    }

    Remove-Item -LiteralPath $fullPath -Recurse -Force -ErrorAction SilentlyContinue
}

Invoke-Python '-c' 'import sys; print(sys.executable); print(sys.version)'

try {
    Invoke-Python '-c' 'import PyInstaller; print("PyInstaller", PyInstaller.__version__)'
} catch {
    throw 'PyInstaller is required for packaging. Install it with: python -m pip install -r requirements-dev.txt'
}

# Build artifacts must never appear inside the repository. Record which of them
# already exist so the post-build check only reports paths this run created.
$projectArtifacts = @('build', 'dist', 'src\__pycache__', 'tests\__pycache__')
$artifactStateBefore = @{}
foreach ($relative in $projectArtifacts) {
    $artifactStateBefore[$relative] = Test-Path -LiteralPath (Join-Path $projectRoot $relative)
}

$tempRoot = $null
$pushedLocation = $false
$previousPycachePrefix = $env:PYTHONPYCACHEPREFIX

try {
    $tempRoot = New-IsolatedTempDir -Prefix $tempDirPrefix
    $workPath = Join-Path $tempRoot 'pyinstaller'
    $pycachePrefix = Join-Path $tempRoot 'pycache'
    New-Item -ItemType Directory -Path $workPath -Force | Out-Null
    New-Item -ItemType Directory -Path $pycachePrefix -Force | Out-Null

    # Keep Python bytecode caches out of the source tree.
    $env:PYTHONPYCACHEPREFIX = $pycachePrefix
    Write-Output "Isolated build directory: $tempRoot"

    if ([string]::IsNullOrWhiteSpace($ReleaseDir)) {
        $ReleaseDir = Join-Path (Split-Path -Parent $projectRoot) 'CodexQuotaMonitor_release'
    }
    New-Item -ItemType Directory -Path $ReleaseDir -Force | Out-Null

    Push-Location $projectRoot
    $pushedLocation = $true

    Invoke-Python '-m' 'unittest' 'discover' '-s' 'tests' '-p' 'test_*.py' '-v'
    Invoke-Python '-m' 'compileall' '-q' 'src' 'tests'
    Invoke-Python (Join-Path $projectRoot 'scripts\create_icon.py')

    Invoke-Python '-m' 'PyInstaller' `
        --noconfirm `
        --clean `
        --distpath $ReleaseDir `
        --workpath $workPath `
        (Join-Path $projectRoot 'CodexQuotaMonitor.spec')

    $exePath = Join-Path $ReleaseDir 'CodexQuotaMonitor_v1.4.1.exe'
    if (-not (Test-Path -LiteralPath $exePath)) {
        throw "Expected executable was not produced: $exePath"
    }

    Get-Item -LiteralPath $exePath | Select-Object FullName, Length, LastWriteTime
    Get-FileHash -Algorithm SHA256 -LiteralPath $exePath

    $violations = @()
    foreach ($relative in $projectArtifacts) {
        if (-not $artifactStateBefore[$relative] -and (Test-Path -LiteralPath (Join-Path $projectRoot $relative))) {
            $violations += $relative
        }
    }
    $strayBytecode = @(Get-ChildItem -LiteralPath $projectRoot -Recurse -Force -File -Filter '*.pyc' -ErrorAction SilentlyContinue)

    if ($violations.Count -gt 0 -or $strayBytecode.Count -gt 0) {
        $reported = if ($violations.Count -gt 0) { $violations -join ', ' } else { 'none' }
        Write-Warning "Project directory check failed. Newly created paths: $reported. Stray .pyc files: $($strayBytecode.Count)."
    } else {
        Write-Output 'Project directory check: no build artifacts were created inside the repository.'
    }
} finally {
    if ($pushedLocation) {
        Pop-Location
    }
    if ($null -eq $previousPycachePrefix) {
        Remove-Item Env:\PYTHONPYCACHEPREFIX -ErrorAction SilentlyContinue
    } else {
        $env:PYTHONPYCACHEPREFIX = $previousPycachePrefix
    }
    Remove-IsolatedTempDir -Path $tempRoot -Prefix $tempDirPrefix
}
