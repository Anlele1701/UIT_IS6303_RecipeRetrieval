# A3 – Luồng xử lý, phương pháp đánh giá, kết quả và hạn chế

Tài liệu tổng hợp để viết báo cáo và slide. Mọi số liệu chép từ các file kết quả do script sinh ra (nguồn ghi dưới mỗi bảng); khi đưa vào báo cáo chính thức, số sẽ được điền tự động từ cùng các file này (quy tắc 9).

---

## 1. Tổng quan

A3 là trợ lý hội thoại tìm công thức nấu ăn, nhận biết ràng buộc (dị ứng, nguyên liệu cần loại, chế độ ăn, thời gian, ngưỡng dinh dưỡng). Ràng buộc đến từ hai nguồn:

- **Câu hỏi và hội thoại** của người dùng, tiếng Việt hoặc tiếng Anh.
- **Hồ sơ bệnh nhân** (C-CDA tổng hợp bằng Synthea), đọc bằng nhánh **vectorless**.

Hai nguồn gộp thành một tập ràng buộc duy nhất. Tập này được thực thi bằng **truy vấn SQL** (lọc cứng) trước khi truy hồi lai của A1 chạy. Mô hình ngôn ngữ chỉ dùng để hiểu câu hỏi, chọn mục hồ sơ, tóm tắt mục hồ sơ và viết câu trả lời. Mọi bước quyết định món nào an toàn đều tất định: đọc mục cố định, ánh xạ luật, lọc, xếp hạng, hậu kiểm.

```
                OFFLINE                                         MỖI LƯỢT HỎI
 recipe.csv ── D1–D8 ──► recipe, chunk, tag ───────────┐
                                                       │
 C-CDA ── P1–P7 ──► cây hồ sơ (patient_node) ──┐       │
                    + tóm tắt nút (V1, LLM)    │       │
                                               ▼       ▼
 câu hỏi ─► M1 hiểu truy vấn ─► V2 chọn nút ─► V3 hồ sơ ràng buộc ─► M2 trạng thái phiên
           (qwen2.5:7b, JSON)   (≤ 1 lời gọi)   (luật, có bằng chứng)   (hồ sơ ∪ hội thoại)
                                                                            │
                                                                            ▼
                                                                    M3 định tuyến
          ┌──────────────┬───────────────┬──────────────────┬─────────────┤
          ▼              ▼               ▼                  ▼             ▼
       retrieve        detail       patient_info          chat         clarify
  M4 lọc SQL + BM25   một công thức  đọc các nút đã chọn   từ chối      hỏi lại
  + dense + RRF       từ DB
  M5 rerank, gom về công thức, top 5
          └──────────────┴───────────────┘
                         ▼
               M6 sinh câu trả lời (stream, trích [R<id>] và [H:<nút>])
                         ▼
               M7 hậu kiểm tất định → sinh lại tối đa 1 lần → câu trả lời do code viết nếu vẫn sai
                         ▼
               sự kiện done + ghi retrieval_trace (độ trễ từng bước)
```

---

## 2. Luồng xử lý

### 2.1. Offline: kho công thức

`scripts/ingest.py` và `scripts/tag.py` xử lý 32.722 dòng của Shengtao/recipe theo các quy tắc có mã. Số đếm được ghi vào `eval/corpus.json`:

| Mã | Việc | Kết quả |
|---|---|---|
| D1 | Loại dòng trùng URL | còn 32.719 công thức |
| D2 | Bỏ cột dinh dưỡng rỗng trên 99% | 13 cột |
| D3 | Đổi thời gian ra phút | null khi rỗng hoặc không đọc được |
| D4 | Tách dòng nguyên liệu (số lượng, đơn vị, tên) | 311.060 dòng; ok 96,5% |
| D5 | Ánh xạ về nguyên liệu chuẩn | 2.005 nguyên liệu chuẩn; độ phủ 99,3% |
| D6 | Gắn 9 nhóm dị ứng FDA (gồm thành phần ẩn: bơ là sữa, Worcestershire là cá…) | "chắc chắn" thì lọc, "có thể" (tùy nhãn hiệu) thì chỉ cảnh báo |
| D6b | Dòng ghi "X-free" không mang nhóm X | 128 dòng |
| D7 | Cờ chay và thuần chay | 16.687 và 4.140 công thức |
| D8 | Dòng không ánh xạ được là unknown | 6,1% công thức có dòng unknown |

Chunk (chiến lược `semantic` kế thừa A1) được đánh chỉ mục BM25 (ParadeDB) và vector (`nomic-embed-text`). Thẻ dị ứng, chế độ ăn và giá trị dinh dưỡng trên khẩu phần được denormalize lên bảng phục vụ lọc (ADR 0001, 0005; migration 006).

### 2.2. Offline: nhận hồ sơ bệnh nhân

1. **Nạp và lọc (P1–P7):** `scripts/patient_ingest.py` đọc tài liệu C-CDA R2.1 của Synthea (120 file: 108 file mẫu, 12 file tự sinh). Script giữ dị ứng và vấn đề đang hiệu lực (P2), tách dị ứng thực phẩm theo mã SNOMED 414285001 (P3), chỉ giữ vấn đề loại "disorder" (P4), thuốc đang dùng (P5), sinh hiệu và xét nghiệm gần nhất (P6). Các mục không liên quan ăn uống (sàng lọc tâm thần, chất gây nghiện, bạo lực, trường định danh) không bao giờ vào ngữ cảnh của mô hình (P7: tối thiểu hóa dữ liệu). Số đếm ghi vào `eval/patient_corpus.json`.
2. **Dựng cây mục lục (V1):** cây dựng tất định từ các section chuẩn của C-CDA, lưu vào bảng `patient_node`:
   - **nút cố định:** Dị ứng, Vấn đề đang điều trị, Thuốc đang dùng, Sinh hiệu gần nhất;
   - **nút theo ngữ cảnh:** Xét nghiệm và Lịch sử khám, chia theo năm.

   Mô hình (`qwen2.5:7b`) chỉ viết một câu tóm tắt cho mỗi nút theo ngữ cảnh, để V2 có thông tin chọn nhánh.
3. **Chọn bệnh nhân cho đánh giá (P8):** chọn phân tầng gồm dị ứng thực phẩm, tiểu đường, tăng huyết áp, bệnh thận mạn, đa bệnh và không ràng buộc.

### 2.3. Bắt đầu một phiên có bệnh nhân

Người dùng chọn bệnh nhân trên `/chat` (`GET /patients`). Ở lượt đầu, orchestrator:

- **V1:** nạp cây của bệnh nhân từ `patient_node`;
- **V3:** dựng **hồ sơ ràng buộc** bằng luật tất định (`api/patient/mapping.py`, `data/rules/*.csv`), lưu đệm theo bệnh nhân và phiên bản bộ luật:
  - dị ứng thực phẩm → nhóm dị ứng cần loại. "Shellfish" của Synthea được mở rộng an toàn: gắn nhóm giáp xác và thêm nghêu, sò, hàu, mực vào danh sách nguyên liệu cấm;
  - bệnh → ngưỡng dinh dưỡng theo WHO, DASH, ADA, KDIGO. Ngưỡng ngày đổi thành ngưỡng một bữa (×1/3, ADR-0007). Loại ngưỡng mà nếu lọc sẽ còn quá ít món (chất béo bão hòa, chất xơ) thì chỉ dùng để xếp hạng và cảnh báo;
  - thuốc → bảng tương tác: statin thì loại bưởi chùm; warfarin thì cảnh báo rau giàu vitamin K;
  - mỗi ràng buộc mang **bằng chứng**: mã nút và dòng hồ sơ đã sinh ra nó.

Giao diện hiện các ràng buộc từ hồ sơ dưới dạng chip có khóa (gom theo mục dị ứng gốc), kèm bằng chứng (`GET /patients/{id}/profile`).

### 2.4. Mỗi lượt hỏi (`POST /chat`, trả về SSE)

1. **M1 – Hiểu truy vấn:** `qwen2.5:7b` đọc câu hỏi và lịch sử, trả JSON theo schema (structured output, temperature 0, seed 42). JSON gồm:
   - ý định;
   - câu truy vấn tiếng Anh **không chứa phủ định** (phủ định chỉ xử lý ở bộ lọc);
   - các ràng buộc: nhóm dị ứng, nguyên liệu loại, chế độ ăn, thời gian;
   - cờ "cần ngữ cảnh hồ sơ".

   Kết quả được hậu xử lý bằng từ điển Việt–Anh. Riêng dị ứng, kết quả của mô hình được **hợp** với kết quả tra từ điển trên câu gốc: thêm thừa chỉ mất vài món, bỏ sót thì nguy hiểm.
2. **V2 – Chọn nút (có bệnh nhân):** nút cố định **luôn được đọc bằng code**. Nút theo ngữ cảnh chỉ mở khi câu hỏi cần ("gần đây chức năng thận thế nào?"). Khi đó mô hình nhận toàn bộ mục lục kèm ngày của hồ sơ và trả danh sách nút trong **một lần gọi**, không có vòng lặp. Sự kiện `patient_profile` được gửi cho UI.
3. **M2 – Trạng thái phiên:** gộp ràng buộc hồ sơ (C_E) với ràng buộc hội thoại (C_t^dlg).
   - Ràng buộc dị ứng do người dùng nêu được giữ cho tới khi gỡ.
   - Ràng buộc tạm thời chỉ áp cho lượt hiện tại.
   - **Ràng buộc từ hồ sơ không gỡ được bằng tin nhắn** (ví dụ "bỏ qua dị ứng tôm đi"). Hệ ghi chú lại và giải thích cho người dùng.
   - Trạng thái lưu trong `session_constraint` theo mã phiên.
4. **M3 – Định tuyến:** `clarify` (hỏi lại), `chat` (ngoài phạm vi thì từ chối lịch sự), `patient_info` (hỏi về bệnh nhân thì trả lời từ các nút đã đọc), `detail` (hỏi chi tiết món vừa gợi ý thì đọc từ DB), còn lại là `retrieve`.
5. **M4 – Truy hồi có lọc cứng (`retrieve`):** ràng buộc hợp nhất thành điều kiện `WHERE` trên thẻ chuẩn hóa (nhóm dị ứng, nguyên liệu chuẩn, chế độ ăn, thời gian, ngưỡng dinh dưỡng một bữa). Sau đó BM25 và dense mỗi nhánh lấy 50 chunk, hợp nhất bằng RRF như A1.
6. **M5 – Xếp hạng lại:** cross-encoder `mxbai-rerank-base-v1` trên 50 ứng viên, gom chunk về cấp công thức. Với bệnh nhân có ngưỡng "mềm", hệ cộng điểm phạt vào thứ hạng thay vì lọc. Hệ xếp hạng tới độ sâu 10 (để đo nDCG@10) và đưa **5 công thức** đầu vào ngữ cảnh. Sự kiện `recipes` gửi các thẻ công thức cho UI.
7. **M6 – Sinh câu trả lời:** `qwen2.5:7b` stream câu trả lời (temperature 0,2, tối đa 2.048 token). Prompt yêu cầu:
   - chỉ dùng công thức trong ngữ cảnh;
   - trả lời bằng ngôn ngữ của người hỏi;
   - trích món bằng `[R<id>]`, trích ràng buộc hồ sơ bằng `[H:<nút>]`;
   - không khẳng định món an toàn tuyệt đối;
   - khi không có món phù hợp thì nói không tìm thấy, chỉ gợi ý nới ràng buộc mềm, **không bao giờ** gợi ý nới dị ứng hay ràng buộc hồ sơ.

   Riêng route `patient_info`: dữ liệu các nút được xếp mới nhất trước và cắt bằng code cho vừa ngữ cảnh 16k (không để Ollama tự cắt đầu prompt).
8. **M7 – Hậu kiểm tất định:** mọi `[R<id>]` phải nằm trong ngữ cảnh và không vi phạm ràng buộc. Với bệnh nhân, M7 kiểm thêm:
   - món được trích không vượt ngưỡng dinh dưỡng;
   - văn bản không gợi ý nguyên liệu bị cấm;
   - `[H:]` phải là nút có thật;
   - với `patient_info`, mọi con số phải khớp số trong hồ sơ và không được diễn giải ("cao", "bình thường").

   Nếu sai, hệ bỏ trích dẫn lỗi và **sinh lại một lần**. Nếu vẫn sai, hệ bỏ câu vi phạm, hoặc thay bằng câu trả lời do code viết (liệt kê món hợp lệ hoặc giá trị trong hồ sơ). Trường hợp này được đếm là "fallback".
9. **Kết thúc:** sự kiện `done` gồm câu trả lời cuối, trích dẫn, số token và độ trễ từng bước. Mỗi bước ghi một dòng vào `retrieval_trace`.

### 2.5. Gỡ ràng buộc hồ sơ có xác nhận

Người dùng chuyên môn gỡ một chip hồ sơ trên giao diện (`PATCH /chat/{session}/constraints/{id}`, bắt buộc `confirm`). Hệ gỡ cả nhóm ràng buộc sinh ra từ cùng một mục dị ứng gốc, nhưng giữ các thành viên còn có bằng chứng khác. Lần gỡ được ghi vào `session_record_lift`. Từ lượt sau, M2, M4, M6 và M7 chạy trên hồ sơ đã bỏ nhóm đó (ADR 0008).

### 2.6. Phiên không có bệnh nhân

Phiên không có bệnh nhân chạy đúng chuỗi M1–M7, không có V1–V3. Mọi cấu hình so sánh là một tập cờ trong `api/pipeline/flags.py`, chạy cùng một hàm `run_turn` (quy tắc 10).

---

## 3. Phương pháp đánh giá

Hai đợt đánh giá trả lời năm câu hỏi nghiên cứu:

| Đợt | Câu hỏi | Dữ liệu | Script |
|---|---|---|---|
| M6 | RQ1–RQ4 | Bộ test A3 (T1–T4), mẫu khoảng 10% | `scripts/eval_a3.py` |
| MV4 | RQ1 (ràng buộc từ hồ sơ), RQ5 | 100 bệnh nhân, 300 câu | `scripts/eval_patient.py` |
| M2 | Độ tin của công cụ đo | 200 công thức có nhãn bạc | `scripts/eval_allergen.py` |

### 3.1. Bộ test

**Bộ test A3** đóng băng ngày 19/10/2026, sha256 lưu trong `eval/testset/frozen.json`:

| Tập | Nội dung | Số câu |
|---|---|---|
| T1 | Hồi quy: lấy mẫu từ bộ truy vấn A1 | 105 |
| T2 | Ràng buộc một lượt (vi 75, en 75, cộng câu viết tay) | 172 |
| T3 | Không trả lời được: ràng buộc mâu thuẫn hoặc ngoài miền | 55 |
| T4 | Hội thoại nhiều lượt, ràng buộc nêu ở lượt trước | 40 hội thoại |

- **Nguồn câu:** ghép mẫu câu rồi diễn đạt lại bằng `llama3.1:8b` (khác họ với mô hình hiểu truy vấn), cộng 32 câu nhóm tự viết.
- **Quy tắc hợp lệ V1–V5** (số câu bị loại ghi trong `eval/testset/testset_flow.json`):
  - V1: không chép tiêu đề công thức;
  - V2: có hoặc không có công thức thỏa, tùy tập;
  - V3: kiểm dấu tiếng Việt;
  - V4: không gần trùng;
  - V5: độ dài 3–40 từ.
- **V6:** gold do Claude soạn, Thy xác nhận.

**Bộ câu hỏi hồ sơ** (`eval/patient/`, đóng băng):

- 100 bệnh nhân × 3 loại câu = 300 câu (151 tiếng Việt, 149 tiếng Anh):
  - không nêu ràng buộc, để kiểm ràng buộc hồ sơ tự áp dụng;
  - thêm ràng buộc mới bên cạnh hồ sơ;
  - cần ngữ cảnh thời gian trong hồ sơ, để kiểm V2 chọn nút.
- **Đáp án:** lấy tự động từ các trường có mã của Synthea, dừng ở mức thực thể (dị ứng nào, bệnh nào, thuốc nào) để không vòng tròn với bộ luật.
- **V7:** tập gold là hợp của đáp án hồ sơ và ràng buộc trong câu, và phải còn công thức thỏa.
- Nhóm kiểm tay bước lấy đáp án trên 20 bệnh nhân.

### 3.2. Các cấu hình so sánh

| Cấu hình | Mô tả |
|---|---|
| B0 | Hybrid của A1: BM25 + dense + RRF + rerank, không hiểu truy vấn, không sinh |
| B1 | RAG thô trên A1: B0 + sinh câu trả lời |
| S | Hệ đầy đủ M1–M7 |
| S−QU, S−Filter, S−Norm, S−Rerank, S−Verify, S−Conv | Ablation: tắt từng thành phần (S−Conv chỉ chạy trên T4). S−Filter đưa ràng buộc vào câu truy vấn thay vì lọc; S−Norm lọc bằng ILIKE trên dòng nguyên liệu thô thay vì thẻ chuẩn hóa |
| P-Direct | Đọc trực tiếp các trường có mã (cận trên) |
| P-Vectorless (= S) | Nút cố định đọc bằng code + V2 chọn nút theo ngữ cảnh |
| P-Vectorless-Fixed | Không có nút cố định: mô hình chọn mọi nút |
| P-Vector | RAG vector trên chính hồ sơ (chunk + nomic-embed-text, top-k), mô hình trích ràng buộc |
| S-Profile | Bỏ ràng buộc hồ sơ, chỉ dùng hội thoại |

Nhánh hồ sơ chạy trên hai dạng đầu vào: **coded** (các entry có mã) và **narrative** (các bảng section đổi thành văn bản tự do, mô hình phải tự trích).

### 3.3. Độ đo và cách chấm

- **Vi phạm ràng buộc:** CVR@5 là tỉ lệ công thức vi phạm trong 5 công thức ngữ cảnh; Safe@5 là tỉ lệ lượt mà cả 5 công thức đều sạch.
  - Dị ứng và chế độ ăn được chấm bằng **bộ kiểm độc lập** (`scripts/checker.py`, `llama3.1:8b`). Bộ kiểm đọc toàn văn nguyên liệu và **không import** từ điển hay thẻ của bộ gắn thẻ (có test kiểm tra). Nhờ vậy không có đánh giá vòng tròn.
  - Phiếu "có vi phạm" phải trích một dòng nguyên liệu làm bằng chứng. Dòng không có thật thì bị loại tự động. Phiếu còn lại vào **hàng duyệt mù** của người: CVR adjudicated. Phiếu chưa duyệt được tính là vi phạm.
  - Nguyên liệu có tên được so khớp nguyên từ (có danh sách "false friend", ví dụ oyster mushroom không phải hàu). Thời gian và dinh dưỡng chấm từ cột số.
- **Truy hồi:** pooling top-10 của mọi cấu hình; judge `llama3.1:8b` (khác họ với mô hình sinh) chấm độ liên quan 0/1/2. rel′ = rel × 1[công thức thỏa ràng buộc]. Từ đó tính nDCG@10′, Recall@10, MRR.
- **Sinh:**
  - citation validity và citation safety, tất định cộng bộ kiểm;
  - faithfulness và answer relevance, judge theo kiểu RAGAS;
  - từ chối đúng (T3) và từ chối sai (T1, T2).
- **Hiểu truy vấn:** độ chính xác intent và slot F1 (micro, theo loại và giá trị chuẩn) so với gold.
- **Nhánh hồ sơ:**
  - P/R/F1 của dị ứng, bệnh, thuốc trích được so với đáp án Synthea;
  - số ca bỏ sót dị ứng;
  - Safe@5 theo dị ứng, dinh dưỡng và hội thoại;
  - tỉ lệ chọn đúng nút;
  - chi phí: số lời gọi LLM, số ký tự đọc, độ trễ V1–V3.
- **Độ trễ:** p50/p95 theo từng module, lấy từ `retrieval_trace`.
- **Kiểm của người (Thy, mù):** 50 cặp độ liên quan, 50 câu trả lời, 60 phiếu của bộ kiểm. Từ đó tính Cohen's κ giữa người và judge, và độ chính xác của bộ kiểm.
- **Thống kê:** so sánh ghép cặp theo câu (theo hội thoại với T4, theo bệnh nhân với MV4). Dùng paired bootstrap (95% CI) và Wilcoxon, hiệu chỉnh Holm trong từng họ so sánh.

---

## 4. Kết quả

### 4.1. Bộ test A3 (M6, 363 lượt, 9 cấu hình)

Nguồn: `eval/runs/20261019-093605/a3/table.md`. Phần trong ngoặc vuông là KTC 95%.

| Cấu hình | nDCG@10′ T1 | nDCG@10′ T2 | CVR@5 adj T2 / T4 | Safe@5 | Trích dẫn an toàn | Từ chối đúng T3 | Từ chối sai T1+T2 |
|---|---|---|---|---|---|---|---|
| B0 (A1) | 0,6 | 0,2 | 67,5% / 48,6% | 6% (1/16) | – | – | – |
| B1 | 0,6 | 0,2 | 67,5% / 48,6% | 6% | 63,2% | 2/6 | 2/27 |
| **S** | **0,9** | **0,8** | **2,7% / 5,7%** | **93% (14/15)** | **98,5%** | 4/6 | 1/27 |
| S−QU | 0,6 | 0,2 | 67,5% / 48,6% | 6% | 61,8% | 3/6 | 2/27 |
| S−Filter | 0,9 | 0,4 | 65,3% / 60,0% | 13% | 84,9% | 4/6 | 3/27 |
| S−Norm | 0,9 | 0,8 | 6,7% / 22,9% | 80% | 100% | 5/6 | 1/27 |
| S−Rerank | 0,8 | 0,7 | 2,7% / 5,7% | 93% | 100% | 4/6 | 0/27 |
| S−Verify | 0,9 | 0,8 | 2,7% / 5,7% | 93% | 96,9% | 3/6 | 1/27 |
| S−Conv (T4) | – | – | – / 34,3% | – | 75,0% | – | – |

**So sánh theo từng câu (S trừ cấu hình khác):**

| So sánh | Độ đo | Chênh lệch [KTC 95%] | Wilcoxon (Holm) |
|---|---|---|---|
| S − B0 | CVR@5 adj | −0,602 [−0,749; −0,451] | 0,001 |
| S − B0 | nDCG@10′ | +0,465 [+0,328; +0,594] | 0,001 |
| S − B0, chỉ T1 | nDCG@10′ | +0,256 [+0,018; +0,521] | 0,19 (bootstrap 0,03) |
| S − S−QU | CVR@5 adj | −0,602 | 0,001 |
| S − S−Filter | CVR@5 adj / nDCG@10′ | −0,618 / +0,273 | 0,001 / 0,008 |
| S − S−Rerank | nDCG@10′ | +0,055 [+0,010; +0,109] | 0,092 (bootstrap 0,037) |
| S − S−Norm | CVR@5 adj | −0,049 [−0,144; +0,042] | 1,0 |
| S − S−Verify | mọi độ đo truy hồi | 0 | 1,0 |
| S − S−Conv (T4, n = 4) | CVR@5 adj | −0,200 [−0,400; 0] | 1,0 |

**Hiểu truy vấn:** intent đúng 98% (43/44), slot F1 0,889. Khi tắt hội thoại (S−Conv): 73% và 0,667.

**Đối chiếu người và máy (160 mục Thy chấm):**

| Thành phần | Kết quả |
|---|---|
| Bộ kiểm độc lập | Chính xác 90%, κ = 0,80. Cả 6 chỗ lệch là bộ kiểm báo thừa (mayonnaise là sữa, pancetta là cá, lạc là hạt cây) |
| Judge chấm độ liên quan | κ = 0,30, khớp 54% |
| Judge chấm faithfulness | κ = −0,02 (không dùng được) |
| Faithfulness theo nhãn của Thy | 34/50 câu trả lời bám ngữ cảnh (68%) |

**Hàng duyệt mù của bộ kiểm:** 137 phiếu được xác nhận vi phạm, 54 phiếu bị bác (báo nhầm), 42 phiếu bị loại tự động vì bằng chứng do chính bộ kiểm đánh dấu là không hợp lệ. Không còn phiếu chờ.

**Nhóm lỗi trên S (44 lượt):**

| Nhóm lỗi | Số lượt | Ví dụ |
|---|---|---|
| F7 câu trả lời không bám ngữ cảnh | 34 | "không có sữa" trong khi món có heavy cream; tự gán "chay", "không gluten" |
| F1 trích ràng buộc sai | 7 | |
| F8 từ chối sai | 3 | |
| F3 bộ gắn thẻ sót | 2 | |
| F2 định tuyến sai | 1 | |

**Độ trễ (p50, ms):**

| Cấu hình | M1 | M4 | M5 | M6 TTFT | M6 | Tổng |
|---|---|---|---|---|---|---|
| B0 | – | 144 | 95 | – | – | 239 |
| B1 | – | 86 | 86 | 387 | 1.818 | 2.000 |
| S | 10.890 | 184 | 67 | 9.040 | 10.677 | 21.965 |

M1 và M6 (mô hình 7B chạy cục bộ) chiếm gần hết thời gian. Các cấu hình ablation dùng chung cache M1 với S, nên độ trễ của chúng không so sánh được với nhau.

### 4.2. Nhánh hồ sơ bệnh nhân (MV4, 100 bệnh nhân, 300 câu)

Nguồn: `eval/runs/20261018-132948/patient/table.md`.

**Trích ràng buộc so với đáp án Synthea:**

| Đầu vào | Cấu hình | Dị ứng P / R | Bỏ sót dị ứng (ca / BN) | Bệnh F1 | Thuốc F1 |
|---|---|---|---|---|---|
| coded | P-Direct | 100% / 100% | 0 / 0 | 100% | 100% |
| coded | **P-Vectorless** | **100% / 100%** | **0 / 0** | **100%** | **100%** |
| coded | P-Vectorless-Fixed | 100% / 34,9% | 41 / 12 | 40,4% | 34,2% |
| coded | P-Vector | 29,0% / 14,3% | 54 / 11 | 76,8% | 87,9% |
| narrative | **P-Vectorless** | **81,8% / 85,7%** | **9 / 3** | 48,8% | 78,2% |
| narrative | P-Vectorless-Fixed | 81,8% / 14,3% | 54 / 12 | 9,3% | 0,0% |
| narrative | P-Vector | 100% / 17,5% | 52 / 12 | 16,8% | 43,0% |

**Đầu cuối (top 5):**

| Đầu vào | Cấu hình | Safe@5 dị ứng (adj) | Safe@5 dinh dưỡng | Safe@5 hội thoại (adj) | Chọn nút đúng |
|---|---|---|---|---|---|
| coded | P-Direct | 99% (73/74) | 100% | 86% | – |
| coded | **P-Vectorless** | **99% (73/74)** | **100%** | **86%** | **78%** |
| coded | P-Vectorless-Fixed | 91% | 96% | 84% | 87% |
| coded | P-Vector | 82% | 98% | 84% | 84% |
| coded | S-Profile | 81% | 36% | 80% | – |
| narrative | P-Vectorless | 97% | 100% | 86% | – |
| narrative | P-Vector | 86% | 94% | 83% | – |

- **P-Vectorless so với S-Profile:** Safe@5 dinh dưỡng +0,64 [+0,575; +0,705] (Wilcoxon Holm p < 0,001); Safe@5 dị ứng +0,176 [+0,081; +0,297] (bootstrap p < 0,001, Wilcoxon Holm 0,072).
- **P-Vectorless so với P-Vector:** Safe@5 dị ứng +0,162 [+0,068; +0,284] (bootstrap Holm 0,001).
- **Chi phí (coded, trung bình mỗi lượt, lượt đầu / các lượt sau):**
  - P-Vectorless: 0 / 0,5 lời gọi LLM; V2 47 / 523 ms. Ràng buộc chủ yếu đến từ nút cố định đọc bằng code.
  - P-Vector: 1 lời gọi mỗi lượt; đọc khoảng 2.400 ký tự; V3 2,4–4,8 giây.
  - Với narrative, P-Vectorless tốn 2,1 lời gọi; đọc khoảng 19.500 ký tự; V3 khoảng 16 giây ở lượt đầu, sau đó được lưu đệm.

### 4.3. Độ tin của công cụ đo (M2, 200 công thức có nhãn bạc)

Nguồn: `eval/labels/report_allergen.md`.

- **Bộ gắn thẻ** (dùng để lọc): trên tập holdout (50 công thức), P và R của 9 nhóm dị ứng và hai cờ chế độ ăn hầu hết từ 0,94 đến 1,00. Ngoại lệ là đậu nành: R = 0,40, chỉ có 5 mẫu dương.
- **Bộ kiểm** (dùng để chấm): recall cao ở hầu hết nhóm, precision thấp hơn (trứng 0,75, đậu phộng 0,25). Nghĩa là bộ kiểm có xu hướng báo thừa. Kết quả này khớp với kiểm của người ở M6.

---

## 5. Kết luận

- **RQ1 – Giảm vi phạm mà không giảm chất lượng xếp hạng:**
  - Hiểu truy vấn kết hợp lọc cứng giảm CVR@5 từ 67,5% (A1) xuống 2,7% trên T2, và từ 48,6% xuống 5,7% trên T4.
  - nDCG@10′ trên T2 tăng từ 0,2 lên 0,8, vì rel′ tính cả việc thỏa ràng buộc. S không hồi quy trên T1 (+0,26).
  - Với ràng buộc từ hồ sơ, P-Vectorless đạt Safe@5 dị ứng 99%, ngang mức cận trên P-Direct, và Safe@5 dinh dưỡng 100%. Khi bỏ hồ sơ (S-Profile), hai con số này là 81% và 36%.
- **RQ2 – Thành phần nào đóng góp:**
  - Hai thành phần quyết định là **hiểu truy vấn** và **lọc cứng**. Tắt một trong hai, CVR quay về mức của A1.
  - Rerank cải thiện nhẹ nDCG (+0,055).
  - Chuẩn hóa nguyên liệu có xu hướng giảm vi phạm trong hội thoại, nhưng chưa có ý nghĩa thống kê trên mẫu nhỏ.
  - M7 không đổi chất lượng truy hồi (đúng thiết kế, vì M7 chạy sau truy hồi). M7 chỉ nâng citation safety từ 96,9% lên 98,5%.
- **RQ3 – Câu trả lời có bám ngữ cảnh:** trích dẫn gần như luôn hợp lệ và an toàn (98,5%) nhờ M7. Nhưng **nội dung chữ** của câu trả lời vẫn hay bịa thuộc tính an toàn ("không có sữa", "chay"): Thy đánh giá chỉ 68% câu trả lời bám ngữ cảnh. Đây là điểm yếu lớn nhất (F7, 34/44 lượt lỗi). Từ chối đúng 4/6 câu T3, từ chối sai 1/27.
- **RQ4 – Độ trễ:** S mất khoảng 22 giây mỗi lượt (p50), so với 0,24 giây của A1. Gần như toàn bộ thời gian nằm ở hai lời gọi mô hình 7B chạy cục bộ (M1 khoảng 11 giây, M6 khoảng 10,7 giây). Lọc, truy hồi và rerank chỉ tốn khoảng 0,25 giây.
- **RQ5 – Nhánh vectorless so với đọc trực tiếp và RAG vector:**
  - Trên hồ sơ có mã, vectorless trích đúng 100% dị ứng, bệnh và thuốc như đọc trực tiếp, với trung bình dưới 1 lời gọi LLM mỗi lượt.
  - RAG vector bỏ sót dị ứng ở 11 trên 37 bệnh nhân có dị ứng (recall 14%).
  - Yếu tố quyết định là **nút cố định đọc bằng code**: bỏ nút cố định (P-Vectorless-Fixed) thì recall dị ứng còn 35%.
  - Trên văn bản tự do, vectorless vẫn tốt nhất (recall dị ứng 86%) nhưng còn bỏ sót 9 ca ở 3 bệnh nhân.

---

## 6. Hạn chế

**Dữ liệu và nhãn**

1. **Corpus** chỉ gồm công thức của Mỹ bằng tiếng Anh: hầu như không có món Việt. Thông tin dị ứng suy ra từ nguyên liệu, không phản ánh nhiễm chéo trong chế biến.
2. **Hồ sơ bệnh nhân** là dữ liệu tổng hợp (Synthea, C-CDA), "sạch" hơn bệnh án thật: không lỗi ghi chép, không mâu thuẫn. Kết quả trích ràng buộc nên hiểu là cận trên. Chưa thử FHIR, ghi chú lâm sàng thật hay ghi chú tổng hợp độc lập (Asclepius). Chế độ narrative là văn bản sinh từ chính C-CDA.
3. **Nhãn 200 công thức là nhãn bạc** (Claude gán), không phải nhãn người. Bộ gắn thẻ và người gán cùng họ mô hình, nên P/R của bộ gắn thẻ có thể bị thổi phồng.
4. **Gold của bộ test (V6)** do mô hình soạn, Thy xác nhận; không câu nào bị sửa.

**Công cụ đo**

5. **Judge `llama3.1:8b`** chấm độ liên quan có κ = 0,30 với người, nên nDCG@10′ chỉ là ước lượng thô. Judge faithfulness có κ = −0,02, nên báo cáo dùng nhãn của Thy (50 câu) cho faithfulness.
6. **Bộ kiểm độc lập** báo thừa (precision trên holdout từ 0,25 đến 0,95 tùy nhóm). Đã bù bằng hàng duyệt mù của người. 59 phiếu bộ kiểm lỗi (mô hình trả lời lặp) được tính là không vi phạm; phần lớn nằm trong ngữ cảnh của B0, nên kết luận S − B0 không đổi.

**Quy mô và môi trường thực nghiệm**

7. **Mẫu nhỏ:** M6 chạy khoảng 10% bộ test (T1 10, T2 17, T3 6 câu, T4 4 hội thoại). KTC rộng; nhiều ablation (S−Norm, S−Conv) chỉ là xu hướng, chưa có ý nghĩa sau Holm.
8. **Một máy** (RTX 4060 Laptop 8 GB). Độ trễ các cấu hình ablation bị ảnh hưởng bởi cache M1 dùng chung. Chưa đo độ trễ lặp lại nhiều lần.

**Hệ thống**

9. **Bịa thuộc tính an toàn:** M6 vẫn bịa thuộc tính an toàn trong lời văn. M7 chỉ kiểm trích dẫn, nguyên liệu bị cấm và con số, chưa kiểm các khẳng định kiểu "không có sữa".
10. **Lỗi còn giữ:**
    - parser dấu phẩy của bộ gắn thẻ (một số dòng nhiều nguyên liệu bị đọc sai);
    - M7 báo động nhầm ở vài câu;
    - M6 đôi khi trả lời sai ngôn ngữ;
    - ràng buộc nguyên liệu còn sót lại sau khi gỡ dị ứng hồ sơ.
11. **Bộ luật ánh xạ là quy ước của đồ án:** ngưỡng một bữa = 1/3 ngưỡng ngày, bảng tương tác thuốc nhỏ do nhóm soạn. Bộ luật chưa được chuyên gia y khoa thẩm định. Hệ chỉ hỗ trợ tra cứu, không thay thế tư vấn y tế.
12. **Chưa có `POST /patients/import`:** hồ sơ được nạp offline bằng script.
