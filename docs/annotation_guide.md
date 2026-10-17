# Hướng dẫn gán nhãn dị ứng và chế độ ăn (M2, 200 công thức)

Mục đích: tạo **nhãn vàng** để đo độ chính xác của bộ gắn thẻ (M1) và của bộ kiểm độc lập (llama3.1:8b). Nhãn được gán **mù**: công cụ không hiển thị dự đoán nào của máy.

Mở công cụ: từ `recipe-assistant/`, chạy `uv run scripts/audit_tool.py` rồi mở http://localhost:8765. Công cụ lưu ngay sau mỗi công thức. Có thể dừng bất cứ lúc nào, mở lại sẽ tiếp tục đúng chỗ.

## 1. Đọc gì

- Đọc **toàn bộ dòng nguyên liệu**. Chỉ mở phần cách làm (directions) khi dòng nguyên liệu bị thiếu hoặc quá mơ hồ.
- **Xét theo thành phần thật** của từng nguyên liệu, kể cả thành phần ẩn. **Không suy ra từ tên gọi.** Ví dụ, "balsamic cream" là giấm balsamic cô đặc, không có sữa.

## 2. Ba mức cho mỗi nhóm dị ứng

| Mức | Khi nào chọn |
|---|---|
| **Có** | Công thức **chắc chắn hoặc rất có thể** chứa nhóm này, kể cả qua thành phần ẩn |
| **Có thể** | Phụ thuộc hãng hoặc lựa chọn của người nấu, hoặc dòng nguyên liệu mơ hồ. Ví dụ: "1 package frosting", "chocolate chips" |
| **Không** | Không có nguyên liệu nào thuộc nhóm. Đây là mức mặc định |

Chín nhóm theo FDA:

| Nhóm | Ví dụ "Có" (kể cả thành phần ẩn) |
|---|---|
| Sữa (milk) | bơ, phô mai, kem, sữa chua, buttermilk, whey, ghee |
| Trứng (egg) | trứng, lòng đỏ/trắng, mayonnaise |
| Cá (fish) | cá các loại, cá cơm, nước mắm, Worcestershire |
| Giáp xác (crustacean_shellfish) | tôm, cua, tôm hùm. Nhuyễn thể (nghêu, sò, hàu, mực) **không** thuộc nhóm này |
| Hạt cây (tree_nuts) | hạnh nhân, óc chó, hồ đào, hạt điều, hạt dẻ cười, hạt phỉ, macadamia, hạt thông, hạt dẻ, pesto. **Dừa không tính** (FDA 2025) |
| Đậu phộng (peanut) | đậu phộng, bơ đậu phộng |
| Lúa mì (wheat) | bột mì, mì ống, vụn bánh mì, bánh mì, nước tương thường |
| Đậu nành (soy) | nước tương, đậu hũ, miso, edamame |
| Mè (sesame) | mè, dầu mè, tahini |

Lưu ý:
- Dòng ghi **"gluten-free", "dairy-free", "egg-free", "nut-free", "vegan"…** thì nhóm tương ứng là **Không**, cho riêng dòng đó.
- "Non-dairy" và "lactose-free" **vẫn có sữa**: non-dairy creamer chứa casein, còn sữa lactose-free vẫn là sữa.
- Một dòng có lựa chọn, ví dụ "butter or margarine": nếu một trong các lựa chọn chứa nhóm thì chọn **Có**.

## 3. Chế độ ăn (bắt buộc chọn cho mỗi công thức)

| Nhãn | Có (đạt) khi |
|---|---|
| **Vegetarian** | Không có thịt, gia cầm, cá, hải sản, gelatin, mỡ động vật, nước dùng từ thịt hay cá |
| **Vegan** | Vegetarian, và thêm: không có sữa, trứng, mật ong |

Chọn **Có thể** khi phụ thuộc hãng. Ví dụ: refried beans đóng hộp có thể có mỡ heo; marshmallow có gelatin.

## 4. Nhịp làm

- Khoảng 1 phút mỗi công thức. Nên chia 4 buổi, mỗi buổi 50 công thức.
- Ô **ghi chú** dùng để ghi chỗ phân vân. Mình sẽ đọc lại các ghi chú này khi tổng hợp.
- Nếu muốn sửa một công thức đã lưu, bấm **← Trước**.

## 5. Phân xử phiếu "yes" của bộ kiểm độc lập (từ MV3, áp cho mọi preset)

Bộ kiểm `llama3.1:8b` (`scripts/checker.py`) đôi khi trả lời "có chứa" với bằng chứng sai. Ví dụ ở demo MV3: "salmon fillets" được dùng làm bằng chứng cho lúa mì. Vì vậy mỗi phiếu "yes" được chấm theo hai cách:

| Số | Cách tính | Vai trò |
|---|---|---|
| **CVR_raw** | Mọi phiếu "yes" đều là vi phạm | Cận trên, tiêu chí chặt |
| **CVR_adjudicated** | Sau bước tự động và bước người duyệt dưới đây | Số chính để so các preset |

Cả hai số được báo cáo **cho mọi preset, kể cả B0 và B1**, theo đúng một quy trình.

**Bước tự động** (`scripts/adjudicate.py`; không import từ điển hay code của bộ gắn thẻ, có test kiểm tra):
- Phiếu mà chính bộ kiểm đánh dấu bằng chứng không hợp lệ (`evidence_ok = false`) → **loại**.
- Chuỗi bằng chứng không xuất hiện nguyên văn trong dòng nguyên liệu thô (không phân biệt hoa thường, nhiều dấu cách tính như một) → **loại**.
- Còn lại → đưa vào **hàng duyệt** `eval/labels/checker_queue.csv`. Trong lúc chờ duyệt, phiếu vẫn **tính là vi phạm**.

**Bước người duyệt:**
- Hàng duyệt chỉ có: mã công thức, tên, nhóm ràng buộc, dòng bằng chứng và toàn bộ dòng nguyên liệu. **Không có preset, run hay thẻ nào sinh ra công thức đó.**
- Người duyệt trả lời một câu: dòng bằng chứng có thật sự làm công thức chứa nhóm đó không. Xét theo thành phần thật như mục 1. Ví dụ: "salmon" → không chứa lúa mì; "1 cup flour" → có.
- Nhãn ghi vào `eval/labels/checker_adjudication.csv` (`recipe_id, constraint, evidence_line, violation = yes|no, reviewer, date, note`), để chạy lại ra cùng kết quả.
- Đã có: R2920 / `allergen:wheat` (Worcestershire) = **no**. Thy quyết định ngày 17/10/2026: gluten (nếu có) đến từ giấm mạch nha làm từ lúa mạch, mà lúa mạch không thuộc nhóm wheat của FDA.
