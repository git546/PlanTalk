param(
    [string]$EnvFile = (Join-Path $PSScriptRoot '..\backend\.env')
)

$ErrorActionPreference = 'Stop'

function Read-DotEnv {
    param([string]$Path)

    if (-not (Test-Path -LiteralPath $Path)) {
        throw "Supabase 설정 파일을 찾을 수 없습니다: $Path"
    }

    $values = @{}
    foreach ($line in Get-Content -LiteralPath $Path) {
        $trimmed = $line.Trim()
        if (-not $trimmed -or $trimmed.StartsWith('#') -or -not $trimmed.Contains('=')) {
            continue
        }

        $parts = $trimmed.Split('=', 2)
        $key = $parts[0].Trim()
        $value = $parts[1].Trim().Trim('"').Trim("'")
        $values[$key] = $value
    }

    return $values
}

$envValues = Read-DotEnv -Path $EnvFile
$supabaseUrl = $envValues['SUPABASE_URL']
$anonKey = $envValues['SUPABASE_ANON_KEY']

if ([string]::IsNullOrWhiteSpace($supabaseUrl)) {
    throw 'SUPABASE_URL이 설정되어 있지 않습니다.'
}

if ([string]::IsNullOrWhiteSpace($anonKey)) {
    throw 'SUPABASE_ANON_KEY가 설정되어 있지 않습니다.'
}

$requestUrl = $supabaseUrl.TrimEnd('/') + '/rest/v1/rpc/keepalive'
$headers = @{
    apikey        = $anonKey
    Authorization = "Bearer $anonKey"
    'Content-Type' = 'application/json'
}

try {
    $response = Invoke-WebRequest `
        -UseBasicParsing `
        -Method Post `
        -Uri $requestUrl `
        -Headers $headers `
        -Body '{}' `
        -TimeoutSec 30
} catch {
    $statusCode = $null
    if ($_.Exception.Response) {
        $statusCode = [int]$_.Exception.Response.StatusCode
    }

    if ($statusCode) {
        throw "Supabase 활동 확인 요청이 실패했습니다. HTTP 상태: $statusCode"
    }

    throw "Supabase 활동 확인 요청이 실패했습니다: $($_.Exception.Message)"
}

if ($response.StatusCode -lt 200 -or $response.StatusCode -ge 300) {
    throw "Supabase 활동 확인 요청이 실패했습니다. HTTP 상태: $($response.StatusCode)"
}

$timestamp = (Get-Date).ToString('yyyy-MM-dd HH:mm:ss zzz')
Write-Output "Supabase activity check succeeded at $timestamp (HTTP $($response.StatusCode))."
