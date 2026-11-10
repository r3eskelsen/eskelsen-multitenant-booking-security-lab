& {
    $ErrorActionPreference = 'Stop'
    $root = Split-Path -Parent $PSScriptRoot
    Set-Location -LiteralPath $root

    $context = docker context show
    if ($LASTEXITCODE -ne 0 -or "$context".Trim() -ne 'desktop-linux') {
        throw 'Use the local desktop-linux Docker context.'
    }

    foreach ($relative in @('.env', 'data')) {
        if (Test-Path -LiteralPath "$root\$relative") {
            throw "Clean setup only: $relative already exists."
        }
    }

    foreach ($relative in @(
        'compose.yaml',
        'compose.api.yaml',
        'compose.local.yaml',
        'src\main.py',
        'scripts\001_schema.sql',
        'scripts\api-runtime\Dockerfile.release',
        'scripts\api-runtime\requirements.lock'
    )) {
        if (-not (Test-Path -LiteralPath "$root\$relative")) {
            throw "Missing file: $relative"
        }
    }

    foreach ($name in @('esk-lab03-db', 'esk-lab03-api')) {
        $found = @(docker ps -aq --filter "name=^/$name`$")
        if ($LASTEXITCODE -ne 0) { throw 'Container inspection failed.' }
        if ($found.Count -gt 0) {
            throw "Existing container: $name. Preserve the existing lab."
        }
    }

    foreach ($name in @('esk-lab03-private', 'esk-lab03-local')) {
        $found = @(docker network ls -q --filter "name=^$name`$")
        if ($LASTEXITCODE -ne 0) { throw 'Network inspection failed.' }
        if ($found.Count -gt 0) {
            throw "Existing network: $name. Preserve the existing lab."
        }
    }

    $listeners = @(Get-NetTCPConnection -State Listen -ErrorAction Stop)
    if ($listeners.LocalPort -contains 18083) {
        throw 'Port 18083 is occupied.'
    }

    function New-Secret {
        $bytes = New-Object byte[] 32
        $rng = [Security.Cryptography.RandomNumberGenerator]::Create()
        try { $rng.GetBytes($bytes) } finally { $rng.Dispose() }
        return ([BitConverter]::ToString($bytes)).Replace('-', '').ToLowerInvariant()
    }

    $utf8 = New-Object System.Text.UTF8Encoding($false)
    $ownerPassword = New-Secret
    $appPassword = New-Secret
    $signingSecret = New-Secret

    $envText = "LAB03_DB_PASSWORD=$ownerPassword`n" +
        "LAB03_APP_PASSWORD=$appPassword`n" +
        "LAB03_JWT_SECRET=$signingSecret`n"
    [IO.File]::WriteAllText("$root\.env", $envText, $utf8)

    New-Item -ItemType Directory -Path "$root\data\postgres" -Force |
        Out-Null

    $run = Join-Path $root (
        'evidence\CLEAN_SETUP_' + (Get-Date -Format 'yyyyMMdd_HHmmss')
    )
    New-Item -ItemType Directory -Path $run -Force | Out-Null

    $composeArgs = @(
        'compose', '-p', 'esk-lab03',
        '-f', "$root\compose.yaml",
        '-f', "$root\compose.api.yaml",
        '-f', "$root\compose.local.yaml"
    )

    & docker @composeArgs config --quiet
    if ($LASTEXITCODE -ne 0) { throw 'Compose validation failed.' }

    # Do not overwrite an existing runtime tag.
    $existingImage = @(docker image ls -q 'esk-lab03-api-runtime:v1')
    if ($LASTEXITCODE -ne 0) { throw 'Image inspection failed.' }
    if ($existingImage.Count -gt 0) {
        throw 'Runtime image already exists. Review before rebuilding; no image was replaced.'
    }

    docker build --memory 1g -t esk-lab03-api-runtime:v1 `
        -f "$root\scripts\api-runtime\Dockerfile.release" `
        "$root\scripts\api-runtime"
    if ($LASTEXITCODE -ne 0) { throw 'Runtime build failed.' }

    $postgresImage = @(docker image ls -q 'postgres:16')
    if ($LASTEXITCODE -ne 0) { throw 'PostgreSQL image inspection failed.' }
    if ($postgresImage.Count -eq 0) {
        docker pull postgres:16
        if ($LASTEXITCODE -ne 0) { throw 'PostgreSQL pull failed.' }
    }

    & docker @composeArgs up -d --wait --wait-timeout 90 db
    if ($LASTEXITCODE -ne 0) { throw 'Database startup failed.' }

    docker cp "$root\scripts\001_schema.sql" `
        'esk-lab03-db:/tmp/lab03_001_schema.sql'
    if ($LASTEXITCODE -ne 0) { throw 'Schema copy failed.' }

    $schemaOutput = docker exec esk-lab03-db psql -X `
        -U lab03_owner -d booking_lab -v ON_ERROR_STOP=1 `
        -f /tmp/lab03_001_schema.sql 2>&1
    $schemaExit = $LASTEXITCODE
    $schemaOutput | Out-File "$run\schema_setup.txt" -Encoding UTF8
    if ($schemaExit -ne 0) { throw 'Schema installation failed.' }

    $sql = "\set ON_ERROR_STOP on`n\set VERBOSITY terse`n" +
        "ALTER ROLE lab03_app LOGIN PASSWORD '$appPassword';"

    $suppressed = $sql | docker exec -i esk-lab03-db psql -X `
        -U lab03_owner -d booking_lab -v ON_ERROR_STOP=1 2>&1
    $provisionExit = $LASTEXITCODE

    Remove-Variable ownerPassword,appPassword,signingSecret,envText,sql,suppressed
    if ($provisionExit -ne 0) {
        throw 'Role provisioning failed; details suppressed to protect secrets.'
    }

    & docker @composeArgs up -d --no-deps --wait --wait-timeout 60 api
    if ($LASTEXITCODE -ne 0) { throw 'API startup failed.' }

    'Initialization completed; verification remains pending.' |
        Set-Content "$run\status.txt" -Encoding UTF8

    Write-Host 'Clean initialization completed.'
    Write-Host 'Run the verification commands in README.md.'
}