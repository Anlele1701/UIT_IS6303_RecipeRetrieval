# So sánh nhánh B: tree navigation và dense retrieval trên hồ sơ bệnh nhân

Ngày chạy: 2026-10-18. Số liệu gốc: `eval/ehr_runs/20261018-001728/` (`patients.jsonl`, `summary.md`, `config.json`). Phép đo dense không cần LLM chạy trước đó ở `eval/ehr_runs/20261017-221608/`.

## 1. Câu hỏi và cách đo

**Câu hỏi:** nếu hồ sơ bệnh nhân chỉ có dạng văn bản (không có bảng SQL), phương pháp nào đọc lại đúng danh sách **bệnh đang active** tốt hơn?

- **SQL (nhánh A)** là đường chạy thật của `/recommend`. Nó đọc thẳng bảng `ehr.condition` nên là đáp án chuẩn, không phải đối thủ.
- **Tree (vectorless)**: LLM chỉ xem mục lục (id, tiêu đề, số dòng, số ký tự), chọn tối đa 4 mục, đọc các mục đó rồi liệt kê bệnh. Không dùng embedding.
- **Dense (baseline)**: cắt tài liệu thành mảnh cố định ~800 ký tự (không nhìn tiêu đề), embed bằng `nomic-embed-text`, lấy 4 mảnh gần câu hỏi cố định nhất, đưa cho LLM liệt kê bệnh.
- Cả hai dùng chung model `qwen2.5:7b` và cùng bước trích xuất, nên khác biệt đến từ cách **chọn phần văn bản cần đọc**.
- Không phương pháp nào ở đây quyết định Filter. Chỉ SQL làm việc đó.

**Mẫu:** 60 bệnh nhân (20 mỗi nhóm độ dài: ngắn, vừa, dài), seed 603. Độ dài tài liệu trên cả 1000 bệnh nhân: median 7.661 ký tự (~1.9k token), p90 27.428, max 319.471.

**Chỉ số (mỗi bệnh nhân):** T = mã bệnh active theo SQL, S = mã chỉ xuất hiện ở dạng đã khỏi, P = mã mô hình báo.
- recall = |P∩T| / |T|, precision = |P∩T| / |P|.
- leak = |P∩S|: bệnh đã khỏi nhưng bị báo là đang active.
- invented = mã mô hình đưa ra nhưng không có trong đoạn đã đọc (bị loại và đếm riêng).
- Số tổng hợp gộp mã của mọi bệnh nhân (không lấy trung bình theo bệnh nhân).

## 2. Kết quả chính

| | Tree | Dense |
|---|---|---|
| Recall (tất cả) | **0,614** | 0,424 |
| Precision | 1,000 | 0,986 |
| Exact (đúng hoàn toàn) | 0,167 (10/60) | 0,183 (11/60) |
| Bệnh đã khỏi bị báo là active | 0 | 5 mã ở 2 bệnh nhân |
| Mã bịa | 0 | 0 |
| Ký tự đọc / tài liệu | ~1.088 (~10%) | ~3.037 (~40%) |
| Số lần gọi LLM | 2 | 1 |
| Thời gian median | ~31 s | ~31 s |

### Theo độ dài tài liệu

| Nhóm | Tree recall | Dense recall |
|---|---|---|
| Ngắn | 0,619 | 0,538 |
| Vừa | **0,743** | 0,577 |
| Dài | **0,515** | 0,248 |

Dense giảm mạnh khi tài liệu dài vì 4 mảnh × 800 ký tự chỉ bao phủ một phần nhỏ (ở nhóm dài khoảng 16% tài liệu). Tree giảm ít hơn vì nó đọc đúng mục `active_conditions`, bất kể độ dài.

### Đo thêm: dense chỉ xét việc lấy đoạn (không LLM)

Phép đo trước đó chỉ xem 4 mảnh có chứa bệnh nào, chưa cho LLM đọc:

| Nhóm | Bệnh active có trong mảnh | Bệnh đã khỏi có trong mảnh | Đủ mọi bệnh active |
|---|---|---|---|
| Ngắn | 0,964 | 0,974 | 0,95 |
| Vừa | 0,776 | 0,98 | 0,55 |
| Dài | 0,438 | 0,795 | 0,05 |
| Tất cả | 0,673 | 0,905 | 0,517 |

Hai điều rút ra: mảnh lấy về chứa nhiều bệnh đã khỏi chẳng kém bệnh active (độ gần ngữ nghĩa không phân biệt trạng thái), và ở tài liệu dài chỉ 5% bệnh nhân được lấy đủ bệnh active.

## 3. Phân tích

**Tree thắng dense ở recall, nhất là tài liệu vừa và dài.** Chênh lệch ở nhóm dài là 0,515 so với 0,248. Tree còn đọc ít hơn (~10% so với ~40% tài liệu) và không báo nhầm bệnh đã khỏi.

**Dense có rò rỉ bệnh đã khỏi, tree thì không.** Cả 5 mã bị báo nhầm đều ở tài liệu dài (2 bệnh nhân). Điều này quan trọng vì một Filter dựng từ bệnh đã khỏi sẽ siết quá mức cho bệnh nhân. Mẫu nhỏ nên chưa kết luận chắc, nhưng hướng đi rõ.

**Điều hướng của tree gần như không bị thử thách.** Tree chọn đúng mục `active_conditions` ở 60/60 bệnh nhân. Recall chỉ 0,61 vì **bước trích xuất** bỏ sót, không phải vì chọn sai mục. Cách bố cục tài liệu (đã tách sẵn mục active) làm bước điều hướng quá dễ.

**Bỏ sót nhiều ở các mã không phải "disorder".** Recall theo loại mã (theo nhãn trong ngoặc của mô tả SNOMED):

| Loại | Tree | Dense |
|---|---|---|
| disorder (329 mã) | **0,77** | 0,42 |
| finding (416 mã) | 0,51 | 0,44 |
| situation (81 mã) | 0,54 | 0,38 |

Recall theo nhóm độ dài, chỉ tính disorder: tree 0,77 / 0,96 / 0,65 (ngắn / vừa / dài), dense 0,62 / 0,62 / 0,24. Giả thuyết của mình: lời nhắc hỏi về "medical conditions" khiến mô hình bỏ qua các finding và situation mang tính xã hội (ví dụ tình trạng việc làm, học vấn). **Chưa kiểm chứng**, cần chạy lại với lời nhắc rộng hơn mới biết.

### Tác động tới các rule ăn uống

Chỉ những mã có trong `api/dietary_rules.json` mới ảnh hưởng tới Filter.

| | Tree | Dense |
|---|---|---|
| Mã thuộc rule tìm được | 198/262 (0,76) | 90/262 (0,34) |
| Bệnh nhân tìm đủ mọi mã thuộc rule | 35/57 | 18/57 |

57 là số bệnh nhân trong mẫu có ít nhất một mã thuộc rule. Với tree, khoảng 4 trên 10 bệnh nhân vẫn sẽ thiếu ít nhất một Filter nếu dùng nó thay SQL. Đây là lý do SQL phải là đường an toàn.

## 4. Ví dụ một bệnh nhân

Apolonia Batz (`3a2ceef0-61b8-776b-eb52-2a808d2ee837`), tài liệu 3.091 ký tự, 8 bệnh active theo SQL:

- **Tree:** chọn `active_conditions`, đọc 590 ký tự, tìm 7/8 (thiếu `224299000`), không báo nhầm.
- **Dense:** lấy 4 trong 5 mảnh (3.029 ký tự, gần như cả tài liệu), nhưng LLM chỉ liệt kê 1/8 bệnh. Ví dụ này cho thấy lỗi của dense ở đây không phải thiếu đoạn mà nằm ở bước trích xuất từ ngữ cảnh gồm các mảnh bị cắt không theo mục. Nguyên nhân cụ thể mình chưa kiểm tra.

## 5. Hạn chế (phải nêu khi báo cáo)

1. **Tree là bản tự viết, kiểu PageIndex, không phải thư viện PageIndex.** Cây dựng từ tiêu đề Markdown bằng code, mục lục không có tóm tắt từng nút, chỉ duyệt một vòng. PageIndex đầy đủ chưa được thử.
2. **Bố cục thuận lợi cho tree.** Tài liệu dựng từ bảng, đã có mục `active_conditions` riêng và ngắn gọn hơn hồ sơ văn bản thực. Lợi thế của điều hướng cây trên văn bản tự do dài chưa được kiểm chứng ở đây.
3. **Mẫu nhỏ, một lần chạy, một seed.** 60 bệnh nhân, mỗi nhóm 20. Không có khoảng tin cậy. Chênh lệch nhỏ (ví dụ exact 0,167 so với 0,183) không có ý nghĩa.
4. **Một model, một lời nhắc.** Kết quả gắn với `qwen2.5:7b` và lời nhắc hiện tại. Dense dùng k=4 và 800 ký tự; tăng k sẽ đổi kết quả (đổi lại đọc nhiều hơn).
5. **Thời gian không so sánh được.** Dense và tree cùng median ~31 s nhưng chạy tuần tự trên máy cá nhân, bị ảnh hưởng bởi lượt chạy nền và việc tải model.
6. **Đã sửa một lỗi định dạng trước khi có số liệu tree.** Lần chạy đầu tree báo "mô hình không chọn mục nào tồn tại" vì qwen chép cả dấu ngoặc vuông (`"[active_conditions]"`). Hàm `parse_sections` nay làm sạch ngoặc, dấu nháy và backtick trước khi đối chiếu id, và lời nhắc đã dặn viết id không có ngoặc. Đây là sửa cách đọc kết quả, không đổi cách mô hình chọn mục.

## 6. Kết luận

- Với hồ sơ có cấu trúc như ở đây, **SQL vẫn là lựa chọn đúng cho `/recommend`**: recall 1,0 theo định nghĩa, không tốn lần gọi LLM, và ảnh hưởng trực tiếp tới an toàn của Filter.
- Trong hai cách đọc văn bản, **tree tốt hơn dense** ở recall (0,614 so với 0,424), nhất là tài liệu dài, đồng thời đọc ít hơn và không báo nhầm bệnh đã khỏi. Kết luận này đúng trong điều kiện bố cục thuận lợi nêu ở mục 5.
- Cả hai đều **chưa đủ tin cậy để thay SQL** (tree vẫn thiếu mã rule ở 22/57 bệnh nhân). Nếu sau này hồ sơ chỉ có dạng văn bản, cần cải thiện bước trích xuất trước khi dùng cho Filter.

## 7. Việc có thể làm tiếp

- Chạy lại tree và dense với lời nhắc trích xuất rộng hơn (gồm finding và situation) để kiểm tra giả thuyết ở mục 3.
- Thêm PageIndex thật làm phương pháp thứ ba trên cùng 60 bệnh nhân, nếu chạy được với model local.
- Chạy nhiều seed hoặc nhiều bệnh nhân hơn để có khoảng tin cậy.
- Thử một phiên bản tài liệu **không tách sẵn** mục `active_conditions` để thử thách bước điều hướng.

## 8. Cách chạy lại

```
uv run scripts/render_ehr_documents.py
uv run scripts/evaluate_ehr_retrieval.py --per-stratum 20 --seed 603
uv run scripts/evaluate_ehr_retrieval.py --retrieval-only   # chỉ dense, không cần model chat
```

Cần Ollama chạy `nomic-embed-text` và `qwen2.5:7b`. Một lần chạy 60 bệnh nhân với cả hai phương pháp mất khoảng 1 giờ 20 phút trên máy này.
