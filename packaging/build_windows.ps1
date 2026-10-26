$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
if ($env:OS -ne 'Windows_NT') { throw 'Run this script on Windows x64.' }
function Invoke-Checked {
    param([string]$Program, [string[]]$Arguments)
    & $Program @Arguments
    if ($LASTEXITCODE -ne 0) { throw "$Program failed with exit code $LASTEXITCODE" }
}
foreach ($program in @('py','node','npm.cmd','cargo','rustup')) {
    if (-not (Get-Command $program -ErrorAction SilentlyContinue)) { throw "Missing prerequisite: $program. See docs/WINDOWS_BUILD.md." }
}
Invoke-Checked 'py' @('-3.11','-c','import platform,struct; assert platform.machine().lower() in ("amd64","x86_64") and struct.calcsize("P")==8, "Use x64 Python"')
Invoke-Checked 'py' @('-3.11','-m','venv','.venv')
$python = Join-Path (Get-Location) '.venv\Scripts\python.exe'
Invoke-Checked $python @('-m','pip','install','--upgrade','pip')
Invoke-Checked $python @('-m','pip','install','-r','requirements.lock')
Invoke-Checked 'npm.cmd' @('ci')
Invoke-Checked 'rustup' @('target','add','x86_64-pc-windows-msvc')
Invoke-Checked $python @('-m','pytest','-q')
Invoke-Checked 'npm.cmd' @('test')
Invoke-Checked $python @('packaging/build_engine.py')
Invoke-Checked 'npm.cmd' @('run','desktop:build','--','--target','x86_64-pc-windows-msvc','--bundles','nsis')
$installers = @(Get-ChildItem 'src-tauri\target\x86_64-pc-windows-msvc\release\bundle\nsis\*-setup.exe')
if ($installers.Count -eq 0) { throw 'Installer was not generated.' }
$installers | ForEach-Object { Write-Host "Installer: $($_.FullName)"; Get-FileHash $_.FullName -Algorithm SHA256 }
