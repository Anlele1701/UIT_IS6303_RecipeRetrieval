# Bảng 3. Phân loại lỗi

Report run `eval/pooled/20260929-182256`, riêng Hybrid lấy từ run `eval/pooled/20261006-224100` (reranker mxbai-rerank-base-v1). Chấm theo answer key gộp `eval/qrels.csv`. Hạng trong ví dụ lấy ở chiến lược semantic.

| Mã | Nhóm lỗi | Dấu hiệu | Tầng | Số truy vấn | Ví dụ |
|---|---|---|---|---|---|
| E1 | Lệch từ vựng | Truy vấn và công thức dùng từ khác nhau cho cùng một ý | Truy xuất (BM25) | 16–17 (11) | q155 "creamy black bean and tomato stew" → *Black Bean and Tomato Soup*: BM25 hạng 20, dense hạng 2 |
| E2 | Mất chi tiết chính xác | Ràng buộc cụ thể (nguyên liệu hiếm, con số, phủ định) bị bỏ qua | Truy xuất (dense) | 17–19 (9) | q012 "yellow split pea soup with curry powder" → *Vegan Split Pea Soup II*: BM25 hạng 1, dense ngoài top 20 |
| E3 | Bỏ sót ứng viên | Không công thức liên quan nào trong top 20 của Hybrid | Truy xuất | 6–7 (5) | q117 "citrusy alcoholic drink with cola" → *Long Island Iced Tea*: cả 4 cấu hình đều ngoài top 20 |
| E4 | Xếp hạng lại sai | Công thức liên quan trong top-5 sau RRF bị đẩy xuống | Xếp hạng lại | 0–2 (0) | q281 "warm, coffee-flavored dessert in mug" → *Easy Coffee Mug Cake*: hạng 1 sau RRF, hạng 7 sau xếp hạng lại |
| E5 | Chunk thiếu ngữ cảnh | Một Direction chunk khớp truy vấn dù cả công thức không phù hợp | Chunking | – | – |
| E6 | Lỗi nhãn hoặc truy vấn | Mô hình đánh giá chấm sai hoặc truy vấn quá mơ hồ | Đánh giá | 30 nhãn "partial", 55 truy vấn mơ hồ | q002 "creamy tomato based dressing with vinegar" → *Dorothy Lynch Style Salad Dressing*: công thức không nói là creamy |

Bảng 3. Phân loại lỗi. Số truy vấn là khoảng giá trị qua ba chiến lược chunking; số trong ngoặc là số truy vấn rơi vào nhóm ở cả ba chiến lược.

E1 và E2 là hai nhóm lớn nhất, mỗi nhóm khoảng 17 truy vấn cho mỗi chiến lược. Tuy vậy, đây là lỗi của từng nhánh truy xuất riêng lẻ, và Hybrid khôi phục phần lớn các trường hợp này: với mxbai, Hybrid đưa cả q155 và q012 lên hạng 1 ở chiến lược semantic. Số lỗi còn lại ở kết quả cuối của Hybrid nhỏ hơn nhiều: E3 có 6–7 truy vấn, E4 chỉ còn 0–2 (với bge-reranker-base trước đây là 7–9).

## Ghi chú trước khi dùng

- E3: run chỉ lưu top 20, nên 7 là giới hạn trên cho định nghĩa gốc "không có trong 50 ứng viên". Giữ "50" chỉ khi chạy lại và lưu hạng đến 50.
- E5: không có kết quả nào ghi nhận. Bỏ dòng này hoặc thêm chú thích "chưa đo".
- E6: số đếm trên toàn bộ 298 truy vấn, không chỉ các truy vấn bị lỗi (`eval/label_check.csv`).

## Cách tính

| Mã | Quy tắc, trên `per_query.csv` |
|---|---|
| E1 | Dense trong top 10, Sparse ngoài top 10 (bucket `dense_win`) |
| E2 | Sparse trong top 10, Dense ngoài top 10 (bucket `sparse_win`) |
| E3 | Hybrid ngoài top 20 |
| E4 | Fusion baseline trong top 5, Hybrid ngoài top 5 |
| E6 | `label = partial` và `vague = yes` trong `eval/label_check.csv` |
