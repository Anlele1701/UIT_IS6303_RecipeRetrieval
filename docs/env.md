# Môi trường máy build

Sinh tự động bởi `scripts/check_env.py` lúc 2026-10-12T00:22:49. Số liệu gốc: `eval/env.json`. Không sửa tay file này.

## Phần cứng

| Mục | Giá trị |
|---|---|
| Hệ điều hành | Windows-11-10.0.26200-SP0 |
| CPU | AMD Ryzen AI 7 350 w/ Radeon 860M (8 nhân, 16 luồng) |
| RAM | 31.1 GB |
| GPU | AMD Radeon(TM) 860M Graphics (driver 32.0.13058.8001) |
| GPU NVIDIA (`nvidia-smi`) | không có |
| Ổ đĩa trống (ổ chứa repo) | 465.2 GB |

## Docker

| Mục | Giá trị |
|---|---|
| Phiên bản | Docker version 29.7.2, build a7dcaa6 · Docker Compose version v5.5.1 |
| Engine | 29.7.2 trên Docker Desktop (kernel 6.18.33.2-microsoft-standard-WSL2) |
| Tài nguyên cấp cho Docker | 16 CPU, 15.2 GB RAM |
| Volume A1 `is603_recipe-pgdata` có trên máy | không (A3 không bao giờ dùng) |
| Volume A3 `is603a3_a3-pgdata` | có |
| Container `a3-paradedb` đang chạy | có |
| Port 5435 dùng được | có |
| Bind mount đường dẫn có dấu cách và tiếng Việt | được |

## Ollama

| Mục | Giá trị |
|---|---|
| CLI | ollama version is 0.40.3 |
| Server | 0.40.3 (http://localhost:11434) |
| Model đã có | llama3.1:8b, nomic-embed-text:latest, qwen2.5:7b |
| Model còn thiếu | không |

## Công cụ

| Mục | Giá trị |
|---|---|
| Python (venv) | 3.12.13 |
| uv | uv 0.10.11 (006b56b12 2026-03-16) |
| Node | v24.18.0 |
| git | git version 2.53.0.windows.2 (core.autocrlf = true) |
| PYTHONUTF8 | 1 |
| Đường dẫn repo có dấu cách / ký tự không ASCII | có (chạy test bằng `uv run python -m pytest`) |

## Benchmark

- **Embedding `nomic-embed-text`:** 33.3 đoạn/giây (256 đoạn trong 7.69 s). `chunk semantic` cần embed khoảng 464,631 đoạn (298,193 câu + 166,438 chunk; nguồn: database), ước tính **3.88 giờ**.
- **`qwen2.5:7b`:** sinh 8.8 token/giây, TTFT (đã nạp) 0.16 s, 128 token mất 6.9 s, nạp lần đầu 10.45 s, chạy trên CPU (size_vram = 0).
- **`llama3.1:8b`:** sinh 8.0 token/giây, TTFT (đã nạp) 0.15 s, 128 token mất 11.57 s, nạp lần đầu 11.51 s, chạy trên CPU (size_vram = 0).
- **Reranker `mixedbread-ai/mxbai-rerank-base-v1`** trên `cpu`: 50 cặp mất p50 7580.3 ms (nạp model 20.3 s).
