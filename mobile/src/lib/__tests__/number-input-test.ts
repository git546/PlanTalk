import { parseLocalizedNumber } from '@/lib/number-input';

describe('parseLocalizedNumber', () => {
  test('한국어 입력 환경의 쉼표 소수를 숫자로 변환한다', () => {
    expect(parseLocalizedNumber(' 12,5 ')).toBe(12.5);
  });

  test.each(['', '   ', 'abc', '1.2.3'])('잘못된 입력 %p은 null을 반환한다', (value) => {
    expect(parseLocalizedNumber(value)).toBeNull();
  });
});
