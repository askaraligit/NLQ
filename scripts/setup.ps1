[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$taskRoot = Split-Path -Parent $PSScriptRoot
$taskEncoding = New-Object System.Text.UTF8Encoding($false)
$taskFiles = @(
    @{ Source = '.env.example'; Target = '.env' },
    @{ Source = 'apps/web/.env.example'; Target = 'apps/web/.env.local' },
    @{ Source = 'apps/api/.env.example'; Target = 'apps/api/.env' }
)

# Check all templates before creating any local configuration.
foreach ($taskFile in $taskFiles) {
    $taskSource = Join-Path $taskRoot $taskFile.Source
    if (-not (Test-Path -LiteralPath $taskSource -PathType Leaf)) {
        throw "Missing environment template: $($taskFile.Source)"
    }
}

foreach ($taskFile in $taskFiles) {
    $taskTarget = Join-Path $taskRoot $taskFile.Target
    if (Test-Path -LiteralPath $taskTarget) {
        Write-Output "Kept existing $($taskFile.Target)"
        continue
    }

    $taskContent = [System.IO.File]::ReadAllText((Join-Path $taskRoot $taskFile.Source))
    if ($taskFile.Target -eq '.env') {
        $taskBytes = New-Object byte[] 32
        $taskRandom = [System.Security.Cryptography.RandomNumberGenerator]::Create()
        try {
            $taskRandom.GetBytes($taskBytes)
        } finally {
            $taskRandom.Dispose()
        }
        $taskPassword = [BitConverter]::ToString($taskBytes).Replace('-', '').ToLowerInvariant()
        $taskContent = $taskContent.Replace('POSTGRES_PASSWORD=', "POSTGRES_PASSWORD=$taskPassword")
    }

    # CreateNew avoids overwriting a file created concurrently by another process.
    $taskStream = [System.IO.File]::Open($taskTarget, [System.IO.FileMode]::CreateNew)
    try {
        $taskData = $taskEncoding.GetBytes($taskContent)
        $taskStream.Write($taskData, 0, $taskData.Length)
    } finally {
        $taskStream.Dispose()
    }
    Write-Output "Created $($taskFile.Target)"
}

Write-Output 'Local configuration is ready. Existing files were not changed.'
