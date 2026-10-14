"""Multi-turn chat with the pipeline in the terminal (gate M3).

    uv run scripts/chat_cli.py [--preset S|B0|B1|S-QU|...] [--session <uuid>]

Prints the understood constraints, the Recipe cards, the streamed answer and the latency of each stage.
Commands: /reset (a new session), /state (the constraints in force), /trace (last turn's trace), /quit.
Every turn is stored (chat_message, session_constraint, retrieval_trace), so a session can be reviewed later.
"""

import argparse
import json
import sys
import uuid
from pathlib import Path

import httpx
import psycopg

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from api import config  # noqa: E402
from api.pipeline.flags import preset  # noqa: E402
from api.pipeline.orchestrator import Assistant  # noqa: E402


def show_constraints(d: dict) -> None:
    c = {k: v for k, v in d["constraints"].items() if v}
    print(f"  [{d['intent']} -> {d['route']}] constraints: {json.dumps(c, ensure_ascii=False) or '{}'}")
    for n in d["notices"]:
        print(f"  notice: {n}")


def show_recipes(rows: list[dict]) -> None:
    for i, r in enumerate(rows, 1):
        may = f" may:{','.join(r['allergens_may'])}" if r["allergens_may"] else ""
        print(f"  {i}. [R{r['id']}] {r['title']} | {r['total_minutes'] or '?'} min | "
              f"{','.join(r['allergens']) or '-'}{may} | {r['score']}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--preset", default="S")
    ap.add_argument("--session", help="continue a stored session")
    args = ap.parse_args()
    flags = preset(args.preset)
    sys.stdout.reconfigure(encoding="utf-8")
    scorer = None
    if flags.rerank:
        print("loading reranker...", flush=True)
        from api.rerank import Reranker
        scorer = Reranker().score
    with psycopg.connect(config.DATABASE_URL) as conn, httpx.Client(timeout=900) as client:
        bot = Assistant(conn, client, scorer)
        sid = uuid.UUID(args.session) if args.session else bot.new_session(args.preset)
        print(f"session {sid}, preset {args.preset}. /reset /state /trace /quit")
        last_reply = None
        while True:
            try:
                msg = input("\nyou> ").strip()
            except (EOFError, KeyboardInterrupt):
                break
            if not msg:
                continue
            if msg == "/quit":
                break
            if msg == "/reset":
                sid = bot.new_session(args.preset)
                print(f"new session {sid}")
                continue
            if msg == "/state":
                for it in bot.state(sid).items:
                    print(f"  {it.type}={it.value} ({it.scope})")
                continue
            if msg == "/trace":
                for stage, payload, ms in conn.execute("SELECT stage, payload, latency_ms FROM retrieval_trace "
                                                       "WHERE message_id = %s ORDER BY id", [last_reply]):
                    print(f"  {stage} {ms:.0f} ms {json.dumps(payload, ensure_ascii=False)[:400]}")
                continue
            streamed = []
            for ev in bot.run_turn(sid, msg, flags):
                if ev.type == "constraints":
                    show_constraints(ev.data)
                elif ev.type == "recipes":
                    show_recipes(ev.data)
                elif ev.type == "token":
                    if not streamed:
                        print("bot> ", end="")
                    streamed.append(ev.data)
                    print(ev.data, end="", flush=True)
                elif ev.type == "done":
                    d = ev.data
                    last_reply = d["message_id"]
                    if d["regenerated"]:
                        print(f"\n  [M7 rewrote the answer, removed {d['removed']}]\nbot> {d['answer']}", end="")
                    print(f"\n  citations {d['citations']} verified={d['verified']} | "
                          + " ".join(f"{k}={v / 1000:.1f}s" for k, v in d["latency_ms"].items()))


if __name__ == "__main__":
    main()
