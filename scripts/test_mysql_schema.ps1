param(
  [string]$MySqlBase = "C:\Program Files\MySQL\MySQL Server 8.0",
  [int]$Port = 3308
)

$ErrorActionPreference = "Stop"

$projectRoot = Split-Path $PSScriptRoot -Parent
$mysqld = Join-Path $MySqlBase "bin\mysqld.exe"
$mysql = Join-Path $MySqlBase "bin\mysql.exe"
$mysqladmin = Join-Path $MySqlBase "bin\mysqladmin.exe"
$testRoot = Join-Path $projectRoot ".mysql-schema-test-$([guid]::NewGuid().ToString('N'))"
$data = Join-Path $testRoot "data"
$log = Join-Path $testRoot "mysql-error.log"
$pidFile = Join-Path $testRoot "mysql.pid"
$connection = @(
  "--protocol=TCP",
  "--host=127.0.0.1",
  "--port=$Port",
  "--user=root",
  "--skip-password"
)
$process = $null

if (-not (Test-Path -LiteralPath $mysqld) -or -not (Test-Path -LiteralPath $mysql)) {
  throw "MySQL binaries were not found under: $MySqlBase"
}

New-Item -ItemType Directory -Path $data -Force | Out-Null

try {
  & $mysqld --no-defaults --initialize-insecure "--basedir=$MySqlBase" "--datadir=$data" --console
  if ($LASTEXITCODE -ne 0) { throw "Temporary MySQL initialization failed" }

  $arguments = @(
    "--no-defaults",
    "`"--basedir=$MySqlBase`"",
    "`"--datadir=$data`"",
    "--port=$Port",
    "--bind-address=127.0.0.1",
    "--skip-log-bin",
    "`"--log-error=$log`"",
    "`"--pid-file=$pidFile`"",
    "--mysqlx=0"
  )

  $process = Start-Process -FilePath $mysqld -ArgumentList $arguments -WindowStyle Hidden -PassThru
  $ready = $false

  for ($attempt = 0; $attempt -lt 25; $attempt++) {
    Start-Sleep -Seconds 1
    & $mysqladmin @connection ping --silent 2>$null
    if ($LASTEXITCODE -eq 0) {
      $ready = $true
      break
    }
    if ($process.HasExited) { break }
  }

  if (-not $ready) {
    if (Test-Path -LiteralPath $log) { Get-Content -LiteralPath $log -Tail 50 }
    throw "Temporary MySQL did not become ready"
  }

  & $mysql @connection --execute="CREATE DATABASE gymfitness CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;"
  if ($LASTEXITCODE -ne 0) { throw "Could not create test database" }

  Get-Content -Raw (Join-Path $projectRoot "database\01_tables.sql") |
    & $mysql @connection gymfitness
  if ($LASTEXITCODE -ne 0) { throw "schema.sql failed" }

  Get-Content -Raw (Join-Path $projectRoot "database\02_triggers.sql") |
    & $mysql @connection gymfitness
  if ($LASTEXITCODE -ne 0) { throw "triggers.sql failed" }

  & $mysql @connection --batch --skip-column-names --execute="
    SELECT CONCAT('tables=', COUNT(*))
    FROM information_schema.tables
    WHERE table_schema = 'gymfitness';
    SELECT CONCAT('triggers=', COUNT(*))
    FROM information_schema.triggers
    WHERE trigger_schema = 'gymfitness';
    SELECT CONCAT('foreign_keys=', COUNT(*))
    FROM information_schema.referential_constraints
    WHERE constraint_schema = 'gymfitness';
  "
  if ($LASTEXITCODE -ne 0) { throw "Schema verification query failed" }
}
finally {
  & $mysqladmin @connection shutdown 2>$null

  if ($process) {
    $process.WaitForExit(8000) | Out-Null
    if (-not $process.HasExited) {
      Stop-Process -Id $process.Id -Force
      Start-Sleep -Seconds 2
    }
  }

  $resolvedTestRoot = [IO.Path]::GetFullPath($testRoot)
  $resolvedProjectRoot = [IO.Path]::GetFullPath($projectRoot)
  $isInsideProject = $resolvedTestRoot.StartsWith(
    $resolvedProjectRoot + [IO.Path]::DirectorySeparatorChar
  )

  if (-not $isInsideProject) {
    throw "Unsafe cleanup path: $resolvedTestRoot"
  }

  if (Test-Path -LiteralPath $resolvedTestRoot) {
    Remove-Item -LiteralPath $resolvedTestRoot -Recurse -Force
  }
}
