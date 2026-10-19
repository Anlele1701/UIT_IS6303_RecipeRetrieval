"""Report figures (build plan M7): charts from the run files, diagrams from Mermaid sources.

    uv run --with matplotlib scripts/report_figures.py            # all figures -> docs/report/figures/
    uv run --with matplotlib scripts/report_figures.py --charts   # charts only (no Mermaid / browser)

Charts read the same metrics as the report text (scripts/report_numbers.SOURCES), so a figure never shows a
number typed by hand. Diagrams: docs/report/figures/src/*.mmd rendered by mermaid-cli with the system Edge
(docs/report/figures/src/puppeteer.json; no Chromium download).
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from report_numbers import SOURCES  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
FIG = ROOT / "docs" / "report" / "figures"
MERMAID_CLI = "@mermaid-js/mermaid-cli@11.4.2"
ACCENT, GREY, A1 = "#2457c5", "#9aa3b2", "#3c9a7a"
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 12, "axes.spines.top": False,
                     "axes.spines.right": False, "figure.dpi": 200})


def load(name: str) -> dict:
    return json.loads(SOURCES[name].read_text(encoding="utf-8"))


def vi(x: float, places: int = 2) -> str:
    return f"{x:.{places}f}".replace(".", ",")


def save(fig, name: str) -> None:
    fig.tight_layout()
    fig.savefig(FIG / f"{name}.png", facecolor="white")
    plt.close(fig)
    print(f"  {name}.png")


def fig_main() -> None:
    """CVR@5 (adjudicated) and nDCG@10' on T2 per configuration, with 95% CIs."""
    s = load("m6")["summary"]
    names = ["B0", "B1", "S", "S-QU", "S-Filter", "S-Norm", "S-Rerank", "S-Verify"]
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.2), sharey=True)
    for ax, metric, title, pct in ((axes[0], "cvr_adj", "CVR@5 trên T2 (thấp hơn là tốt)", True),
                                   (axes[1], "ndcg10", "nDCG@10′ trên T2 (cao hơn là tốt)", False)):
        vals = [s[f"{n}|t2"][metric] for n in names]
        mean = [v["mean"] * (100 if pct else 1) for v in vals]
        lo = [m - v["ci95"][0] * (100 if pct else 1) for m, v in zip(mean, vals)]
        hi = [v["ci95"][1] * (100 if pct else 1) - m for m, v in zip(mean, vals)]
        colors = [ACCENT if n == "S" else (A1 if n == "B0" else GREY) for n in names]
        ax.barh(names, mean, xerr=[lo, hi], color=colors, capsize=3, error_kw={"elinewidth": 1, "ecolor": "#444"})
        for y, (m, h) in enumerate(zip(mean, hi)):  # the label sits past the CI whisker, never on it
            ax.text(m + h, y, f"  {vi(m, 1)}%" if pct else f"  {vi(m)}", va="center", fontsize=10)
        ax.set_xlim(0, max(m + h for m, h in zip(mean, hi)) * 1.25)
        ax.set_title(title, fontsize=12)
        ax.invert_yaxis()
    save(fig, "fig_main")


def fig_testset_flow() -> None:
    """Generated, rejected by V2 and V4, and frozen per set (testset_flow.json)."""
    sets = load("flow")["sets"]
    labels = {"t1": "T1 hồi quy", "t2": "T2 ràng buộc", "t3": "T3 không trả lời được", "t4": "T4 hội thoại"}
    fig, ax = plt.subplots(figsize=(10, 3.8))
    keys = list(labels)
    ys = range(len(keys))
    gen = [sets[k]["generated"] for k in keys]
    v2 = [sets[k]["rejected"]["V2"] for k in keys]
    v4 = [sets[k]["rejected"]["V4"] for k in keys]
    final = [sets[k]["V6"]["final"] for k in keys]
    ax.barh(ys, gen, color="#e6e9ef", label="sinh ra")
    ax.barh(ys, v2, color="#d9534f", label="loại ở V2 (có / không có công thức thỏa)")
    ax.barh(ys, v4, left=v2, color="#f0ad4e", label="loại ở V4 (gần trùng)")
    ax.barh([y + 0.0 for y in ys], final, height=0.35, color=ACCENT, label="đóng băng sau V6")
    for y, (g, f) in enumerate(zip(gen, final)):
        ax.text(g, y, f"  {g} → {f}", va="center", fontsize=10)
    ax.set_yticks(list(ys), [labels[k] for k in keys])
    ax.invert_yaxis()
    ax.set_xlabel("số câu (T4: số hội thoại)")
    ax.legend(fontsize=9, loc="lower right", frameon=False)
    save(fig, "fig_testset_flow")


def fig_mv4() -> None:
    """Allergy recall and Safe@5 (allergen, adjudicated) per way of reading the record."""
    t = load("mv4")["all"]["table"]
    presets = ["P-Direct", "P-Vectorless", "P-Vectorless-Fixed", "P-Vector"]
    fig, axes = plt.subplots(1, 2, figsize=(11, 4))
    for ax, key, title in ((axes[0], "recall", "Recall dị ứng so với đáp án Synthea"),
                           (axes[1], "safe", "Safe@5 theo dị ứng (đầu cuối)")):
        width = 0.38
        for i, inp in enumerate(("coded", "narrative")):
            vals = []
            for p in presets:
                row = t.get(f"{inp}|{p}")
                if row is None or (inp == "narrative" and p == "P-Direct"):
                    vals.append(0.0)
                    continue
                vals.append(100 * (row["food_allergy_substances"]["recall"] if key == "recall"
                                   else row["safe_allergen_adj"]["value"]))
            xs = [x + (i - 0.5) * width for x in range(len(presets))]
            bars = ax.bar(xs, vals, width, color=ACCENT if inp == "coded" else GREY,
                          label="hồ sơ có mã" if inp == "coded" else "narrative (văn bản tự do)")
            for b, v in zip(bars, vals):
                if v:
                    ax.text(b.get_x() + b.get_width() / 2, v, f"{v:.0f}", ha="center", va="bottom", fontsize=9)
        ax.set_xticks(range(len(presets)), presets, rotation=15, fontsize=10)
        ax.set_ylim(0, 110)
        ax.set_ylabel("%")
        ax.set_title(title, fontsize=12)
    axes[0].legend(fontsize=9, frameon=False, loc="upper right")
    save(fig, "fig_mv4")


def fig_latency() -> None:
    """Median latency per module (p50, ms) for B0, B1 and S."""
    s = load("m6")["summary"]
    stages = [("m1", "M1 hiểu truy vấn", "#7c6fd6"), ("m4", "M4 lọc + truy hồi", A1), ("m5", "M5 rerank", "#5bc0de"),
              ("m6", "M6 sinh", ACCENT)]
    names = ["B0", "B1", "S"]
    fig, ax = plt.subplots(figsize=(10, 3))
    for n_i, n in enumerate(names):
        left = 0.0
        lat = s[f"{n}|all"]["latency_ms"]
        for key, label, color in stages:
            v = lat.get(key, {}).get("p50", 0.0) / 1000
            ax.barh(n_i, v, left=left, color=color, label=label if n_i == 0 else None)
            left += v
        ax.text(left, n_i, f"  {vi(lat['total']['p50'] / 1000, 1)} s", va="center", fontsize=10)
    ax.set_yticks(range(len(names)), names)
    ax.invert_yaxis()
    ax.set_xlabel("giây (p50 theo module)")
    ax.legend(fontsize=9, frameon=False, ncol=4, loc="upper center", bbox_to_anchor=(0.5, -0.3))
    save(fig, "fig_latency")


def fig_architecture() -> None:
    """The four layers of [13] as horizontal bands, each with its components (drawn, not data)."""
    from matplotlib.patches import FancyBboxPatch
    layers = [("Frontend · React + Vite", "#eaf0fb", ["Chatbox /chat\nchọn bệnh nhân · chip", "Tìm kiếm nâng cao\n(kế thừa A1)",
                                                      "Báo cáo kết quả"]),
              ("Backend · FastAPI", "#eef7f2", ["Bộ điều phối M1–M7\n(cờ preset)", "Dịch vụ hồ sơ\nC-CDA · cây · luật V1–V3",
                                                "Ollama\nqwen2.5:7b · nomic-embed", "Reranker\nmxbai-rerank-base"]),
              ("Data Infrastructure · ParadeDB", "#fbf3e6", ["Công thức · chunk\nBM25 + vector · thẻ",
                                                              "Bệnh nhân · cây hồ sơ\nhồ sơ ràng buộc",
                                                              "Phiên · tin nhắn\nràng buộc phiên"]),
              ("Governance", "#f3eefb", ["Truy vết từng bước\nretrieval_trace", "Hậu kiểm M7", "Banner · phản hồi",
                                         "Tối thiểu hóa dữ liệu\n(quy tắc P7)"])]
    fig, ax = plt.subplots(figsize=(11, 6.2))
    ax.set_xlim(0, 11)
    ax.set_ylim(0, 4 * 1.5)
    ax.axis("off")
    for i, (name, color, items) in enumerate(layers):
        y = (3 - i) * 1.5
        ax.add_patch(FancyBboxPatch((0.05, y + 0.08), 10.9, 1.32, boxstyle="round,pad=0.02", fc=color, ec="#b8bfcc"))
        ax.text(0.2, y + 1.22, name, fontsize=12, fontweight="bold", va="center")
        w = 10.5 / len(items)
        for j, item in enumerate(items):
            x = 0.25 + j * w
            ax.add_patch(FancyBboxPatch((x, y + 0.2), w - 0.25, 0.78, boxstyle="round,pad=0.02", fc="white", ec="#7d8698"))
            ax.text(x + (w - 0.25) / 2, y + 0.59, item, ha="center", va="center", fontsize=10)
        if i < 3:
            ax.annotate("", xy=(5.5, y + 0.06), xytext=(5.5, y + 0.12), arrowprops={"arrowstyle": "-|>", "color": "#555"})
    save(fig, "fig_architecture")


def diagrams() -> None:
    env = {**os.environ, "PUPPETEER_SKIP_DOWNLOAD": "1"}
    npx = "npx.cmd" if os.name == "nt" else "npx"
    for src in sorted((FIG / "src").glob("*.mmd")):
        out = FIG / f"{src.stem}.png"
        subprocess.run([npx, "-y", "-p", MERMAID_CLI, "mmdc", "-p", str(FIG / "src" / "puppeteer.json"), "-i", str(src),
                        "-o", str(out), "-s", "3", "-b", "white"], check=True, env=env, capture_output=True)
        print(f"  {out.name}")


if __name__ == "__main__":
    FIG.mkdir(parents=True, exist_ok=True)
    for f in (fig_main, fig_testset_flow, fig_mv4, fig_latency, fig_architecture):
        f()
    if "--charts" not in sys.argv:
        diagrams()
