---
status: proposed (MV2, 17/10/2026; chờ duyệt ở gate MV2)
---

# Quy đổi ngưỡng dinh dưỡng theo ngày sang ngưỡng một khẩu phần, và lọc ngay trong index

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

## Lý do

- Chia 3 là giả định đơn giản và minh bạch (ba bữa chính), dễ đổi qua cấu hình và dễ nêu trong báo cáo.
- Ngưỡng theo phần năng lượng không phụ thuộc kích thước khẩu phần, nên không cần quy đổi.
- Dữ liệu chỉ có **đường tổng**, không có đường tự do như WHO quy định. Lọc theo đường tổng sẽ loại oan món có trái cây (43,5% công thức trượt), nên luật này chỉ dùng để cảnh báo.

## Số đo (`eval/patient_corpus.json`, `nutrient_rule_pass`, trên 32.719 công thức)

Tỉ lệ công thức qua từng luật:

| Luật | Tỉ lệ qua |
|---|---:|
| Natri ≤ 667 mg | 68,9% |
| Chất béo bão hòa ≤ 6% năng lượng | 17,2% |
| Chất xơ ≥ 14 g/1000 kcal | 23,2% |
| Protein ≤ 18,7 g (70 kg) | 68,0% |

Gộp theo bệnh: tăng huyết áp 12,6%, tiểu đường type 2 16,6%, CKD giai đoạn 3/4 56,9%.

## Hệ quả

- Chất béo bão hòa và chất xơ thu hẹp kho công thức mạnh. Quy tắc V7 (mỗi câu hỏi gắn hồ sơ còn ≥ 1 công thức thỏa) phải được kiểm khi dựng bộ câu hỏi ở MV4.
- `PER_MEAL_FRACTION` nằm trong cấu hình, không nằm trong file luật, nên đổi giá trị này không làm đổi `ruleset_version`. Vì vậy `settings.json` của mỗi run phải ghi giá trị này.
