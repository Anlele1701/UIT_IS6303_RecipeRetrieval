# Hướng dẫn duyệt từ điển M1 (việc 👤 của Thy)

Có 3 file cần duyệt, đều nằm trong `data/lexicon/`. Mở bằng Excel hoặc VS Code đều được. **Khi lưu, giữ định dạng CSV UTF-8.** Với Excel, chọn "CSV UTF-8 (Comma delimited)".

Duyệt xong thì nhắn mình "đã duyệt M1". Mình sẽ nhập các sửa đổi, chạy lại gắn thẻ, đưa thẻ xuống `chunk`, rồi trình gate M1.

---

## 1. `synonym_suggestions.csv`: gợi ý đồng nghĩa của LLM (khoảng 5 phút)

Mỗi dòng là một tên nguyên liệu mà từ điển chưa nhận ra, có xuất hiện từ 2 dòng nguyên liệu trở lên. `qwen2.5:7b` đã đề xuất tên gốc cho nó.

**Chỉ cần duyệt khoảng 17 dòng đầu.** File đã được xếp sẵn để các dòng quan trọng đứng trên:
- **5 dòng đầu** có `tags_if_accepted`. Nếu chấp nhận, các dòng này sẽ thêm hoặc đổi thẻ dị ứng hay nhóm thực phẩm.
- **12 dòng tiếp theo** trỏ vào một canonical đã có sẵn.

Các dòng còn lại đều là `NEW:…`. LLM thường chỉ đưa ra một tên rất chung chung như `powder`, `mix`, `sauce`. Chấp nhận các dòng này chỉ xóa cờ `unknown`, chứ không thêm thẻ nào. **Khuyến nghị để trống.** Giữ `unknown` thì an toàn hơn, và nhánh ablation S+Unknown ở M6 sẽ đo đúng điều này.

Toàn bộ 446 dòng chỉ chiếm 1.440 dòng nguyên liệu, khoảng 0,5% số dòng. Lý do: mình đã tự rà toàn bộ 1.668 tên `unknown` và thêm quy tắc cho các từ có thịt, cá hoặc dị ứng (bologna, milkfish, labneh, brioche, natto…).

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

## 3. `allergen_map.csv`: hai mức thẻ (đã áp dụng theo quyết định của Thy, 14/10)

Theo quyết định của Thy: **gắn thẻ "có thể chứa" nhưng không loại hẳn công thức khi chưa chắc**, vì người nấu có thể chủ động chọn nguyên liệu.
- **Chắc chắn** (`kind` = `direct` / `hidden`): dùng để **lọc cứng**. Ví dụ: butter → milk, soy sauce → wheat + soy, worcestershire → fish, mayonnaise → egg.
- **Có thể chứa** (dấu `?` trong cột `allergens`, `kind` = `possible`): **không lọc**, chỉ cảnh báo ở câu trả lời và trên thẻ công thức.

Quyết định của Thy (chat 14/10), xét theo thành phần thật của nguyên liệu:

| Nguyên liệu | Mức |
|---|---|
| chocolate, chocolate chips, frosting | milk?, soy? (có thể chứa) |
| white chocolate, milk chocolate | milk chắc chắn (theo chuẩn FDA) |
| margarine, buttery spread, Parkay, I Can't Believe It's Not Butter | **không gắn** |
| peanut oil | peanut? |
| almond extract, amaretto | tree_nuts? |
| granola | **không gắn** |
| chestnut | tree_nuts **chắc chắn** |
| nuts / mixed nuts / trail mix | tree_nuts + peanut **chắc chắn** |
| red/green curry paste, tom yum paste | crustacean_shellfish? (+ fish?) |
| kimchi | **không gắn** |
| imitation crab | fish chắc chắn + crustacean_shellfish? |
| cake mix, brownie mix | wheat chắc chắn + soy? |
| Oreo | wheat + soy chắc chắn, milk? |
| oyster sauce, doubanjiang, injera | wheat? |
| naan | wheat chắc chắn + milk? |
| refried/baked beans, Jiffy mix, vỏ bánh pie làm sẵn | có thể không chay (meat?) |
| bacon bits (không ghi rõ loại) | thịt **chắc chắn** |
| seafood stock | fish?, crustacean_shellfish? (vẫn không chay) |
| instant pistachio pudding mix | **không gắn** |
| hoisin | soy + wheat chắc chắn, sesame? |

**Dòng ghi "X-free"** (gluten-free, dairy-free, egg-free, nut-free, vegan…): dòng đó không mang nhóm X, cũng theo quyết định của Thy. Ngoại lệ: "non-dairy" và "lactose-free" **không** được tính là không có sữa, vì creamer non-dairy vẫn có casein, còn sữa lactose-free vẫn là sữa.

Nếu Thy muốn chuyển mục nào giữa hai mức, chỉ cần nói tên nguyên liệu. Ngoài ra Thy có thể lướt khoảng 100 dòng đầu `allergen_map.csv` và ghi nhận xét vào cột mới `review`.
