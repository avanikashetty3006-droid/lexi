import { mockAnalyze, mockBaseline } from './mock';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';
const USE_MOCK = import.meta.env.VITE_USE_MOCK === 'true';
const AUTH_STORAGE_KEY = 'lexi_auth_user';

function getAuthHeaders() {
  try {
    const raw = localStorage.getItem(AUTH_STORAGE_KEY);
    if (!raw) return {};
    const parsed = JSON.parse(raw);
    if (parsed?.token) {
      return { Authorization: `Bearer ${parsed.token}` };
    }
  } catch {
    // Ignore storage errors
  }
  return {};
}

export async function analyze(payload) {
  if (USE_MOCK) {
    return mockAnalyze(payload);
  }

  const res = await fetch(`${API_URL}/analyze`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...getAuthHeaders(),
    },
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
    headers: {
      'Content-Type': 'application/json',
      ...getAuthHeaders(),
    },
    body: JSON.stringify({ sentence }),
  });

  if (!res.ok) {
    throw new Error(`Baseline request failed (${res.status})`);
  }

  return res.json();
}
