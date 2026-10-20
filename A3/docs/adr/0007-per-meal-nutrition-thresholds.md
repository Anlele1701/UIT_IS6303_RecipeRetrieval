---
status: accepted (Thy, 17/10/2026, sau khi ghi số liệu và lựa chọn luật mềm)
---

# Quy đổi ngưỡng dinh dưỡng theo ngày sang ngưỡng một khẩu phần, lọc trong index, và luật mềm cho luật quá chặt

Các khuyến nghị (WHO, DASH, ADA, KDIGO) cho ngưỡng **theo ngày**, còn `recipe_nutrition` ghi giá trị **theo khẩu phần**. M4 phải lọc công thức theo ngưỡng của bệnh nhân **trước khi xếp hạng**, cùng nguyên tắc với ADR-0001 và ADR-0005. Luật nằm trong `data/rules/condition_nutrient.csv`, phép quy đổi nằm ở `api/patient/nutrition.py`.

**Quyết định:**
1. **Ngưỡng tuyệt đối (mg, g):** ngưỡng một khẩu phần = ngưỡng ngày × `PER_MEAL_FRACTION`. Mặc định là 1/3, cấu hình trong `api/config.py`. Ví dụ natri 2.000 mg/ngày thành 666,67 mg/khẩu phần.
2. **Ngưỡng theo phần năng lượng:** tính trên calo của chính công thức, không chia 3.
   - `sat_fat_pct_kcal = saturated_fat_g × 9 / calories × 100`
   - `sugar_pct_kcal = sugars_g × 4 / calories × 100`
   - `fiber_per_1000kcal = dietary_fiber_g / calories × 1000`
3. **Ngưỡng theo kg:** `protein_g ≤ 0,8 × cân nặng × PER_MEAL_FRACTION`.
   - Cân nặng là `29463-7` mới nhất trong hồ sơ.
   - Không có cân nặng, hoặc đo cách ngày hồ sơ hơn 2 năm, thì luật thành cảnh báo.
4. **Nhiều luật cùng một chất:** lấy ngưỡng chặt nhất. Bằng chứng vẫn giữ mọi luật, kể cả luật bị lấn át (ví dụ natri 2.300 mg của DASH và ADA bị lấn át bởi 2.000 mg của WHO).
5. **Hai luật trái chiều trên cùng một chất** (một `max`, một `min`): không lọc chất đó, chỉ sinh cảnh báo.
6. **Chất không có cột** (phospho): luật tự chuyển thành cảnh báo khi nạp, và được ghi vào `rules_log`. Ngược lại, luật lọc trỏ tới một cột lẽ ra phải có trên `chunk` mà không thấy, thì nạp luật sẽ báo lỗi.
7. **Cột dẫn xuất trên `chunk`** (migration 006): `sat_fat_pct_kcal`, `sugar_pct_kcal`, `fiber_per_1000kcal`, `potassium_mg`.
   - Kiểu `real`, được đưa vào `chunk_search_idx`.
   - Điền bằng `ingest.py retag <strategy>`, giữ nguyên embedding và id.
   - Calo bằng null hoặc 0 thì cột tỉ lệ là null.
   - Với ràng buộc `max`, công thức có giá trị null bị loại khi `unknown_strict` bật, và được giữ kèm cảnh báo khi tắt.
8. **Ngưỡng lưu ở dạng chính xác**, không làm tròn. Bản đầu làm tròn 666,67 và để lọt 2 công thức có natri nằm giữa 666,667 và 666,67. Chỉ làm tròn khi hiển thị.
9. **Luật dinh dưỡng để lại dưới 50% kho công thức thì chuyển thành luật mềm** (`mode = soft`, Thy, 17/10/2026):
   - Luật mềm **không lọc**. Profile ghi nó vào `nutrient_soft` (tách khỏi `nutrient_limits`), kèm một cảnh báo và bằng chứng `soft:<cột>`.
   - **Xếp hạng (làm ở MV3, bước M5):** sau rerank, công thức đạt mọi luật mềm được đưa lên trước, công thức không đạt xuống sau (sắp xếp ổn định, giữ thứ tự rerank trong mỗi nhóm). Công thức không đạt vẫn có thể được trả về, và thẻ của nó ghi giá trị của chất đó để M6 nêu rõ.
   - **Ngưỡng 50% tính trên chính luật đó**, đo trên toàn kho (32.719 công thức). Có test chặn (`test_every_hard_nutrient_rule_leaves_at_least_half_of_the_recipes`): mọi luật `filter` phải ≥ 50%.
   - **Không áp cho dị ứng và nguyên liệu bị loại.** Đó là luật an toàn, luôn cứng, kể cả khi để lại dưới 50% kho (sữa 40,1%, lúa mì 46,6%).

## Lý do

- Chia 3 là giả định đơn giản và minh bạch (ba bữa chính), dễ đổi qua cấu hình và dễ nêu trong báo cáo.
- Ngưỡng theo phần năng lượng không phụ thuộc kích thước khẩu phần, nên không cần quy đổi.
- Dữ liệu chỉ có **đường tổng**, không có đường tự do như WHO quy định. Lọc theo đường tổng sẽ loại oan món có trái cây (43,5% công thức trượt), nên luật này chỉ dùng để cảnh báo.
- Một luật dinh dưỡng loại hơn nửa kho thì biến hệ thống thành bộ lọc quá hẹp. Khi cộng thêm ràng buộc trong câu hỏi (món chay, dưới 30 phút…), nhiều câu sẽ không còn công thức nào (vi phạm quy tắc V7). Chất béo bão hòa và chất xơ là khuyến nghị cho cả chế độ ăn trong ngày, không phải ngưỡng an toàn cho từng món, nên hợp với vai trò ưu tiên hơn là chặn.

## Số đo

Nguồn: `eval/patient_corpus.json` (`nutrient_rule_pass`) và `eval/patient_profiles.json` (`rule_pass_rates`, `patient_pass_spread`, `per_patient`). Tỉ lệ tính trên công thức có đủ số liệu, trên toàn bộ 32.719 công thức.

### Từng luật

| Luật | Ngưỡng / khẩu phần | Tỉ lệ qua | Chế độ |
|---|---:|---:|---|
| Natri, mặc định và CKD (2.000 mg/ngày) | ≤ 666,67 mg | 68,9% | filter |
| Natri, tăng huyết áp và tiểu đường (2.300 mg/ngày, bị lấn át) | ≤ 766,67 mg | 73,7% | filter |
| Protein, CKD 3–4 (0,8 g/kg; nặng 60 / 70 / 80 kg) | ≤ 16,0 / 18,7 / 21,3 g | 63,5% / 68,0% / 72,8% | filter |
| **Chất béo bão hòa, tăng huyết áp** | ≤ 6% năng lượng | **17,2%** | **soft** (từ v2) |
| **Chất xơ, tiểu đường type 2** | ≥ 14 g/1000 kcal | **23,2%** | **soft** (từ v2) |
| Đường tổng, mặc định | ≤ 10% năng lượng | 56,5% | warn |
| Kali, phospho (CKD 3–4) | – | – | warn |

Luật an toàn (luôn cứng):
- Theo nhóm dị ứng: sữa 40,1%; lúa mì 46,6%; trứng 65,4%; cá 87,3%; hạt cây 89,3%; đậu nành 93,1%; giáp xác 93,4%; mè 96,4%; đậu phộng 97,3%.
- Nguyên liệu bị loại: nhuyễn thể (Shellfish) 97,7%; bưởi chùm 99,9%.

### Tổ hợp theo bệnh (ngưỡng chặt nhất cho mỗi chất)

| Bệnh | Chỉ luật cứng (v2) | Nếu luật mềm cũng lọc (như v1) |
|---|---:|---:|
| Mặc định | 68,9% | 68,9% |
| Tăng huyết áp | 68,9% | 12,6% |
| Tiểu đường type 2 | 68,9% | 16,6% |
| CKD giai đoạn 3–4 (70 kg) | 56,9% | 56,9% |

### Tổ hợp cho từng bệnh nhân (100 người còn sống: dị ứng, nguyên liệu bị loại và ngưỡng dinh dưỡng của họ)

| | Mọi luật đều cứng (v1) | Luật mềm (v2) |
|---|---:|---:|
| Thấp nhất | 5,5% | 18,4% |
| Phân vị 10 | 12,6% | 64,7% |
| Trung vị | 68,9% | 68,9% |
| Số bệnh nhân dưới 50% kho | 25 | **6** |
| Số bệnh nhân dưới 25% kho | 22 | 2 |

Ở v2, cả 6 bệnh nhân dưới 50% đều do **dị ứng**, không phải do luật dinh dưỡng. Ví dụ: một người dị ứng trứng, sữa, đậu nành còn 18,4%; một người dị ứng giáp xác, trứng, hạt cây, lúa mì còn 22,5%. Số v1 lấy từ cột `hard_and_soft` của `per_patient`: luật mềm của v2 chính là các luật cứng của v1.

## Hệ quả

- `PatientProfile` có thêm `nutrient_soft`. M4 chỉ lọc theo `nutrient_limits`; M5 xếp hạng theo `nutrient_soft` (MV3).
- Quy tắc V7 (mỗi câu hỏi gắn hồ sơ còn ≥ 1 công thức thỏa) vẫn phải kiểm khi dựng bộ câu hỏi ở MV4, nhất là với 6 bệnh nhân có nhiều dị ứng.
- `PER_MEAL_FRACTION` nằm trong cấu hình, không nằm trong file luật, nên đổi giá trị này không làm đổi `ruleset_version`. Vì vậy `settings.json` của mỗi run phải ghi giá trị này.
- Đổi một luật giữa `filter` và `soft` là đổi file luật, nên làm đổi `ruleset_version` và vô hiệu cache profile.
