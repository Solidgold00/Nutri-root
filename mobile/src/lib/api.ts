import { AnalysisResult } from './types';

const API_URL = process.env.EXPO_PUBLIC_API_URL?.trim().replace(/\/+$/, '');

function requireApiUrl(): string {
  if (!API_URL) {
    throw new Error(
      'EXPO_PUBLIC_API_URL is not configured. Create mobile/.env from mobile/.env.example and rebuild the app.',
    );
  }
  return API_URL;
}

export async function analyzeMeal(meal: string): Promise<AnalysisResult> {
  const response = await fetch(`${requireApiUrl()}/analyze`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ meal }),
  });

  if (!response.ok) {
    const body = await response.text();
    throw new Error(body || 'Analysis failed');
  }

  return response.json();
}
