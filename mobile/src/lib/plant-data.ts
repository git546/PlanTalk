import { supabase } from '@/lib/supabase';

export type PersistedPlant = {
  id: string;
  name: string;
  species: string;
  setupWeightG: number | null;
  targetWetWeightG: number | null;
  wateringTriggerWeightG: number | null;
  maxSingleWateringMl: number | null;
  calibrationUpdatedAt: string | null;
};

type PlantRow = {
  id: string;
  name: string;
  care_overrides: Record<string, unknown> | null;
};

type CalibrationRow = {
  plant_id: string;
  setup_weight_g: number | string;
  target_wet_weight_g: number | string;
  watering_trigger_weight_g: number | string;
  max_single_watering_ml: number | string | null;
  calibrated_at: string;
};

function asNumber(value: number | string | null): number | null {
  if (value === null) return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function message(action: string, detail?: string): Error {
  return new Error(detail ? `${action} (${detail})` : action);
}

export async function loadPersistedPlants(): Promise<PersistedPlant[]> {
  const { data: plantRows, error: plantError } = await supabase
    .from('plants')
    .select('id,name,care_overrides')
    .order('created_at', { ascending: true });
  if (plantError) throw message('식물 목록을 불러오지 못했습니다.', plantError.message);

  const plants = (plantRows ?? []) as PlantRow[];
  if (plants.length === 0) return [];

  const { data: calibrationRows, error: calibrationError } = await supabase
    .from('plant_water_calibrations')
    .select(
      'plant_id,setup_weight_g,target_wet_weight_g,watering_trigger_weight_g,max_single_watering_ml,calibrated_at',
    )
    .in('plant_id', plants.map((plant) => plant.id))
    .eq('is_active', true);
  if (calibrationError) {
    throw message('식물 보정값을 불러오지 못했습니다.', calibrationError.message);
  }

  const calibrationByPlant = new Map(
    ((calibrationRows ?? []) as CalibrationRow[]).map((row) => [row.plant_id, row]),
  );
  return plants.map((plant) => {
    const calibration = calibrationByPlant.get(plant.id);
    const species = plant.care_overrides?.species_label;
    return {
      id: plant.id,
      name: plant.name,
      species: typeof species === 'string' && species.trim() ? species : '종류 미정',
      setupWeightG: asNumber(calibration?.setup_weight_g ?? null),
      targetWetWeightG: asNumber(calibration?.target_wet_weight_g ?? null),
      wateringTriggerWeightG: asNumber(calibration?.watering_trigger_weight_g ?? null),
      maxSingleWateringMl: asNumber(calibration?.max_single_watering_ml ?? null),
      calibrationUpdatedAt: calibration?.calibrated_at ?? null,
    };
  });
}

export async function createPersistedPlant(
  userId: string,
  name: string,
  species: string,
): Promise<PersistedPlant> {
  const normalizedSpecies = species.trim() || '종류 미정';
  const { data, error } = await supabase
    .from('plants')
    .insert({
      user_id: userId,
      name: name.trim() || '새 식물',
      care_overrides: { species_label: normalizedSpecies },
    })
    .select('id,name,care_overrides')
    .single();
  if (error) throw message('식물을 저장하지 못했습니다.', error.message);
  const row = data as PlantRow;
  return {
    id: row.id,
    name: row.name,
    species: normalizedSpecies,
    setupWeightG: null,
    targetWetWeightG: null,
    wateringTriggerWeightG: null,
    maxSingleWateringMl: null,
    calibrationUpdatedAt: null,
  };
}

export async function savePersistedCalibration(plant: PersistedPlant): Promise<void> {
  if (
    plant.setupWeightG === null
    || plant.targetWetWeightG === null
    || plant.wateringTriggerWeightG === null
  ) {
    throw new Error('저장할 보정값이 완전하지 않습니다.');
  }
  const { error } = await supabase.rpc('save_plant_water_calibration', {
    p_plant_id: plant.id,
    p_setup_weight_g: plant.setupWeightG,
    p_target_wet_weight_g: plant.targetWetWeightG,
    p_watering_trigger_weight_g: plant.wateringTriggerWeightG,
    p_max_single_watering_ml: plant.maxSingleWateringMl,
    p_notes: 'mobile',
  });
  if (error) throw message('식물 보정값을 저장하지 못했습니다.', error.message);
}

export async function deletePersistedPlant(plantId: string): Promise<void> {
  const { error } = await supabase.from('plants').delete().eq('id', plantId);
  if (error) throw message('식물을 삭제하지 못했습니다.', error.message);
}

export async function deleteAllPersistedPlants(): Promise<void> {
  const { data: userData } = await supabase.auth.getUser();
  const userId = userData.user?.id;
  if (!userId) throw new Error('로그인이 필요합니다.');
  const { error } = await supabase.from('plants').delete().eq('user_id', userId);
  if (error) throw message('식물 데이터를 초기화하지 못했습니다.', error.message);
}
