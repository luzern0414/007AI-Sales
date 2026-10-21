param([Parameter(Mandatory=$true)][string]$Destination)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot
$backupRoot = [System.IO.Path]::GetFullPath($Destination)
if (Test-Path -LiteralPath $backupRoot) { throw 'Backup destination must be new.' }
& (Join-Path $projectRoot '.venv\Scripts\python.exe') (Join-Path $projectRoot 'scripts\storage-maintenance.py') backup $backupRoot
if ($LASTEXITCODE -ne 0) { throw 'Backup failed.' }
