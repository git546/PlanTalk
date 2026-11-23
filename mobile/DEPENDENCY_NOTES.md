# 모바일 의존성 점검

마지막 점검: 2026-11-22

## 적용한 조치

- Expo SDK 57 공식 테스트 구성인 `jest-expo`와 Jest 29를 사용한다.
- React 19.2와 맞는 `test-renderer` 1.2.0을 직접 고정했다. 이 버전은 React 19.2 계열의 `react-reconciler` 0.33을 사용해 최신 1.3 계열에서 발생한 React 19.3 peer 경고를 피한다.
- `npm run audit:prod`로 운영 의존성 감사만 별도로 실행할 수 있다.

## 남은 감사 항목

`npm audit`에는 Expo SDK 57과 그 개발 도구가 끌어오는 전이 의존성 경고가 남아 있다.

- `expo-router` → `query-string` → `decode-uri-component`: 조작된 URI 처리 과정의 서비스 거부 위험
- `expo` → `@expo/fingerprint` → `minimatch`: 복잡한 패턴 처리의 서비스 거부 위험
- ESLint 계열 → Zod·TypeScript ESLint: 개발 도구에서 사용하는 입력 처리 위험

현재 npm이 제시하는 자동 수정은 Expo SDK 52로 내리거나 SDK 58로 올리는 주 버전 변경을 포함한다. `npm audit fix --force`는 사용하지 않는다. SDK 58 마이그레이션 때 Expo Router와 테스트 도구를 함께 갱신하고 다시 감사한다.
