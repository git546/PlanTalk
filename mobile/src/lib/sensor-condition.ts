export type SensorConditionStatus = 'normal' | 'check_required' | 'unavailable' | 'error';
export type SensorConditionConfidence = 'none' | 'low' | 'medium' | 'high';

export type SensorConditionReading = {
  measuredAt: string;
  weightG?: number | null;
  isStable?: boolean | null;
  soilMoisturePercent?: number | null;
  soilRaw?: number | null;
};

export type SensorConditionCalibration = {
  wateringTriggerWeightG?: number | null;
  targetWetWeightG?: number | null;
  soilMoistureMinPercent?: number | null;
  soilMoistureMaxPercent?: number | null;
};

export type SensorConditionResult = {
  status: SensorConditionStatus;
  confidence: SensorConditionConfidence;
  reasons: string[];
  ageMinutes: number | null;
};

type Signal = 'dry' | 'normal' | 'wet';

function result(
  status: SensorConditionStatus,
  confidence: SensorConditionConfidence,
  reasons: string[],
  ageMinutes: number | null,
): SensorConditionResult {
  return { status, confidence, reasons, ageMinutes };
}

function lowerConfidence(
  confidence: Exclude<SensorConditionConfidence, 'none'>,
): Exclude<SensorConditionConfidence, 'none'> {
  if (confidence === 'high') return 'medium';
  return 'low';
}

export function evaluateSensorCondition(
  reading: SensorConditionReading | null,
  calibration: SensorConditionCalibration,
  options: { now?: Date; maxAgeMinutes?: number } = {},
): SensorConditionResult {
  if (!reading) {
    return result('unavailable', 'none', ['최근 센서 측정값이 없습니다.'], null);
  }

  const measuredAtMs = Date.parse(reading.measuredAt);
  if (!Number.isFinite(measuredAtMs)) {
    return result('error', 'none', ['센서 측정 시각을 해석할 수 없습니다.'], null);
  }

  const nowMs = (options.now ?? new Date()).getTime();
  const ageMinutes = (nowMs - measuredAtMs) / 60_000;
  const maxAgeMinutes = options.maxAgeMinutes ?? 60;
  if (ageMinutes < -5) {
    return result('error', 'none', ['센서 측정 시각이 현재보다 미래입니다.'], ageMinutes);
  }
  if (ageMinutes > maxAgeMinutes) {
    return result(
      'unavailable',
      'none',
      [`센서 데이터가 ${Math.round(ageMinutes)}분 전 값이라 현재 상태를 판단하지 않았습니다.`],
      ageMinutes,
    );
  }

  if (reading.weightG !== null && reading.weightG !== undefined && reading.weightG <= 0) {
    return result('error', 'none', ['화분 무게는 0보다 커야 합니다.'], ageMinutes);
  }
  if (
    reading.soilMoisturePercent !== null
    && reading.soilMoisturePercent !== undefined
    && (reading.soilMoisturePercent < 0 || reading.soilMoisturePercent > 100)
  ) {
    return result('error', 'none', ['토양 수분율은 0~100% 범위여야 합니다.'], ageMinutes);
  }

  const triggerWeight = calibration.wateringTriggerWeightG;
  const targetWeight = calibration.targetWetWeightG;
  if (
    triggerWeight !== null
    && triggerWeight !== undefined
    && targetWeight !== null
    && targetWeight !== undefined
    && triggerWeight >= targetWeight
  ) {
    return result('error', 'none', ['급수 기준 무게는 습윤 목표 무게보다 작아야 합니다.'], ageMinutes);
  }

  const soilMin = calibration.soilMoistureMinPercent;
  const soilMax = calibration.soilMoistureMaxPercent;
  if (
    soilMin !== null
    && soilMin !== undefined
    && soilMax !== null
    && soilMax !== undefined
    && soilMin > soilMax
  ) {
    return result('error', 'none', ['토양 수분 하한은 상한보다 클 수 없습니다.'], ageMinutes);
  }

  const signals: { source: 'weight' | 'soil'; value: Signal }[] = [];
  const reasons: string[] = [];
  if (
    reading.weightG !== null
    && reading.weightG !== undefined
    && triggerWeight !== null
    && triggerWeight !== undefined
    && targetWeight !== null
    && targetWeight !== undefined
  ) {
    const weightSignal: Signal = reading.weightG <= triggerWeight ? 'dry' : 'normal';
    signals.push({ source: 'weight', value: weightSignal });
    reasons.push(
      weightSignal === 'dry'
        ? '현재 무게가 화분별 급수 기준 이하입니다.'
        : '현재 무게가 화분별 급수 기준보다 높습니다.',
    );
  }

  if (
    reading.soilMoisturePercent !== null
    && reading.soilMoisturePercent !== undefined
    && soilMin !== null
    && soilMin !== undefined
    && soilMax !== null
    && soilMax !== undefined
  ) {
    const soilSignal: Signal = reading.soilMoisturePercent < soilMin
      ? 'dry'
      : reading.soilMoisturePercent > soilMax
        ? 'wet'
        : 'normal';
    signals.push({ source: 'soil', value: soilSignal });
    reasons.push(
      soilSignal === 'dry'
        ? '보정된 토양 수분율이 설정 하한보다 낮습니다.'
        : soilSignal === 'wet'
          ? '보정된 토양 수분율이 설정 상한보다 높습니다.'
          : '보정된 토양 수분율이 설정 범위 안입니다.',
    );
  }

  if (signals.length === 0) {
    if (reading.soilRaw !== null && reading.soilRaw !== undefined) {
      reasons.push('토양 원본값은 보정 전 상대값이라 상태 판정에 사용하지 않았습니다.');
    }
    reasons.push('화분별 보정값이 부족해 현재 상태를 판단할 수 없습니다.');
    return result('unavailable', 'low', reasons, ageMinutes);
  }

  const uniqueSignals = new Set(signals.map((signal) => signal.value));
  const disagrees = uniqueSignals.size > 1;
  if (disagrees) {
    reasons.push('무게와 토양 센서 결과가 일치하지 않아 직접 확인이 필요합니다.');
    return result('check_required', 'low', reasons, ageMinutes);
  }

  const signal = signals[0].value;
  const status: SensorConditionStatus = signal === 'normal' ? 'normal' : 'check_required';
  let confidence: Exclude<SensorConditionConfidence, 'none'> = signals.length >= 2 ? 'high' : 'medium';
  if (reading.isStable === false) {
    reasons.push('안정화되지 않은 측정값이어서 신뢰도를 낮췄습니다.');
    confidence = lowerConfidence(confidence);
  }

  return result(status, confidence, reasons, ageMinutes);
}
