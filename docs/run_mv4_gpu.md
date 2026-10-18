# Chạy MV4 đầy đủ (MV4d)

Hướng dẫn chạy lần đánh giá đầy đủ của nhánh hồ sơ bệnh nhân: 300 câu hỏi đã đóng băng, 5 preset, 2 chế độ đầu vào.

**Máy chạy (Thy duyệt 18/10/2026):** máy phát triển (RTX 4060 Laptop, 8 GB VRAM, driver 577 / CUDA 12.9).
- Ollama chạy trên GPU.
- Reranker dùng torch `2.11.0+cu128`, lấy theo `[tool.uv.sources]` trong `pyproject.toml`.
- Lần chạy thử 10 câu ở MV4c cho thấy mỗi lượt mất khoảng 10–50 giây. Ước tính cả lần chạy khoảng 8–9 giờ, cộng thêm khoảng 1 giờ chấm bằng bộ kiểm.

Hướng dẫn dưới đây dùng được cho bất kỳ máy nào: máy này, hoặc một máy GPU khác nếu cần.
- Trên máy có driver NVIDIA ≥ 580 (CUDA 13), có thể đổi index sang `cu130` để dùng torch mới hơn. Giữ `cu128` vẫn chạy được.
- Sau khi đổi torch, chạy `uv run python -m pytest -q -m slow tests/test_no_patient_regression.py` để chắc thứ hạng của reranker không đổi.

Số lượt: 300 câu × 8 = **2.400 lượt**, cộng phần chấm bằng bộ kiểm độc lập (`llama3.1:8b`). Con số 8 gồm:
- 5 preset ở chế độ coded;
- 3 preset ở chế độ narrative. P-Direct đọc mã nên không áp dụng cho narrative. S-Profile không đọc hồ sơ nên chỉ chạy một lần ở chế độ coded, và dòng narrative của nó dùng chung các lượt đó.

## 1. Chuẩn bị máy

Cần có Docker, `uv`, Git LFS, Ollama và driver NVIDIA. Kiểm tra Ollama có dùng GPU: chạy một model rồi gõ `ollama ps`; cột PROCESSOR phải ghi `100% GPU`.

```
git clone <repo> && cd <repo> && git checkout a3 && git lfs pull
ollama pull nomic-embed-text && ollama pull qwen2.5:7b && ollama pull llama3.1:8b
uv sync
```

Trên Windows:
- đặt `PYTHONUTF8=1`;
- chạy lệnh trong Git Bash;
- thêm `MSYS_NO_PATHCONV=1` trước các lệnh `docker exec` có đường dẫn.

## 2. Cơ sở dữ liệu

1. Restore bản dump A3 theo `docs/handoff.md` mục 3 (Cách 1). Bản dump có migration 001–005.
2. Áp migration 006–008, rồi dựng lại phân vùng semantic để điền các cột dinh dưỡng phái sinh (khoảng 2 phút, không embed lại):

```
for m in 006-nutrition-derived 007-patient 008-patient-constraint-types; do
  docker exec -i a3-paradedb psql -U recipe -d recipe -v ON_ERROR_STOP=1 --single-transaction \
    -f /docker-entrypoint-initdb.d/sql/migrations/$m.sql
done
uv run scripts/ingest.py retag semantic
```

## 3. Hồ sơ bệnh nhân

Hai thư mục C-CDA không có trong git (`data/*` bị bỏ qua).

- **`data/synthea_sample_data_ccda_latest/`**
  - Tải zip theo `file_url` trong `data/sources.json`, rồi giải nén vào thư mục này.
  - Kiểm tra: `sha256sum` của file zip phải bằng `zip_sha256`.
- **`data/synthea_generated_ccda/`** (12 file)
  - Chép từ máy gốc. Nếu muốn sinh lại thì chạy Synthea đúng commit và lệnh ghi trong `data/sources.json`, rồi chạy `scripts/patient_select.py`.
  - Kiểm tra: lệnh sau phải in `caad75b0…2595171`:

```
uv run python -c "import sys; sys.path.insert(0,'scripts'); from patient_select import files_sha; from pathlib import Path; print(files_sha(sorted(Path('data/synthea_generated_ccda').glob('*.xml'))))"
```

Nạp hồ sơ, rồi viết tóm tắt nút ngữ cảnh bằng LLM (V1c; trên CPU bước này mất nhiều giờ nên chưa chạy):

```
uv run scripts/patient_ingest.py load
uv run scripts/patient_ingest.py tree --summarize llm
uv run scripts/patient_ingest.py profiles
uv run scripts/patient_ingest.py stats
git diff --stat eval/patient_corpus.json eval/patient_profiles.json   # số đếm phải trùng bản trong git
```

Sau `tree --summarize llm`, mục lục mà V2 đọc dùng tóm tắt do LLM viết. Các lần chạy thử ở MV4c dùng tóm tắt template, nên số liệu chọn nút ở hai lần sẽ khác nhau.

## 4. Kiểm tra trước khi chạy

```
uv run scripts/check_env.py            # sinh docs/env.md của máy này (đừng commit đè bản của máy gốc)
uv run python -m pytest -q             # khoảng 1 phút, không cần Ollama
uv run python -m pytest -q -m slow tests/test_no_patient_regression.py tests/test_patient_demo.py
```

`eval_patient.py` tự kiểm sha256 của `eval/patient/queries.jsonl` và `gold.jsonl` so với `frozen.json`. Nếu khác, nó từ chối chạy.

## 5. Chạy đánh giá

```
uv run scripts/eval_patient.py run
```

- Kết quả ghi vào `eval/runs/<thời điểm>/patient/`:
  - `settings.json`: máy, GPU, commit, seed, `PER_MEAL_FRACTION`, `ruleset_version`, model, số dòng cache;
  - `turns.jsonl`: mỗi lượt một dòng, ghi ngay sau khi lượt xong;
  - sau khi chạy xong: `metrics.json`, `per_query.csv`, `table.md`.
- Nếu bị ngắt, chạy tiếp từ chỗ dừng:
  ```
  uv run scripts/eval_patient.py run --resume eval/runs/<thời điểm>/patient
  ```
- Có thể chạy từng chế độ: `--input coded` hoặc `--input narrative`. Chạy chế độ coded trước vì nhanh hơn. Chế độ narrative đọc khoảng 12.000 ký tự mỗi bệnh nhân với `num_ctx` 16384.
- Khi chạy đầy đủ (không có `--limit`), các phán quyết "yes" của bộ kiểm cần người duyệt được **thêm** vào `eval/labels/checker_queue.csv`. Hàng duyệt là mù: không ghi preset hay run.

**Đo độ trễ khi chưa có cache (tùy chọn).** `data/cache/llm.jsonl` có trong git, nên lượt đầu của nhiều câu là cache hit. Để đo độ trễ thật mà không làm bẩn cache chung:

```
LLM_CACHE_FILE=/tmp/cold.jsonl uv run scripts/eval_patient.py run --limit 30 --no-score
```

Lần chạy này chỉ dùng cho bảng chi phí. Số liệu chính lấy từ lần chạy ở trên.

## 6. Duyệt hàng chờ và chấm lại

1. Thy gán nhãn các dòng mới trong `eval/labels/checker_queue.csv` vào `eval/labels/checker_adjudication.csv`, theo `docs/annotation_guide.md` mục 8.
2. Chấm lại (không chạy lại pipeline):

```
uv run scripts/eval_patient.py score eval/runs/<thời điểm>/patient
```

## 7. Đưa kết quả về

Thư mục run bị `.gitignore` bỏ qua, nên phải thêm bằng `-f`:

```
git add -f eval/runs/<thời điểm>/patient
git add data/cache/llm.jsonl data/cache/checker.jsonl eval/labels/checker_queue.csv eval/patient_corpus.json
git commit -m "eval: MV4d full patient run on <GPU>" && git push
```

Không commit `docs/env.md` hay `eval/env.json` của máy GPU. `settings.json` của run đã ghi thông tin máy.

## Những điều cần biết khi đọc kết quả

- **Đáp án ràng buộc** là hồ sơ coded qua bảng luật (cái P-Direct áp dụng). CVR@5 và Safe@5 của mọi preset đều so với đáp án này, cộng ràng buộc trong câu hỏi.
- **Cách chấm từng loại ràng buộc:**
  - nhóm dị ứng và chế độ ăn: bộ kiểm độc lập (raw và adjudicated; phiếu pending tính là vi phạm);
  - nguyên liệu có tên: so khớp nguyên từ trên dòng nguyên liệu thô;
  - thời gian: cột `total_minutes`;
  - dinh dưỡng: các cột dinh dưỡng. Giá trị NULL đếm riêng, không tính là đạt.
- **Chế độ narrative:** văn bản không qua danh sách cho phép của ADR-0006, vì không có mã để đối chiếu. Chỉ các dòng P7 bị bỏ, và việc bỏ dựa vào cột Code của bảng trước khi văn bản đến mô hình. Chế độ này chỉ dùng khi đánh giá.
- **Bảng kết quả xét nghiệm** trong `<text>` của Synthea chỉ có tên panel, không có giá trị. Vì vậy câu hỏi về xét nghiệm ở chế độ narrative có ít thông tin hơn chế độ coded.
