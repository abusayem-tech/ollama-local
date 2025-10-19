## Ollama GUI (Windows)

Small Windows desktop app to manage and chat with local Ollama models.

- List installed models
- Pull new models with progress
- Delete models
- Chat with streaming responses
- Configure host/port

### Prerequisites

- Windows 10/11
- Ollama running (default `http://127.0.0.1:11434`)
- Python 3.10+

### Run from source

```bash
python -m pip install -r requirements.txt
python -m app.main
```

### Build a standalone .exe

```powershell
./build_win.ps1 -OneFile
# Output: dist/OllamaGUI/OllamaGUI.exe
```

If startup seems slow, try one-dir build:

```powershell
./build_win.ps1
```

### Usage

- Use the left pane to refresh, pull and delete models (Stop Pull to cancel).
- Enter a model in the chat pane (e.g., `llama3.1:8b`), type a message, and Send (Ctrl+Enter to send, Esc to stop).
- Set chat parameters (temperature, top_p, max tokens) and optional system prompt.
- Configure host/port via Settings. Connection status shows in the status bar.
- Save/Load conversation from File menu. Default model and UI settings persist.
 - Advanced:
   - GPU toggle and context size (`num_ctx`).
   - Per-model presets (auto-load when the model name matches; save/delete presets).
   - Prompt templates: save/apply/delete stored system prompts.

### Remote access (run here, control from anywhere)

Run a small proxy server on this PC and point your Vercel app to it.

1) Start the server (PowerShell, from repo root):

```powershell
cd server
python -m pip install -r requirements.txt
.\n+./run_server.ps1 -ApiKey YOUR_SECRET -AllowOrigins * -Host 0.0.0.0 -Port 8080 -OllamaHost 127.0.0.1 -OllamaPort 11434
```

2) Expose it to the internet (choose one):

- Cloudflare Tunnel (free, robust): `cloudflared tunnel --url http://localhost:8080`
- ngrok: `ngrok http 8080`

3) Deploy a minimal Next.js app to Vercel that calls your server URL (e.g., `https://your-tunnel.example/ws/chat`). Include header `x-api-key: YOUR_SECRET`.

Endpoints:
- `GET /health`
- `GET /models`
- `POST /pull` (NDJSON stream)
- `POST /delete`
- `POST /chat`
- `POST /chat_stream` (NDJSON stream tokens)
- `WS /ws/chat` (send `{model, messages, options}`)


### Notes

- Endpoints used: `/api/tags`, `/api/pull`, `/api/delete`, `/api/chat`.
- Config: `%APPDATA%/OllamaGUI/config.json`.


