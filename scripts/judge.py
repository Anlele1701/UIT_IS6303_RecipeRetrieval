"""M6 judge: llama3.1:8b (another family than the generator qwen2.5:7b), structured output, temperature 0, seed 42,
cached with every LLM call (data/cache/llm.jsonl, keyed by model and prompt). Build plan 7.2 and sườn báo cáo 4.4.

    relevance(client, query, recipe)     0 / 1 / 2 (rubric 7.2: constraints are NOT part of it, the checker scores them)
    faithful(client, context, answer)     does every claim of the answer come from the context recipes?
    answers_question(client, q, answer)  0 / 1 / 2: does the answer address the question?
    refuses(client, q, answer)           does the answer decline or say nothing was found?

Human check (scripts/human_check.py) measures it against Thy: Cohen's kappa in the M6 report.
"""

import httpx

from api.pipeline.llm import LLMError, chat_json

JUDGE_MODEL = "llama3.1:8b"
JUDGE_CTX = 8192
JUDGE_MAX_TOKENS = 512  # a judge reply is a score or a short list; the cap stops a looping one (M6b)

REL = ("You judge how relevant a recipe is to a cooking request.\n"
       "2: the right kind of dish or need, matching the request's main point.\n"
       "1: partly relevant: the main idea fits but a secondary detail does not.\n"
       "0: not relevant.\n"
       "Ignore allergies, diets, excluded ingredients and time limits: they are checked separately. Answer with JSON only.")
FAITH = ("You check an assistant's answer against the RECIPES it was given. faithful is true when every factual claim "
         "about a dish (its ingredients, time, allergens, steps) is supported by those recipes, or the answer makes no "
         "such claim. General advice ('check the labels') is fine. List any unsupported claim. Answer with JSON only.")
ANSWERS = ("You judge whether an answer addresses the user's question. 2: it answers it directly; 1: partly; "
           "0: it does not (off topic, or only generic text). Answer with JSON only.")
REFUSES = ("You read a cooking assistant's answer. refuses is true when the answer declines the request, says it can "
           "only help with recipes, or says no fitting recipe was found; false when it suggests or explains a recipe. "
           "Answer with JSON only.")

S_REL = {"type": "object", "required": ["score"], "properties": {"score": {"type": "integer", "enum": [0, 1, 2]}}}
S_FAITH = {"type": "object", "required": ["faithful", "unsupported"],
           "properties": {"faithful": {"type": "boolean"}, "unsupported": {"type": "array", "items": {"type": "string"}}}}
S_REFUSE = {"type": "object", "required": ["refuses"], "properties": {"refuses": {"type": "boolean"}}}


def recipe_text(title: str, summary: str, lines: list[str]) -> str:
    return f"Title: {title}\nDescription: {summary[:400]}\nIngredients: " + "; ".join(lines[:40])


def _ask(client: httpx.Client, schema: dict, system: str, user: str) -> dict | None:
    msgs = [{"role": "system", "content": system}, {"role": "user", "content": user}]
    for _ in range(2):
        try:
            return chat_json(client, schema, msgs, model=JUDGE_MODEL, temperature=0.0, num_ctx=JUDGE_CTX,
                             num_predict=JUDGE_MAX_TOKENS)
        except (LLMError, httpx.HTTPError):
            continue
    return None  # counted as missing, never as a score


def relevance(client, query: str, recipe: str) -> int | None:
    out = _ask(client, S_REL, REL, f"REQUEST: {query}\n\nRECIPE:\n{recipe}")
    return None if out is None else int(out["score"])


def faithful(client, context: str, answer: str) -> bool | None:
    out = _ask(client, S_FAITH, FAITH, f"RECIPES:\n{context}\n\nANSWER:\n{answer}")
    return None if out is None else bool(out["faithful"])


def answers_question(client, question: str, answer: str) -> int | None:
    out = _ask(client, S_REL, ANSWERS, f"QUESTION: {question}\n\nANSWER:\n{answer}")
    return None if out is None else int(out["score"])


def refuses(client, question: str, answer: str) -> bool | None:
    out = _ask(client, S_REFUSE, REFUSES, f"QUESTION: {question}\n\nANSWER:\n{answer}")
    return None if out is None else bool(out["refuses"])
