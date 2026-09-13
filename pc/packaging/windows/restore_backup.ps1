param(
    [string]$BackupPath = ""
)

$ErrorActionPreference = "Stop"

$installRoot = Split-Path -Parent $PSScriptRoot
$python = Join-Path $installRoot "python\python.exe"
$serviceScript = Join-Path $PSScriptRoot "MilkWeighService.py"
$restoreScript = Join-Path $PSScriptRoot "restore_backup.py"
$programData = if ($env:PROGRAMDATA) { $env:PROGRAMDATA } else { "C:\ProgramData" }
$dataDir = Join-Path $programData "MilkWeigh\data"

if (-not (Test-Path -LiteralPath $python)) {
    throw "Python runtime not found: $python"
}
if (-not (Test-Path -LiteralPath $restoreScript)) {
    throw "Restore tool not found: $restoreScript"
}

if ([string]::IsNullOrWhiteSpace($BackupPath)) {
    $BackupPath = Read-Host "Backup ZIP path"
}
$resolvedBackup = (Resolve-Path -LiteralPath $BackupPath).Path

Write-Host ""
Write-Host "WARNING: This will replace the current database and evidence files." -ForegroundColor Yellow
Write-Host "The system creates a complete pre-restore backup before replacing data." -ForegroundColor Yellow
$confirmation = Read-Host "Type RESTORE to continue"
if ($confirmation -ne "RESTORE") {
    Write-Host "Restore cancelled."
    exit 1
}

Write-Host "Stopping MilkWeigh backend service..."
& $python $serviceScript stop
$serviceStopped = $false
for ($attempt = 0; $attempt -lt 20; $attempt++) {
    $service = Get-Service -Name "MilkWeighBackend" -ErrorAction SilentlyContinue
    if ($null -ne $service -and $service.Status -eq "Stopped") {
        $serviceStopped = $true
        break
    }
    Start-Sleep -Milliseconds 500
}
if (-not $serviceStopped) {
    throw "MilkWeigh backend service did not stop; restore aborted."
}

$succeeded = $false
try {
    $env:MILK_DATA_DIR = $dataDir
    & $python $restoreScript --backup $resolvedBackup --yes
    if ($LASTEXITCODE -ne 0) {
        throw "Restore tool exited with code $LASTEXITCODE"
    }
    $succeeded = $true
}
finally {
    Remove-Item Env:\MILK_DATA_DIR -ErrorAction SilentlyContinue
    $journal = Join-Path $dataDir ".restore-journal.json"
    if ($succeeded -or -not (Test-Path -LiteralPath $journal)) {
        Write-Host "Starting MilkWeigh backend service..."
        & $python $serviceScript start
    }
    else {
        Write-Warning "Restore rollback did not complete. The service was left stopped; keep the data directory and restore journal for recovery."
    }
}

if (-not $succeeded) {
    exit 1
}

Write-Host "Restore completed successfully." -ForegroundColor Green
Write-Host "Backend URL: http://127.0.0.1:8011/"
