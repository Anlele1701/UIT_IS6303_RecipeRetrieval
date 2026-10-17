# PROJECT: Condition-aware Recipe Recommendation (Synthea Patient → Dietary Rules → Hybrid RAG)

> Planning này căn chỉnh theo hệ thống đang chạy trong repo (xem `README.md`, `CONTEXT.md`, `docs/adr/`) **và theo hướng mới: hồ sơ bệnh nhân lấy từ Synthea**.
> Thuật ngữ (Recipe, Chunk, Chunking strategy, Filter, Hybrid retrieval, Reranking…) dùng đúng nghĩa trong `CONTEXT.md`.
> `CONTEXT.md` ghi **Filter** có “_Avoid_: Constraint”, nên planning này dùng **Filter** (điều kiện áp lên Recipe) và **Dietary rule** (quy tắc bệnh → giới hạn dinh dưỡng). Không dùng từ “constraint”.
> Sơ đồ luồng: `diagrams/architecture-flow.mermaid` (PNG cùng thư mục là bản cũ, cần render lại).
> Kế hoạch chi tiết cho **database hồ sơ bệnh nhân, sinh data Synthea, Dietary Rule Engine**: xem `ehr-and-rules-planning.md` (file này giữ vai trò tổng quan).

## 1. System Overview

Hệ thống nhận một yêu cầu gợi ý món ăn kèm `patient_id`. Hệ thống:

1. Đọc **hồ sơ Synthea** của bệnh nhân (bệnh đang mắc, chỉ số xét nghiệm, thuốc) từ Medical DB. Đây là truy vấn có cấu trúc, **không embedding** (phần “Vectorless”).
2. Đưa các **bệnh đang hoạt động** qua **Dietary Rule Engine** (bảng rule có nguồn tham chiếu, viết trong repo) để ra **Filter dinh dưỡng cứng** (vd `max_sodium_mg`).
3. Chạy **Hybrid retrieval** trên kho Recipe đã có (BM25 + vector + RRF + cross-encoder Reranking), Filter áp _trong_ index.
4. LLM viết câu trả lời giải thích, trích dẫn bệnh và rule đã dùng.

Phần đã có: toàn bộ retrieval trên Recipe, evaluation, report.
Phần cần làm: **nạp Synthea → Patient profile → Dietary Rule Engine → Orchestrator → Generator**, cộng 1–3 cột Filter còn thiếu trên `chunk`.

## 2. Vì sao đổi sang Synthea (và nó làm thay đổi gì)

Bộ 40 hồ sơ Markdown tổng hợp trước đó (`eval/records/pNNN.md`) được thiết kế để chứa sẵn **diet order có số** (“maximum 500 mg sodium per serving”), nên bài toán là _trích số từ văn bản dài_. Hồ sơ Synthea thì ngược lại:

|                                  | Hồ sơ Markdown cũ                   | Hồ sơ Synthea                                     |
| -------------------------------- | ----------------------------------- | ------------------------------------------------- |
| Dạng dữ liệu                     | Văn bản dài, nhiễu, 3k–32k ký tự    | Bảng có cấu trúc (CSV) hoặc FHIR JSON             |
| Có bệnh lý?                      | Không                               | **Có** (`conditions`: mã SNOMED, `START`, `STOP`) |
| Có giới hạn dinh dưỡng bằng số?  | Có (diet order)                     | **Không**                                         |
| Bước chuyển sang dinh dưỡng      | Trích số + bỏ order cũ (superseded) | **Bệnh → rule → số** (cần bảng rule)              |
| Có đáp án chuẩn để chấm?         | Có (`answer_key.json`)              | **Không** (phải tự dựng, xem mục 7)               |
| Vai trò Navigator kiểu PageIndex | Cần (hồ sơ dài)                     | **Không cần** (dữ liệu đã có cấu trúc, dùng SQL)  |

Hệ quả: ý tưởng “bệnh → giới hạn dinh dưỡng” trong sơ đồ gốc quay lại thành trục chính. Phần trích constraint bằng regex/LLM và “latest order wins” của planning trước **không còn nằm trên đường chính**. Bộ Markdown giữ nguyên trong repo, có thể dùng lại làm test cho phần Validator (xem mục 7).

**Thông tin đã kiểm tra trên module Synthea** (đối chiếu file module trên GitHub): Synthea có sinh `Essential hypertension` (59621000), `Diabetes mellitus type 2` (44054006), `Prediabetes` (714628002), `Metabolic syndrome X` (237602007), `Hypertriglyceridemia` (302870006), `Chronic congestive heart failure` (88805009), `Gout` (90560007). Careplan của Synthea chỉ là nhãn chung (vd “Lifestyle education regarding hypertension”, “Diabetes self management plan”), **không có ngưỡng dinh dưỡng**. Các bệnh khác (hyperlipidemia, bệnh mạch vành, béo phì, bệnh thận mạn…) **chưa kiểm tra mã**; phải xem output thật (Step 0 ở mục 9).

## 3. Hiện trạng vs. kế hoạch cũ (những chỗ đã đổi)

| Hạng mục                 | Planning cũ                                               | Hệ thống hiện tại → quyết định                                                                                                                                                                                                                         |
| ------------------------ | --------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Backend                  | NestJS / Spring Boot / Go                                 | **Python 3.11 + FastAPI + psycopg pool + pydantic** (`api/`, `uv`). Dùng tiếp.                                                                                                                                                                         |
| Database                 | PostgreSQL + `pgvector` + `paradedb`                      | **ParadeDB (pg17, pg_search 0.25.9)** port 5434, `docker-compose.yml`. Dense chạy bằng **index vector của ParadeDB**, không phải pgvector HNSW (ADR 0003; HNSW chỉ là ablation `hnsw-dense`).                                                          |
| Bảng thực phẩm           | `foods(...nutrients jsonb, embedding vector(1536))`       | `recipe` **+** `recipe_nutrition` **(3NF) +** `chunk` (partition theo Chunking strategy, ADR 0002). `embedding vector(768)` (`nomic-embed-text` qua Ollama). Đơn vị xếp hạng là **Chunk**. 32,719 Recipe, 3 strategy: `fixed`, `sentence`, `semantic`. |
| Index                    | HNSW + BM25 trên `name`, `description`                    | **1 index ParadeDB / partition** (`sql/indexes.sql`): BM25 trên `content` + vector + các cột Filter.                                                                                                                                                   |
| Hard filter              | `nutrients->>'sodium' < max`                              | **Cột thật copy lên** `chunk` (ADR 0001), áp _trong_ index trước khi xếp hạng, qua `min_<col>` / `max_<col>` (`api/filters.py`). Cột NULL không bao giờ lọt qua `<=` → fail-safe.                                                                      |
| Hồ sơ bệnh nhân          | Bảng `medical_records(user_id, conditions jsonb)`         | **Synthea CSV nạp vào schema riêng** `ehr` trong cùng ParadeDB (bảng `patient`, `condition`, `observation`, `medication`). Không đụng `chunk`/`recipe`. Chi tiết mục 4.1.                                                                              |
| Step 2 “Dietary mapping” | LLM: bệnh → `{max_sodium_mg, allowed_purine_levels, ...}` | **Rule table trong repo, không để LLM sinh số.** Bệnh (mã SNOMED) → rule có nguồn → Filter. LLM chỉ được dùng để _gán một tên bệnh lạ vào một rule id có sẵn_ (tập đóng), tuỳ chọn, mục 5.                                                             |
| Purine / Gout            | `allowed_purine_levels`, “Purine bằng 0”                  | **Dataset Recipe không có cột purine** (và sau khi nạp schema chỉ còn các cột trong `recipe_nutrition`). Synthea _có_ Gout nên cần quyết định riêng, mục 8 câu 4.                                                                                      |
| Retrieval Step 3         | BM25 + vector + RRF, LIMIT 5                              | Đã có trong `api/retrieval.py`: `sparse` + `dense` → `rrf` (k=60, 50 ứng viên mỗi nhánh) → **cross-encoder Reranking** (`mxbai-rerank-base-v1`) → top k Chunk. Planning cũ thiếu bước rerank; sơ đồ gốc gọi nhầm “re-rank bằng RRF”.                   |
| LLM                      | OpenAI API                                                | **Ollama local** (`OLLAMA_URL`; repo đã dùng `nomic-embed-text` và `qwen2.5:7b` để sinh query). Không thêm phụ thuộc OpenAI.                                                                                                                           |
| Lỗi ở Step 2             | Fallback bộ rule mặc định an toàn                         | **Không bịa rule y tế.** Lỗi đọc hồ sơ / rule engine → trả lỗi rõ ràng, **không bao giờ** chạy search không Filter như một _phương án dự phòng khi lỗi_. (Bệnh nhân thật sự không có bệnh nào cần rule thì khác, xem mục 8 câu 2.)                     |
| Design pattern           | Controller / Service / Usecase / Repository               | Repo là module phẳng theo vai trò. Giữ phong cách đó (mục 6).                                                                                                                                                                                          |

## 4. Data Specs

### 4.1 Hồ sơ bệnh nhân: Synthea

- **Sinh dữ liệu (offline, một lần):** chạy Synthea (Java) với seed cố định (đề xuất `-s 603` như bộ record cũ), xuất **CSV**. Chỉ lấy người lớn (đề xuất tuổi 40–90) vì trẻ/người trẻ gần như không có bệnh mạn tính; sau đó giữ lại bệnh nhân có ít nhất một bệnh đang hoạt động có rule, cộng một số ít bệnh nhân “khoẻ” và “bệnh không có rule” để test các nhánh biên. Cỡ mẫu đề xuất: vài trăm bệnh nhân sinh ra, giữ ~100 (số chốt sau Step 0).
- **Bảng dùng (từ CSV Synthea):**
  - `patients`: id, ngày sinh, giới tính (dùng cho hiển thị, không dùng để lọc).
  - `conditions`: `START`, `STOP`, `PATIENT`, `SYSTEM`, `CODE`, `DESCRIPTION`. **Bệnh đang hoạt động =** `STOP` **rỗng.** Luôn khớp theo `CODE` (SNOMED), không khớp theo tên.
  - `observations`: `DATE`, `PATIENT`, `CODE` (LOINC), `VALUE`, `UNITS`. Giai đoạn 1 chưa dùng; giai đoạn 2 dùng để _tinh chỉnh_ rule (vd eGFR, HbA1c, BMI, huyết áp).
  - `medications`: giai đoạn 1 chỉ hiển thị.
- **Nạp vào Postgres:** `scripts/load_synthea.py` + `sql/ehr.sql` (schema `ehr`). Chỉ giữ cột cần dùng, thêm index theo `patient_id`. Đây là _Medical DB_ trong sơ đồ.
- Ngày “hiện tại” của hồ sơ là ngày sinh dữ liệu của Synthea, không phải ngày chạy hệ thống. Orchestrator đọc “đang hoạt động” theo `STOP IS NULL`, không so với `now()`.
- Dữ liệu tổng hợp 100%, không phải hồ sơ thật; vẫn không log nội dung hồ sơ đầy đủ.

### 4.2 Bảng Dietary rule

Một file dữ liệu trong repo, vd `api/dietary_rules.json` (đọc bằng code, có test), không nằm trong prompt. Mỗi rule:

```json
{
  "rule_id": "htn-sodium",
  "snomed_codes": ["59621000"],
  "label": "Essential hypertension",
  "limits": [{ "nutrient": "sodium_mg", "op": "max", "daily": 1500 }],
  "source": "AHA / DASH (ghi rõ tài liệu + năm khi chốt)",
  "status": "proposed"
}
```

Quy ước:

- `daily` là **giới hạn theo ngày** (hướng dẫn y khoa thường tính theo ngày). Code đổi sang **per serving** bằng `per_serving = daily / MEALS_PER_DAY` (đề xuất `MEALS_PER_DAY = 3`, đặt trong `api/config.py`). Dữ liệu Recipe là per serving nên so sánh trực tiếp được. **Đây là giả định thiết kế, không phải sự thật y khoa:** một “serving” không phải lúc nào cũng là một bữa; phải nói rõ trong báo cáo.
- `status`: `proposed` cho đến khi có nguồn tham chiếu và người review. Tuyệt đối không coi bảng này là lời khuyên y tế.
- Nhiều bệnh cùng giới hạn một nutrient → lấy **giá trị chặt nhất** (`min` của các `max`).

Đề xuất rule khởi đầu. Các con số là **điểm xuất phát cần xác nhận**, không phải kết luận; những ô “cần quyết định” chưa có giá trị:

| Bệnh (SNOMED)                                                                                  | Nutrient lọc                             | Giới hạn gợi ý / ngày → / serving (÷3) | Ghi chú                                                            |
| ---------------------------------------------------------------------------------------------- | ---------------------------------------- | -------------------------------------- | ------------------------------------------------------------------ |
| Essential hypertension (59621000)                                                              | `sodium_mg`                              | 1,500 → 500                            | AHA nêu 1,500 mg là mức lý tưởng, 2,300 mg là trần chung           |
| Chronic congestive heart failure (88805009)                                                    | `sodium_mg`                              | 2,000 → ~667                           | cần xác nhận nguồn                                                 |
| Diabetes mellitus type 2 (44054006), Prediabetes (714628002), Metabolic syndrome X (237602007) | `carbohydrates_g`                        | cần quyết định (vd ~60 g/bữa)          | không có “trần ngày” duy nhất; `sugars_g` tuỳ chọn                 |
| Hypertriglyceridemia (302870006), tăng mỡ máu / mạch vành (mã chưa xác minh)                   | `saturated_fat_g`                        | ~13 → ~4                               | AHA: dưới 6% năng lượng, ≈13 g/ngày trên 2,000 kcal (đã xác minh)                        |
| Béo phì (mã chưa xác minh)                                                                     | `calories`                               | cần quyết định                         | không có chuẩn chung; có thể bỏ khỏi v1                            |
| Bệnh thận mạn (mã chưa xác minh)                                                               | `potassium_mg`, `protein_g`, `sodium_mg` | **phụ thuộc xét nghiệm**               | hướng dẫn thường cá thể hoá theo eGFR/kali máu, nên để giai đoạn 2 |
| Gout (90560007)                                                                                | không có (thiếu purine)                  | n/a                                    | xem mục 8 câu 4                                                    |

### 4.3 Phía thực phẩm: cột Filter còn thiếu (làm theo nhu cầu của rule)

> **HOÃN — sẽ implement sau.** Chưa thêm cột nào lên `chunk` ở giai đoạn này. Hệ quả: v1 chỉ lọc được trên 5 cột sẵn có (`calories, protein_g, fat_g, carbohydrates_g, sodium_mg`). Rule cần nutrient khác (vd `saturated_fat_g`) vẫn được nạp nhưng bị đánh dấu _chưa áp dụng được_ và phải hiện trong `unapplied_limits` của response (không được bỏ qua âm thầm). Chi tiết ở `ehr-and-rules-planning.md`.
>
> Ghi lại để khỏi mất khi quay lại làm:
>
> - Thêm **cả nhóm cột một lần** (`saturated_fat_g`, `potassium_mg`, `sugars_g`, có thể `dietary_fiber_g`) thay vì từng cột, vì migration không phải embed lại, chi phí chỉ là index to hơn.
> - Phương án dự phòng không đổi schema: lọc `recipe_nutrition` lấy `recipe_id` đạt giới hạn trước, rồi truyền `recipe_id = ANY(...)` vào tìm kiếm (cột `recipe_id` đã nằm trong index). Chưa đo hiệu năng với danh sách id lớn.
> - JOIN thông thường bị loại vì lọc _sau_ top-k (ADR 0001): an toàn nhưng dễ ra 0 kết quả.

Cột trong `chunk` hiện có đúng 5 nutrient để lọc: `calories, protein_g, fat_g, carbohydrates_g, sodium_mg`. Bảng rule khởi đầu ở trên cần thêm tối đa:

| Nutrient cần                                                     | Có sẵn để lọc?                                                             | Hành động                                                                |
| ---------------------------------------------------------------- | -------------------------------------------------------------------------- | ------------------------------------------------------------------------ |
| `sodium_mg`, `carbohydrates_g`, `calories`, `protein_g`, `fat_g` | Có                                                                         | Không cần làm gì                                                         |
| `saturated_fat_g`                                                | **Chưa** (có trong `recipe_nutrition`, NULL ~3.3% trong `data/recipe.csv`) | **Thêm** (cần cho rule mỡ máu/tim mạch)                                  |
| `potassium_mg`                                                   | **Chưa** (NULL ~0.4%)                                                      | Chỉ thêm nếu giữ rule thận mạn                                           |
| `sugars_g`                                                       | **Chưa** (NULL ~1.8%)                                                      | Chỉ thêm nếu rule tiểu đường dùng đường                                  |
| `cholesterol_mg`                                                 | **Chưa** (NULL ~14.9%)                                                     | Không thêm trong v1: tỉ lệ NULL cao + cột NULL bị loại ⇒ mất ~15% Recipe |
| `phosphorus_mg`                                                  | **Không có** (NULL ~99.4%, đã bị bỏ khỏi `recipe_nutrition`)               | Không dùng được (quan trọng cho thận mạn)                                |
| purine                                                           | **Không có trong dataset**                                                 | Không dùng được                                                          |

Nên bắt đầu bằng **chỉ** `saturated_fat_g` (và các cột khác khi rule thật sự cần), thay vì thêm cả ba như planning cũ.

Phải sửa đồng bộ khi thêm cột:

- `sql/schema.sql` (cột trên `chunk`) và `sql/indexes.sql` (thêm vào index ParadeDB)
- `scripts/ingest.py` (danh sách cột copy và consistency check ADR 0001)
- `api/filters.py` (`RANGE_COLUMNS`) và `ui/src/filters.ts` (`RANGE_GROUPS`)
- `tests/test_index_sql.py`, `tests/test_ingest.py`
- Migration mới trong `sql/migrations/` cho DB đang chạy (hiện chỉ có `001-partition-chunk.sql`)

**Cách thêm cột (cần quyết định, mục 8 câu 1):** `chunk` theo quy tắc “không sửa tại chỗ, chỉ rebuild” (ADR 0001) nhưng rebuild đầy đủ tốn ~3.5 giờ embedding. Đề xuất: migration `ALTER TABLE … ADD COLUMN` + backfill từ `recipe_nutrition` + tái tạo index mỗi partition, **không embed lại**, ghi thành ADR 0005, rồi chạy consistency check và `scripts/runcheck.py` để chứng minh rank của Report run không đổi.

Mapping nutrient của rule → cột filter (một nguồn duy nhất trong code): `nutrient` trong rule trùng tên cột `chunk`, bóc `max_` + nutrient ra `SearchParams`. Whitelist = `RANGE_COLUMNS` trong `api/filters.py`; rule dùng nutrient ngoài whitelist thì test fail ngay khi load.

## 5. Core Implementation Workflow (The Orchestrator)

Một request → một pipeline tuần tự, mỗi step có log riêng (`logging`, kèm `request_id`, `patient_id`, thời gian từng step như `watch(stage)` trong `retrieval.fused_candidates`).

Endpoint mới: `POST /recommend` body `{ patient_id, query, strategy, k=5 }`.

### Step 1: Patient Profile (Vectorless, SQL)

- Validate `patient_id` (UUID của Synthea hoặc id đã nạp; tham số hoá khi query, không nối chuỗi).
- Truy vấn `ehr.condition` lấy bệnh đang hoạt động (`stop IS NULL`) kèm `code`, `description`, `start`. Gom theo `code`.
- Output **Patient profile**: `{patient_id, active_conditions: [{snomed, description, start}], (giai đoạn 2: latest observations)}`.
- Không có bệnh nhân → 404. Lỗi DB → lỗi rõ ràng.

### Step 2: Dietary Rule Engine (code, không LLM sinh số)

1. Với mỗi bệnh đang hoạt động, tra bảng rule theo `snomed_code`. Bệnh không có rule → được đếm vào `unmatched_conditions`; nếu là bệnh ta biết liên quan chế độ ăn nhưng chưa có giới hạn (Gout, thận mạn, béo phì) thì vào `unsupported_conditions` kèm lý do (không bị bỏ qua âm thầm).
2. **(Tuỳ chọn, bật bằng cờ)** _Condition normalizer_ dùng LLM: chỉ khi một bệnh không khớp mã, LLM nhận tên bệnh và danh sách `rule_id` hiện có, phải trả về **một rule_id trong danh sách hoặc** `none`, JSON mode, `temperature=0`. LLM **không bao giờ** tạo ngưỡng. Kết quả đánh dấu `source: "llm_mapped"` và phải được trả về trong response để người dùng thấy.
3. Đổi `daily` → per serving (`÷ MEALS_PER_DAY`).
4. **Strictest wins** cho từng nutrient (nhiều bệnh cùng giới hạn một nutrient → lấy nhỏ nhất).
5. **Validator (code):** nutrient thuộc whitelist `RANGE_COLUMNS`; `op == "max"`; giá trị là số dương; mỗi Filter ra đều có evidence (condition + rule_id + `source`).

- Output: `Filters = {max_sodium_mg: 500, max_saturated_fat_g: 4.3, …}` cùng `evidence[]` và `unsupported_conditions[]`.
- Nếu không có rule nào áp dụng: không bịa; trả `applied_filters: {}` kèm cờ `no_applicable_rules` (xử lý theo mục 8 câu 2).

### Step 3: Food Retrieval (Hybrid + Hard Filters) — không đổi so với planning trước

- Embed câu hỏi gốc bằng `embed_query` (có sẵn).
- Dựng `SearchParams(q, strategy, k, max_<col>…)` bằng code. **Không build SQL động**: `where_clause()` dùng tham số hoá và `extra="forbid"`; Orchestrator chỉ truyền giá trị đã validate.
- Gọi `retrieval.hybrid(conn, params, qvec, reranker.score)`: sparse + dense → RRF (`score = Σ 1/(60 + rank)`) → cross-encoder → top k Chunk. Dùng đúng cấu hình đã đo trong Report run.
- **Chunk → Recipe:** xin `k` Chunk lớn hơn 5 (vd 20–30, `MAX_K = 50`), gom theo `recipe_id` giữ Chunk điểm cao nhất, lấy top 5 Recipe, đọc `title`, ingredients, `recipe_nutrition`.
- **Safety re-check (defense in depth):** kiểm lại từng Recipe với `recipe_nutrition`; vi phạm hoặc thiếu giá trị thì loại và ghi log (về lý thuyết = 0 trường hợp).
- **Không nới Filter** nếu kết quả ít. Ít hơn 5 thì trả ít hơn; 0 thì trả “không tìm được món phù hợp”. Lưu ý: bệnh nhân nhiều bệnh ⇒ nhiều Filter chồng nhau ⇒ dễ ra 0 kết quả; đây là hiện tượng cần đo ở mục 7.

### Step 4: Generation

- Ollama chat với prompt (tiếng Việt hoặc theo ngôn ngữ query):
  "Bạn là trợ lý gợi ý bữa ăn. Chỉ dùng thông tin được cung cấp.
  - Câu hỏi: {query}
  - Bệnh đang hoạt động của bệnh nhân và giới hạn dinh dưỡng suy ra, kèm nguồn rule: {evidence}
  - Món ăn đã lọc, kèm giá trị dinh dưỡng thực tế mỗi khẩu phần: {recipes}
    Với mỗi món, giải thích vì sao phù hợp, dẫn đúng con số. Không nêu số hay món ngoài danh sách. Không đưa lời khuyên y tế ngoài các giới hạn đã cho."
- Response: `{ answer, recipes[], evidence[], applied_filters, unapplied_limits, unsupported_conditions, timings_ms }`. `recipes`, `evidence`, `applied_filters` là dữ liệu có cấu trúc từ code; LLM chỉ viết phần giải thích.
- Lỗi LLM ở bước này: vẫn trả Recipe và evidence, `answer: null`.
- Response nên có dòng cố định “đây là dữ liệu tổng hợp, không phải lời khuyên y tế”.

## 6. Code Layout & Rules

Giữ phong cách module phẳng hiện có trong `api/`, thêm:

| File                      | Vai trò                                                                                                                    |
| ------------------------- | -------------------------------------------------------------------------------------------------------------------------- |
| `scripts/load_synthea.py` | Đọc CSV Synthea, lọc cột/bệnh nhân, nạp vào schema `ehr` (offline, chạy một lần).                                          |
| `sql/ehr.sql`             | Schema `ehr` (patient, condition, observation, medication) + index.                                                        |
| `api/dietary_rules.json`  | Bảng rule (bệnh → giới hạn theo ngày, nguồn, trạng thái).                                                                  |
| `api/patients.py`         | Truy vấn Patient profile (bệnh đang hoạt động) từ `ehr`.                                                                   |
| `api/dietary_rules.py`    | Load + validate bảng rule, đổi daily→per serving, strictest-wins, tạo `Filters` + evidence. Logic thuần, không gọi DB/LLM. |
| `api/llm.py`              | Client Ollama chat (timeout, retry, JSON mode). Dùng cho normalizer (tuỳ chọn) và generator.                               |
| `api/recommend.py`        | Orchestrator 4 step, logging, gom Chunk → Recipe, safety re-check.                                                         |
| `api/main.py`             | Thêm route `POST /recommend`. Route chỉ validate input rồi gọi orchestrator.                                               |

Quy tắc:

- Tách rõ: route (HTTP) / orchestrator (luồng) / từng bước (logic thuần, test được) / truy cập DB. LLM, embedder, reranker được truyền vào như tham số để test bằng bản giả (đúng cách `tests/` đang làm).
- Mọi giá trị đi vào SQL phải qua `SearchParams` hoặc tham số hoá; không nối chuỗi.
- Logging từng step: input rút gọn, số bệnh, số rule khớp, filter áp dụng, số Chunk/Recipe, ms từng stage.
- Thêm `LLM_MODEL` (mặc định `qwen2.5:7b`), `LLM_TIMEOUT`, `MEALS_PER_DAY`, `RULES_PATH` vào `api/config.py`.
- Ghi thêm vào `CONTEXT.md` khi code xong: **Patient profile**, **Active condition**, **Dietary rule**, **Unmapped condition**. Giữ nguyên “Filter”.

## 7. Evaluation

Synthea **không có đáp án chuẩn** cho giới hạn dinh dưỡng (khác `answer_key.json` cũ), nên đánh giá chia theo từng tầng, mỗi tầng tự có tiêu chí riêng:

1. **Rule engine (deterministic):** test bằng bảng ca vàng tự viết (~15–20 ca): một bệnh; nhiều bệnh cùng nutrient (strictest wins); bệnh đã có `STOP` (phải bị bỏ); bệnh không có rule (vào `unsupported_conditions` hoặc `unmatched_conditions`); bệnh nhân khoẻ. Đây là unit test, mục tiêu 100%.
2. **Condition normalizer (nếu bật LLM):** gán tay nhãn đúng cho các tên bệnh trong cohort, đo tỉ lệ đúng và tỉ lệ trả `rule_id` ngoài tập cho phép (phải 0%, validator chặn). So với baseline “chỉ khớp mã”.
3. **End-to-end safety:** với mỗi bệnh nhân × tập query, tỉ lệ Recipe trả về vi phạm _bất kỳ_ Filter nào, kiểm bằng `recipe_nutrition` độc lập với đường retrieval. Mục tiêu 0%.
4. **Cái giá của Filter cứng:** với mỗi bệnh nhân, số Recipe trả về và tỉ lệ bệnh nhân bị < 5 hoặc 0 kết quả theo số bệnh (1, 2, 3 bệnh). So Hybrid có/không Filter (độ lệch rank). Không đụng đến Report run.
5. **Generation:** kiểm tự động mọi con số LLM nêu có nằm trong dữ liệu đã cấp; không nêu món ngoài danh sách.
6. (Tuỳ chọn) **Tái dùng bộ Markdown cũ** + `answer_key.json` để test riêng đường trích diet order bằng văn bản, nếu muốn giữ như một nhánh so sánh.

Script mới `scripts/evaluate_patients.py` ghi vào thư mục run riêng, không lẫn với `eval/runs/` của retrieval.

Hạn chế phải nêu rõ trong báo cáo: bảng rule là giả định thiết kế (theo hướng dẫn công khai, đổi ngày → serving), không được bác sĩ xác nhận; “đúng” ở đây nghĩa là _nhất quán với bảng rule_, không phải đúng lâm sàng.

## 8. Câu hỏi mở cần chốt

1. **Cách thêm cột filter** (`saturated_fat_g`, có thể thêm `potassium_mg`, `sugars_g`): **đã quyết định hoãn, implement sau** (xem ghi chú ở 4.3). Khi quay lại: migration tại chỗ không embed lại (đề xuất, ADR 0005) hay rebuild đầy đủ (~3.5h, đúng ADR 0001 nhất)?
2. **Bệnh nhân không có rule áp dụng:** (a) chạy search không Filter nhưng ghi rõ `applied_filters: {}` + `unsupported_conditions` (đề xuất, hợp lý cho người khoẻ), hay (b) từ chối và trả “thiếu thông tin”? Nếu _có bệnh nhưng bệnh đó chưa có rule_ (vd Gout) thì nên cảnh báo mạnh hơn.
3. **Cách lưu hồ sơ Synthea:** schema `ehr` trong ParadeDB (đề xuất, khớp “Medical DB” trong sơ đồ và tận dụng SQL) hay file JSON/Markdown theo từng bệnh nhân (khớp cách `eval/records` đang làm)? Nếu muốn giữ câu chuyện “Vectorless/PageIndex” cho báo cáo thì có thể render hồ sơ ra Markdown rồi điều hướng cây, nhưng dữ liệu Synthea vốn có cấu trúc nên bước đó chủ yếu mang tính minh hoạ.
4. **Gout và purine:** Synthea có Gout nhưng dataset Recipe không có purine. Các lựa chọn: (a) để Gout không tạo Filter (cảnh báo `unsupported_conditions`), (b) thêm bộ _ingredient-exclusion_ (từ khoá nội tạng, cá cơm, sardine… áp lên `recipe_ingredient`, bằng code, không LLM), (c) bỏ Gout khỏi phạm vi. Đề xuất (a) cho v1, (b) nếu còn thời gian.
5. **Bệnh thận mạn:** rule phụ thuộc xét nghiệm (eGFR, kali máu) và thiếu phosphorus trong dữ liệu. Đưa vào giai đoạn 2 hay bỏ khỏi phạm vi?
6. **Nguồn và người xác nhận rule:** chốt tài liệu tham chiếu (AHA/ADA/KDIGO…) cho từng dòng bảng rule và `MEALS_PER_DAY = 3` có chấp nhận được không?
7. **LLM normalizer (mục 5 Step 2.2):** có cần ngay không, hay chỉ khớp theo mã SNOMED trong v1 (đơn giản, an toàn hơn) rồi thêm LLM sau?
8. **Strategy mặc định** khi gọi `/recommend`: `semantic` (đang dùng cho demo) hay để client chọn?

## 9. Thứ tự thực hiện

1. **Khảo sát dữ liệu:** cài Synthea, sinh một mẫu nhỏ CSV, xem `conditions.csv` thực sự có những `CODE`/`DESCRIPTION` nào (đếm theo bệnh) → chốt danh sách bệnh có rule và mã SNOMED còn “chưa xác minh” ở mục 4.2.
2. Chốt bảng rule v1 (câu hỏi 4–7) và tài liệu tham chiếu.
3. `scripts/load_synthea.py` + `sql/ehr.sql`; nạp cohort; kiểm tra số bệnh nhân theo từng bệnh.
4. `api/dietary_rules.py` + `api/patients.py` + test ca vàng (đạt 100%).
5. ~~Migration cột Filter còn thiếu (ADR 0005)~~ — **hoãn, làm sau.** Khi làm: chạy `runcheck` xác nhận rank không đổi.
6. `api/recommend.py` + `POST /recommend` (retrieval, gom Recipe, safety re-check).
7. `api/llm.py` + Generator + kiểm tra con số. (Normalizer LLM sau cùng, nếu chốt có làm.)
8. `scripts/evaluate_patients.py`: safety, cái giá của Filter, generation; cập nhật README / CONTEXT / ADR; render lại sơ đồ.
