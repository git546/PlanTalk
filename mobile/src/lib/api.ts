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
