import asyncio
import json
import os
from typing import Any, AsyncGenerator, Dict, List, Optional

from fastapi import Depends, FastAPI, Header, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse

from app.ollama_client import OllamaClient


API_KEY = os.getenv("API_KEY") or ""
ALLOW_ORIGINS = [o.strip() for o in (os.getenv("ALLOW_ORIGINS") or "*").split(",") if o.strip()]
HOST = os.getenv("SERVER_HOST") or "0.0.0.0"
PORT = int(os.getenv("SERVER_PORT") or 8080)
OLLAMA_HOST = os.getenv("OLLAMA_HOST") or "127.0.0.1"
OLLAMA_PORT = int(os.getenv("OLLAMA_PORT") or 11434)


def require_api_key(x_api_key: Optional[str] = Header(default=None)) -> None:
    if API_KEY:
        if not x_api_key or x_api_key != API_KEY:
            raise HTTPException(status_code=401, detail="invalid api key")


client = OllamaClient(OLLAMA_HOST, OLLAMA_PORT)
app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOW_ORIGINS if ALLOW_ORIGINS != ["*"] else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)


@app.get("/health")
def health(_: None = Depends(require_api_key)) -> Dict[str, Any]:
    try:
        ver = client.version()
        return {"ok": True, "version": ver.get("version", "")}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@app.get("/models")
def list_models(_: None = Depends(require_api_key)) -> Dict[str, Any]:
    return {"models": client.list_models()}


@app.post("/pull")
def pull_model(body: Dict[str, Any], _: None = Depends(require_api_key)) -> StreamingResponse:
    name = body.get("name", "")
    if not name:
        raise HTTPException(status_code=400, detail="name is required")

    def gen():
        try:
            for ev in client.pull_model(name, stream=True):
                yield json.dumps(ev) + "\n"
        except Exception as e:
            yield json.dumps({"error": str(e)}) + "\n"

    return StreamingResponse(gen(), media_type="application/x-ndjson")


@app.post("/delete")
def delete_model(body: Dict[str, Any], _: None = Depends(require_api_key)) -> Dict[str, Any]:
    name = body.get("name", "")
    if not name:
        raise HTTPException(status_code=400, detail="name is required")
    return client.delete_model(name)


@app.post("/chat")
def chat(body: Dict[str, Any], _: None = Depends(require_api_key)) -> Dict[str, Any]:
    model = body.get("model", "")
    messages = body.get("messages", [])
    options = body.get("options")
    if not model or not isinstance(messages, list):
        raise HTTPException(status_code=400, detail="model and messages required")
    # Aggregate non-stream response by concatenating content pieces
    assistant: str = ""
    for ev in client.chat_stream(model, messages, options):
        msg = ev.get("message") or {}
        content = msg.get("content", "")
        if content:
            assistant += content
    return {"message": assistant}


@app.post("/chat_stream")
def chat_stream(body: Dict[str, Any], _: None = Depends(require_api_key)) -> StreamingResponse:
    model = body.get("model", "")
    messages = body.get("messages", [])
    options = body.get("options")
    if not model or not isinstance(messages, list):
        raise HTTPException(status_code=400, detail="model and messages required")

    def gen():
        try:
            for ev in client.chat_stream(model, messages, options):
                msg = ev.get("message") or {}
                content = msg.get("content", "")
                if content:
                    yield json.dumps({"token": content}) + "\n"
        except Exception as e:
            yield json.dumps({"error": str(e)}) + "\n"
        finally:
            yield json.dumps({"done": True}) + "\n"

    return StreamingResponse(gen(), media_type="application/x-ndjson")


@app.websocket("/ws/chat")
async def ws_chat(websocket: WebSocket):
    # Simple header auth for WS
    if API_KEY:
        if websocket.headers.get("x-api-key") != API_KEY:
            await websocket.close(code=4401)
            return
    await websocket.accept()
    try:
        data = await websocket.receive_text()
        req = json.loads(data)
        model: str = req.get("model", "")
        messages: List[Dict[str, str]] = req.get("messages", [])
        options = req.get("options")
        if not model or not isinstance(messages, list):
            await websocket.send_text(json.dumps({"error": "model and messages required"}))
            await websocket.close()
            return
        loop = asyncio.get_running_loop()

        def iter_events():
            for ev in client.chat_stream(model, messages, options):
                msg = ev.get("message") or {}
                content = msg.get("content", "")
                if content:
                    yield content

        for token in await loop.run_in_executor(None, lambda: list(iter_events())):
            await websocket.send_text(json.dumps({"token": token}))
        await websocket.send_text(json.dumps({"done": True}))
    except WebSocketDisconnect:
        return
    except Exception as e:
        try:
            await websocket.send_text(json.dumps({"error": str(e)}))
        finally:
            await websocket.close()


def run() -> None:
    import uvicorn
    uvicorn.run(app, host=HOST, port=PORT)


if __name__ == "__main__":
    run()


