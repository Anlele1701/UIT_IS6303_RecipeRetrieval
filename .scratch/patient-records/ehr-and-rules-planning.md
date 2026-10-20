# PLAN: Synthea → EHR database (Vectorless) → Dietary Rule Engine → food RAG

> Kế hoạch chi tiết cho ba việc: **(A)** sinh dữ liệu Synthea, **(B)** build database hồ sơ bệnh nhân, **(C)** Dietary Rule Engine nối với hệ thống RAG thức ăn.
> `planning.md` là tổng quan; file này là phần triển khai của Step 1–2 trong đó.
> Thuật ngữ theo `CONTEXT.md`: dùng **Filter** cho điều kiện áp lên Recipe, **Dietary rule** cho quy tắc bệnh → giới hạn. Không dùng “constraint”.

## Trạng thái triển khai (cập nhật sau khi build)

Dữ liệu Synthea do bạn tự sinh (`./run_synthea -p 1000 -a 40-90 -s 603`, 1000 bệnh nhân) nằm ở `data/patients_record/`. **Không sinh lại.** Mục 2 (Phần A) vì vậy chỉ còn giá trị tham khảo; T1 bỏ.

| Tác vụ | Trạng thái | Ở đâu |
|---|---|---|
| T0 Khảo sát dữ liệu | **Xong** | Kết quả ở mục “Kết quả khảo sát” bên dưới |
| T1 Script sinh Synthea | **Bỏ** (đã có dữ liệu) | n/a |
| T2 Schema `ehr` + loader | **Xong**, đã nạp vào DB đang chạy (run `synthea-603-p1000`) | `sql/ehr.sql`, `scripts/load_synthea.py`, `tests/fixtures/synthea_mini/` |
| T3 Lớp truy cập + endpoint hồ sơ | **Xong** | `api/patients.py`, `GET /patients`, `GET /patients/{id}` |
| T4 Rule file + engine | **Xong** | `api/dietary_rules.json`, `api/dietary_rules.py` |
| T5 Nối vào RAG | **Xong (generator chưa thử với LLM thật):** `POST /recommend` (profile → rule → Filter → Hybrid → gom Chunk thành Recipe → kiểm lại `recipe_nutrition` → LLM giải thích), `GET /patients?q=&order=`, trang UI `/diet`. Đã chạy thật trên 166k Chunk: Filter đúng, mọi Recipe thoả giới hạn. Model `qwen2.5:7b` chưa được pull nên nhánh giải thích mới chỉ thử đường lỗi (`answer: null` + `answer_error`) | `api/recommend.py`, `api/llm.py`, `api/main.py`, `ui/src/Recommend.tsx`, `tests/test_recommend.py` |
| T5b Dị ứng thức ăn | **Xong:** profile đọc `ehr.allergy` (đang hiệu lực); `/recommend` loại Recipe có từ khoá dị ứng trong title/ingredient (sau khi lấy tới 50 Chunk), báo `allergy_check.excluded/unchecked`. Từ khoá viết tay trong `api/food_allergens.json` (8 dị ứng thức ăn của cohort). Là bộ lọc theo từ khoá, **không phải bảo đảm**: không thấy được chất gây dị ứng mà dòng nguyên liệu không nêu. Dị ứng thuốc/môi trường bị bỏ qua | `api/allergens.py`, `api/food_allergens.json`, `tests/test_allergens.py` |
| T6 Thống kê cohort | **Xong** | `scripts/diet_plan_stats.py` |
| T7–T9 Nhánh B (tree navigation) | **Xong, đã đo** (60 bệnh nhân, `qwen2.5:7b`, seed 603). Tree recall 0,614 (ngắn 0,62 / vừa 0,74 / dài 0,52), precision 1,0, 0 bệnh đã khỏi bị báo nhầm, đọc ~10% tài liệu, 2 lần gọi LLM. Dense recall 0,424 (0,54 / 0,58 / 0,25), 5 mã bệnh đã khỏi bị báo nhầm ở tài liệu dài, đọc ~40%. Tree là bản tự viết kiểu PageIndex, không phải thư viện PageIndex; bố cục tài liệu thuận lợi cho tree; chưa thể thay SQL (tree thiếu mã rule ở 22/57 bệnh nhân). Báo cáo đầy đủ: `.scratch/patient-records/ehr-retrieval-evaluation.md`. T7: `ehr.record_document` (1000 tài liệu), median 7.7k ký tự (~1.9k token), p90 27k, max 319k. T8: `api/ehr_navigator.py`, `GET /patients/{id}/active-conditions?source=sql|tree|dense`. T9: `scripts/evaluate_ehr_retrieval.py` | `api/ehr_document.py`, `api/ehr_navigator.py`, `scripts/render_ehr_documents.py`, `scripts/evaluate_ehr_retrieval.py`, `eval/ehr_runs/` |

Test: `tests/test_dietary_rules.py` (31 test, hàm thuần) và `tests/test_patients.py` (16 test, cần DB, dùng DB tạm `ehr_test`, **không cần docker**). Trong sandbox của mình, các test cũ cần `docker exec` hoặc tải tokenizer từ HuggingFace không chạy được; đó là lỗi môi trường chứ không liên quan thay đổi này.

### Lệch so với kế hoạch (và lý do)

1. **Rule file nằm ở `api/dietary_rules.json`, không phải `data/`.** `data/` bị `.gitignore`; rule phải được commit.
2. **`unmapped_conditions` đổi thành hai trường.** Mỗi bệnh nhân có trung bình ~13.7 bệnh đang hoạt động, phần lớn là *finding xã hội* (“Full-time employment”, “Stress”, “Received higher education”…). Liệt kê tất cả là nhiễu.
   - `unsupported_conditions`: bệnh ta **biết** liên quan chế độ ăn nhưng chưa biến thành giới hạn được (Gout, bệnh thận mạn, béo phì), kèm lý do. Được khai báo trong rule file bằng rule `limits: []` + `unsupported_reason`.
   - `unmatched_conditions`: chỉ là một **con số** (bệnh không rule nào nhắc tới).
3. **`MEALS_PER_DAY` và `RULES_PATH` đặt trong `api/config.py`** (qua biến môi trường), không đặt trong rule file.
4. **Loader tự chạy `sql/ehr.sql`** (idempotent) nên không còn bước chạy tay.
5. **Không có `manifest.json` từ Synthea** vì không dùng script sinh. Loader tự lập manifest (đường dẫn, `--synthea-args` do bạn khai, SHA-256 từng CSV, số dòng).
6. **Ngày tham chiếu suy ra từ dữ liệu:** `reference_date` = ngày bắt đầu muộn nhất của mọi condition (hiện là 2026-10-17). Tuổi tính theo ngày này. Bạn không dùng `-r`, nên đây là ngày bạn chạy Synthea.
8. **`eval/records/` (40 hồ sơ Markdown + `answer_key.json`) không còn trong working tree** (git báo đã xoá, thư mục được sửa lúc 17:59, trước khi build này bắt đầu). Mình không chạm vào. Vẫn khôi phục được từ git (commit `959a4fa`: `git checkout -- eval/records`). Các chỗ trong planning nói “giữ bộ Markdown cũ làm test/nhánh so sánh” (`planning.md` mục 2 và mục 7.6) chỉ còn đúng nếu bạn khôi phục nó.
7. **`list_patients` chưa có tham số `has_rule`** (sẽ cần engine trong truy vấn danh sách; chưa cần).

### Nguồn của bảng rule (đã kiểm tra)

Các con số trong `api/dietary_rules.json` do mình soạn; trang nguồn được kiểm tra bằng cách đọc trực tiếp:

| Rule | Con số | Nguồn | Tình trạng |
|---|---|---|---|
| `htn-sodium` | 1,500 mg/ngày | AHA, “How Much Sodium Should I Eat Per Day?” (xem lại 2025-07-15): tối đa 2,300, mục tiêu tối ưu 1,500 mg cho đa số người lớn | **Đã xác minh**, nhưng là khuyến nghị cho người lớn nói chung, không riêng tăng huyết áp, và không áp dụng nếu bác sĩ chỉ định khác |
| `lipid-satfat` | 13 g/ngày | AHA, “Saturated Fats” (xem lại 2024-08-23): dưới 6% năng lượng, ≈13 g trên 2,000 kcal | **Đã xác minh**, cũng là khuyến nghị chung, áp cho các bệnh này là giả định |
| `diabetes-carbs` | 180 g/ngày (60 g/serving) | ADA nói rõ **“no magic number”** cho carb mỗi bữa, tuỳ cân nặng, vận động, thuốc | **Không có nguồn.** Con số là giả định của dự án |
| `chf-sodium` | 2,000 mg/ngày | Chưa kiểm tra | **Chưa xác minh** |
| Phép chia ngày → serving (÷3) | 3 bữa | Giả định thiết kế | Không có nguồn |
| Bệnh nào ứng với nutrient nào | vd tăng huyết áp → natri | Phán đoán của mình | Không có nguồn |

### Kết quả khảo sát dữ liệu thật (T0)

- 1000 bệnh nhân, tuổi 40–89, **không có ai đã mất**. 51,107 dòng condition (đều SNOMED-CT), 75,918 thuốc, 636 dị ứng, 180,687 observation sau khi lọc whitelist (từ 1.19M dòng gốc).
- **`years_of_history` mặc định (10) không làm mất bệnh mạn tính đang hoạt động:** condition sớm nhất bắt đầu năm 1942. (Bệnh *đã kết thúc* quá 10 năm có thể bị cắt, nhưng chỉ bệnh đang hoạt động quyết định Filter.)
- Mọi mã SNOMED trong rule đã được xác nhận có trong dữ liệu: tăng huyết áp 59621000 (425 bệnh nhân), suy tim 88805009 (16), Gout 90560007 (11), tiền tiểu đường 714628002 (606), hội chứng chuyển hoá 237602007 (302), tiểu đường type 2 44054006 (166), mỡ máu 55822004 (226), tăng triglyceride 302870006 (156), bệnh tim thiếu máu cục bộ 414545008 (397), béo phì 162864005 (795), thận mạn giai đoạn 1–4 (142/120/65/18), ESRD (4).
- **Tiểu đường: 142 bệnh nhân có biến chứng tiểu đường (vd “Disorder of kidney due to diabetes mellitus”) nhưng không có mã `Diabetes mellitus type 2` đang hoạt động.** Rule `diabetes-carbs` vì vậy phủ cả các mã biến chứng, không chỉ mã bệnh gốc. Khớp theo tên bệnh gốc sẽ bỏ sót nhóm này.
- Không có cặp (bệnh nhân, mã) nào trùng dòng đang hoạt động.
- Dị ứng thực phẩm có thật (136 dòng: Shellfish 31, Eggs 19, Cow's milk 17, Fish 17, Wheat 15, Tree nut 13, Peanut 12, soy 12) ở 141 bệnh nhân. Đã nạp nhưng **chưa dùng**.

### Kết quả `scripts/diet_plan_stats.py` trên 1000 bệnh nhân (3 bữa/ngày)

| Chỉ số | Kết quả |
|---|---|
| Có ≥1 Filter | **78.0%** (1 Filter: 43.1%, 2 Filter: 34.9%) |
| Không Filter nào (`no_applicable_rules`) | 22.0% |
| Có giới hạn **chưa áp dụng được** (`saturated_fat_g`, do hoãn cột) | **54.1%** (541 bệnh nhân) |
| Có bệnh “biết nhưng chưa dùng được” (Gout / thận mạn / béo phì) | 82.3% (823), chủ yếu do béo phì 795 |
| Bộ Filter khác nhau | chỉ 6 tổ hợp (vd `carbs≤60`: 349; `carbs≤60 + sodium≤500`: 346; `sodium≤500`: 79) |
| Search (BM25) dưới mỗi tổ hợp, 5 truy vấn | **luôn đủ 50 Chunk, 0 vi phạm** khi đối chiếu độc lập với `recipe_nutrition` |

Ý nghĩa:

- Filter áp dụng đúng *trong index* (kể cả `sodium ≤ 500`) và không vi phạm, trên kho 166k Chunk, nên chưa thấy hiện tượng “ra 0 kết quả” ở mức 1–2 Filter. Chưa chứng minh được gì về Hybrid, vì phép thử này chỉ dùng Sparse (không cần Ollama); Hybrid dùng cùng `where_clause` nhưng chưa được đo ở đây.
- **Hơn một nửa bệnh nhân có một giới hạn mà hệ thống chưa lọc được** (chất béo bão hoà). Đây là lý do mạnh để đưa việc thêm cột filter (đang hoãn) lên sớm.
- Với rule hiện tại, tối đa 2 Filter chồng nhau, nên phép đo “cái giá của Filter cứng khi nhiều bệnh” (mục 7 của `planning.md`) chưa có ý nghĩa nhiều. Nó chỉ trở nên thú vị khi thêm các rule/cột mới.

**Quyết định bạn cần đưa ra:** béo phì chiếm 79.5% bệnh nhân nhưng đang là `unsupported` (không có giới hạn calo per serving). Có thêm rule `calories` không? Nếu có, gần như mọi bệnh nhân sẽ có Filter calo, và cần chốt con số + nguồn trước.

## 0. Phạm vi và các quyết định đã chốt

| Quyết định | Nội dung |
|---|---|
| Cột Filter mới trên `chunk` | **Hoãn, implement sau** (ghi ở `planning.md` mục 4.3). Hệ quả cho kế hoạch này: engine chỉ *áp dụng* được rule trên 5 cột sẵn có: `calories, protein_g, fat_g, carbohydrates_g, sodium_mg`. |
| Rule cần nutrient chưa lọc được | Vẫn nạp, nhưng engine ghi vào `unapplied_limits` của kết quả. **Không được bỏ qua âm thầm.** Khi cột được thêm sau này chỉ cần đổi một danh sách, không đổi code engine. |
| Định dạng Synthea | **CSV** (phẳng, nạp bằng `COPY`). Không dùng FHIR ở v1. |
| Nơi lưu | Schema `ehr` trong cùng ParadeDB (cổng 5434), không đụng `recipe`, `chunk`. |
| LLM trong engine | **Không có ở v1.** Khớp bệnh theo mã SNOMED. Normalizer LLM để giai đoạn sau. |
| Lab-based refinement (eGFR, HbA1c…) | **Ngoài phạm vi v1**, nhưng nạp sẵn một số observation để sau này dùng. |
| Lưu hồ sơ | **Schema `ehr` trong ParadeDB** (đã chốt). |
| Vectorless RAG ở phía hồ sơ | **A + B (đã chốt).** **A:** SQL theo khoá là đường chạy thật, nằm trên đường an toàn. **B:** nhánh văn bản có điều hướng cây (kiểu PageIndex) dùng để so sánh và đo, **không** quyết định Filter. Xem mục 3B. |

## 1. “Vectorless” ở đây nghĩa là gì (để báo cáo không bị hiểu sai)

Hồ sơ Synthea là dữ liệu **có cấu trúc**. “Retrieval” hồ sơ ở đây là **truy vấn có khoá** (`patient_id` → các dòng bệnh), không có embedding, không có xếp hạng. Nó vẫn đúng tinh thần “vectorless”: thông tin lấy ra *chính xác theo khoá*, không theo độ tương tự.

Khác với PageIndex/điều hướng cây cho văn bản dài (đó là bộ Markdown cũ). Để phần này có nội dung RAG thật và đo được, kế hoạch có **hai nhánh** (đã chốt A + B):

- **A (đường chạy thật):** SQL theo khoá → Patient profile → Rule Engine. Luận điểm: lấy bệnh để quyết định an toàn phải **chính xác**, không dùng độ tương tự gần đúng.
- **B (nhánh so sánh, mục 3B):** dựng hồ sơ thành tài liệu Markdown có mục, LLM điều hướng cây để chọn mục cần đọc. Kết quả được **đối chiếu với SQL** và với một baseline dense retrieval. Nhánh này cho số liệu để *chứng minh* luận điểm của A, và không bao giờ quyết định Filter.

## 2. Phần A: Sinh dữ liệu Synthea

### 2.1 Công cụ

- Synthea yêu cầu **JDK 17 trở lên**. Máy đang có JDK 21.0.4, đủ điều kiện.
- Hai cách chạy: tải `synthea-with-dependencies.jar` từ bản release mới nhất của Synthea (đã kiểm tra link tồn tại), hoặc clone repo rồi `./run_synthea`. **Đề xuất dùng jar** (không cần Gradle).
- Đặt jar ở thư mục bị ignore (vd `tools/synthea/`, thêm vào `.gitignore`), **không commit jar**. Output CSV vào `data/synthea/<run_id>/` (`data/` đã nằm trong `.gitignore`).

### 2.2 Cấu hình sinh (đề xuất)

Synthea nhận `--<property>=value` trên dòng lệnh (README ghi `--config*=value`) và các cờ `-s` (seed), `-p` (số bệnh nhân), `-a` (khoảng tuổi), `-r` (ngày tham chiếu `YYYYMMDD`).

```bash
java -jar tools/synthea/synthea-with-dependencies.jar \
  -s 603 -p 500 -a 40-90 -r 20260101 \
  --exporter.csv.export=true \
  --exporter.fhir.export=false \
  --exporter.years_of_history=0 \
  --exporter.baseDirectory=data/synthea/run1/ \
  Massachusetts
```

Giải thích từng lựa chọn:

- `-s 603`: cùng seed với bộ record cũ trong repo. **Cần kiểm tra tính tái lập** (chạy hai lần, so sánh CSV), không giả định.
- `-a 40-90`: người trẻ hầu như không có bệnh mạn tính, nên bệnh nhân sinh ra sẽ vô ích. Con số 40 là đề xuất, chốt sau Step 0.
- `-r 20260101`: cố định “ngày hiện tại” của mô phỏng, để “bệnh đang hoạt động” không trôi theo ngày chạy.
- `exporter.years_of_history=0`: mặc định là 10 và file cấu hình ghi *“anything older may be filtered out”*. Bệnh mạn tính chẩn đoán cách đây hơn 10 năm có thể mất khỏi export, khiến bệnh nhân trông như khoẻ. Đặt 0 để giữ toàn bộ lịch sử. **Cần xác minh** ảnh hưởng thực tế ở Step 0.
- Tắt FHIR để chạy nhanh hơn và output gọn.
- Có thể thêm `exporter.csv.excluded_files` để bỏ file không dùng (mặc định đã bỏ `patient_expenses.csv`).

### 2.3 File CSV sẽ dùng

Theo data dictionary của Synthea:

| File | Cột dùng | Dùng để |
|---|---|---|
| `patients.csv` | `Id`, `BirthDate`, `DeathDate`, `Gender`, tên (giả) | Danh tính, tuổi, loại người đã mất |
| `conditions.csv` | `Start`, `Stop`, `Patient`, `Encounter`, `System`, `Code`, `Description` | **Nguồn chính cho rule.** `Stop` rỗng = đang hoạt động |
| `medications.csv` | `Start`, `Stop`, `Patient`, `Code`, `Description`, `ReasonCode`, `ReasonDescription` | Hiển thị; `ReasonCode` nối thuốc với bệnh (evidence phụ) |
| `observations.csv` | `Date`, `Patient`, `Code` (LOINC), `Description`, `Value`, `Units`, `Type` | Giai đoạn 2. Rất lớn, nên **chỉ nạp whitelist LOINC** |
| `allergies.csv` | cột tương tự `conditions` | Nạp sẵn, **chưa dùng ở v1** (xem mục 6) |

Không nạp ở v1: `encounters`, `procedures`, `claims`, `payers`, `providers`, `organizations`, `immunizations`, `imaging_studies`, `devices`, `supplies`.

### 2.4 Chọn cohort

- Sinh ~500, **nạp hết người còn sống** (số nhỏ, không cần script chọn riêng). Nhóm đánh giá (stratum) được tính khi truy vấn, không lưu cứng.
- Các stratum cần có đủ mẫu để test nhánh biên: không bệnh nào; 1 bệnh có rule; 2 bệnh; ≥3 bệnh; chỉ có bệnh **chưa có rule** (vd Gout); có bệnh đã kết thúc (`Stop` có giá trị).
- Nếu stratum nào quá ít, tăng `-p` hoặc chạy thêm một seed khác, ghi cả hai vào manifest.
- Dữ liệu **hoàn toàn tổng hợp**; ghi lại điều này ở README.

### 2.5 Tái lập và provenance

- Script `scripts/generate_synthea.sh` (hoặc Python mỏng) chỉ gói lệnh ở 2.2 và ghi `data/synthea/<run_id>/manifest.json`: phiên bản jar (tên file + SHA-256), `seed`, `population`, `age range`, `reference date`, các `--config`, thời điểm sinh.
- Manifest được nạp vào bảng `ehr.cohort_run` (mục 3) để biết DB đang chứa dữ liệu từ lần chạy nào.
- Commit vào repo: script + manifest nhỏ + **fixture mini** (mục 3.5), không commit CSV đầy đủ.

## 3. Phần B: Database hồ sơ bệnh nhân (schema `ehr`)

### 3.1 Vì sao cùng DB, schema riêng

- `api/` dùng một connection pool trên `DATABASE_URL`; cùng DB thì không phải thêm pool hay cấu hình.
- Schema riêng (`ehr.*`) tách bạch với `recipe`/`chunk`: **không** sửa `sql/schema.sql` nên không vi phạm quy tắc “chunk chỉ rebuild” (ADR 0001) và không ảnh hưởng Report run.
- **Lưu ý áp dụng:** `docker-compose` chỉ chạy `schema.sql` khi volume mới. DB đang chạy dùng volume có sẵn nên `sql/ehr.sql` phải được **chạy tay một lần** (giống cách migration `sql/migrations/001-partition-chunk.sql`). Đặt tên `sql/migrations/002-ehr-schema.sql` hoặc `sql/ehr.sql` rồi hướng dẫn lệnh chạy trong README. Chọn một trong hai ở Task T2.
- `tests/conftest.py` hiện tạo `recipe_test` chỉ từ `schema.sql`. Test EHR cần thêm fixture riêng chạy `ehr.sql` (và vẫn skip khi container không chạy, như các test DB khác).

### 3.2 Schema đề xuất (v1)

```sql
CREATE SCHEMA IF NOT EXISTS ehr;

CREATE TABLE ehr.cohort_run (
  run_id      text PRIMARY KEY,
  manifest    jsonb NOT NULL,          -- seed, population, age range, reference date, jar sha256
  loaded_at   timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE ehr.patient (
  id          uuid PRIMARY KEY,         -- Synthea Id
  run_id      text NOT NULL REFERENCES ehr.cohort_run(run_id),
  birth_date  date NOT NULL,
  gender      char(1) NOT NULL,
  display_name text NOT NULL            -- tên giả của Synthea, chỉ để hiển thị
);

CREATE TABLE ehr.condition (
  patient_id  uuid NOT NULL REFERENCES ehr.patient(id) ON DELETE CASCADE,
  start_date  date NOT NULL,
  stop_date   date,                     -- NULL = đang hoạt động
  system      text NOT NULL,            -- thường SNOMED-CT
  code        text NOT NULL,
  description text NOT NULL
);
CREATE INDEX ON ehr.condition (patient_id);
CREATE INDEX ON ehr.condition (code);

CREATE TABLE ehr.medication (
  patient_id  uuid NOT NULL REFERENCES ehr.patient(id) ON DELETE CASCADE,
  start_at    timestamptz NOT NULL,
  stop_at     timestamptz,
  code        text NOT NULL,            -- RxNorm
  description text NOT NULL,
  reason_code text,                     -- SNOMED, nối với condition.code
  reason_description text
);
CREATE INDEX ON ehr.medication (patient_id);

CREATE TABLE ehr.observation (          -- chỉ whitelist LOINC (giai đoạn 2 dùng)
  patient_id  uuid NOT NULL REFERENCES ehr.patient(id) ON DELETE CASCADE,
  observed_at timestamptz NOT NULL,
  code        text NOT NULL,            -- LOINC
  description text NOT NULL,
  value_num   numeric,                  -- NULL nếu giá trị dạng text
  value_text  text,
  units       text
);
CREATE INDEX ON ehr.observation (patient_id, code, observed_at DESC);

CREATE TABLE ehr.allergy (              -- nạp sẵn, chưa dùng ở v1
  patient_id  uuid NOT NULL REFERENCES ehr.patient(id) ON DELETE CASCADE,
  start_date  date NOT NULL,
  stop_date   date,
  code        text NOT NULL,
  description text NOT NULL
);
CREATE INDEX ON ehr.allergy (patient_id);
```

Ghi chú:

- Khớp bệnh luôn theo `code`, **không khớp theo `description`** (tên có thể đổi dạng).
- Cột `Encounter` bị bỏ vì v1 không nạp `encounters`; thêm sau nếu cần “ngày khám gần nhất”.
- Whitelist observation: các mã đã thấy trong module Synthea là Potassium `6298-4` và Sodium `2947-0`. Các mã HbA1c, BMI, huyết áp, eGFR **chưa xác minh**; lấy danh sách từ output thật ở Step 0 rồi mới chốt. Nếu ngoài phạm vi v1, có thể trì hoãn toàn bộ bảng `observation`.

### 3.3 Script nạp: `scripts/load_synthea.py`

Theo phong cách `scripts/ingest.py` (khối header `uv run`, `argparse` subcommand, `psycopg`).

```
uv run scripts/load_synthea.py load  data/synthea/run1/csv  [--replace]
uv run scripts/load_synthea.py stats
uv run scripts/load_synthea.py reset [--yes]
```

Hành vi:

- `load`: đọc `manifest.json` cạnh thư mục CSV; một transaction; dùng `COPY` (qua psycopg `copy`). Từ chối nếu `run_id` đã có, trừ khi `--replace`.
- Lọc lúc nạp: bỏ bệnh nhân có `DeathDate`; observation chỉ giữ whitelist LOINC; chỉ giữ cột cần.
- Chuẩn hoá: `Stop` rỗng → `NULL`; `Value` có thể là text → tách `value_num`/`value_text`.
- **Kiểm tra sau nạp (fail nếu sai):** không dòng condition/medication/allergy nào mồ côi bệnh nhân (FK đã bảo đảm); mọi bệnh nhân có ngày sinh; số dòng nạp khớp số dòng đã lọc từ CSV.
- `stats`: số bệnh nhân; số bệnh nhân theo từng bệnh đang hoạt động (top N theo `code`, `description`); phân bố số bệnh/bệnh nhân. Đây là công cụ cho Step 0 và cho chương đánh giá.

### 3.4 Lớp truy cập: `api/patients.py`

Logic thuần theo kiểu `api/retrieval.py` (nhận `conn`, trả dữ liệu, không biết HTTP).

- `get_profile(conn, patient_id) -> PatientProfile`
  - `PatientProfile`: `patient_id, age, gender, display_name, active_conditions[], (giai đoạn 2) latest_observations{}`.
  - `active_conditions` = `SELECT … FROM ehr.condition WHERE patient_id = %s AND stop_date IS NULL`, gom theo `code` (một bệnh có thể xuất hiện nhiều dòng), giữ `start_date` sớm nhất.
  - Không tìm thấy bệnh nhân → ngoại lệ riêng, route đổi thành 404.
- `list_patients(conn, limit, offset, has_rule: bool | None)` cho dropdown demo / UI. Tham số hoá hoàn toàn.
- Endpoint (route mỏng trong `api/main.py`):
  - `GET /patients`: danh sách rút gọn (id, tuổi, giới, tên bệnh đang hoạt động).
  - `GET /patients/{id}`: Patient profile.
  - Giao diện `PatientProfile` này là hợp đồng giữa Phần B và Phần C.
- Không log nội dung hồ sơ đầy đủ; log `patient_id`, số bệnh, thời gian truy vấn.

### 3.5 Test và fixture

- Fixture mini (commit được): `tests/fixtures/synthea_mini/` với CSV viết tay vài dòng, các bệnh nhân được dựng có chủ đích: chỉ tăng huyết áp; tăng huyết áp + tiểu đường type 2; bệnh đã có `Stop`; khoẻ (không bệnh); chỉ Gout (bệnh chưa có rule); người đã mất (phải bị loại).
- Test loader trên DB test (skip nếu container không chạy), test `get_profile` trên các ca đó.
- Test không dùng dữ liệu Synthea thật để kết quả không phụ thuộc lần sinh.

## 3B. Nhánh B: hồ sơ dạng văn bản + điều hướng cây (vectorless, để so sánh)

Mục đích: có một phần vectorless RAG đúng nghĩa (không embedding, LLM đọc mục lục và chọn mục), và **đo được** nó so với SQL và so với dense retrieval. Nhánh này không nằm trên đường `/recommend`.

### 3B.1 Dựng tài liệu từ dữ liệu có cấu trúc

- Render **xác định (không LLM)** từ các bảng `ehr` ra Markdown, cùng quy ước với bộ `eval/records` (tiêu đề `##`, kèm `<!-- section_id: … -->`) để dùng lại ý tưởng parse cây.
- Mục đề xuất: `## Demographics`, `## Active conditions`, `## Resolved conditions` (kèm `start`–`stop`), `## Medications` (đang dùng / đã dừng, kèm lý do), `## Allergies`, `## Laboratory` (nếu đã nạp observation).
- Lưu vào `ehr.record_document(patient_id, run_id, markdown, rendered_at)`. Đây là dữ liệu **dẫn xuất**: chỉ dựng lại từ các bảng, không sửa tay (cùng tinh thần ADR 0001).
- Vì tài liệu sinh ra từ chính các bảng, **đáp án chuẩn có sẵn (SQL)**, không cần gán nhãn tay.
- Hạn chế phải nói rõ: tài liệu dựng từ bảng sẽ **ngắn và gọn hơn** hồ sơ văn bản thực. Lợi thế của điều hướng cây rõ nhất ở văn bản dài. Đo phân bố độ dài ở T7 trước khi kết luận gì; nếu quá ngắn, kết quả “tree thắng dense” sẽ không thuyết phục, và báo cáo phải nói thẳng điều đó.

### 3B.2 Ba cách lấy “bệnh đang hoạt động” để so sánh

| Cách | Cơ chế | Vai trò |
|---|---|---|
| **SQL** (A) | `stop_date IS NULL` | Đường chạy thật, và là **đáp án chuẩn** |
| **Tree navigation** (B) | Parse cây tiêu đề → đưa LLM mục lục (tên mục + số dòng) → LLM chọn mục → đọc mục → LLM trích JSON danh sách bệnh đang hoạt động | Vectorless RAG |
| **Dense baseline** | Chia tài liệu thành đoạn, embed bằng `nomic-embed-text` (dùng `api/embed.py`), lấy top-k theo câu hỏi “bệnh đang hoạt động của bệnh nhân”, LLM trích JSON từ các đoạn đó | Đối chứng có vector |

### 3B.3 Cách đo (script riêng: `scripts/evaluate_ehr_retrieval.py`)

Đáp án chuẩn = tập bệnh đang hoạt động từ SQL.

- **Recall / precision** của tập bệnh trích được (khớp theo mã SNOMED hoặc theo mã gắn trong tài liệu, không so tên tự do).
- **Stale leak rate:** tỉ lệ trả nhầm bệnh **đã kết thúc** (`stop_date` có giá trị) như đang hoạt động. Đây là lỗi nguy hiểm nhất và là chỗ dense retrieval dễ sai.
- **Chi phí:** số token/ký tự đã đọc, độ trễ, số lần gọi LLM.
- Theo stratum (số bệnh, độ dài tài liệu) để xem khi nào phương pháp nào bắt đầu sai.
- Kết quả ghi vào thư mục run riêng, không lẫn với `eval/runs/` của retrieval món ăn.

### 3B.4 Mã nguồn

| File | Vai trò |
|---|---|
| `api/ehr_document.py` | Render Markdown từ `ehr`; parse cây tiêu đề (logic thuần). |
| `api/ehr_navigator.py` | Navigator LLM và baseline dense; nhận `llm` và `embed` như tham số để test bằng bản giả. |
| `api/llm.py` | Client Ollama chat dùng chung (JSON mode, `temperature=0`, timeout, retry). Cũng là nền cho Generator ở `planning.md`. |
| `scripts/render_ehr_documents.py` | Dựng/dựng lại `ehr.record_document` cho cả cohort. |
| `scripts/evaluate_ehr_retrieval.py` | Phép đo ở 3B.3. |

### 3B.5 Quy tắc an toàn cho nhánh B

- **Không bao giờ** dùng kết quả B để tạo Filter. `/recommend` chỉ dùng SQL.
- Tuỳ chọn, chi phí thấp: chạy B làm **second opinion**; nếu khác SQL thì chỉ ghi log để theo dõi, không đổi hành vi.
- Endpoint debug (nếu cần cho demo) `GET /patients/{id}/profile?source=sql|tree|dense`, mặc định `sql`. Chỉ phục vụ trình bày và so sánh.

## 4. Phần C: Dietary Rule Engine

### 4.1 Hợp đồng với hai phía

```
PatientProfile (Phần B)  ──►  derive_diet_plan(...)  ──►  DietPlan  ──►  SearchParams (api/filters.py)
                                       ▲                                    │
                              RuleBook (api/dietary_rules.json)            ▼
                                                              retrieval.hybrid(...) (đã có)
```

Engine là **hàm thuần**: không gọi DB, không gọi LLM, không đọc env trong thân hàm (config truyền vào).

```python
derive_diet_plan(
    profile: PatientProfile,
    rules: RuleBook,
    filterable: frozenset[str],   # = set(api.filters.RANGE_COLUMNS) hôm nay
    meals_per_day: int,
) -> DietPlan
```

`DietPlan`:

| Trường | Ý nghĩa |
|---|---|
| `filters: dict[str, float]` | Khoá dạng `max_<cột>`, chỉ gồm nutrient trong `filterable`. Truyền thẳng vào `SearchParams(**filters)`. |
| `evidence: list` | Mỗi Filter ra đời từ: bệnh (code, description, ngày bắt đầu), `rule_id`, nutrient, giá trị theo ngày, giá trị per serving, `source`, `status` của rule, và cờ `binding` (giá trị nào đang thắng khi nhiều bệnh trùng nutrient). |
| `unsupported_conditions` | Bệnh biết là liên quan chế độ ăn nhưng chưa biến được thành giới hạn (kèm `rule_id`, lý do). |
| `unmatched_conditions` | Số bệnh đang hoạt động mà không rule nào nhắc tới (một con số, không liệt kê). |
| `unapplied_limits` | Giới hạn mà rule có nhưng nutrient **chưa lọc được** (vd `saturated_fat_g` khi cột chưa thêm). |
| `status` | `filtered` (có ≥1 Filter), `no_applicable_rules` (không có Filter nào), để Orchestrator quyết định theo `planning.md` mục 8 câu 2. |

Quy tắc an toàn cho `unapplied_limits`: nếu một bệnh nhân có giới hạn *không áp dụng được*, response cuối **phải** nói rõ điều đó. Đây là chỗ thay thế cho việc “thêm cột” đã hoãn: hệ thống không được im lặng giả vờ đã tuân thủ rule mà nó không lọc được.

### 4.2 Định dạng bảng rule: `api/dietary_rules.json`

```json
{
  "version": 1,
  "meals_per_day_default": 3,
  "rules": [
    {
      "rule_id": "htn-sodium",
      "label": "Essential hypertension",
      "snomed_codes": ["59621000"],
      "limits": [{"nutrient": "sodium_mg", "op": "max", "daily": 1500}],
      "source": "AHA (ghi tài liệu + năm khi chốt)",
      "status": "proposed"
    }
  ]
}
```

- `nutrient` trùng **tên cột của `chunk`** để không cần bảng ánh xạ riêng.
- `snomed_codes` là danh sách (một rule có thể phủ nhiều mã, vd nhiều giai đoạn thận mạn).
- `status`: `proposed` | `reviewed`. Hiển thị trong evidence.
- Đơn vị: `daily` luôn là mg/g/kcal theo ngày; code đổi sang per serving. Không để người viết rule tự chia.
- **Chỗ trống cho giai đoạn 2:** có thể thêm trường tuỳ chọn `when` (điều kiện theo xét nghiệm) vào `limits[]`. v1 không đọc và **không implement** `when`; loader từ chối file có `when` để khỏi hiểu nhầm là đang chạy.

Validator khi load file (lỗi là fail ngay, không chạy tiếp):

1. `rule_id` duy nhất; `snomed_codes` không rỗng và là chuỗi số.
2. `op == "max"` (v1 chưa có `min`); `daily` là số dương.
3. `nutrient` thuộc tập nutrient đã biết của `recipe_nutrition` (chặn gõ sai tên). Không bắt buộc thuộc `filterable`, vì rule có thể đi trước cột.
4. Một mã SNOMED có thể thuộc nhiều rule (cho phép), nhưng không trùng `(rule_id, nutrient)`.

### 4.3 Thuật toán

1. Với mỗi `active_condition`, tìm mọi rule có `code` trong `snomed_codes`. Không có rule nào → tăng `unmatched_conditions`. Rule không có `limits` (chỉ có `unsupported_reason`) → `unsupported_conditions`.
2. Với mỗi `limit` của mỗi rule khớp: `per_serving = daily / meals_per_day`.
3. Nếu `nutrient` **không** thuộc `filterable` → thêm vào `unapplied_limits`, không tạo Filter.
4. Còn lại: gom theo nutrient, **lấy giá trị nhỏ nhất** (strictest wins); đánh dấu `binding`.
5. **Làm tròn xuống** (không làm tròn lên) một chữ số thập phân, vì đây là trần: ví dụ 4.333 → 4.3. Làm tròn lên có thể cho qua món vượt giới hạn.
6. Sinh `filters = {"max_<nutrient>": value}` và `status`.

Về hành vi dữ liệu thiếu: cột NULL không bao giờ lọt qua `<=` (fail-safe đã có). Với các cột hiện lọc được, tỉ lệ NULL thấp (~0.3–0.7% trong `data/recipe.csv`), nên tác động nhỏ.

### 4.4 Bảng rule v1, với việc “hoãn cột Filter”

Các giá trị bên dưới là **điểm xuất phát cần xác nhận nguồn**, không phải lời khuyên y tế. Mục “Trạng thái” cho thấy rule nào áp dụng được ngay.

| Rule | Mã SNOMED (đã kiểm tra trên module Synthea) | Nutrient | Giới hạn/ngày (gợi ý) | Per serving (÷3) | Trạng thái |
|---|---|---|---|---|---|
| `htn-sodium` | 59621000 Essential hypertension | `sodium_mg` | 1,500 | 500 | **Áp dụng được** |
| `chf-sodium` | 88805009 Chronic congestive heart failure | `sodium_mg` | 2,000 | ~666.7 → 666.6 | **Áp dụng được** |
| `diabetes-carbs` | 44054006 T2DM, 714628002 Prediabetes, 237602007 Metabolic syndrome X | `carbohydrates_g` | cần quyết định (vd ~180 g/ngày) | ~60 | **Áp dụng được** khi chốt giá trị |
| `lipid-satfat` | 302870006 Hypertriglyceridemia (và mã mỡ máu/mạch vành khác sau Step 0) | `saturated_fat_g` | ~13 | ~4.3 | **Chưa áp dụng được** → `unapplied_limits` |
| `obesity-calories` | mã chưa xác minh | `calories` | cần quyết định | cần quyết định | Áp dụng được khi có mã và giá trị; có thể bỏ khỏi v1 |
| `ckd-*` | mã chưa xác minh | `potassium_mg`, `protein_g`, `sodium_mg` | phụ thuộc xét nghiệm | n/a | Ngoài v1 |
| Gout | 90560007 | thiếu purine | n/a | n/a | Rule `gout-unsupported` → `unsupported_conditions` |

Điểm cần nhớ: với bảng này, bệnh nhân chỉ có mỡ máu cao sẽ nhận `filters = {}` và `unapplied_limits = [saturated_fat_g]`. Đây là *trạng thái hợp lệ* chứ không phải lỗi, và phải hiện ra cho người dùng.

### 4.5 Ghép vào hệ thống RAG thức ăn

- Orchestrator (`api/recommend.py`, theo `planning.md`) gọi: `profile = get_profile(...)` → `plan = derive_diet_plan(profile, RULES, frozenset(RANGE_COLUMNS), MEALS_PER_DAY)` → `SearchParams(q=query, strategy=..., k=..., **plan.filters)` → `retrieval.hybrid(...)`.
- `SearchParams` có `extra="forbid"`: nếu engine tạo khoá sai, lỗi lộ ra ngay lúc test thay vì lọc sai âm thầm. Vì vậy `filterable` lấy trực tiếp từ `RANGE_COLUMNS`, không viết tay lại.
- **Endpoint độc lập `GET /patients/{id}/diet-plan`:** trả `DietPlan` mà **không** gọi embedding/LLM/retrieval. Dùng để debug, demo, và để test engine trên bệnh nhân Synthea thật mà không phụ thuộc Ollama hay reranker.
- Cấu hình thêm vào `api/config.py`: `MEALS_PER_DAY` (mặc định 3), `RULES_PATH` (mặc định `api/dietary_rules.json`). Rule file được nạp và validate **một lần lúc startup**; hỏng thì app không khởi động.

### 4.6 Test cho engine

Bảng ca vàng (hàm thuần, không cần DB):

| Ca | Kỳ vọng |
|---|---|
| Một bệnh: tăng huyết áp | `max_sodium_mg = 500` |
| Tăng huyết áp + suy tim | `max_sodium_mg = 500` (nhỏ hơn thắng), cả hai có trong evidence, `binding` đúng |
| Tăng huyết áp + tiểu đường | hai Filter: sodium và carbohydrates |
| Bệnh đã có `Stop` | không tạo Filter |
| Chỉ mỡ máu cao | `filters = {}`, `unapplied_limits` có `saturated_fat_g` |
| Chỉ Gout | `unsupported_conditions` có Gout, `status = no_applicable_rules` |
| Không bệnh | `status = no_applicable_rules`, không lỗi |
| Làm tròn | 4.333 → 4.3 (không phải 4.4) |
| Rule file lỗi (nutrient sai tên, `op` sai, có `when`) | loader báo lỗi ngay |

Thuộc tính cần kiểm: giá trị mỗi Filter **không lớn hơn** per-serving của bất kỳ bệnh nào đóng góp; thêm một bệnh vào hồ sơ không bao giờ làm một Filter *nới ra*.

Test hợp đồng: mọi nutrient trong `dietary_rules.json` hoặc thuộc `RANGE_COLUMNS`, hoặc được liệt kê rõ là “chưa áp dụng được”. Khi sau này thêm cột, test này nhắc cập nhật.

## 5. Thứ tự thực hiện (tác vụ, sản phẩm, tiêu chí xong)

| # | Tác vụ | Sản phẩm | Xong khi |
|---|---|---|---|
| T0 | **Khảo sát Synthea:** tải jar, sinh mẫu nhỏ (vd `-p 50`), xem output | Danh sách `Code`/`Description` bệnh thực tế xuất hiện (đếm); xác nhận mã mỡ máu/mạch vành/béo phì/thận mạn; kiểm tra tái lập (chạy 2 lần, diff); so sánh `years_of_history` 10 vs 0; dung lượng `observations.csv`; có allergy dạng thực phẩm không | Chốt được danh sách bệnh có rule và mã SNOMED |
| T1 | Script sinh + manifest | `scripts/generate_synthea.sh`, `.gitignore` cho jar, hướng dẫn ngắn | Chạy lại ra cùng CSV (hoặc ghi rõ phần nào không tái lập được) |
| T2 | Schema `ehr` + loader | `sql/ehr.sql` (hoặc migration 002), `scripts/load_synthea.py`, fixture mini, test | `load` + `stats` chạy trên DB thật; test loader qua |
| T3 | Lớp truy cập + endpoint hồ sơ | `api/patients.py`, `GET /patients`, `GET /patients/{id}`, test | `get_profile` đúng trên mọi ca fixture |
| T4 | Rule file + engine (có thể làm song song T1–T3, chỉ cần fixture) | `api/dietary_rules.json`, `api/dietary_rules.py`, bảng ca vàng | 100% ca vàng; validator chặn file hỏng |
| T5 | Nối vào RAG | `GET /patients/{id}/diet-plan`; thử `SearchParams(**plan.filters)` + `retrieval.hybrid` với vài bệnh nhân thật | Mọi Recipe trả về thoả `recipe_nutrition` (kiểm tay bằng SQL); không lỗi `extra=forbid` |
| T6 | Thống kê cohort | Bảng: bao nhiêu bệnh nhân có 0/1/2/3+ Filter; bao nhiêu bị `unapplied_limits`; bao nhiêu có `unsupported_conditions`; số kết quả search theo số Filter | Số liệu dùng được cho chương đánh giá |

Nhánh B (mục 3B), làm **sau T3** (cần dữ liệu `ehr` và `get_profile` làm đáp án chuẩn), độc lập với T4–T6:

| # | Tác vụ | Sản phẩm | Xong khi |
|---|---|---|---|
| T7 | Render tài liệu + parse cây | `ehr.record_document`, `api/ehr_document.py`, `scripts/render_ehr_documents.py`, test | Mọi bệnh nhân có tài liệu; đã đo phân bố độ dài (ký tự/token) và nhận xét có đủ dài để điều hướng cây có ý nghĩa không |
| T8 | `api/llm.py` + Navigator + dense baseline | `api/llm.py`, `api/ehr_navigator.py`, test với LLM/embedder giả | Navigator trả JSON hợp lệ trên fixture; baseline chạy được |
| T9 | Đo B so với SQL | `scripts/evaluate_ehr_retrieval.py`, bảng recall/precision/stale-leak/chi phí theo stratum | Có số liệu cho chương đánh giá; kết luận nêu thẳng cả trường hợp B không hơn dense |

T0 là cổng: kết quả của nó có thể đổi bảng rule (mục 4.4) và cỡ cohort trước khi viết bất kỳ code nào khác. `api/llm.py` làm ở T8 cũng dùng lại cho Generator của `/recommend`, nên có thể kéo lên làm sớm nếu cần.

## 6. Rủi ro và điều chưa biết

| Rủi ro | Cách xử lý |
|---|---|
| Synthea có thể **không tái lập hoàn toàn** dù cùng seed (phụ thuộc phiên bản, ngày tham chiếu, clinician seed `-cs`) | Kiểm ở T0; ghi SHA-256 jar và toàn bộ tham số vào manifest; nếu không tái lập thì **commit cohort đã chọn** thay vì cam kết “sinh lại giống hệt” |
| `years_of_history` mặc định 10 làm mất bệnh cũ | Đặt 0; xác minh ở T0 |
| Nhiều bệnh nhân Synthea không có bệnh nào có rule | Dùng `-a 40-90`; kiểm số liệu ở T6; có sẵn stratum “không có rule” để test |
| Bảng rule là **giả định thiết kế** (ngày → serving ÷3, giá trị khởi đầu) chứ không được bác sĩ duyệt | Đánh dấu `status: proposed`, nêu rõ ở báo cáo: “đúng” = nhất quán với bảng rule, không phải đúng lâm sàng |
| Với cột hoãn, nhiều bệnh nhân sẽ có `unapplied_limits` | Đây là hành vi được thiết kế; cần thống kê tỉ lệ ở T6 để quyết định có nên đưa việc thêm cột lên sớm hơn |
| **Dị ứng thực phẩm** trong Synthea (nếu có) là rủi ro an toàn thật cho gợi ý món ăn nhưng recipe chỉ có dòng nguyên liệu dạng text, không có trường allergen | Nạp bảng `ehr.allergy` sẵn, **chưa dùng ở v1**; ghi rõ là hạn chế đã biết. Hướng sau: lọc theo từ khoá trên `recipe_ingredient` bằng code |
| Mã bệnh thận mạn có thể nhiều, rule phụ thuộc xét nghiệm | Ngoài v1 |
| Nhánh B có thể **không thắng** SQL hay dense (tài liệu dựng từ bảng ngắn, ground truth lại chính là SQL nên SQL luôn đúng theo định nghĩa) | Đây là điều cần nói thẳng. So sánh có ý nghĩa chủ yếu giữa **tree vs dense** (cùng đọc văn bản), còn SQL đóng vai đáp án chuẩn và là đường chạy thật vì chính xác tuyệt đối. Báo cáo không được trình bày B như bằng chứng B “tốt hơn SQL” |
| LLM trích sai ở nhánh B | Chỉ ảnh hưởng số liệu đo, không ảnh hưởng an toàn vì B không quyết định Filter |
| Volume DB đang chạy không tự chạy lại `docker-init.sql` | Hướng dẫn chạy tay `ehr.sql`; kiểm tra bằng `stats` |

## 7. Câu hỏi mở

1. ~~**Lưu hồ sơ:** schema `ehr` hay file JSON?~~ **Đã chốt: schema `ehr` trong ParadeDB.**
2. ~~**Nhánh văn bản cho “điều hướng cây”**~~ **Đã chốt: có (nhánh B, mục 3B).** Còn một câu nhỏ: tài liệu dựng từ bảng có thể quá ngắn để điều hướng cây có ý nghĩa. Synthea có tuỳ chọn xuất ghi chú lâm sàng dạng text (`exporter.clinical_note.export`, mặc định tắt, **chưa kiểm tra định dạng**) có thể cho văn bản dài và nhiễu hơn. Thử ở T0 để so với tài liệu tự dựng, hay chỉ dùng tài liệu tự dựng?
3. **Cỡ cohort:** sinh ~500 và nạp hết, hay cố định một số cụ thể (vd 100–150 bệnh nhân) cho đánh giá?
4. **Giá trị rule:** ai/tài liệu nào chốt các con số ở 4.4, và `MEALS_PER_DAY = 3` có chấp nhận không?
5. **Có cần `GET /patients` + UI chọn bệnh nhân** ngay, hay demo bằng `patient_id` gõ tay trước?
6. **Obesity (`calories`)**: giữ trong v1 hay bỏ vì không có chuẩn rõ ràng?
