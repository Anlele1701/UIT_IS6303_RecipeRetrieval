"""Ollama calls for the pipeline: structured output (JSON schema) cached by input hash, and streamed text.

CLAUDE.md: structured output via Ollama's `format`, cache by input hash, fixed seed. The cache holds only
JSON calls (M1); generation is streamed and not cached, since the UI shows it live.
"""

import hashlib
import json
import threading
from collections.abc import Iterator
from pathlib import Path

import httpx

from .. import config

CACHE = Path(__file__).resolve().parents[2] / "data" / "cache" / "llm.jsonl"
_lock = threading.Lock()
_cache: dict[str, dict] | None = None


class LLMError(RuntimeError):
    pass


def _load() -> dict[str, dict]:
    global _cache
    if _cache is None:
        _cache = {}
        if CACHE.exists():
            for line in CACHE.read_text(encoding="utf-8").splitlines():
                row = json.loads(line)
                _cache[row["key"]] = row["out"]
    return _cache


def cache_key(model: str, schema: dict, messages: list[dict], temperature: float) -> str:
    return hashlib.sha256(json.dumps([model, schema, messages, temperature, config.SEED],
                                     ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def chat_json(client: httpx.Client, schema: dict, messages: list[dict], model: str = config.QU_MODEL,
              temperature: float = config.QU_TEMPERATURE, use_cache: bool = True) -> dict:
    """One structured-output call; the parsed JSON object. Raises LLMError on a reply that is not JSON."""
    k = cache_key(model, schema, messages, temperature)
    if use_cache and k in _load():
        return _load()[k]
    r = client.post(f"{config.OLLAMA_URL}/api/chat", json={
        "model": model, "stream": False, "format": schema, "messages": messages,
        "options": {"temperature": temperature, "seed": config.SEED, "num_ctx": 4096}}, timeout=600)
    r.raise_for_status()
    try:
        out = json.loads(r.json()["message"]["content"])
    except (json.JSONDecodeError, KeyError) as e:
        raise LLMError(f"not JSON: {e}") from e
    if use_cache:
        with _lock:
            CACHE.parent.mkdir(parents=True, exist_ok=True)
            with open(CACHE, "a", encoding="utf-8") as f:
                f.write(json.dumps({"key": k, "model": model, "out": out}, ensure_ascii=False) + "\n")
            _load()[k] = out
    return out


def chat_stream(client: httpx.Client, messages: list[dict], model: str = config.GEN_MODEL,
                temperature: float = config.GEN_TEMPERATURE, usage: dict | None = None) -> Iterator[str]:
    """Answer tokens as they come. `usage` (if given) receives prompt/completion token counts at the end."""
    with client.stream("POST", f"{config.OLLAMA_URL}/api/chat", json={
            "model": model, "stream": True, "messages": messages,
            "options": {"temperature": temperature, "seed": config.SEED, "num_ctx": 8192}}, timeout=900) as r:
        r.raise_for_status()
        for line in r.iter_lines():
            if not line:
                continue
            chunk = json.loads(line)
            piece = chunk.get("message", {}).get("content", "")
            if piece:
                yield piece
            if chunk.get("done") and usage is not None:
                usage["prompt_tokens"] = chunk.get("prompt_eval_count", 0)
                usage["completion_tokens"] = chunk.get("eval_count", 0)
