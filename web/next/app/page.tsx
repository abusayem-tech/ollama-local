"use client";
import { useEffect, useMemo, useRef, useState } from "react";

export default function Page() {
  const [serverUrl, setServerUrl] = useState<string>("");
  const [apiKey, setApiKey] = useState<string>("");
  const [models, setModels] = useState<string[]>([]);
  const [model, setModel] = useState<string>("");
  const [system, setSystem] = useState<string>("");
  const [input, setInput] = useState<string>("");
  const [history, setHistory] = useState<{ role: string; content: string }[]>([]);
  const [pullName, setPullName] = useState<string>("");
  const [pullLog, setPullLog] = useState<string>("");
  const [busy, setBusy] = useState<boolean>(false);

  useEffect(() => {
    const s = localStorage.getItem("serverUrl") || "";
    const k = localStorage.getItem("apiKey") || "";
    setServerUrl(s);
    setApiKey(k);
  }, []);

  const headers = useMemo(() => {
    const h: Record<string, string> = { "Content-Type": "application/json" };
    if (apiKey) h["x-api-key"] = apiKey;
    return h;
  }, [apiKey]);

  async function refreshModels() {
    if (!serverUrl) return;
    const r = await fetch(new URL("/models", serverUrl), { headers });
    const j = await r.json();
    const names = (j.models || []).map((m: any) => m.name).filter(Boolean);
    setModels(names);
  }

  async function send() {
    if (!serverUrl || !model || !input) return;
    const messages = [
      ...(system ? [{ role: "system", content: system }] : []),
      ...history,
      { role: "user", content: input },
    ];
    setHistory((h) => [...h, { role: "user", content: input }]);
    setInput("");
    setBusy(true);
    const res = await fetch(new URL("/chat_stream", serverUrl), {
      method: "POST",
      headers,
      body: JSON.stringify({ model, messages, options: {} }),
    });
    const reader = res.body?.getReader();
    if (!reader) return;
    let assistant = "";
    const decoder = new TextDecoder();
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      const text = decoder.decode(value);
      for (const line of text.split("\n")) {
        if (!line.trim()) continue;
        try {
          const j = JSON.parse(line);
          if (j.token) {
            assistant += j.token;
            setHistory((h) => {
              const last = h[h.length - 1];
              if (last && last.role === "assistant") {
                const copy = h.slice(0, -1);
                copy.push({ role: "assistant", content: assistant });
                return copy;
              }
              return [...h, { role: "assistant", content: assistant }];
            });
          }
        } catch {}
      }
    }
    setBusy(false);
  }

  async function pull() {
    if (!serverUrl || !pullName) return;
    setPullLog("");
    const res = await fetch(new URL("/pull", serverUrl), {
      method: "POST",
      headers,
      body: JSON.stringify({ name: pullName }),
    });
    const reader = res.body?.getReader();
    if (!reader) return;
    const decoder = new TextDecoder();
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      const text = decoder.decode(value);
      setPullLog((l) => l + text);
    }
    refreshModels();
  }

  return (
    <div style={{ maxWidth: 900, margin: "0 auto", padding: 16 }}>
      <h1>Ollama Remote</h1>
      <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
        <input
          placeholder="Server URL (https://your-tunnel.example)"
          value={serverUrl}
          onChange={(e) => setServerUrl(e.target.value)}
          style={{ flex: 1, minWidth: 320 }}
        />
        <input
          placeholder="API Key"
          value={apiKey}
          onChange={(e) => setApiKey(e.target.value)}
          style={{ width: 200 }}
        />
        <button
          onClick={() => {
            localStorage.setItem("serverUrl", serverUrl);
            localStorage.setItem("apiKey", apiKey);
            refreshModels();
          }}
        >
          Save & Refresh
        </button>
      </div>

      <hr />

      <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
        <select value={model} onChange={(e) => setModel(e.target.value)}>
          <option value="">Select model</option>
          {models.map((m) => (
            <option key={m} value={m}>
              {m}
            </option>
          ))}
        </select>
        <button onClick={refreshModels}>Refresh Models</button>
      </div>

      <div style={{ marginTop: 8 }}>
        <textarea
          placeholder="System prompt (optional)"
          value={system}
          onChange={(e) => setSystem(e.target.value)}
          rows={3}
          style={{ width: "100%" }}
        />
      </div>

      <div style={{ border: "1px solid #ddd", padding: 8, marginTop: 8, minHeight: 200 }}>
        {history.map((m, i) => (
          <div key={i} style={{ whiteSpace: "pre-wrap" }}>
            <b>{m.role === "user" ? "You" : "Assistant"}:</b> {m.content}
          </div>
        ))}
      </div>

      <div style={{ display: "flex", gap: 8, marginTop: 8 }}>
        <textarea
          placeholder="Your message"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          rows={3}
          style={{ flex: 1 }}
        />
        <button disabled={busy} onClick={send}>
          {busy ? "Sending..." : "Send"}
        </button>
      </div>

      <hr />

      <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
        <input
          placeholder="Model to pull (e.g., deepseek-r1:1.5b)"
          value={pullName}
          onChange={(e) => setPullName(e.target.value)}
          style={{ flex: 1, minWidth: 320 }}
        />
        <button onClick={pull}>Pull</button>
      </div>
      <pre style={{ background: "#f7f7f7", padding: 8, whiteSpace: "pre-wrap" }}>{pullLog}</pre>
    </div>
  );
}


