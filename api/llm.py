"""Chat with the local Ollama model. Used to write /recommend's explanation; never to decide a Filter."""

import httpx

from . import config


class LLMError(RuntimeError):
    pass


def chat(client: httpx.Client, messages: list[dict], *, model: str | None = None, json_mode: bool = False,
         temperature: float = 0.0, timeout: float | None = None, attempts: int = 2) -> str:
    """One non-streaming chat completion; returns the reply text.

    Retries once on a network error or a 5xx; a 4xx (unknown model, bad request) fails at once.
    Raises LLMError with a readable message otherwise.
    """
    body = {"model": model or config.LLM_MODEL, "messages": messages, "stream": False,
            "options": {"temperature": temperature}}
    if json_mode:
        body["format"] = "json"
    problem = "no attempt made"
    for _ in range(max(1, attempts)):
        try:
            r = client.post(f"{config.OLLAMA_URL}/api/chat", json=body, timeout=timeout or config.LLM_TIMEOUT)
            r.raise_for_status()
            content = r.json()["message"]["content"]
        except httpx.HTTPStatusError as e:
            problem = f"Ollama answered HTTP {e.response.status_code}: {e.response.text[:200]}"
            if e.response.status_code < 500:
                break
            continue
        except httpx.HTTPError as e:
            problem = f"Ollama is not reachable ({type(e).__name__}): {e}"
            continue
        except (KeyError, ValueError):
            problem = "Ollama sent a reply this client cannot read"
            continue
        if content.strip():
            return content
        problem = "the model returned an empty reply"
    raise LLMError(problem)
