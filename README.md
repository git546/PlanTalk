# PlanTalk

반려식물과 대화하고 식물 상태를 관리하는 모바일 앱의 초기 개발 환경입니다.

- 모바일: React Native + Expo SDK 57 + TypeScript + Expo Router
- API: FastAPI + Python 3.12
- 향후 연동: Supabase, OpenAI API, 센서/외부 API

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
```

- Android 에뮬레이터: `http://10.0.2.2:8000`
- Expo Go를 설치한 실제 휴대폰: `http://<PC의-같은-Wi-Fi-IP>:8000`
- `EXPO_PUBLIC_` 값은 앱에 포함되므로 비밀키를 넣으면 안 됩니다.

### 백엔드

`backend/.env`에 서버 전용 값을 입력합니다. 실제 키는 Git에 커밋하지 않습니다.

```dotenv
OPENAI_API_KEY=
SUPABASE_URL=
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

## 4. 검사

```powershell
npm --prefix mobile run typecheck
npm --prefix mobile run lint
npm --prefix mobile run doctor
.\backend\.venv\Scripts\python.exe -m pytest backend\tests
.\backend\.venv\Scripts\python.exe -m ruff check backend
```

## 보안 원칙

- `OPENAI_API_KEY`와 `SUPABASE_SERVICE_ROLE_KEY`는 FastAPI 서버에서만 사용합니다.
- 모바일에는 공개 가능한 `EXPO_PUBLIC_` 값만 둡니다.
- `.env`, `.env.local`, 가상환경, 빌드 결과물은 Git에서 제외됩니다.
