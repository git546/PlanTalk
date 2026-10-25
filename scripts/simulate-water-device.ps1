param(
    [string]$AccessToken,
    [string]$ApiUrl = "http://localhost:8000",
    [ValidateSet("simulator", "device")]
    [string]$Source = "simulator",
    [string]$DeviceId = "scale-simulator-01",
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"

$endedAt = [DateTimeOffset]::UtcNow
$startedAt = $endedAt.AddDays(-3)

$payload = [ordered]@{
    plant_id = "test-plant-01"
    calibration = [ordered]@{
        setup_weight_g = 2800
        target_wet_weight_g = 3800
        watering_trigger_weight_g = 3300
        max_single_watering_ml = 600
        calibrated_at = $startedAt.AddDays(-1).ToString("o")
        version = 1
    }
    start_measurement = [ordered]@{
        measured_at = $startedAt.ToString("o")
        weight_g = 3800
        source = $Source
        device_id = $DeviceId
        sequence_no = 100
        is_stable = $true
        raw_sensor_value = 842000
        sample_count = 20
    }
    end_measurement = [ordered]@{
        measured_at = $endedAt.ToString("o")
        weight_g = 3550
        source = $Source
        device_id = $DeviceId
        sequence_no = 101
        is_stable = $true
        raw_sensor_value = 788000
        sample_count = 20
    }
    water_added_ml = 500
    drainage_ml = 100
    environment = [ordered]@{
        temperature_c = 24.5
        humidity_percent = 55
        light_lux = 12000
    }
}

$json = $payload | ConvertTo-Json -Depth 8
if ($DryRun) {
    $json
    exit 0
}

if ([string]::IsNullOrWhiteSpace($AccessToken)) {
    throw "API 호출에는 -AccessToken이 필요합니다. JSON만 확인하려면 -DryRun을 사용하세요."
}

$headers = @{ Authorization = "Bearer $AccessToken" }
Invoke-RestMethod `
    -Method Post `
    -Uri "$($ApiUrl.TrimEnd('/'))/api/water-balance/evaluate" `
    -Headers $headers `
    -ContentType "application/json; charset=utf-8" `
    -Body $json
