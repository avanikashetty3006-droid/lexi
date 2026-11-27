import { mockAnalyze, mockBaseline } from './mock';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';
const USE_MOCK = import.meta.env.VITE_USE_MOCK === 'true';

export async function analyze(payload) {
  if (USE_MOCK) {
    return mockAnalyze(payload);
  }

  const res = await fetch(`${API_URL}/analyze`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });

  if (!res.ok) {
    throw new Error(`Analyze request failed (${res.status})`);
  }

  return res.json();
}

export async function baseline(sentence) {
  if (USE_MOCK) {
    return mockBaseline(sentence);
  }

  const res = await fetch(`${API_URL}/baseline`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ sentence }),
  });

  if (!res.ok) {
    throw new Error(`Baseline request failed (${res.status})`);
  }

  return res.json();
}
