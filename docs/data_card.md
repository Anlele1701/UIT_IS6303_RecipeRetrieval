# Data Card – A3

Sinh tự động bởi `scripts/make_cards.py`. Không sửa tay. Mọi số đếm lấy từ JSON do pipeline ghi.

## 1. Kho công thức (quy tắc D-x, `eval/corpus.json`)

Nguồn: Shengtao/recipe, công thức nấu ăn của Mỹ bằng tiếng Anh. Chạy lúc 2026-10-17T21:33:04, commit `f2f8100`, 9,6 giây.

| Mã | Quy tắc | Số đếm |
|---|---|---|
| D1 | Loại dòng trùng URL với một dòng trước đó | 3 dòng trùng URL bị loại; còn 32.719 công thức |
| D2 | Bỏ cột dinh dưỡng rỗng trên 99% | 13 cột bị bỏ |
| D3 | Đổi thời gian ("1 hr 10 mins") ra phút; null khi rỗng hoặc không đọc được | prep_time: 1.986 null; cook_time: 6.663 null; total_time: 1.859 null |
| D4 | Tách dòng nguyên liệu thành số lượng, đơn vị, tên, ghi chú (theo luật) | 311.060 dòng; ok 96,5%, partial 3,5%, fail 57 |
| D5 | Ánh xạ tên về nguyên liệu chuẩn (từ đồng nghĩa dài nhất trước) | 2.005 nguyên liệu chuẩn; độ phủ dòng 99,3% |
| D6 | Gắn 9 nhóm dị ứng FDA cho nguyên liệu chuẩn: chắc chắn (trực tiếp hoặc ẩn) thì lọc, có thể (tùy nhãn hiệu) thì chỉ cảnh báo | milk 19.590; egg 11.322; fish 4.143; crustacean_shellfish 2.146; tree_nuts 3.506; peanut 876; wheat 17.459; soy 2.269; sesame 1.178 |
| D6b | Dòng ghi rõ không chứa X (gluten-free, dairy-free, vegan…) không mang nhóm X | 128 dòng ở 118 công thức |
| D7 | Chay: không có nhóm động vật, cá, giáp xác; thuần chay: thêm không sữa, trứng, mật ong | chay 16.687 (51,0%), thuần chay 4.140 (12,7%) |
| D8 | Dòng không ánh xạ được là unknown; mặc định không đổi thẻ | 2.244 dòng unknown ở 2.001 công thức (6,1%) |

Dị ứng theo 9 nhóm FDA; thẻ "chắc chắn" (trực tiếp hoặc thành phần ẩn) được lọc, thẻ "có thể" (phụ thuộc nhãn hiệu) chỉ được cảnh báo. Thông tin dị ứng suy ra từ nguyên liệu, không phản ánh nhiễm chéo.

## 2. Hồ sơ bệnh nhân (quy tắc P-x, `eval/patient_corpus.json`)

Nguồn: tài liệu C-CDA R2.1 sinh bằng Synthea: `sample`; `generated`. Dữ liệu tổng hợp, không có bệnh án thật.

| Mã | Quy tắc | Số đếm |
|---|---|---|
| P1 | Nạp mọi tài liệu C-CDA | 120 file, parse được 120; còn sống 112, đã mất 8 |
| P2 | Chỉ giữ dị ứng và vấn đề đang hiệu lực | dị ứng giữ 114; vấn đề bỏ 4.019 |
| P3 | Dị ứng thực phẩm (SNOMED 414285001), ánh xạ về 9 nhóm | 21 mục |
| P4 | Vấn đề: chỉ giữ loại (disorder) | giữ 411; bỏ (finding) 604, (situation) 130 |
| P5 | Thuốc đang dùng | 392 đang dùng; 8.777 đã ngừng |
| P6 | Sinh hiệu gần nhất, xét nghiệm, lần khám | 925 chỉ số sinh hiệu; 5.651 nhóm xét nghiệm; 8.013 lần khám |
| P7 | Không đưa vào ngữ cảnh mô hình: sức khỏe tâm thần, chất gây nghiện, bạo lực, định danh | 2.149 nhóm sàng lọc tâm thần; 1.083 nhóm chất gây nghiện; 483 nhóm bạo lực; trường định danh không đọc ở 120 hồ sơ |

P8 (chọn bệnh nhân phân tầng) và báo cáo đầy đủ: `docs/patient_corpus_report.md`.

## 3. Bộ test A3 (quy tắc V-x, `eval/testset/testset_flow.json`)

Sinh lúc 2026-10-19T08:27:57, seed 42; diễn đạt lại bằng `llama3.1:8b` (khác họ với mô hình hiểu truy vấn); bộ kiểm V2 `llama3.1:8b`.

| Tập | Sinh ra | V1 | V2 | V3 | V4 | V5 | Còn lại | Bớt khi cắt về chỉ tiêu | Sau V6 |
|---|---|---|---|---|---|---|---|---|---|
| T1 hồi quy (từ bộ truy vấn A1) | 150 | 0 | 0 | 0 | 0 | 0 | 150 | 50 | 105 |
| T2 ràng buộc một lượt | 240 | 0 | 4 | 0 | 48 | 0 | 188 | 38 | 172 |
| T3 không trả lời được | 98 | 0 | 34 | 0 | 0 | 0 | 64 | 14 | 55 |
| T4 hội thoại nhiều lượt | 65 | 0 | 3 | 0 | 22 | 0 | 40 | 0 | 40 |

- Câu viết tay của nhóm: 32 câu, giữ 32 (5 cảnh báo V3: không dấu hoặc trộn ngôn ngữ, vẫn giữ).
- V6 (xác nhận gold): Claude drafted (eval/labels/testset_review_draft.csv, reviewer claude-draft); Thy confirmed. Xác nhận từng câu 144 câu trong 32 giây; chấp nhận hàng loạt 228 câu; bản nháp bị sửa 0.
- Đóng băng lúc 2026-10-19T08:39:23.

## 4. Bộ câu hỏi hồ sơ bệnh nhân (`eval/patient/queries_summary.json`)

- 100 bệnh nhân, 300 câu: no_constraint 100, added_constraint 100, needs_context 100; tiếng Việt 151, tiếng Anh 149.
- V7: tập ràng buộc gold = ràng buộc lấy từ trường có mã của Synthea ∪ ràng buộc trong câu; ít nhất 3.584 công thức thỏa ở câu chặt nhất.
- Kiểm tay bước lấy đáp án: 20 bệnh nhân (`eval/patient/manual_check.csv`).

## 5. Nhãn

- 200 công thức có nhãn dị ứng và chế độ ăn là **nhãn bạc** (Claude Sonnet gán mù theo hướng dẫn của nhóm; `eval/labels/report_allergen.md`), không có nhãn vàng do người gán.
- Hàng duyệt mù của bộ kiểm (`eval/labels/checker_adjudication.csv`): người gán là Thy.
- Kiểm của người M6 (`eval/labels/human_check.csv`): 160 mục, người gán là Thy.
