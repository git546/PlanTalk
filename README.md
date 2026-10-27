# PlanTalk

반려식물과 대화하고 식물 상태를 관리하는 모바일 앱의 초기 개발 환경입니다.

- 모바일: React Native + Expo SDK 57 + TypeScript + Expo Router
- API: FastAPI + Python 3.12
- 데이터/인증: Supabase Auth + PostgreSQL(RLS)
- AI/확장: Gemini API, 센서/외부 API

## 폴더 구조

```text
PlanTalk/
├─ mobile/                 # Expo 모바일 앱
├─ backend/                # FastAPI 서버
├─ scripts/                # Windows 개발 스크립트
└─ .vscode/                # 팀 공용 VS Code 설정
```

## 1. 최초 설치

PowerShell에서 저장소 루트로 이동한 뒤 실행합니다.

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\scripts\setup.ps1
```

스크립트가 다음 작업을 수행합니다.

1. Node.js와 Python 3.12 설치 여부 확인
2. `mobile/node_modules` 설치
3. `backend/.venv` 가상환경 생성
4. FastAPI 및 테스트/검사 도구 설치
5. 로컬 환경변수 파일 생성

## 2. 로컬 환경변수

### 모바일

`mobile/.env.local`의 API 주소를 실행 환경에 맞게 바꿉니다.

```dotenv
EXPO_PUBLIC_API_URL=http://localhost:8000
EXPO_PUBLIC_SUPABASE_URL=
EXPO_PUBLIC_SUPABASE_ANON_KEY=
```

- Android 에뮬레이터: `http://10.0.2.2:8000`
- Expo Go를 설치한 실제 휴대폰: `http://<PC의-같은-Wi-Fi-IP>:8000`
- `EXPO_PUBLIC_` 값은 앱에 포함되므로 비밀키를 넣으면 안 됩니다.

### 백엔드

`backend/.env`에 서버 전용 값을 입력합니다. 실제 키는 Git에 커밋하지 않습니다.

```dotenv
OPENAI_API_KEY=
SUPABASE_URL=
SUPABASE_ANON_KEY=
SUPABASE_SERVICE_ROLE_KEY=
```

초기 상태 확인 API는 키 없이 실행할 수 있습니다.

## 3. 실행

터미널 1 — FastAPI:

```powershell
.\scripts\api.ps1
```

브라우저에서 다음 주소를 확인할 수 있습니다.

- API 상태: <http://localhost:8000/api/health>
- API 문서: <http://localhost:8000/docs>

터미널 2 — Expo:

```powershell
npm --prefix mobile start
```

터미널에 표시된 QR 코드를 Expo Go로 스캔합니다. 휴대폰과 PC는 같은 네트워크에 연결해야 합니다.

## 4. 로그인

- 앱을 열면 로그인 화면이 먼저 표시됩니다.
- 아이디만 입력하면 내부적으로 `아이디@plantalk.local` 형식으로 변환해 Supabase Auth에 로그인합니다.
- 현재 회원가입 화면은 없습니다. 팀 테스트 계정은 Supabase 대시보드의 Authentication에서 관리자가 생성합니다.
- 로그인 세션은 기기에 저장되며 로그아웃할 때 삭제됩니다.
- FastAPI의 `POST /api/chat`은 로그인 세션의 Bearer 토큰이 있어야 호출할 수 있습니다.
- 테스트 계정 비밀번호는 저장소에 기록하지 않고 팀원에게 별도로 전달합니다.

로그인 후에는 관리 홈이 열리고 `홈`, `채팅`, `식물`, `페르소나`, `설정` 탭을 사용할 수 있습니다.
`식물` 탭에서 여러 화분과 화분 세팅 기준 무게를 관리합니다. 홈의 `수분량 계산기`에서는
선택한 식물의 기준값과 누적 급수·배수량으로 수분 손실과 다음 물주기 시점을 추정합니다.
식물 목록, 화분 보정값, 무게 측정과 급수·배수 이력은 Supabase에 저장됩니다. 기존 버전의
로컬 식물 목록은 로그인 후 최초 1회 같은 계정의 DB로 옮겨집니다. 화면 대화와 페르소나
편집값은 아직 사용자별 기기에 저장됩니다. 페르소나에서 지정한 식물 이름,
종류, 말투, 활발함, 애정 표현, 유머, 답변 길이와 사용자 호칭은 다음 AI 대화부터 적용됩니다.
직접 성격 설명과 말투 예시를 추가하면 프리셋보다 구체적인 캐릭터를 만들 수 있습니다.
설정 화면에서 로컬 대화와 페르소나를 기본값으로 초기화할 수 있습니다.

## 5. 검사

```powershell
npm --prefix mobile run typecheck
npm --prefix mobile run lint
npm --prefix mobile run doctor
.\backend\.venv\Scripts\python.exe -m pytest backend\tests
.\backend\.venv\Scripts\python.exe -m ruff check backend
```

## 보안 원칙

- `OPENAI_API_KEY`, `GEMINI_API_KEY`, `SUPABASE_SERVICE_ROLE_KEY`는 FastAPI 서버에서만 사용합니다.
- 모바일에는 공개 가능한 `EXPO_PUBLIC_` 값만 둡니다.
- `.env`, `.env.local`, 가상환경, 빌드 결과물은 Git에서 제외됩니다.

## macOS에서 Gemini 채팅 실행

프론트엔드는 공통 형식 `POST /api/chat`에 `messages: [{role, content}]`를 보내고
`{reply}`를 받습니다. 공급자별 코드는 `backend/app/services/chat.py`에 분리되어 있습니다.
현재 Gemini만 구현되어 있으며 OpenAI로 전환할 때 해당 공급자 어댑터를 추가합니다.

1. `backend/.env.example`을 `backend/.env`로 복사하고 `GEMINI_API_KEY`를 로컬에서 입력합니다.
2. AI Studio에서 해당 프로젝트가 Free Tier인지 확인합니다. 유료 결제를 연결한
   프로젝트는 같은 모델도 과금될 수 있습니다. 코드는 결제 등급을 판별하지 않습니다.
3. 기본 모델은 무료 등급이 제공되는 `gemini-3.1-flash-lite`입니다. 계정별 할당량은
   AI Studio에서 확인합니다. 한도 초과 시 재시도/유료 모델 전환은 자동으로 하지 않습니다.
4. 서버를 실행합니다 (환경변수 변경 후 서버 재시작 필요):

```sh
backend/.venv/bin/python -m uvicorn app.main:app --app-dir backend --reload --port 8000
```

다른 터미널에서 `npm --prefix mobile run web`을 실행합니다.
메시지 전송 중에는 중복 전송을 막고 실패하면 원문을 입력창에 복원합니다.
최근 10개 대화 쌍을 서버에 전달하며 대화는 새로고침 시 초기화됩니다.
기본 데이터베이스는 `supabase/migrations/202610030001_initial_plantalk_schema.sql`, 수분 측정
파이프라인은 `supabase/migrations/202610250001_water_measurement_pipeline.sql`에 있습니다.
PlanTalk 원격 Supabase 프로젝트에는 2026-10-27 기준으로 두 스키마가 적용되어 있습니다.
`202610270001_keepalive_rpc.sql`은 데이터 내용을 공개하지 않는 읽기 전용 활동 확인 함수를
추가하며, `scripts/check-supabase-activity.ps1`의 주기 실행에 사용합니다.
채팅 API는 Supabase 로그인 토큰을 검증하며 기본 localhost 주소에서 실행합니다.
API 키를 프론트엔드나 Git에 넣지 마세요.

## 데이터베이스와 페르소나

초기 스키마는 다음 데이터를 분리합니다.

- `profiles`: Supabase Auth 사용자의 추가 프로필
- `plant_species`: 종별 일조량, 수분, 온도, 습도 등 공통 권장 범위
- `persona_templates`: 재사용 가능한 성격 유형
- `plants`: 개별 식물과 성격·관리 설정 덮어쓰기
- `messages`: 식물별 전체 대화 원문
- `memories`: 대화에서 추출한 식물별 장기 기억
- `sensor_readings`: 시간에 따른 센서 측정 이력

모든 사용자 데이터 테이블에는 RLS가 적용되어 소유자만 접근할 수 있습니다.
기본 페르소나는 `backend/app/prompts/base_plant_persona.md`에서 관리합니다.
채팅 API에 식물 컨텍스트를 함께 보내면 기본 페르소나 위에 개별 성격과 기억이 적용됩니다.

```json
{
  "messages": [{"role": "user", "content": "오늘 기분 어때?"}],
  "plant": {
    "name": "초록이",
    "species": "몬스테라",
    "personality": {
      "tone": "활발하고 다정한 반말",
      "energy": 5,
      "affection": 4,
      "humor": 3,
      "talk_length": "짧게",
      "traits": ["장난꾸러기", "호기심이 많음"],
      "calling_user": "친구"
    },
    "memories": ["사용자는 식물을 창가에서 키운다."]
  }
}
```

클라이언트는 선택한 식물의 DB ID와 컨텍스트를 함께 전달합니다. 로그인 사용자가 대화하면
백엔드가 해당 사용자가 소유한 식물을 확인해 갱신하고, `messages`에 대화 원문을 저장합니다.
답변 후에는 별도의 Gemini 호출이 다음
대화에도 유용한 사실을 최대 3개까지 추출해 `memories`에 저장합니다. 다음 답변을 만들기
전에는 중요도와 최신순으로 활성 기억을 최대 20개 불러와 판단 프롬프트에 포함합니다.
기억 추출이나 저장이 실패해도 현재 채팅 응답은 정상적으로 반환됩니다. 식물 목록과 수분
계산은 여러 식물을 지원하며, 식물별 페르소나 편집과 기억 편집 UI는 다음 확장 단계입니다.

## 수분수지 계산기

모바일 홈에서 계산기 화면으로 이동하며, 로그인 토큰과 함께 `POST /api/water-balance`를
호출합니다. 계산식은 다음과 같습니다.

```text
추정 수분 손실량 = 누적 급수량 - 누적 배수량 - (현재 무게 - 화분 세팅 기준 무게)
하루 평균 손실량 = 추정 수분 손실량 / 화분 세팅 후 경과 일수
목표까지 부족량 = 충분히 젖은 목표 무게 - 현재 무게
```

식물 목록에는 화분 세팅 직후 무게, 충분히 젖은 목표 무게, 물주기 시작 기준 무게와
1회 최대 급수량을 버전 이력으로 저장합니다. 현재 무게가 식물별 물주기 기준 이하일 때만 `지금 권장 급수량`을 반환하며, 한 번에 줄
최대량이 입력되면 해당 값으로 제한합니다. 계산된 손실량이 음수이거나 배수량이 급수량보다
큰 경우에는 숫자를 그대로 권장에 사용하지 않고 측정값 확인 경고를 반환합니다. 화분 무게
1g을 물 1mL로 근사하며, 손실량에는 식물의 증산과 흙 표면 증발이 함께 포함됩니다.

검사: `backend/.venv/bin/python -m pytest backend/tests`,
`backend/.venv/bin/python -m ruff check backend`,
`npm --prefix mobile run typecheck`, `npm --prefix mobile run lint`.

### 실제 기기 연동을 위한 측정 계약

기존 수동 계산 API는 유지하면서 `POST /api/water-balance/evaluate`를 추가했습니다. 새 API는
`manual`, `simulator`, `device`가 같은 형식으로 시간대가 포함된 시작·종료 무게를 보내며,
실제 기기 입력에는 `device_id`가 필요합니다. 응답에는 계산 버전, 입력 출처, 측정 구간,
기기 식별자가 포함되어 나중에 계산을 재현할 수 있습니다.

표준 JSON은 다음 명령으로 실제 호출 없이 확인할 수 있습니다.

```powershell
.\scripts\simulate-water-device.ps1 -DryRun
```

전체 구조, 기기 측정 규칙과 검증 순서는
[`docs/water-measurement-architecture.md`](docs/water-measurement-architecture.md)를 참고합니다.
계산기 화면의 `측정·돌봄 기록`에서는 이번 1회의 안정 무게와 급수·배수량을 별도로 저장하고
최근 이력을 확인합니다. 계산 입력의 누적값과 1회 이벤트를 분리해 중복 합산을 막습니다.
기기·보정 이력·무게 측정·급수/배수 이벤트용 스키마는
`supabase/migrations/202610250001_water_measurement_pipeline.sql`에 있습니다.
