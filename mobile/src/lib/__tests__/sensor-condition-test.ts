import { evaluateSensorCondition } from '@/lib/sensor-condition';

const NOW = new Date('2026-11-22T12:00:00.000Z');
const CALIBRATION = {
  wateringTriggerWeightG: 1400,
  targetWetWeightG: 1600,
  soilMoistureMinPercent: 35,
  soilMoistureMaxPercent: 70,
};

describe('evaluateSensorCondition', () => {
  test('최근 데이터가 없으면 판정을 보류한다', () => {
    expect(evaluateSensorCondition(null, CALIBRATION, { now: NOW })).toMatchObject({
      status: 'unavailable',
      confidence: 'none',
    });
  });

  test('오래된 데이터는 현재 상태 판단에 사용하지 않는다', () => {
    const result = evaluateSensorCondition(
      { measuredAt: '2026-11-22T10:00:00.000Z', weightG: 1350, isStable: true },
      CALIBRATION,
      { now: NOW, maxAgeMinutes: 60 },
    );

    expect(result.status).toBe('unavailable');
    expect(result.confidence).toBe('none');
    expect(result.reasons.join(' ')).toContain('120분 전');
  });

  test('센서값이 물리 범위를 벗어나면 오류로 분류한다', () => {
    const result = evaluateSensorCondition(
      {
        measuredAt: '2026-11-22T11:50:00.000Z',
        weightG: 1500,
        soilMoisturePercent: 120,
      },
      CALIBRATION,
      { now: NOW },
    );

    expect(result.status).toBe('error');
    expect(result.reasons.join(' ')).toContain('0~100%');
  });

  test('보정 전 토양 원본값만으로는 건조 상태를 단정하지 않는다', () => {
    const result = evaluateSensorCondition(
      { measuredAt: '2026-11-22T11:50:00.000Z', soilRaw: 491, isStable: true },
      {},
      { now: NOW },
    );

    expect(result.status).toBe('unavailable');
    expect(result.confidence).toBe('low');
    expect(result.reasons.join(' ')).toContain('보정 전 상대값');
  });

  test('무게와 보정 수분율이 모두 건조하면 확인 필요로 판정한다', () => {
    const result = evaluateSensorCondition(
      {
        measuredAt: '2026-11-22T11:50:00.000Z',
        weightG: 1380,
        soilMoisturePercent: 30,
        isStable: true,
      },
      CALIBRATION,
      { now: NOW },
    );

    expect(result.status).toBe('check_required');
    expect(result.confidence).toBe('high');
  });

  test('무게와 토양 센서가 충돌하면 신뢰도를 낮추고 직접 확인을 요구한다', () => {
    const result = evaluateSensorCondition(
      {
        measuredAt: '2026-11-22T11:50:00.000Z',
        weightG: 1500,
        soilMoisturePercent: 30,
        isStable: true,
      },
      CALIBRATION,
      { now: NOW },
    );

    expect(result.status).toBe('check_required');
    expect(result.confidence).toBe('low');
    expect(result.reasons.join(' ')).toContain('일치하지 않아');
  });

  test('두 보정값이 정상 범위에서 일치하면 높은 신뢰도로 정상 판정한다', () => {
    const result = evaluateSensorCondition(
      {
        measuredAt: '2026-11-22T11:50:00.000Z',
        weightG: 1500,
        soilMoisturePercent: 50,
        isStable: true,
      },
      CALIBRATION,
      { now: NOW },
    );

    expect(result.status).toBe('normal');
    expect(result.confidence).toBe('high');
  });

  test('안정화되지 않은 값은 같은 판정에서도 신뢰도를 낮춘다', () => {
    const result = evaluateSensorCondition(
      {
        measuredAt: '2026-11-22T11:50:00.000Z',
        weightG: 1500,
        soilMoisturePercent: 50,
        isStable: false,
      },
      CALIBRATION,
      { now: NOW },
    );

    expect(result.status).toBe('normal');
    expect(result.confidence).toBe('medium');
  });
});
