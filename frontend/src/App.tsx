import React, { useMemo, useRef, useState } from 'react';
import { askQuestion, AskResponse, uploadExcel, UploadResponse } from './lib/api';
import { DataTable } from './components/DataTable';
import { ChartPanel } from './components/ChartPanel';

type Message = { role: 'user' | 'assistant'; content: string; meta?: Partial<AskResponse> };

export const App: React.FC = () => {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [dataset, setDataset] = useState<UploadResponse | null>(null);
  const baseUrl = useMemo(() => (import.meta.env.VITE_API_BASE_URL || '/api') as string, []);
  const inputRef = useRef<HTMLInputElement>(null);

  async function onSend() {
    const q = input.trim();
    if (!q || loading || !dataset) return;
    setInput('');
    setMessages((m) => [...m, { role: 'user', content: q }]);
    setLoading(true);
    try {
      const res = await askQuestion(q, dataset.dataset_id, baseUrl);
      const summary = res.explanation || 'Results ready.';
      setMessages((m) => [...m, { role: 'assistant', content: summary, meta: res }]);
    } catch (e: any) {
      setMessages((m) => [...m, { role: 'assistant', content: `Error: ${e?.message || 'Request failed'}` }]);
    } finally {
      setLoading(false);
      inputRef.current?.focus();
    }
  }

  async function onUpload(file: File) {
    setLoading(true);
    try {
      const info = await uploadExcel(file, baseUrl);
      setDataset(info);
      setMessages((m) => [...m, { role: 'assistant', content: `Dataset uploaded. Found ${info.tables.length} table(s).` }]);
    } catch (e: any) {
      setMessages((m) => [...m, { role: 'assistant', content: `Upload error: ${e?.message || 'failed'}` }]);
    } finally {
      setLoading(false);
    }
  }

  const lastMeta = useMemo(() => {
    for (let i = messages.length - 1; i >= 0; i--) {
      const m = messages[i];
      if (m.role === 'assistant' && m.meta) return m.meta;
    }
    return undefined;
  }, [messages]);

  return (
    <div className="app">
      <div className="header">
        <div className="title">NL2SQL Analytics</div>
        <div className="env">Backend: {baseUrl}</div>
      </div>

      <div className="content">
        <div className="messages">
          {messages.map((m, idx) => (
            <div className="msg" key={idx}>
              <div className="role">{m.role}</div>
              <div className="bubble">{m.content}</div>
            </div>
          ))}
          {loading && (
            <div className="msg">
              <div className="role">assistant</div>
              <div className="bubble">Thinking…</div>
            </div>
          )}
        </div>

        <div className="panel">
          <div className="inputRow" style={{ alignItems: 'center' }}>
            <input
              type="file"
              accept=".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
              className="input"
              onChange={(e) => { const f = e.target.files?.[0]; if (f) onUpload(f); }}
            />
            <div style={{ color: '#9aa4b2', fontSize: 12 }}>
              {dataset ? `Dataset: ${dataset.dataset_id} (${dataset.tables.length} table${dataset.tables.length !== 1 ? 's' : ''})` : 'Upload an Excel file to begin'}
            </div>
          </div>
          <div className="inputRow">
            <input
              ref={inputRef}
              className="input"
              placeholder="Ask a question about your data…"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter') onSend(); }}
            />
            <button className="button" onClick={onSend} disabled={loading || !input.trim() || !dataset}>
              {loading ? 'Sending…' : 'Send'}
            </button>
          </div>
          {lastMeta && (
            <div className="grid2">
              <div>
                <div className="card">
                  <h3>SQL</h3>
                  <div style={{ fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace', fontSize: 12, whiteSpace: 'pre-wrap' }}>
                    {lastMeta.sql}
                  </div>
                </div>
              </div>
              <div>
                <ChartPanel chart={lastMeta.chart} columns={lastMeta.columns} rows={lastMeta.data} />
              </div>
            </div>
          )}
          {lastMeta && (
            <DataTable columns={lastMeta.columns} rows={lastMeta.data} />
          )}
          <div className="footer">Built with React, Recharts, FastAPI, and LangChain.</div>
        </div>
      </div>
    </div>
  );
};
