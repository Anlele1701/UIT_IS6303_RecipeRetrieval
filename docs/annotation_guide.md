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
