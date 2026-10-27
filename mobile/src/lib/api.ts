import { supabase } from '@/lib/supabase';

const DEFAULT_API_URL = 'http://localhost:8000';

export const API_URL = process.env.EXPO_PUBLIC_API_URL ?? DEFAULT_API_URL;

export type HealthResponse = {
  status: 'ok';
  service: string;
  environment: string;
};

export async function fetchHealth(): Promise<HealthResponse> {
  const response = await fetch(`${API_URL}/api/health`);

  if (!response.ok) {
    throw new Error(`API request failed: ${response.status}`);
  }

  return response.json() as Promise<HealthResponse>;
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
        'Content-Type': 'application/json',
        Authorization: `Bearer ${accessToken}`,
      },
      body: JSON.stringify({ messages, ...(plant ? { plant } : {}) }),
      signal: controller.signal,
    });
    const data = await response.json();
    if (!response.ok) {
      throw new Error(typeof data.detail === 'string' ? data.detail : '메시지를 보내지 못했어요. 다시 시도해 주세요.');
    }
    if (typeof data.reply !== 'string' || !data.reply.trim()) {
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
      'Content-Type': 'application/json',
      Authorization: `Bearer ${accessToken}`,
    },
    body: JSON.stringify(request),
  });
  const data = await response.json();
  if (!response.ok) {
    const detail = typeof data.detail === 'string' ? data.detail : null;
    throw new Error(detail ?? '수분량을 계산하지 못했어요. 입력값을 확인해 주세요.');
  }
  return data as WaterBalanceResponse;
}
