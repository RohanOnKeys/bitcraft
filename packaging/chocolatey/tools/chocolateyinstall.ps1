$ErrorActionPreference = 'Stop'

# Installs the embedded BitCraft wheel into a private virtual environment and
# exposes only `bitcraft` on PATH, so the user's own Python stays untouched.
$toolsDir   = Split-Path -Parent $MyInvocation.MyCommand.Definition
$installDir = Join-Path (Get-ToolsLocation) 'bitcraft'
$venv       = Join-Path $installDir 'venv'
$wheel      = Get-ChildItem -Path $toolsDir -Filter 'bitcraft-*.whl' | Select-Object -First 1
if (-not $wheel) { throw 'BitCraft wheel missing from the package.' }

# The python3 dependency may have just been installed; reload PATH.
Update-SessionEnvironment

function Find-Python {
    $candidates = @(
        @{ Exe = 'py';     Args = @('-3') },
        @{ Exe = 'python'; Args = @() }
    )
    foreach ($c in $candidates) {
        $cmd = Get-Command $c.Exe -ErrorAction SilentlyContinue
        # Skip the Microsoft Store alias, which only opens the Store.
        if (-not $cmd -or $cmd.Source -like '*\WindowsApps\*') { continue }
        $ok = & $cmd.Source @($c.Args) -c 'import sys; print(sys.version_info >= (3, 10))' 2>$null
        if ($LASTEXITCODE -eq 0 -and $ok -eq 'True') {
            return @{ Exe = $cmd.Source; Args = $c.Args }
        }
    }
    throw 'BitCraft needs Python 3.10 or newer (choco install python3).'
}

$python = Find-Python
if (Test-Path $venv) { Remove-Item $venv -Recurse -Force }
New-Item -ItemType Directory -Force -Path $installDir | Out-Null

Write-Host "Creating BitCraft environment in $venv"
& $python.Exe @($python.Args) -m venv $venv
if ($LASTEXITCODE -ne 0) { throw 'Could not create the BitCraft virtual environment.' }

$venvPython = Join-Path $venv 'Scripts\python.exe'
& $venvPython -m pip install --disable-pip-version-check --no-input --quiet $wheel.FullName
if ($LASTEXITCODE -ne 0) { throw 'pip could not install BitCraft.' }

Install-BinFile -Name 'bitcraft' -Path (Join-Path $venv 'Scripts\bitcraft.exe')
Write-Host 'BitCraft installed. Open a new terminal and run: bitcraft'
