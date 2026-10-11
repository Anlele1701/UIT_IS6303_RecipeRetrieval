"""Build-machine check for A3 (M0 step 1). Writes eval/env.json and docs/env.md; nothing is typed by hand.

    uv run scripts/check_env.py            # hardware, Docker, Ollama, tools, bind-mount test
    uv run scripts/check_env.py --bench    # also time embedding, the two LLMs and the reranker

The benchmarks need Ollama with the models pulled. The embedding estimate is sharper once
`ingest.py load` has run, since it then counts the real sentences and Chunks to embed.
"""

import argparse
import json
import os
import platform
import shutil
import socket
import statistics
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import httpx  # noqa: E402

from api import config  # noqa: E402

OUT_JSON = ROOT / "eval" / "env.json"
OUT_MD = ROOT / "docs" / "env.md"
A1_VOLUME = "is603_recipe-pgdata"
A3_VOLUME = "is603a3_a3-pgdata"
A3_PORT = 5435
MODELS = {"embed": config.EMBED_MODEL, "generate": "qwen2.5:7b", "judge": "llama3.1:8b"}
# Semantic strategy in A1 (eval/pooled/20261006-224100/corpus.json): summary + ingredients + step Chunks.
A1_SEMANTIC_CHUNKS = 32719 + 32719 + 101000
EMBED_SAMPLE = 256
SEED = 42


def sh(*cmd: str, timeout: int = 60) -> tuple[int, str]:
    """Run a command; (exit code, stdout+stderr). A missing program is exit code 127."""
    if shutil.which(cmd[0]) is None:
        return 127, f"{cmd[0]}: not found"
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout)
    except subprocess.TimeoutExpired:
        return 124, "timeout"
    return p.returncode, (p.stdout + p.stderr).strip()


def ps(expr: str):
    """A PowerShell expression converted to JSON (Windows only)."""
    code, out = sh("powershell", "-NoProfile", "-Command", f"{expr} | ConvertTo-Json -Compress")
    return json.loads(out) if code == 0 and out else None


def hardware() -> dict:
    hw = {"os": platform.platform(), "machine": platform.machine(), "logical_cpus": os.cpu_count()}
    if sys.platform == "win32":
        cs = ps("Get-CimInstance Win32_ComputerSystem | Select TotalPhysicalMemory")
        cpu = ps("Get-CimInstance Win32_Processor | Select Name,NumberOfCores")
        gpu = ps("Get-CimInstance Win32_VideoController | Select Name,DriverVersion")
        hw["ram_gb"] = round(cs["TotalPhysicalMemory"] / 2**30, 1) if cs else None
        cpu = cpu[0] if isinstance(cpu, list) else cpu
        hw["cpu"] = cpu and cpu["Name"].strip()
        hw["cores"] = cpu and cpu["NumberOfCores"]
        hw["gpus"] = [g if isinstance(g, dict) else {} for g in (gpu if isinstance(gpu, list) else [gpu])] if gpu else []
    du = shutil.disk_usage(ROOT)
    hw["disk_free_gb"] = round(du.free / 2**30, 1)
    hw["nvidia_smi"] = sh("nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader")[1]
    return hw


def port_free(port: int) -> bool:
    with socket.socket() as s:
        return s.connect_ex(("127.0.0.1", port)) != 0


def docker() -> dict:
    d = {"version": sh("docker", "--version")[1], "compose": sh("docker", "compose", "version")[1]}
    code, out = sh("docker", "info", "--format", "{{json .}}")
    if code == 0:
        info = json.loads(out)
        d.update(server_version=info.get("ServerVersion"), os=info.get("OperatingSystem"),
                 kernel=info.get("KernelVersion"), ncpu=info.get("NCPU"),
                 mem_gb=round(info.get("MemTotal", 0) / 2**30, 1))
    else:
        d["error"] = out
    volumes = sh("docker", "volume", "ls", "--format", "{{.Name}}")[1].split()
    d["a1_volume_present"] = A1_VOLUME in volumes
    d["a3_volume_present"] = A3_VOLUME in volumes
    running = sh("docker", "ps", "--format", "{{.Names}}")[1].split()
    d["a3_container_running"] = "a3-paradedb" in running
    d["port_5435_free"] = port_free(A3_PORT) or d["a3_container_running"]
    # The repo path has spaces and Vietnamese letters; check Docker Desktop can bind-mount it.
    code, out = sh("docker", "run", "--rm", "-v", f"{ROOT / 'sql'}:/m:ro", "alpine:3.20", "ls", "/m", timeout=180)
    d["bind_mount_ok"] = code == 0 and "schema.sql" in out
    d["bind_mount_output"] = out[-300:]
    return d


def ollama() -> dict:
    o = {"cli": sh("ollama", "--version")[1], "url": config.OLLAMA_URL}
    try:
        with httpx.Client(timeout=5) as c:
            o["version"] = c.get(f"{config.OLLAMA_URL}/api/version").json().get("version")
            o["models"] = sorted(m["name"] for m in c.get(f"{config.OLLAMA_URL}/api/tags").json()["models"])
            o["loaded"] = [{"name": m["name"], "size_vram": m.get("size_vram"), "size": m.get("size")}
                           for m in c.get(f"{config.OLLAMA_URL}/api/ps").json().get("models", [])]
    except httpx.HTTPError as e:
        o["error"] = f"not reachable: {e.__class__.__name__}"
    have = set(o.get("models", []))
    o["missing"] = [m for m in MODELS.values() if m not in have and f"{m}:latest" not in have]
    return o


def tools() -> dict:
    return {
        "python": platform.python_version(),
        "uv": sh("uv", "--version")[1],
        "node": sh("node", "--version")[1],
        "git": sh("git", "--version")[1],
        "git_autocrlf": sh("git", "config", "--get", "core.autocrlf")[1] or None,
        "pythonutf8": os.environ.get("PYTHONUTF8"),
        "repo_path": str(ROOT),
        "path_has_space_or_non_ascii": " " in str(ROOT) or not str(ROOT).isascii(),
    }


# ---------------------------------------------------------------------------
# Benchmarks
# ---------------------------------------------------------------------------

def sample_texts() -> tuple[list[str], dict]:
    """Chunk-like texts to embed and, when the DB is loaded, how many texts `chunk semantic` embeds."""
    import psycopg

    import ingest
    try:
        with psycopg.connect(config.DATABASE_URL, connect_timeout=3) as conn:
            n = conn.execute("SELECT count(*) FROM recipe").fetchone()[0]
            if n == 0:
                raise psycopg.OperationalError("no recipes loaded")
            conn.execute("SELECT setseed(%s)", [SEED / 100])
            texts = [f"search_document: {t}\n{d}" for t, d in conn.execute(
                "SELECT title, description FROM recipe ORDER BY random() LIMIT %s", [EMBED_SAMPLE])]
            sentences = sum(len(ingest.split_sentences(ingest.normalize_fractions(d)))
                            for (d,) in conn.execute("SELECT directions FROM recipe"))
            # semantic_cut embeds every sentence, then every Chunk is embedded once more
            return texts, {"recipes": n, "sentences": sentences, "chunks_a1": A1_SEMANTIC_CHUNKS,
                           "texts_to_embed": sentences + A1_SEMANTIC_CHUNKS, "source": "database"}
    except psycopg.OperationalError:
        base = ("search_document: Creamy garlic chicken pasta\nCook the pasta, then toss with a sauce of "
                "butter, garlic, cream and parmesan until glossy; season and serve hot.")
        # ~3 sentences per sentence-strategy Chunk in A1 (110,314 Chunks) as a stand-in for the count
        return [f"{base} ({i})" for i in range(EMBED_SAMPLE)], {
            "chunks_a1": A1_SEMANTIC_CHUNKS, "sentences": 3 * 110314,
            "texts_to_embed": 3 * 110314 + A1_SEMANTIC_CHUNKS, "source": "estimate (DB not loaded)"}


def bench_embed(c: httpx.Client) -> dict:
    texts, counts = sample_texts()
    c.post(f"{config.OLLAMA_URL}/api/embed", json={"model": MODELS["embed"], "input": texts[:8]})  # load model
    started = time.perf_counter()
    r = c.post(f"{config.OLLAMA_URL}/api/embed", json={"model": MODELS["embed"], "input": texts})
    r.raise_for_status()
    secs = time.perf_counter() - started
    rate = len(texts) / secs
    return {"texts": len(texts), "seconds": round(secs, 2), "texts_per_s": round(rate, 1), **counts,
            "estimated_hours_chunk_semantic": round(counts["texts_to_embed"] / rate / 3600, 2)}


def bench_llm(c: httpx.Client, model: str) -> dict:
    prompt = "List five quick vegetarian dinner ideas, one line each."
    runs = []
    for i in range(3):  # first run includes loading the model
        r = c.post(f"{config.OLLAMA_URL}/api/generate", json={
            "model": model, "prompt": prompt, "stream": False,
            "options": {"seed": SEED, "temperature": 0, "num_predict": 128}})
        r.raise_for_status()
        j = r.json()
        runs.append({"load_s": j.get("load_duration", 0) / 1e9,
                     "prompt_tok_per_s": j["prompt_eval_count"] / (j["prompt_eval_duration"] / 1e9)
                     if j.get("prompt_eval_duration") else None,
                     "gen_tok_per_s": j["eval_count"] / (j["eval_duration"] / 1e9),
                     "ttft_s": (j.get("load_duration", 0) + j.get("prompt_eval_duration", 0)) / 1e9,
                     "total_s": j["total_duration"] / 1e9})
    warm = runs[1:]
    with httpx.Client(timeout=5) as q:
        loaded = q.get(f"{config.OLLAMA_URL}/api/ps").json().get("models", [])
    placement = next(({"size": m.get("size"), "size_vram": m.get("size_vram")} for m in loaded
                      if m["name"].startswith(model)), {})
    return {"cold_load_s": round(runs[0]["load_s"], 2),
            "gen_tok_per_s": round(statistics.median(r["gen_tok_per_s"] for r in warm), 1),
            "ttft_warm_s": round(statistics.median(r["ttft_s"] for r in warm), 2),
            "total_128_tokens_s": round(statistics.median(r["total_s"] for r in warm), 2), **placement}


def bench_rerank() -> dict:
    from api.rerank import Reranker
    started = time.perf_counter()
    rr = Reranker()
    load = time.perf_counter() - started
    texts = [f"Recipe {i}\nMix flour, sugar and butter; bake at 350 F for {20 + i} minutes until golden."
             for i in range(config.RERANK_TOP)]
    rr.score("easy butter cookies", texts)  # warm-up
    times = []
    for _ in range(3):
        started = time.perf_counter()
        rr.score("easy butter cookies", texts)
        times.append((time.perf_counter() - started) * 1000)
    return {"model": config.RERANK_MODEL, "device": rr.device, "load_s": round(load, 1),
            "pairs": len(texts), "p50_ms": round(statistics.median(times), 1)}


def benchmarks(o: dict) -> dict:
    b: dict = {}
    if "error" in o:
        b["skipped"] = "Ollama not reachable"
    else:
        with httpx.Client(timeout=900) as c:
            if MODELS["embed"] not in o["missing"]:
                b["embed"] = bench_embed(c)
            for role in ("generate", "judge"):
                if MODELS[role] not in o["missing"]:
                    b[role] = {"model": MODELS[role], **bench_llm(c, MODELS[role])}
    b["rerank"] = bench_rerank()
    return b


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

def yes(v) -> str:
    return "có" if v else "không"


def render(env: dict) -> str:
    hw, d, o, t, b = env["hardware"], env["docker"], env["ollama"], env["tools"], env.get("bench", {})
    gpus = ", ".join(f"{g.get('Name')} (driver {g.get('DriverVersion')})" for g in hw.get("gpus", [])) or "?"
    lines = [
        "# Môi trường máy build",
        "",
        f"Sinh tự động bởi `scripts/check_env.py` lúc {env['checked_at']}. Số liệu gốc: `eval/env.json`. "
        "Không sửa tay file này.",
        "",
        "## Phần cứng",
        "",
        "| Mục | Giá trị |", "|---|---|",
        f"| Hệ điều hành | {hw['os']} |",
        f"| CPU | {hw.get('cpu')} ({hw.get('cores')} nhân, {hw['logical_cpus']} luồng) |",
        f"| RAM | {hw.get('ram_gb')} GB |",
        f"| GPU | {gpus} |",
        f"| GPU NVIDIA (`nvidia-smi`) | {'không có' if 'not found' in hw['nvidia_smi'] else hw['nvidia_smi']} |",
        f"| Ổ đĩa trống (ổ chứa repo) | {hw['disk_free_gb']} GB |",
        "",
        "## Docker",
        "",
        "| Mục | Giá trị |", "|---|---|",
        f"| Phiên bản | {d['version']} · {d['compose']} |",
        f"| Engine | {d.get('server_version')} trên {d.get('os')} (kernel {d.get('kernel')}) |",
        f"| Tài nguyên cấp cho Docker | {d.get('ncpu')} CPU, {d.get('mem_gb')} GB RAM |",
        f"| Volume A1 `{A1_VOLUME}` có trên máy | {yes(d['a1_volume_present'])} (A3 không bao giờ dùng) |",
        f"| Volume A3 `{A3_VOLUME}` | {yes(d['a3_volume_present'])} |",
        f"| Container `a3-paradedb` đang chạy | {yes(d['a3_container_running'])} |",
        f"| Port {A3_PORT} dùng được | {yes(d['port_5435_free'])} |",
        f"| Bind mount đường dẫn có dấu cách và tiếng Việt | {'được' if d['bind_mount_ok'] else 'LỖI'} |",
        "",
    ]
    if d.get("mem_gb") is not None and d["mem_gb"] < 8:
        lines += ["> ⚠️ Docker được cấp dưới 8 GB RAM, build index ParadeDB có thể chậm hoặc lỗi.", ""]
    lines += [
        "## Ollama",
        "",
        "| Mục | Giá trị |", "|---|---|",
        f"| CLI | {o['cli']} |",
        f"| Server | {o.get('version') or o.get('error')} ({o['url']}) |",
        f"| Model đã có | {', '.join(o.get('models', [])) or '–'} |",
        f"| Model còn thiếu | {', '.join(o['missing']) or 'không'} |",
        "",
        "## Công cụ",
        "",
        "| Mục | Giá trị |", "|---|---|",
        f"| Python (venv) | {t['python']} |",
        f"| uv | {t['uv']} |",
        f"| Node | {t['node']} |",
        f"| git | {t['git']} (core.autocrlf = {t['git_autocrlf']}) |",
        f"| PYTHONUTF8 | {t['pythonutf8']} |",
        f"| Đường dẫn repo có dấu cách / ký tự không ASCII | {yes(t['path_has_space_or_non_ascii'])} "
        "(chạy test bằng `uv run python -m pytest`) |",
        "",
        "## Benchmark",
        "",
    ]
    if not b:
        lines += ["Chưa chạy (`uv run scripts/check_env.py --bench`).", ""]
    else:
        if b.get("skipped"):
            lines += [f"Ollama: bỏ qua ({b['skipped']}).", ""]
        if "embed" in b:
            e = b["embed"]
            lines += [
                f"- **Embedding `{MODELS['embed']}`:** {e['texts_per_s']} đoạn/giây ({e['texts']} đoạn trong "
                f"{e['seconds']} s). `chunk semantic` cần embed khoảng {e['texts_to_embed']:,} đoạn "
                f"({e['sentences']:,} câu + {e['chunks_a1']:,} chunk; nguồn: {e['source']}), "
                f"ước tính **{e['estimated_hours_chunk_semantic']} giờ**.",
            ]
        for role in ("generate", "judge"):
            if role in b:
                g = b[role]
                where = "GPU" if g.get("size_vram") else "CPU"
                lines.append(f"- **`{g['model']}`:** sinh {g['gen_tok_per_s']} token/giây, TTFT (đã nạp) "
                             f"{g['ttft_warm_s']} s, 128 token mất {g['total_128_tokens_s']} s, nạp lần đầu "
                             f"{g['cold_load_s']} s, chạy trên {where} (size_vram = {g.get('size_vram')}).")
        r = b["rerank"]
        lines += [f"- **Reranker `{r['model']}`** trên `{r['device']}`: {r['pairs']} cặp mất p50 {r['p50_ms']} ms "
                  f"(nạp model {r['load_s']} s).", ""]
    return "\n".join(lines)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--bench", action="store_true", help="also run the embedding, LLM and reranker benchmarks")
    a = p.parse_args()
    env = {"checked_at": datetime.now().isoformat(timespec="seconds"), "seed": SEED,
           "hardware": hardware(), "docker": docker(), "ollama": ollama(), "tools": tools()}
    if a.bench:
        env["bench"] = benchmarks(env["ollama"])
    elif OUT_JSON.exists():  # keep the last benchmark when only re-checking the setup
        old = json.loads(OUT_JSON.read_text(encoding="utf-8"))
        if "bench" in old:
            env["bench"] = old["bench"]
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(env, indent=2, ensure_ascii=False), encoding="utf-8")
    OUT_MD.write_text(render(env), encoding="utf-8")
    print(render(env))


if __name__ == "__main__":
    main()
