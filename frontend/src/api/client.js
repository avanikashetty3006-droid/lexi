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

export async function analyzeStream(
  payload,
  { onStage, onResolver, onVote, onToken } = {}
) {
  if (USE_MOCK) {
    onStage?.({ step: 'detecting', message: 'Checking ambiguity...' });
    const mockRes = await mockAnalyze(payload);
    onStage?.({
      step: 'detected',
      ambiguous: mockRes.ambiguous,
      ambiguities: mockRes.ambiguities,
      interpretations: mockRes.interpretations,
    });
    return mockRes;
  }

  const res = await fetch(`${API_URL}/analyze/stream`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...getAuthHeaders(),
    },
    body: JSON.stringify(payload),
  });

  if (!res.ok) {
    throw new Error(`Analyze stream failed (${res.status})`);
  }
  if (!res.body) {
    throw new Error('Streaming not supported by this browser');
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  let finalResult = null;

  const processFrame = (rawFrame) => {
    const trimmed = rawFrame.trim();
    if (!trimmed) return;

    let eventType = 'message';
    const dataLines = [];
    for (const line of trimmed.split('\n')) {
      if (line.startsWith('event:')) {
        eventType = line.slice(6).trim();
      } else if (line.startsWith('data:')) {
        dataLines.push(line.slice(5).trimStart());
      }
    }

    if (dataLines.length === 0) return;
    const data = JSON.parse(dataLines.join('\n'));

    if (eventType === 'stage') {
      onStage?.(data);
    } else if (eventType === 'resolver') {
      onResolver?.(data);
    } else if (eventType === 'vote') {
      onVote?.(data);
    } else if (eventType === 'token') {
      onToken?.(data);
    } else if (eventType === 'done') {
      finalResult = data;
    } else if (eventType === 'error') {
      throw new Error(data?.detail || 'Analyze stream returned an error');
    }
  };

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true }).replace(/\r\n/g, '\n');

    let boundary = buffer.indexOf('\n\n');
    while (boundary !== -1) {
      const frame = buffer.slice(0, boundary);
      buffer = buffer.slice(boundary + 2);
      processFrame(frame);
      boundary = buffer.indexOf('\n\n');
    }
  }

  buffer += decoder.decode().replace(/\r\n/g, '\n');
  if (buffer.trim()) {
    for (const frame of buffer.split('\n\n')) {
      processFrame(frame);
    }
  }

  if (!finalResult) {
    throw new Error('Analyze stream ended without a final result');
  }

  return finalResult;
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

// Sends a user-interaction event (override, thumbs, slider) to POST /feedback.
// Never throws: logging must not break the chat.
export async function sendEvent(event) {
  if (USE_MOCK) {
    console.log('[Lexi event]', event);
    return;
  }
  try {
    await fetch(`${API_URL}/feedback`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
      body: JSON.stringify(event),
    });
  } catch {
    // ignore network errors
  }
}
