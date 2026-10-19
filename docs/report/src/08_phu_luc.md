# Phụ lục

## Phụ lục A. RAG Card (tóm tắt)

RAG Card đầy đủ được sinh tự động tại `docs/rag_card.md`; Data Card tại `docs/data_card.md`.

| Hạng mục | Giá trị |
|---|---|
| Kho công thức | Shengtao/recipe, {{corpus:D1.recipes|int}} công thức sau D1; pipeline dữ liệu commit `{{corpus:git_commit|raw}}`, seed {{corpus:seed|raw}} |
| Hồ sơ bệnh nhân | {{pcorpus:total.P1.files|int}} tài liệu C-CDA R2.1 tổng hợp bằng Synthea; {{pq:patients|int}} bệnh nhân được chọn cho đánh giá |
| Chunk | chiến lược semantic kế thừa A1; BM25 (ParadeDB) và dense (nomic-embed-text), mỗi nhánh 50 chunk, hợp nhất RRF |
| Xếp hạng lại | mxbai-rerank-base-v1 trên 50 ứng viên; 5 công thức vào ngữ cảnh |
| Hiểu truy vấn, chọn nút, tóm tắt nút | qwen2.5:7b, temperature 0, structured output theo lược đồ JSON |
| Sinh câu trả lời | qwen2.5:7b, temperature 0,2, tối đa 2.048 token |
| Bộ kiểm độc lập và judge | llama3.1:8b, temperature 0 (khác họ với mô hình sinh) |
| Tái lập | seed {{m6s:seed|raw}}; lưu đệm mọi lời gọi mô hình theo hash đầu vào; bộ test và bộ câu hỏi hồ sơ khóa bằng sha256 |
| Lần chạy M6 | `eval/runs/20261019-093605/a3`, commit `{{m6s:git|raw}}` |

## Phụ lục B. Prompt chính

Nguyên văn lấy từ mã nguồn tại thời điểm dựng báo cáo.

**B.1. Hiểu truy vấn (M1)**

{{d:prompts.[M1 SYSTEM]|raw}}

**B.2. Sinh câu trả lời (M6)**

{{d:prompts.[M6 RULES]|raw}}

**B.3. Quy tắc bổ sung khi có hồ sơ bệnh nhân (M6)**

{{d:prompts.[M6 PATIENT_RULES]|raw}}

**B.4. Chọn nút hồ sơ theo ngữ cảnh (V2)**

{{d:prompts.[V2 chọn nút]|raw}}

**B.5. Bộ kiểm độc lập**

{{d:prompts.[Bộ kiểm độc lập]|raw}}

**B.6. Judge độ liên quan và faithfulness**

{{d:prompts.[Judge độ liên quan]|raw}}

{{d:prompts.[Judge faithfulness]|raw}}

## Phụ lục C. Lược đồ đầu ra của bước hiểu truy vấn

Lược đồ JSON gửi cho Ollama ở chế độ structured output (phiên có bệnh nhân; phiên không có bệnh nhân không có giá trị `patient_info` và trường `needs_record_context`).

{{d:m1_schema|raw}}

## Phụ lục D. Phân công thành viên

**[CẦN NHÓM ĐIỀN]**

| Thành viên | MSSV | Công việc | Mức đóng góp |
|---|---|---|---|
| | | | |
| | | | |
| | | | |
