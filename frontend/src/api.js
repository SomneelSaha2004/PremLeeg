const API_BASE = import.meta.env.VITE_API_BASE || '';

export async function fetchSchema() {
  const res = await fetch(`${API_BASE}/api/schema`);
  if (!res.ok) {
    throw new Error(`Schema fetch failed: ${res.status}`);
  }
  return await res.json();
}

export async function fetchGoldenPrompts(limit = 5) {
  const res = await fetch(`${API_BASE}/api/golden-prompts?limit=${encodeURIComponent(limit)}`);
  if (!res.ok) {
    throw new Error(`Golden prompts fetch failed: ${res.status}`);
  }
  const data = await res.json();
  return data.items || [];
}

export async function runQuery(question, { summarize = true, includeRows = true } = {}) {
  const res = await fetch(`${API_BASE}/api/query`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question, summarize, include_rows: includeRows }),
  });

  const payload = await res.json().catch(() => null);

  if (!res.ok) {
    const detail = payload?.detail;
    const message = detail?.message || `Query failed: ${res.status}`;
    const err = new Error(message);
    err.status = res.status;
    err.detail = detail;
    throw err;
  }

  return payload;
}
