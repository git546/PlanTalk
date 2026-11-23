# PlanTalk Arduino Uno 통합 센서 코드

정현 팀원의 개별 센서 테스트 커밋 `135709b`를 바탕으로 핀 충돌을 해결하고, 네 센서 값을 한 줄의 JSON으로 출력하는 통합 코드입니다.

## 연결

| 센서 | Arduino Uno 핀 | 출력값 |
| --- | --- | --- |
| WAT-LOAD594-5kg + HX711 DT | D2 | 로드셀 원본값 |
| WAT-LOAD594-5kg + HX711 SCK | D3 | 로드셀 클록 |
| DHT11 | D4 | 온도·습도 |
| DFRobot SEN0193 | A0 | 토양 수분 원본값 |
| 조도 저항 분압 회로 | A1 | 조도 원본값 |

라이브러리는 `DHT sensor library`와 Bogdan Necula의 `HX711 Arduino Library`를 사용합니다. 시리얼 모니터 속도는 `9600 baud`입니다.

## 출력 예시

```json
{"sequence_no":1,"device_uptime_ms":2041,"status":"ok","hx711_ready":true,"raw_sensor_value":-354631,"soil_raw":491,"light_raw":720,"temperature_c":23.4,"humidity_percent":51.0,"firmware_version":"0.2.0"}
```

HX711이 준비되지 않아도 2초마다 상태 JSON을 계속 출력합니다.

```json
{"sequence_no":2,"device_uptime_ms":4041,"status":"hx711_not_ready","hx711_ready":false,"raw_sensor_value":null,"soil_raw":491,"light_raw":720,"temperature_c":23.4,"humidity_percent":51.0,"firmware_version":"0.2.0"}
```

- Arduino Uno에는 실시간 시계가 없으므로 측정 시각은 출력하지 않습니다. 게이트웨이가 수신 시각을 UTC로 기록합니다.
- `soil_raw`와 `light_raw`는 보정 전 상대값이며 퍼센트나 lux가 아닙니다.
- DHT11 읽기에 실패한 항목은 JSON의 `null`로 출력합니다.
- 부팅 시 `status=boot`, HX711 오류 시 `status=hx711_not_ready`를 출력합니다.
- HX711 오류 중에도 온습도·토양·조도와 장치 가동시간은 계속 기록됩니다.
- 로드셀 원본값은 배선 방향에 따라 음수일 수 있으며, 음수 자체는 오류가 아닙니다.
- 아날로그값과 로드셀값은 각각 10회 평균을 사용합니다.

## PC 게이트웨이 연결

Arduino IDE 시리얼 모니터를 닫은 뒤 프로젝트 최상위 폴더에서 실행합니다.

```powershell
python -m pip install -r sensor_gateway/requirements.txt
python -m sensor_gateway ports
python -m sensor_gateway run --adapter serial --port COM3 --baud 9600
```

`COM3`은 팀원 PC에서 확인한 포트로 바꿉니다. Supabase에도 전송하려면 개인
`.env.gateway` 설정을 완료한 뒤 마지막 명령에 `--upload`를 붙입니다.

## 로드셀 보정 전 사용

현재 코드는 로드셀 원본값을 `raw_sensor_value`로 출력합니다. 알려진 추로 영점과 환산계수를 구한 뒤 `sensor_gateway/.env.gateway`에 다음 값을 넣으면 게이트웨이가 g 단위로 변환합니다.

```dotenv
GATEWAY_RAW_ZERO_VALUE=
GATEWAY_RAW_GRAMS_PER_UNIT=
```

계산식은 다음과 같습니다.

```text
weight_g = (raw_sensor_value - zero) * grams_per_unit
```

센서 방향에 따라 원본값이 무게가 증가할수록 감소할 수도 있습니다. 이 경우 `GATEWAY_RAW_GRAMS_PER_UNIT`에 음수 환산계수를 사용할 수 있습니다. 환산계수가 0이면 무게를 계산할 수 없으므로 허용하지 않습니다.

## 확인 순서

1. 화분 없이 30개 이상의 로드셀 원본값을 저장합니다.
2. 알려진 추 500g과 1kg을 각각 올려 30개 이상의 값을 저장합니다.
3. 같은 무게를 세 번 이상 올렸다 내리며 반복 오차를 확인합니다.
4. 네 센서 동시 연결 상태에서 JSON 한 줄이 2초마다 출력되는지 확인합니다.
5. 실제 화분은 충분히 젖은 상태에서도 5kg 로드셀의 안전 범위를 넘지 않는지 확인합니다.
6. HX711 DT 선을 잠시 분리했을 때 `hx711_not_ready`가 출력되고 재연결 후 `ok`로 복구되는지 확인합니다.
