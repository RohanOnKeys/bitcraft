# Opens BitCraft in a new, large terminal window. Usage: ./bitcraft.ps1 [run | demo | here | status] [options]
$root = $PSScriptRoot
$py = Join-Path $root '.venv\Scripts\python.exe'
if (-not (Test-Path $py)) { $py = 'python' }
Push-Location $root
try { & $py -m tui.cli @args } finally { Pop-Location }
