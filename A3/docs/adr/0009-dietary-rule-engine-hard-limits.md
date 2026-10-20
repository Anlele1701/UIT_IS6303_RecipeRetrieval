---
status: proposed (21/10/2026, chờ xác nhận)
---

# Giới hạn cứng của Dietary Rule Engine được ghép vào profile cùng luật CSV, lấy số chặt hơn

Có hai bộ luật biến bệnh thành ngưỡng dinh dưỡng trên một khẩu phần: bảng CSV của A3 (`data/rules/condition_nutrient.csv`, ADR-0007) và Dietary Rule Engine từ nhánh `feature/health-record-vectorless-rag` (`api/patient/dietary_rules.py`, `dietary_rules.json`). Trước quyết định này chat chỉ dùng CSV.

**Quyết định (hướng lai):**
1. **Giới hạn cứng lấy thêm từ engine.** `build_profile` chạy engine trên các bệnh trong `problems.active`. Mỗi `max_<cột>` của engine vào `nutrient_limits`. Nếu CSV đã giới hạn cột đó thì lấy **số chặt hơn**.
2. **Bằng chứng giữ cả hai bên**, kể cả luật bị lấn át (ADR-0007 mục 4). Bằng chứng của engine có dạng `<bệnh> – <rule_id> (<status>)` và trỏ tới nút `problems.active` cùng `entry_id` của bệnh. Nguồn đầy đủ nằm trong `dietary_rules.json` và `GET /patients/{id}/diet-plan`.
3. **Một `max` của engine gặp một `min` của CSV trên cùng một cột:** không lọc cột đó, sinh cảnh báo (ADR-0007 mục 5).
4. **Phần còn lại vẫn thuộc CSV:** luật mềm, cảnh báo, chỉ số theo tỉ lệ (chất béo bão hòa % năng lượng, chất xơ trên 1.000 kcal), đạm theo cân nặng, bệnh `unmapped`.
5. **Không đưa vào profile:** giới hạn engine không lọc được (chất béo bão hòa tính bằng g) và bệnh engine ghi `unsupported` (gút, CKD, béo phì). Chúng vẫn nằm trong `/diet-plan`. CSV đã có luật chất béo bão hòa theo % năng lượng và luật CKD.
6. **`ruleset_version` gồm cả `dietary_rules.json` và `MEALS_PER_DAY`**, nên cache profile cũ không bị dùng lại.
7. **Cột mới đi qua pipeline:** `calories`, `fat_g`, `carbohydrates_g` được thêm vào `NUTRIENT_COLUMNS` (M4), `COLUMN_SQL` (M5, M7, đếm tỉ lệ qua), nhãn M6 và nhãn giao diện. Một test kiểm mọi chất engine có thể lọc đều được pipeline biết.
8. **Làm tròn:** engine làm tròn xuống 0,1 (666,6), CSV giữ nguyên số lẻ (ADR-0007 mục 8). Làm tròn xuống chỉ chặt hơn, không để lọt công thức.

## Số đo

Trên 32.719 công thức, tỉ lệ qua của từng giới hạn (ADR-0007 mục 9 đòi ≥ 50% cho luật cứng):

| Giới hạn của engine | Một khẩu phần | Tỉ lệ qua |
|---|---:|---:|
| Natri, tăng huyết áp (AHA 1.500 mg/ngày) | ≤ 500 mg | 58,8% |
| Natri, suy tim (2.000 mg/ngày) | ≤ 666,6 mg | 68,9% |
| Carbohydrate, tiểu đường (180 g/ngày) | ≤ 60 g | 90,6% |

Test `test_every_hard_limit_of_the_diet_rules_leaves_at_least_half_of_the_recipes` đo lại điều này trên DB thật mỗi khi chạy, nên sửa `daily` quá chặt trong file luật sẽ bị chặn.

Trên 100 bệnh nhân còn sống, tỉ lệ công thức còn lại sau mọi luật cứng:

| | Chỉ CSV | CSV và engine |
|---|---:|---:|
| Số bệnh nhân có giới hạn thay đổi | – | 20 |
| Phân vị 10 | 64,7% | 54,6% |
| Trung vị | 68,9% | 68,9% |
| Số bệnh nhân dưới 50% | 6 | 7 |
| Số bệnh nhân dưới 25% | 2 | 2 |

Bệnh nhân thứ 7 dưới 50% có natri, carbohydrate và đạm (CKD): 58,6% xuống 48,1%. Sáu người còn lại vẫn do dị ứng như trước.

## Hệ quả

- `ruleset_version` đổi (từ `a41f51ffa251`), cache profile cũ không còn dùng. `eval/patient_profiles.json` và các số đo ghi dưới phiên bản cũ không còn khớp mã hiện tại cho tới khi chạy lại `patient_ingest.py profiles` và đánh giá. Chưa làm bước này.
- Người tăng huyết áp bị lọc chặt hơn trước (500 mg thay vì 666,7 mg). Người không có bệnh nào engine nhắc tới giữ nguyên CSV.
- **Hai luật của engine tự ghi là chưa kiểm chứng:** `chf-sodium` ("UNVERIFIED assumption") và `diabetes-carbs` ("NOT FROM A GUIDELINE"); cả bảy luật có `status: proposed`. Giới hạn carbohydrate 60 g của người tiểu đường vì vậy là giả định, không phải khuyến nghị. Trước khi báo cáo cần duyệt hoặc đổi sang `soft`.
- Có hai tham số cùng ý nghĩa: `PER_MEAL_FRACTION` (CSV) và `MEALS_PER_DAY` (engine). Cần giữ nhất quán, hoặc gộp khi refactor.
- Danh sách bệnh được phép hiện trong prompt (`RuleSet.condition_codes`) chỉ gồm mã trong CSV. Bệnh mà chỉ engine nhắc tới (ví dụ suy tim) có thể được trích dẫn qua `[H:problems.active]` nhưng không hiện trong prompt. Chưa mở rộng danh sách này vì nó quyết định dữ liệu nào model được thấy (ADR-0006).
