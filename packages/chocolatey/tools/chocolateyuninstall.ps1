$ErrorActionPreference = 'Stop'

Uninstall-BinFile -Name 'bitcraft'

$installDir = Join-Path (Get-ToolsLocation) 'bitcraft'
if (Test-Path $installDir) {
    Remove-Item $installDir -Recurse -Force
}
