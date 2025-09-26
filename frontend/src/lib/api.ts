export type AskResponse = {
  sql: string;
  columns: string[];
  data: Record<string, unknown>[];
  explanation: string;
  chart: 'bar' | 'line' | 'pie' | 'scatter' | 'table';
};

const DEFAULT_BASE_URL = (typeof import.meta !== 'undefined' && (import.meta as any).env?.VITE_API_BASE_URL) || '/api';

export async function askQuestion(question: string, datasetId: string, baseUrl = DEFAULT_BASE_URL): Promise<AskResponse> {
  const res = await fetch(`${baseUrl}/ask`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question, dataset_id: datasetId })
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`Request failed: ${res.status} ${text}`);
  }
  return res.json();
}

export type UploadResponse = { dataset_id: string; tables: string[]; note?: string };

export async function uploadExcel(file: File, baseUrl = DEFAULT_BASE_URL): Promise<UploadResponse> {
  const form = new FormData();
  form.append('file', file);
  const res = await fetch(`${baseUrl}/upload`, { method: 'POST', body: form });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`Upload failed: ${res.status} ${text}`);
  }
  return res.json();
}

export async function uploadJSON(tables: { name?: string; rows: Record<string, unknown>[] }[], baseUrl = DEFAULT_BASE_URL): Promise<UploadResponse> {
  const res = await fetch(`${baseUrl}/upload_json`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ tables })
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`Upload JSON failed: ${res.status} ${text}`);
  }
  return res.json();
}
