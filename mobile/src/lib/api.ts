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

export async function fetchReply(messages: ChatMessage[]): Promise<string> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 45000);
  try {
    const response = await fetch(`${API_URL}/api/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ messages }),
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
