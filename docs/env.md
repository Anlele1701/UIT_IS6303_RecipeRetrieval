# Môi trường máy build

Sinh tự động bởi `scripts/check_env.py` lúc 2026-10-11T23:46:59. Số liệu gốc: `eval/env.json`. Không sửa tay file này.

## Phần cứng

| Mục | Giá trị |
|---|---|
| Hệ điều hành | Windows-11-10.0.26200-SP0 |
| CPU | AMD Ryzen AI 7 350 w/ Radeon 860M (8 nhân, 16 luồng) |
| RAM | 31.1 GB |
| GPU | AMD Radeon(TM) 860M Graphics (driver 32.0.13058.8001) |
| GPU NVIDIA (`nvidia-smi`) | không có |
| Ổ đĩa trống (ổ chứa repo) | 482.8 GB |

## Docker

| Mục | Giá trị |
|---|---|
| Phiên bản | Docker version 29.7.2, build a7dcaa6 · Docker Compose version v5.5.1 |
| Engine | 29.7.2 trên Docker Desktop (kernel 6.18.33.2-microsoft-standard-WSL2) |
| Tài nguyên cấp cho Docker | 16 CPU, 15.2 GB RAM |
| Volume A1 `is603_recipe-pgdata` có trên máy | không (A3 không bao giờ dùng) |
| Volume A3 `is603a3_a3-pgdata` | không |
| Container `a3-paradedb` đang chạy | không |
| Port 5435 dùng được | có |
| Bind mount đường dẫn có dấu cách và tiếng Việt | được |

## Ollama

| Mục | Giá trị |
|---|---|
| CLI | ollama: not found |
| Server | not reachable: ConnectError (http://localhost:11434) |
| Model đã có | – |
| Model còn thiếu | nomic-embed-text, qwen2.5:7b, llama3.1:8b |

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

Chưa chạy (`uv run scripts/check_env.py --bench`).
