import { supabase } from '@/lib/supabase';

const DEFAULT_API_URL = 'http://localhost:8000';

export const API_URL = process.env.EXPO_PUBLIC_API_URL ?? DEFAULT_API_URL;

function apiErrorMessage(response: Response, fallback: string): string {
  if (response.redirected || response.status === 401 || response.status === 403) {
    return '접속 권한을 확인할 수 없어요. 페이지를 다시 열고 로그인해 주세요.';
  }
  if (response.status === 504 || response.status === 524) {
    return '서버 응답 시간이 초과됐어요. 잠시 후 다시 시도해 주세요.';
  }
  if (response.status >= 500) {
    return '서버 연결에 문제가 생겼어요. 잠시 후 다시 시도해 주세요.';
  }
  if (response.ok) {
    return '서버 응답을 읽을 수 없어요. 페이지를 다시 열고 다시 시도해 주세요.';
  }
  return fallback;
}

async function readApiResponse(response: Response, fallback: string): Promise<unknown> {
  const contentType = response.headers.get('content-type')?.split(';', 1)[0].trim().toLowerCase();
  const errorMessage = apiErrorMessage(response, fallback);
  if (contentType !== 'application/json' && !contentType?.endsWith('+json')) {
    throw new Error(errorMessage);
  }

  let data: unknown;
  try {
    data = await response.json();
  } catch (error) {
    if (error instanceof Error && error.name === 'AbortError') throw error;
    throw new Error(errorMessage);
  }

  if (!response.ok) {
    const detail = data && typeof data === 'object' && 'detail' in data ? data.detail : null;
    throw new Error(typeof detail === 'string' && detail.trim() ? detail : errorMessage);
  }
  return data;
}

export type HealthResponse = {
  status: 'ok';
  service: string;
  environment: string;
};

export async function fetchHealth(): Promise<HealthResponse> {
  const response = await fetch(`${API_URL}/api/health`, {
    headers: { Accept: 'application/json' },
  });
  return (await readApiResponse(response, '서버 상태를 확인하지 못했어요.')) as HealthResponse;
}

export type SpeciesReference = {
  query: string;
  normalized_query: string;
  common_name: string | null;
  scientific_names: string[];
  watering: string | null;
  sunlight: string[];
  care_level: string | null;
  indoor: boolean | null;
  cycle: string | null;
  taxonomy: {
    scientific_name: string | null;
    canonical_name: string | null;
    family: string | null;
    genus: string | null;
    rank: string | null;
    status: string | null;
    confidence: number | null;
  } | null;
  sources: string[];
  source_urls: string[];
  warnings: string[];
};

export type SpeciesReferenceResponse = {
  reference: SpeciesReference;
  usage: string;
};

export async function fetchSpeciesReference(
  query: string,
  plantId?: string,
  refresh = false,
): Promise<SpeciesReferenceResponse> {
  const { data: sessionData } = await supabase.auth.getSession();
  const accessToken = sessionData.session?.access_token;
  if (!accessToken) throw new Error('로그인이 필요합니다.');
  const params = new URLSearchParams({ q: query });
  if (plantId) params.set('plant_id', plantId);
  if (refresh) params.set('refresh', 'true');
  const response = await fetch(`${API_URL}/api/species-reference?${params.toString()}`, {
    headers: { Accept: 'application/json', Authorization: `Bearer ${accessToken}` },
  });
  const data = await readApiResponse(response, '식물 참고 정보를 찾지 못했습니다.');
  return data as SpeciesReferenceResponse;
}

export type ChatMessage = { role: 'user' | 'assistant'; content: string };

export type PlantPersonality = {
  tone?: string;
  energy?: number;
  affection?: number;
  humor?: number;
  talk_length?: '짧게' | '보통' | '길게';
  traits?: string[];
  habits?: string[];
  favorite_topics?: string[];
  calling_user?: string;
  custom_description?: string;
  speech_example?: string;
};

export type PlantContext = {
  id?: string;
  name: string;
  species?: string;
  personality?: PlantPersonality;
  memories?: string[];
};

function deviceTimeZone(): string | undefined {
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone;
  } catch {
    return undefined;
  }
}

export async function fetchReply(messages: ChatMessage[], plant?: PlantContext): Promise<string> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 45000);
  try {
    const { data: sessionData } = await supabase.auth.getSession();
    const accessToken = sessionData.session?.access_token;
    if (!accessToken) throw new Error('로그인이 필요합니다.');
    const response = await fetch(`${API_URL}/api/chat`, {
      method: 'POST',
      headers: {
        Accept: 'application/json',
        'Content-Type': 'application/json',
        Authorization: `Bearer ${accessToken}`,
      },
      body: JSON.stringify({ messages, time_zone: deviceTimeZone(), ...(plant ? { plant } : {}) }),
      signal: controller.signal,
    });
    const data = await readApiResponse(response, '메시지를 보내지 못했어요. 다시 시도해 주세요.');
    if (!data || typeof data !== 'object' || !('reply' in data)
      || typeof data.reply !== 'string' || !data.reply.trim()) {
      throw new Error('답변이 비어 있어요. 다시 시도해 주세요.');
    }
    return data.reply;
  } finally {
    clearTimeout(timeout);
  }
}

export type WaterBalanceRequest = {
  period_days: number;
  start_pot_weight_g: number;
  end_pot_weight_g: number;
  water_added_ml: number;
  drainage_ml: number;
  target_wet_weight_g: number;
  watering_trigger_weight_g: number;
  max_single_watering_ml?: number;
};

export type WaterBalanceResponse = {
  observation_period_days: number;
  storage_change_ml: number;
  net_water_added_ml: number;
  estimated_water_loss_ml: number;
  average_daily_loss_ml: number;
  drainage_ratio_percent: number | null;
  refill_to_target_ml: number;
  recommended_water_now_ml: number;
  estimated_days_until_watering: number | null;
  status: 'hydrated' | 'monitor' | 'water_soon' | 'water_now';
  confidence: 'low' | 'medium' | 'high';
  warnings: string[];
  assumption: string;
  trace: {
    calculation_version: 'water-balance-rules-v1';
    input_mode: 'legacy' | 'measurement_window';
    measurement_sources: ('manual' | 'simulator' | 'device')[];
    started_at: string | null;
    ended_at: string | null;
    device_ids: string[];
  };
};

export async function fetchWaterBalance(
  request: WaterBalanceRequest,
): Promise<WaterBalanceResponse> {
  const { data: sessionData } = await supabase.auth.getSession();
  const accessToken = sessionData.session?.access_token;
  if (!accessToken) throw new Error('로그인이 필요합니다.');

  const response = await fetch(`${API_URL}/api/water-balance`, {
    method: 'POST',
    headers: {
      Accept: 'application/json',
      'Content-Type': 'application/json',
      Authorization: `Bearer ${accessToken}`,
    },
    body: JSON.stringify(request),
  });
  const data = await readApiResponse(response, '수분량을 계산하지 못했어요. 입력값을 확인해 주세요.');
  return data as WaterBalanceResponse;
}
