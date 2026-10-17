---
status: proposed (MV2, 17/10/2026; chờ duyệt ở gate MV2)
---

# Đọc hồ sơ bệnh nhân theo kiểu vectorless: cây mục lục tất định, chỉ đưa cho LLM nội dung đã qua danh sách cho phép

A3 cần suy ra ràng buộc món ăn (dị ứng thực phẩm, ngưỡng dinh dưỡng theo bệnh, tương tác thuốc – thực phẩm) từ hồ sơ bệnh nhân Synthea dạng C-CDA. Hồ sơ có cấu trúc rõ (section nhận diện bằng LOINC, entry có mã SNOMED, RxNorm, LOINC), nhưng dài (khoảng 480 KB mỗi file) và chứa nhiều dữ liệu nhạy cảm (sàng lọc tâm thần, sử dụng chất, bạo lực, tử vong). Đặc tả: `docs/plan/A3_vectorless_ho_so.md`.

**Quyết định:**
1. **Cây mục lục tất định** (`api/patient/tree.py`), dựng bằng code từ cấu trúc C-CDA, không dùng LLM:
   - nút gốc: giới tính, tuổi;
   - 4 nút cố định: dị ứng, vấn đề đang điều trị, thuốc đang dùng, sinh hiệu gần nhất;
   - nút ngữ cảnh theo năm: xét nghiệm, lần khám.
2. **Ràng buộc chỉ lấy từ nút cố định, bằng bảng luật CSV** (`api/patient/mapping.py`). LLM không quyết định ràng buộc an toàn. Mỗi ràng buộc kèm bằng chứng (`node_id` và `entry_id` của C-CDA).
3. **LLM chỉ làm hai việc, số lần gọi cố định:**
   - viết tóm tắt cho nút ngữ cảnh (V1c, offline, có cache);
   - chọn nút ngữ cảnh khi câu hỏi cần (V2, tối đa 1 lần gọi mỗi lượt).
4. **Danh sách cho phép cho prompt** (`api/patient/prompt_view.py`, Thy, gate MV1). Chỉ nội dung đã qua một bảng luật mới được đưa cho LLM:
   - dị ứng thực phẩm có luật;
   - bệnh có dòng trong `condition_nutrient.csv`;
   - thuốc khớp `drug_food.csv`;
   - sinh hiệu trong `prompt_vitals.csv`;
   - organizer trong `include_loinc.csv`;
   - lần khám chỉ ở dạng loại chung (`encounter_class.csv`).

   Cây trong DB vẫn đầy đủ. `exclude_loinc.csv` và `exclude_codes.csv` giữ lại để thống kê P7 và làm test.

## Lý do

- C-CDA có mã, nên đọc bằng code thì tái lập được và kiểm được bằng test. Embedding và top-k trên văn bản hồ sơ (phương án `P-Vector`) có thể bỏ sót đúng entry dị ứng cần thiết.
- **Danh sách loại trừ luôn có thể bỏ sót.** Ở MV1, sau khi đã có `exclude_loinc.csv`, vẫn còn các mục lọt qua: chẩn đoán "Dependent drug abuse", lần khám cai nghiện, thuốc buprenorphine/naloxone. Tên lần khám cũng tự tiết lộ bệnh ("Asthma follow-up", "Prenatal visit"). Danh sách cho phép đóng các lỗ này theo mặc định.
- Rượu là trường hợp duy nhất mà mục nhạy cảm lại có hệ quả với món ăn. Hệ thống không suy ra ràng buộc "tránh rượu", vì bằng chứng hiện trên giao diện sẽ để lộ chẩn đoán. Điều này được ghi vào phần hạn chế của báo cáo.

## Các phương án đã xét

- **Cho LLM đọc cả hồ sơ, hoặc mọi nút:** tốn token, khó kiểm chứng, và lộ dữ liệu P7.
- **Chỉ dùng danh sách loại trừ:** đã bỏ sót trong thực tế (xem trên).
- **Vòng lặp agent tự duyệt cây:** loại, vì với mô hình 7B thì khó kiểm soát số lần gọi và độ trễ.

## Hệ quả

- Thêm một bệnh, thuốc hay loại lần khám vào prompt nghĩa là thêm một dòng luật, có `version` và có người duyệt.
- Các preset `P-Vectorless-Fixed` và `P-Vector` (MV4) dùng chung `prompt_view`, nên phép so sánh không bị lệch do khác dữ liệu đầu vào.
