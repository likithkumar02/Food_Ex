$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$mysqlFile = Join-Path $scriptDir "mysql_setup.sql"

$DB_NAME = if ($env:DB_NAME) { $env:DB_NAME } else { "food_ex" }
$DB_USER = if ($env:DB_USER) { $env:DB_USER } else { "root" }
$DB_PASSWORD = $env:DB_PASSWORD

if (-not (Test-Path $mysqlFile)) {
    Write-Error "MySQL script not found: $mysqlFile"
    exit 1
}

if ($DB_PASSWORD) {
    & mysql -u $DB_USER -p$DB_PASSWORD $DB_NAME < $mysqlFile
} else {
    & mysql -u $DB_USER $DB_NAME < $mysqlFile
}

if ($LASTEXITCODE -ne 0) {
    Write-Error "MySQL import failed."
    exit $LASTEXITCODE
}

Write-Host "MySQL import completed for database: $DB_NAME"
