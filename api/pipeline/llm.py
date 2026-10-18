"""Ollama calls for the pipeline: structured output (JSON schema) cached by input hash, and streamed text.

CLAUDE.md: structured output via Ollama's `format`, cache by input hash, fixed seed. The cache holds only
JSON calls (M1); generation is streamed and not cached, since the UI shows it live.
"""

import hashlib
import json
import os
import threading
from collections.abc import Iterator
from pathlib import Path

import httpx

from .. import config

# LLM_CACHE_FILE: another cache file, e.g. an empty one to time cold calls without touching the shared cache
CACHE = Path(os.environ.get("LLM_CACHE_FILE") or Path(__file__).resolve().parents[2] / "data" / "cache" / "llm.jsonl")
_lock = threading.Lock()
_cache: dict[str, dict] | None = None


class LLMError(RuntimeError):
    pass


class PromptTooLong(RuntimeError):
    """Ollama keeps at most half of num_ctx for the prompt and drops its START (the system prompt, the rules)
    without an error (found in MV4c: a 178k-token prompt cut to 4,098). Not an LLMError: retrying cannot help and
    callers must not swallow it."""


GEN_CTX = 8192
CHARS_PER_TOKEN_MAX = 4  # an English-ish upper bound: chars/4 never overestimates the tokens of this data
TRUNCATION_SLACK = 64  # Ollama may reuse a few cached prompt tokens and leave them out of prompt_eval_count


def check_fits(messages: list[dict], num_ctx: int) -> None:
    """Before a call: refuse a prompt that is surely over half of num_ctx (chars/4 underestimates the tokens)."""
    chars = sum(len(m.get("content", "")) for m in messages)
    if chars / CHARS_PER_TOKEN_MAX > num_ctx // 2:
        raise PromptTooLong(f"prompt of {chars} characters cannot fit half of num_ctx={num_ctx}")


def check_not_cut(prompt_tokens: int | None, num_ctx: int) -> None:
    """After a call: Ollama read num_ctx/2 tokens, so it cut the prompt."""
    if prompt_tokens and prompt_tokens >= num_ctx // 2 - TRUNCATION_SLACK:
        raise PromptTooLong(f"Ollama read {prompt_tokens} prompt tokens with num_ctx={num_ctx}: the prompt was cut")


def _load() -> dict[str, dict]:
    global _cache
    if _cache is None:
        _cache = {}
        if CACHE.exists():
            for line in CACHE.read_text(encoding="utf-8").splitlines():
                row = json.loads(line)
                _cache[row["key"]] = row["out"]
    return _cache


NUM_CTX = 4096


def cache_key(model: str, schema: dict, messages: list[dict], temperature: float, num_ctx: int = NUM_CTX) -> str:
    """num_ctx enters the key only when it is not the default, so keys written before it existed still match."""
    parts = [model, schema, messages, temperature, config.SEED] + ([num_ctx] if num_ctx != NUM_CTX else [])
    return hashlib.sha256(json.dumps(parts, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def chat_json(client: httpx.Client, schema: dict, messages: list[dict], model: str = config.QU_MODEL,
              temperature: float = config.QU_TEMPERATURE, use_cache: bool = True, num_ctx: int = NUM_CTX) -> dict:
    """One structured-output call; the parsed JSON object. Raises LLMError on a reply that is not JSON."""
    k = cache_key(model, schema, messages, temperature, num_ctx)
    if use_cache and k in _load():
        return _load()[k]
    check_fits(messages, num_ctx)
    r = client.post(f"{config.OLLAMA_URL}/api/chat", json={
        "model": model, "stream": False, "format": schema, "messages": messages,
        "options": {"temperature": temperature, "seed": config.SEED, "num_ctx": num_ctx}}, timeout=600)
    r.raise_for_status()
    check_not_cut(r.json().get("prompt_eval_count"), num_ctx)
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
                temperature: float = config.GEN_TEMPERATURE, usage: dict | None = None,
                num_ctx: int = GEN_CTX) -> Iterator[str]:
    """Answer tokens as they come. `usage` (if given) receives prompt/completion token counts at the end.
    A cut prompt raises PromptTooLong at the end of the stream (Ollama tells the count only then)."""
    check_fits(messages, num_ctx)
    with client.stream("POST", f"{config.OLLAMA_URL}/api/chat", json={
            "model": model, "stream": True, "messages": messages,
            "options": {"temperature": temperature, "seed": config.SEED, "num_ctx": num_ctx}}, timeout=900) as r:
        r.raise_for_status()
        for line in r.iter_lines():
            if not line:
                continue
            chunk = json.loads(line)
            piece = chunk.get("message", {}).get("content", "")
            if piece:
                yield piece
            if chunk.get("done"):
                if usage is not None:
                    usage["prompt_tokens"] = chunk.get("prompt_eval_count", 0)
                    usage["completion_tokens"] = chunk.get("eval_count", 0)
                check_not_cut(chunk.get("prompt_eval_count"), num_ctx)
