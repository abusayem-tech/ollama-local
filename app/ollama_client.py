import json
import os
import threading
from typing import Any, Dict, Generator, Iterable, List, Optional

import requests


def get_app_config_dir() -> str:
    appdata = os.getenv("APPDATA") or os.path.expanduser("~/.config")
    path = os.path.join(appdata, "OllamaGUI")
    os.makedirs(path, exist_ok=True)
    return path


def get_config_path() -> str:
    return os.path.join(get_app_config_dir(), "config.json")


def load_config() -> Dict[str, Any]:
    config_path = get_config_path()
    if os.path.exists(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_config(config: Dict[str, Any]) -> None:
    config_path = get_config_path()
    try:
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2)
    except Exception:
        pass


class OllamaClient:
    def __init__(self, host: str = "127.0.0.1", port: int = 11434, timeout: int = 60) -> None:
        self._host = host
        self._port = port
        self._timeout = timeout
        self._session = requests.Session()
        self._lock = threading.Lock()

    @property
    def base_url(self) -> str:
        return f"http://{self._host}:{self._port}"

    def configure(self, host: str, port: int) -> None:
        with self._lock:
            self._host = host
            self._port = port

    # Models
    def list_models(self) -> List[Dict[str, Any]]:
        url = f"{self.base_url}/api/tags"
        resp = self._session.get(url, timeout=self._timeout)
        resp.raise_for_status()
        data = resp.json()
        return data.get("models", [])

    def version(self) -> Dict[str, Any]:
        url = f"{self.base_url}/api/version"
        resp = self._session.get(url, timeout=self._timeout)
        resp.raise_for_status()
        return resp.json()

    def pull_model(
        self,
        name: str,
        stream: bool = True,
        stop_event: Optional[threading.Event] = None,
    ) -> Iterable[Dict[str, Any]]:
        url = f"{self.base_url}/api/pull"
        payload = {"name": name, "stream": stream}
        headers = {"Content-Type": "application/json"}
        resp = self._session.post(url, headers=headers, data=json.dumps(payload), stream=stream, timeout=None)
        resp.raise_for_status()
        if stream:
            for line in resp.iter_lines(decode_unicode=True):
                if stop_event is not None and stop_event.is_set():
                    break
                if not line:
                    continue
                try:
                    yield json.loads(line)
                except Exception:
                    yield {"status": "message", "detail": line}
        else:
            yield resp.json()
        try:
            resp.close()
        except Exception:
            pass

    def delete_model(self, name: str) -> Dict[str, Any]:
        # Ollama currently uses POST /api/delete with JSON body {"name": "model"}
        url = f"{self.base_url}/api/delete"
        payload = {"name": name}
        headers = {"Content-Type": "application/json"}
        resp = self._session.post(url, headers=headers, data=json.dumps(payload), timeout=self._timeout)
        resp.raise_for_status()
        return resp.json()

    # Chat
    def chat_stream(
        self,
        model: str,
        messages: List[Dict[str, str]],
        options: Optional[Dict[str, Any]] = None,
        stop_event: Optional[threading.Event] = None,
    ) -> Generator[Dict[str, Any], None, None]:
        url = f"{self.base_url}/api/chat"
        payload: Dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": True,
        }
        if options:
            payload["options"] = options
        headers = {"Content-Type": "application/json"}
        resp = self._session.post(url, headers=headers, data=json.dumps(payload), stream=True, timeout=None)
        resp.raise_for_status()
        for line in resp.iter_lines(decode_unicode=True):
            if stop_event is not None and stop_event.is_set():
                break
            if not line:
                continue
            try:
                yield json.loads(line)
            except Exception:
                yield {"status": "message", "detail": line}
        try:
            resp.close()
        except Exception:
            pass


