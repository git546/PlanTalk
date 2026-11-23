# PlanTalk 원격 센서 게이트웨이

Arduino Uno가 9600 baud로 출력하는 PlanTalk JSONL을 COM 포트에서 직접 수집하는 PC
게이트웨이입니다. 센서 원본 보존, PC UTC 수신시각 부여, 로드셀 g 단위 보정, 안정 구간 판정,
오프라인 큐, Supabase 원격 전송, 파일 재생, 시뮬레이터, 급수·배수 이벤트 및 장치 진단 기록을 담당합니다.

```text
Arduino COM 포트 / JSONL 파일 / 시뮬레이터
                    ↓
          RawSample 계약
              ↓
      SQLite 원본 로그(항상 먼저 저장)
              ↓
        안정 구간 중앙값 판정
              ↓
      정규화 측정값 + durable outbox
              ↓
    Supabase authenticated 사용자로 전송
```

## 1. 설치와 아두이노 연결

프로젝트 최상위 폴더에서 시리얼 의존성을 설치합니다.

```powershell
python -m pip install -r sensor_gateway/requirements.txt
```

통합 펌웨어 `sensor_gateway/firmware/plantalk_uno/plantalk_uno.ino`를 Arduino Uno에
업로드한 뒤 시리얼 모니터를 닫습니다. Arduino IDE 시리얼 모니터와 게이트웨이는 같은 COM
포트를 동시에 열 수 없습니다.

현재 PC의 포트를 확인합니다.

```powershell
python -m sensor_gateway ports
```

포트가 하나면 `auto`로 자동 선택할 수 있고, 여러 개면 `COM3`처럼 명시합니다.

```powershell
python -m sensor_gateway run --adapter serial --port COM3 --baud 9600
```

수집은 `Ctrl+C`로 종료합니다. USB가 잠시 끊기면 같은 COM 포트로 재연결을 시도합니다. 짧은
시험은 `--max-samples 60`을 붙여 60개 수집 후 자동 종료할 수 있습니다.

## 2. 로드셀 보정

빈 저울의 원본값 평균과 알려진 추를 올린 원본값 평균을 구합니다. 예를 들어 영점이
`350000`, 1kg 추를 올린 값이 `100000`이면 다음처럼 계산합니다.

```powershell
python -m sensor_gateway calibration `
  --zero-raw 350000 `
  --loaded-raw 100000 `
  --known-weight 1000
```

출력된 다음 두 줄을 `.env.gateway`에 복사합니다.

```env
GATEWAY_RAW_ZERO_VALUE=350000
GATEWAY_RAW_GRAMS_PER_UNIT=-0.004
```

센서 방향에 따라 환산계수는 음수일 수 있습니다. 게이트웨이는
`weight_g = (raw_sensor_value - zero) × grams_per_unit`으로 변환합니다.

## 3. PC 시각과 순번 처리

Arduino Uno에는 RTC와 인터넷 시간이 없으므로 펌웨어는 `device_uptime_ms`와
`sequence_no`만 출력합니다. 게이트웨이는 JSON을 받은 순간의 PC UTC 시각을
`measured_at`으로 저장합니다.

아두이노 순번은 재부팅할 때 1로 돌아가므로 기본적으로 원본에만 보존하고, 저장용 순번은
PC SQLite가 계속 증가시키며 부여합니다. 재부팅 후에도 순번이 유지되는 다른 기기를 연결할
때만 `--trust-device-sequence`를 사용합니다.

## 4. 로컬 시뮬레이터로 전체 수집 경로 확인

프로젝트 최상위 폴더에서 실행합니다.

```powershell
python -m sensor_gateway init
python -m sensor_gateway run --adapter simulator --count 120
python -m sensor_gateway status
```

Windows에서는 `sensor_gateway/run-simulator.cmd`를 더블클릭할 수 있습니다.
시뮬레이터는 네트워크와 Supabase 설정 없이 작동합니다.

## 5. 표준 센서 JSON 확인

```powershell
python -m sensor_gateway contract
```

기본 계약은 다음과 같습니다.

```json
{
  "status": "ok",
  "hx711_ready": true,
  "raw_sensor_value": 788240,
  "sequence_no": 1532,
  "device_uptime_ms": 3064000,
  "temperature_c": 24.3,
  "humidity_percent": 56.1,
  "soil_raw": 491,
  "light_raw": 720
}
```

펌웨어 0.2.0은 부팅과 HX711 오류도 JSON으로 보냅니다. `raw_sensor_value=null`인
상태 레코드는 SQLite 원본 로그에는 보존하지만 무게 안정값 계산에는 넣지 않습니다.
오류가 복구되면 과거 창을 버리고 새 정상 표본 20개를 다시 모읍니다.

게이트웨이는 다음 진단 이벤트를 별도로 기록합니다.

- `arduino_boot`, `arduino_restart_detected`
- `hx711_not_ready`, `hx711_recovered`
- `serial_connected`, `serial_disconnected`
- `collection_gap_power_or_restart`, `collection_gap_device_running`

팀원 프로그램이 다른 필드명을 사용해도 `.env.gateway`에서 매핑할 수 있습니다.

```env
GATEWAY_FIELD_TIMESTAMP=data.time
GATEWAY_FIELD_WEIGHT=data.scale.grams
GATEWAY_FIELD_RAW_VALUE=data.scale.raw
GATEWAY_FIELD_TEMPERATURE=data.environment.temperature
GATEWAY_FIELD_STATUS=data.status
GATEWAY_FIELD_HX711_READY=data.scale.ready
```

점으로 구분한 중첩 JSON 경로도 지원합니다. 단, 바이너리 시리얼 프로토콜처럼 JSON으로 변환할
수 없는 형식이면 실제 스펙을 받은 뒤 전용 어댑터가 필요합니다.

센서가 `weight_g` 없이 로드셀 원시값만 제공하더라도 알려진 추로 영점과 환산계수를 구한 뒤
다음 두 값으로 일반적인 선형 변환을 적용할 수 있습니다.

```env
GATEWAY_RAW_ZERO_VALUE=120430
GATEWAY_RAW_GRAMS_PER_UNIT=0.004545
```

계산식은 `weight_g = (raw_sensor_value - zero) × grams_per_unit`입니다. 비선형 보정이나 제조사
전용 프레임 해석은 실제 센서 스펙을 받은 뒤 어댑터에서 처리합니다.

`soil_raw`와 `light_raw`는 퍼센트나 lux로 바꾸지 않고 원본 보조값으로 보존합니다. 안정 구간이
만들어질 때 두 값의 중앙값도 Supabase `raw_payload`에 함께 저장합니다.

## 6. 저장된 로그 재생

센서 프로그램이 한 줄에 JSON 하나를 남기면 그대로 재생할 수 있습니다.

```powershell
$env:GATEWAY_STABILITY_WINDOW="5"
$env:GATEWAY_EMIT_INTERVAL_SECONDS="0"
python -m sensor_gateway run --adapter file --input sensor_gateway/sample-input.jsonl
```

표준 출력으로 JSONL을 내보내는 프로그램이라면 파이프로 연결할 수 있습니다.

```powershell
센서프로그램.exe | python -m sensor_gateway run --adapter stdin
```

게이트웨이는 입력을 받자마자 `raw_samples`에 저장합니다. 안정값 생성이나 원격 전송이 실패해도
원본 로그는 남습니다.

## 7. Supabase 원격 전송 설정

예시 파일을 복사해 개인 설정을 만듭니다.

```powershell
Copy-Item sensor_gateway/.env.example sensor_gateway/.env.gateway
```

`.env.gateway`에는 다음을 입력합니다.

- `GATEWAY_PLANT_ID`: 센서 테스트 계정이 소유한 식물 UUID
- `SUPABASE_URL`: PlanTalk Supabase 주소
- `SUPABASE_PUBLISHABLE_KEY`: `sb_publishable_...` 공개키
- `SUPABASE_TEST_EMAIL`, `SUPABASE_TEST_PASSWORD`: 전용 테스트 사용자

진단 이벤트를 원격에 저장하려면
`supabase/migrations/202611230001_device_diagnostics.sql`도 Supabase에 적용해야 합니다.

그다음 로컬 큐를 원격으로 전송합니다.

```powershell
python -m sensor_gateway flush
```

최근 진단 이벤트는 로컬에서 다음 명령으로 확인합니다.

```powershell
python -m sensor_gateway status
```

수집과 동시에 전송하려면 다음처럼 실행합니다.

```powershell
python -m sensor_gateway run --adapter serial --port COM3 --baud 9600 --upload
```

네트워크 오류가 발생하면 항목은 삭제되지 않고 `failed` 상태와 다음 재시도 시각을 저장합니다.
이후 `flush`를 다시 실행하면 아직 전송되지 않은 항목만 순서대로 전송합니다.

## 8. 급수·배수 이벤트 기록

```powershell
python -m sensor_gateway event watering --volume 300 --notes "오후 급수"
python -m sensor_gateway event drainage --volume 45
```

원격에도 즉시 보낼 때만 `--upload`를 붙입니다. 이벤트 ID는 자동으로 생성되므로 재시도 중복을
구분할 수 있습니다.

## 9. 데이터 내보내기와 계산기 재생

```powershell
python -m sensor_gateway export --output sensor_gateway/exports/measurements.jsonl
```

내보낸 정규화 로그는 독립 수분 계산기 실험과 회귀 테스트의 입력 자료로 사용할 수 있습니다.

## 10. 다른 센서 어댑터가 지켜야 할 인터페이스

어댑터는 반복 가능한 객체이며 매번 `RawSample` 하나를 반환하면 됩니다.

```python
from sensor_gateway.models import RawSample

class TeamSensorAdapter:
    def __iter__(self):
        while True:
            vendor_value = read_from_team_sensor()
            yield RawSample(
                captured_at=vendor_value.timestamp,
                weight_g=vendor_value.grams,
                raw_sensor_value=vendor_value.raw,
                sequence_no=vendor_value.sequence,
                raw_payload=vendor_value.original_payload,
            )
```

다른 하드웨어가 바이너리 프레임이나 체크섬을 사용하더라도 이 어댑터 안에서 `RawSample`로
변환하면 저장·재전송·Supabase 코드는 변경하지 않습니다.

## 보안 원칙

- `sb_secret_...` 또는 `service_role` 키를 게이트웨이에 넣지 않습니다.
- 테스트 전용 사용자만 사용합니다.
- `.env.gateway`, SQLite DB, 세션 로그는 Git에 커밋하지 않습니다.
- 비밀번호, Publishable key 값, Access/Refresh Token은 출력하지 않습니다.
- 게이트웨이는 외부로 HTTPS 요청만 보내므로 공유기 포트포워딩이 필요 없습니다.

## 테스트

```powershell
python -m unittest discover -s sensor_gateway/tests -v
```

