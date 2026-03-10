param(
    [ValidateSet('web', 'desktop')]
    [string]$Target = 'web',
    [switch]$OneFile,
    [switch]$SkipDeps
)

$ErrorActionPreference = 'Stop'

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $projectRoot

$pythonExe = '.\.venv\Scripts\python.exe'

if (-not (Test-Path $pythonExe)) {
    if ($SkipDeps) {
        throw 'Virtual environment not found. Create it first with: python -m venv .venv'
    }
    Write-Host 'Virtual environment not found. Creating .venv...'
    python -m venv .venv
    if ($LASTEXITCODE -ne 0) {
        throw 'Failed to create virtual environment.'
    }
}

if (-not $SkipDeps) {
    & $pythonExe -m pip install --upgrade pip
    & $pythonExe -m pip install -r requirements-export.txt
}

if (Test-Path '.\build') {
    Remove-Item '.\build' -Recurse -Force
}

if (Test-Path '.\dist') {
    Remove-Item '.\dist' -Recurse -Force
}

$pyInstallerArgs = @(
    '-m', 'PyInstaller',
    '--noconfirm',
    '--clean',
    '--windowed',
    '--name', 'AccountingSystem'
)

$entryPoint = 'main.py'

if ($Target -eq 'web') {
    $entryPoint = 'web_entry.py'
    $pyInstallerArgs += @(
        '--add-data', 'app\templates;app\templates',
        '--add-data', 'app\static;app\static'
    )
}

if ($OneFile) {
    $pyInstallerArgs += '--onefile'
}

$pyInstallerArgs += $entryPoint

& $pythonExe @pyInstallerArgs

if ($OneFile) {
    Write-Host 'Build complete. Executable: .\dist\AccountingSystem.exe'
}
else {
    $zipPath = '.\dist\AccountingSystem-windows.zip'
    if (Test-Path $zipPath) {
        Remove-Item $zipPath -Force
    }
    Compress-Archive -Path '.\dist\AccountingSystem\*' -DestinationPath $zipPath
    Write-Host 'Build complete. Folder: .\dist\AccountingSystem'
    Write-Host "Release archive: $zipPath"
}
