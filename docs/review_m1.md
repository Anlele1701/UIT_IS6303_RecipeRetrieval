# Hướng dẫn duyệt từ điển M1 (việc 👤 của Thy)

Có 3 file cần duyệt, đều nằm trong `data/lexicon/`. Mở bằng Excel hoặc VS Code đều được. **Khi lưu, giữ định dạng CSV UTF-8.** Với Excel, chọn "CSV UTF-8 (Comma delimited)".

Duyệt xong thì nhắn mình "đã duyệt M1". Mình sẽ nhập các sửa đổi, chạy lại gắn thẻ, đưa thẻ xuống `chunk`, rồi trình gate M1.

---

## 1. `synonym_suggestions.csv`: gợi ý đồng nghĩa của LLM (khoảng 15–30 phút)

Mỗi dòng là một tên nguyên liệu mà từ điển chưa nhận ra, có xuất hiện từ 2 dòng nguyên liệu trở lên. `qwen2.5:7b` đã đề xuất tên gốc cho nó.

| Cột | Ý nghĩa |
|---|---|
| `variant` | Tên sau khi parse (ví dụ `swai fish`) |
| `lines` | Số dòng nguyên liệu có tên này. Ưu tiên duyệt các dòng có số lớn, file đã được xếp sẵn theo thứ tự này |
| `llm_base` | Tên gốc LLM đề xuất (ví dụ `fish`) |
| `proposed_canonical` | Canonical mà mình ánh xạ `llm_base` vào. `NEW:x` nghĩa là sẽ tạo canonical mới tên `x`. `nonfood` là vật dụng không ăn được |
| `accept` | **Thy điền:** `y` để chấp nhận. Để trống nghĩa là bỏ qua, tên đó vẫn là `unknown` |
| `corrected_canonical` | **Tùy chọn:** điền canonical đúng nếu đề xuất sai nhưng Thy biết đáp án |

Nguyên tắc duyệt:
- Chấp nhận khi `variant` **thật sự là** `proposed_canonical`, hoặc là một biến thể của nó.
- **Cẩn thận với nhóm dị ứng.** Nếu ánh xạ làm mất hay thêm nhóm dị ứng thì không chấp nhận, hoặc sửa ở `corrected_canonical`. Ví dụ: ánh xạ `buttery spread` → `vegetable oil` làm mất milk.
- Nếu không chắc, để trống.

## 2. `vi_alias.csv`: từ tiếng Việt (khoảng 10 phút)

Có 276 alias. Mỗi alias có thêm một bản không dấu, sinh tự động. Bản không dấu bị bỏ khi nó trùng với một alias khác nghĩa: `bo` (bò/bơ), `dua` (dứa/dừa), `ngo` (ngò/ngô).

Kiểm các điểm sau:
- Mỗi `alias` trỏ đúng `target` không. Ví dụ: `chanh` → `lime`, `chanh vàng` → `lemon`.
- Có thiếu từ phổ biến nào không. Nếu thiếu, thêm dòng mới **ở bản có dấu**, rồi nhắn mình sinh lại bản không dấu.
- Các từ đa nghĩa đã được chọn theo nghĩa nấu ăn: `bơ` → butter, `kem` → ice cream, `hải sản` → fish + crustacean.

Sửa thẳng vào file, hoặc ghi chú vào cột `note`.

## 3. `allergen_map.csv`: khoảng 100 dòng đầu, thành phần ẩn (khoảng 15 phút)

File đã được xếp sẵn theo thứ tự: các dòng `kind = hidden` (nguyên liệu không ghi rõ tên nhóm dị ứng) đứng đầu, rồi theo số dòng giảm dần. Với mỗi dòng, kiểm cột `allergens` có đúng và đủ không.

Mình đã chọn **hướng bảo thủ** cho các ca sau. Cần Thy xác nhận, vì các ca này cũng ảnh hưởng hướng dẫn gán nhãn ở M2:

| Nguyên liệu | Gắn | Lý do / cần Thy xác nhận |
|---|---|---|
| chocolate chips, semisweet/dark chocolate | milk, soy | Thường chứa bơ sữa và lecithin đậu nành |
| margarine | milk | Nhiều loại có whey hoặc buttermilk |
| peanut oil | peanut | FDA miễn cho dầu tinh luyện cao. Mình vẫn gắn để an toàn |
| almond extract, amaretto | tree_nuts | Hương hạnh nhân |
| granola | tree_nuts | Thường có hạnh nhân hoặc hồ đào |
| red/green curry paste | crustacean_shellfish | Loại truyền thống có mắm tôm, tùy hãng |
| kimchi | fish, crustacean_shellfish | Thường có nước mắm và tôm muối |
| oyster sauce | wheat | Đa số hãng có bột mì. Hàu là nhuyễn thể, không thuộc 9 nhóm FDA |
| refried beans, baked beans, canned chili | (không dị ứng) nhưng **không chay** | Loại đóng hộp truyền thống có mỡ heo, thịt xông khói hoặc thịt bò |
| marshmallow, Jell-O | **không chay** | Có gelatin |
| nhuyễn thể (clam, mussel, oyster, scallop, squid) | không có nhóm FDA nào | FDA chỉ tính giáp xác; EU có tính nhuyễn thể |
| dừa | không phải tree_nuts | FDA 2025 |

Sửa thẳng cột `allergens` trong file này **chỉ có tác dụng đến lần build tiếp theo**, vì file được sinh từ `rules.csv`. Vì vậy Thy chỉ cần **ghi nhận xét vào một cột mới `review`** (ví dụ `bỏ soy`, `thêm egg`, `ok`). Mình sẽ chuyển các nhận xét đó thành quy tắc trong `rules.csv`.
