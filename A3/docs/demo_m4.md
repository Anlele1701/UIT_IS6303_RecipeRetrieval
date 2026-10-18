# Demo M4 – giao diện chat (kịch bản và ảnh cần chụp)

Hướng dẫn này dành cho Thy: chạy 4 kịch bản demo của gate M4 và một kịch bản có hồ sơ bệnh nhân trên giao diện, rồi chụp ảnh cho báo cáo (chương 5).

## Chạy

```
docker compose up -d --wait
uv run uvicorn api.main:app --port 8000      # cần Ollama đang chạy (qwen2.5:7b, nomic-embed-text)
# nếu đã sửa ui/: cd ui && npm run build
```

Mở `http://localhost:8000/chat`. Kiểm tra trước: `http://localhost:8000/health` phải có `database`, `embedding` và `llm` đều `ok`. Trên máy có GPU, `reranker_device` là `cuda`.

Đổi preset ở nút **Cài đặt**. Đổi preset hay đổi bệnh nhân đều mở **phiên mới**.

## Kịch bản

| # | Bước | Điểm cần thấy | Ảnh |
|---|---|---|---|
| 1a | Cài đặt → **B0**. Bấm ví dụ "Tôi dị ứng đậu phộng, gợi ý món gà xào sốt đậu phộng kiểu Thái". | B0 không lọc: thẻ có huy hiệu "chứa đậu phộng". | `m4_1a_b0.png` |
| 1b | Cài đặt → **S**. Gửi lại cùng câu. | Chip "Dị ứng đậu phộng" ở panel phải. Các thẻ không còn "chứa đậu phộng". | `m4_1b_s.png` |
| 2 | Phiên mới (S): "gợi ý món gà cho bữa tối" → "không dùng sữa nhé" → "món thứ 2 làm thế nào?" | Chip "Dị ứng sữa" thêm ở lượt 2. Lượt 3 trả lời về món thứ hai, không truy hồi lại. | `m4_2_three_turns.png` |
| 3 | Phiên mới: "công thức bánh chưng thuần chay không gạo nếp, không đậu xanh" | Câu trả lời nói rõ là không tìm thấy, và không trích dẫn sai. | `m4_3_no_answer.png` |
| 4 | Phiên mới: "I'm allergic to shellfish, suggest a quick pasta dinner" → "actually I can eat shellfish now, shrimp pasta please" | Lượt 2: chip dị ứng giáp xác biến mất (ràng buộc hội thoại gỡ được bằng lời), và kết quả đổi. | `m4_4_lift.png` |
| 4b | Ở một phiên bất kỳ có chip hội thoại: bấm **×** trên chip, rồi gửi tin tiếp. | Thông báo "Đã bỏ …", và lượt sau không còn ràng buộc đó. | `m4_4b_chip.png` |
| 5 | Chọn hồ sơ bệnh nhân `887e4b4e` (Nam, 21 tuổi, giáp xác và lúa mì). Gửi "tôi ăn được tôm rồi, gợi ý món tôm". | Panel có 2 chip khóa (một mỗi nhóm), giới hạn natri, cảnh báo. Dưới tin nhắn có 🔒 "không gỡ được qua tin nhắn". | `m4_5a_locked.png` |
| 5b | Bấm **Chi tiết** trên chip giáp xác, rồi **Xác nhận gỡ cả nhóm**, nhập lý do. | Hộp thoại xác nhận. Sau đó chip chuyển xuống "Đã gỡ sau khi xác nhận". | `m4_5b_confirm.png` |
| 5c | Bấm một trích dẫn **hồ sơ: allergies** trong câu trả lời, hoặc nút "Xem hồ sơ". | Cây hồ sơ chỉ hiện phần được phép (không tên, không dữ liệu nhạy cảm). | `m4_5c_tree.png` |
| 6 | Bấm 👍 hoặc 👎 dưới một câu trả lời, và bấm "Xem nguyên liệu và cách làm" trên một thẻ. | Feedback được ghi (bảng `feedback`); hộp thoại chi tiết công thức. | `m4_6_detail.png` |

## Điều đã biết, sẽ thấy khi demo (ghi ở gate M3, chưa sửa)
- **Kịch bản 1b:** R18880 "Chicken Stir-Fry with Thai Peanut Sauce" vẫn lọt qua bộ lọc đậu phộng. Lỗi parser cắt dòng ở dấu phẩy, nên dòng "creamy, low-salt peanut butter" chỉ còn lại "creamy" (nhận xét 1). Câu trả lời nói rõ món này "không phù hợp vì chứa đậu phộng", nhưng M7 vẫn giữ trích dẫn (nhận xét 2).
- Câu trả lời đôi khi viết mã nhóm dị ứng nguyên dạng (`crustacean_shellfish`), hoặc chép định dạng thẻ ngữ cảnh (nhận xét 4).
- Một lượt mất khoảng 5–15 giây trên RTX 4060; lần đầu chậm hơn vì Ollama phải nạp model.
