# Lý giải lựa chọn embedding, index và độ đo tương đồng của A3

*Bản nháp cho báo cáo (mục 3.4 và mục 4.5). Đối chiếu với Elkiran & Rasheed (2026). Số liệu dẫn từ file sinh tự động.*

**Tài liệu đối chiếu.** H. Elkiran, J. Rasheed, "An Empirical Evaluation of Retrieval, Reranking, and Similarity for a Q&A-Based Retrieval Augmented Generation System," *IEEE Access*, vol. 14, pp. 26053–26066, 2026, doi: 10.1109/ACCESS.2026.3664852. Đề xuất mã trích dẫn **[S27]** trong `A3_tong_hop_tai_lieu.md`.

Bài trên đánh giá một pipeline RAG trên SQuAD. Các thành phần được thay đổi gồm: 3 loại index ANN (HNSW, IVF, ScaNN), 3 độ đo (cosine, inner product, L2), 4 cách truy hồi và 2 reranker. Kết quả được phân tích bằng ANOVA, η² và hồi quy. Các kết luận chính:
- (i) Cách truy hồi và độ đo quyết định hiệu năng.
- (ii) Loại index gần như không ảnh hưởng chất lượng (η² < 0,01), chỉ ảnh hưởng độ trễ.
- (iii) Inner product ≈ cosine, cả hai hơn L2.

A3 **không đổi thiết lập** theo bài (quyết định của Thy ngày 14/10/2026). Phần dưới so sánh hai bên và giải thích vì sao.

## 1. Bảng so sánh

| Thành phần | Elkiran & Rasheed (2026) | A3 | Bằng chứng của A3 |
|---|---|---|---|
| Embedding | OpenAI `text-embedding-3-large` (3.072 chiều, API trả phí) | `nomic-embed-text` (768 chiều, chạy cục bộ qua Ollama) | Mục 2 |
| Index | Milvus: HNSW, IVF, ScaNN | Index cụm (kiểu IVF) của ParadeDB, **nằm cùng index BM25**, probe 0,02 | Mục 3, ADR-0003, ADR-0005 |
| Độ đo | cosine, inner product, L2 | cosine trên vector đã chuẩn hóa độ dài 1 | Mục 4, `eval/similarity_check.json` |
| Miền dữ liệu | SQuAD (Wikipedia, tiếng Anh, hỏi đáp có đáp án) | 32.719 công thức nấu ăn, truy vấn tiếng Việt và tiếng Anh, có ràng buộc cứng | |

## 2. Embedding: giữ `nomic-embed-text`, chạy cục bộ

1. **Chạy cục bộ là yêu cầu của đề tài** (quyết định Q3).
   - Dữ liệu hội thoại, trong đó có thông tin dị ứng (dữ liệu sức khỏe), không rời khỏi máy.
   - Không tốn phí API.
   - Tái lập được, vì model được ghim theo phiên bản Ollama.

   Embedding qua API như của bài thì vi phạm cả ba điều trên.
2. **So sánh công bằng với baseline.** Theo góp ý số 1 của GV, B0 phải là A1 Hybrid. Hệ S dùng cùng model embedding với B0, nên chênh lệch đo được ở M6 chỉ đến từ các module mới (hiểu truy vấn, lọc cứng, hậu kiểm), không lẫn hiệu ứng của embedding.
3. **Chi phí embed lại.** Trên máy build (chỉ có CPU), embed lại phân vùng semantic mất khoảng 3,9 giờ (`eval/env.json`). Mỗi model embedding mới thêm vào là thêm một lượt như vậy, cộng một index mới.
4. **Chính bài cũng tự nhận** việc chỉ dùng một model embedding là một hạn chế (mục IX), nên bài không cho bằng chứng rằng đổi embedding sẽ tốt hơn.
5. **Phần tiếng Việt** là điểm khác hẳn so với bài. Câu tiếng Việt được M1 dịch sang tiếng Anh trước khi embed. Nhánh tùy chọn S+M3 (BGE-M3, cũng chạy cục bộ) để dành cho câu hỏi RQ5.

## 3. Index: giữ index vector của ParadeDB, đặt chung với BM25

1. **Lý do cốt lõi là bộ lọc cứng.** A3 cần loại công thức theo dị ứng **trong lúc** tìm vector, không phải lọc sau. ParadeDB đặt cột thẻ, BM25 và vector trong **một index cho mỗi phân vùng**. Nhờ vậy, điều kiện `NOT (allergens @@@ pdb.term_set(...))` được áp ngay trong index cho cả BM25 lẫn dense (ADR-0005).
   - Spike M0 trên 166.438 chunk thật cho kết quả: 0 vi phạm, không truy vấn nào thiếu kết quả, overlap của dense có lọc không giảm.
   - HNSW của pgvector thì thường phải lọc sau khi tìm (post-filter), dễ trả thiếu kết quả khi điều kiện lọc chặt.
2. **Loại index hầu như không ảnh hưởng chất lượng**, đúng như kết luận (ii) của bài. Ablation của A1 trên chiến lược semantic, 298 truy vấn, reranker bge (`A1/eval/pooled/20260929-*`):

| Cấu hình | Index | R@5 | MRR | nDCG@10 |
|---|---|---:|---:|---:|
| Dense đứng riêng | ParadeDB, probe 0,02 | 0,859 | 0,697 | 0,744 |
| Dense đứng riêng | ParadeDB, probe 1,0 | 0,872 | 0,703 | 0,754 |
| Dense đứng riêng | pgvector HNSW (ef 200) | 0,872 | 0,704 | 0,755 |
| **Hybrid (B0)** | ParadeDB, probe 0,02 | 0,919 | 0,758 | 0,808 |
| Hybrid | ParadeDB, probe 1,0 | 0,916 | 0,760 | 0,809 |
| Hybrid | pgvector HNSW (ef 200) | 0,916 | 0,760 | 0,809 |

   - Index chỉ ảnh hưởng **dense đứng riêng**, khoảng +1,3 điểm R@5.
   - Sau khi qua fusion và rerank, chênh lệch **bằng 0 trong phạm vi nhiễu**. BM25 và reranker bù lại những ứng viên mà ANN bỏ sót.
   - Kết quả này khớp với nhận định của bài: index chủ yếu đánh đổi độ trễ, không phải chất lượng.
3. **Hạn chế cần nêu trong báo cáo.** Ở M1, mình phát hiện tìm vector của ParadeDB **vẫn xấp xỉ** ngay cả khi probe = 1,0 (truy vấn q080, `docs/progress.md`). Vì vậy nhánh "exact-dense" của A1 không thật sự chính xác. Hệ quả này không ảnh hưởng so sánh giữa B0 và S, vì cả hai chạy trên cùng index.

## 4. Độ đo: cosine trên vector đã chuẩn hóa, tương đương inner product và L2

1. Với vector có độ dài 1: ‖q − d‖² = 2 − 2·q·d và cos(q, d) = q·d. Do đó **cosine, inner product và L2 cho cùng một thứ hạng**. Chọn độ đo nào không ảnh hưởng chất lượng.
2. **Kiểm chứng trên dữ liệu A3** (`scripts/similarity_check.py`, file kết quả `eval/similarity_check.json`):
   - Cả 166.438 embedding có độ dài trong khoảng [0,999999; 1,000001].
   - Với 20 truy vấn A1 lấy ngẫu nhiên (seed 42), top-50 theo inner product và theo L2 **trùng hoàn toàn** với top-50 theo cosine: **20/20 truy vấn**. Phép tìm ở đây là tìm chính xác bằng quét toàn bảng, không qua index.
3. **Nhận xét phản biện.** Embedding của OpenAI vốn cũng được chuẩn hóa độ dài 1. Vì thế khoảng cách lớn giữa L2 và inner product mà bài báo cáo (MRR 0,521 so với 0,709) khó giải thích bằng toán học của độ đo. Nhiều khả năng nó đến từ cách mỗi loại index ANN cài đặt từng độ đo, hoặc từ ngưỡng điểm. Bài không tách riêng yếu tố này. Đây là một luận điểm để A3 **không** đưa độ đo vào thành nhánh ablation.
4. A3 dùng cosine (`<=>`), cùng quy ước với A1. Nomic được huấn luyện với cosine, và vector được chuẩn hóa ngay khi nạp (`ingest.embed`, `api.embed.embed_query`).

## 5. Những gì A3 có thể học thêm từ bài (đưa vào bài viết, không đổi code)

- **Độ lớn hiệu ứng.** Bài nhấn mạnh rằng p-value cực nhỏ khi N lớn thì chưa nói lên mức độ quan trọng của khác biệt. A3 dùng kiểm định cặp đôi Wilcoxon + Holm theo từng truy vấn, nên báo cáo nên ghi thêm độ lớn hiệu ứng và bootstrap CI cạnh p-value. Kiểm định cặp đôi phù hợp với thiết kế "cùng truy vấn, khác cấu hình" của A3 hơn ANOVA nhiều nhân tố, vì ANOVA giả định các mẫu độc lập.
- **Reranker.** Bài kết luận MiniLM tốt hơn BGE. Trên dữ liệu công thức, A1 đo được thứ tự mxbai (MRR 0,895) > MiniLM (0,799) > BGE (0,758). Thứ hạng MiniLM > BGE khớp với bài, nhưng reranker tốt nhất thì phụ thuộc miền dữ liệu. Đây là lý do A3 giữ mxbai.
- **HyPE / HyDE** (sinh câu hỏi giả hoặc văn bản giả). Đưa vào phần hướng phát triển. Với A3, HyPE có rủi ro rò rỉ dữ liệu: bộ truy vấn A1 do chính `qwen2.5:7b` sinh từ công thức, nên câu hỏi giả do cùng model sinh sẽ khớp một cách giả tạo. HyDE có thể viết ra văn bản giả chứa đúng nguyên liệu người dùng cần tránh.
