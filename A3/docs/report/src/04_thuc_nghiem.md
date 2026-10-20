# Chương 4. Thực nghiệm và đánh giá

## 4.1. Xây dựng bộ test

Bộ test của A3 gồm năm tập (Bảng 4.1). Tập hồi quy T1 lấy mẫu từ bộ truy vấn của A1, dùng để bảo đảm A3 không làm giảm chất lượng ở loại truy vấn mà A1 đã xử lý tốt. Tập ràng buộc một lượt T2 (một nửa bằng tiếng Việt) chứa các yêu cầu về dị ứng, loại trừ nguyên liệu, chế độ ăn hoặc thời gian. Tập không trả lời được T3 gồm các tổ hợp ràng buộc mà không công thức nào thỏa mãn và các câu hỏi ngoài phạm vi. Tập hội thoại nhiều lượt T4 gồm các hội thoại trong đó ràng buộc được nêu ở lượt trước và phải còn hiệu lực ở lượt sau.

Tập mới là tập hồ sơ bệnh nhân. Nhóm chọn {{pq:patients|int}} bệnh nhân Synthea còn sống theo phân tầng của quy tắc P8 và gắn cho mỗi bệnh nhân ba câu hỏi, tổng cộng {{pq:questions|int}} truy vấn ({{pq:by_lang.vi|int}} tiếng Việt, {{pq:by_lang.en|int}} tiếng Anh). Tập này cố ý gồm ba loại câu với số lượng bằng nhau: câu không nhắc ràng buộc nào, để kiểm tra ràng buộc từ hồ sơ có được tự động áp dụng; câu thêm ràng buộc mới bên cạnh ràng buộc của hồ sơ; và câu cần ngữ cảnh thời gian trong hồ sơ, để kiểm tra bước chọn nút theo ngữ cảnh. Để so sánh các cách đọc hồ sơ khi đầu vào là văn bản tự do, cùng bộ câu hỏi được chạy thêm ở chế độ narrative (mục 3.4.1).

Truy vấn được tạo bằng ba nguồn: ghép mẫu câu kết hợp diễn đạt lại bằng mô hình ngôn ngữ, viết tay bởi thành viên nhóm ({{flow:handwritten.kept|int}} câu), và các câu tiếng Việt tự nhiên có cả lỗi chính tả hay viết không dấu. Vì qwen2.5:7b vừa là mô hình hiểu truy vấn của hệ, phần câu do mô hình diễn đạt lại được sinh bằng llama3.1:8b, để tránh kết quả F1 bị đẹp hơn thực tế do mô hình quen với cách diễn đạt của chính nó.

Mọi truy vấn ứng viên phải qua bảy quy tắc hợp lệ, mỗi quy tắc được báo cáo số câu bị loại. V1 yêu cầu truy vấn không chép nguyên tiêu đề công thức. V2 yêu cầu truy vấn có ít nhất một công thức thỏa ràng buộc (với tập không trả lời được thì ngược lại). V3 kiểm tra câu tiếng Việt có dấu và đúng ngôn ngữ đã định. V4 loại các câu gần trùng nhau. V5 giới hạn độ dài từ 3 đến 40 từ. V6 yêu cầu ràng buộc chuẩn của mỗi câu phải được người xác nhận; ở A3, bản nháp ràng buộc chuẩn do mô hình soạn và thành viên nhóm xác nhận từng câu hoặc chấp nhận theo nhóm. V7 yêu cầu với câu gắn hồ sơ, tập ràng buộc chuẩn phải bằng hợp của ràng buộc lấy từ đáp án Synthea và ràng buộc trong câu hỏi, và phải còn ít nhất một công thức thỏa tập này. Kết quả được trình bày ở Bảng 4.1 và Hình 4.1. Bộ test được đóng băng (lưu sha256) trước khi chạy thực nghiệm.

**Bảng 4.1. Luồng lọc bộ test A3 (`eval/testset/testset_flow.json`)**

| Tập | Sinh ra | Loại ở V2 | Loại ở V4 | Còn lại | Sau V6 (đóng băng) |
|---|---|---|---|---|---|
| T1 hồi quy | {{flow:sets.t1.generated|int}} | {{flow:sets.t1.rejected.V2|int}} | {{flow:sets.t1.rejected.V4|int}} | {{flow:sets.t1.kept|int}} | {{flow:sets.t1.V6.final|int}} |
| T2 ràng buộc một lượt | {{flow:sets.t2.generated|int}} | {{flow:sets.t2.rejected.V2|int}} | {{flow:sets.t2.rejected.V4|int}} | {{flow:sets.t2.kept|int}} | {{flow:sets.t2.V6.final|int}} |
| T3 không trả lời được | {{flow:sets.t3.generated|int}} | {{flow:sets.t3.rejected.V2|int}} | {{flow:sets.t3.rejected.V4|int}} | {{flow:sets.t3.kept|int}} | {{flow:sets.t3.V6.final|int}} |
| T4 hội thoại (số hội thoại) | {{flow:sets.t4.generated|int}} | {{flow:sets.t4.rejected.V2|int}} | {{flow:sets.t4.rejected.V4|int}} | {{flow:sets.t4.kept|int}} | {{flow:sets.t4.V6.final|int}} |
| Hồ sơ bệnh nhân | – | – | – | – | {{pq:questions|int}} |

V1, V3 và V5 không loại câu nào ở bốn tập. Sau khi lọc, các tập được cắt về chỉ tiêu theo seed, rồi cộng các câu viết tay.

![Hình 4.1. Sơ đồ luồng lọc bộ test](figures/fig_testset_flow.png)

## 4.2. Gán nhãn và bộ kiểm độc lập

Nhãn độ liên quan được xây dựng bằng phương pháp pooling: gộp mười kết quả đầu của mọi cấu hình, rồi gán nhãn theo thang 0, 1, 2. Việc gán nhãn do một mô hình ngôn ngữ khác họ với mô hình sinh (llama3.1:8b) thực hiện, nhằm tránh thiên lệch giám khảo ưu ái câu trả lời của mô hình cùng họ [9]. Nhóm kiểm tra lại 50 mẫu bằng tay và báo cáo hệ số Cohen's κ giữa người và mô hình.

Vi phạm ràng buộc được chấm bằng một bộ kiểm độc lập: mô hình ngôn ngữ đọc toàn văn danh sách nguyên liệu và trả lời công thức có chứa nhóm dị ứng hoặc vi phạm chế độ ăn hay không, kèm dòng nguyên liệu làm bằng chứng. Bộ kiểm không sử dụng từ điển hay thẻ của bộ gắn thẻ, và một unit test kiểm tra rằng mã của bộ kiểm không import mã của bộ gắn thẻ. Thiết kế này tránh đánh giá vòng tròn: nếu dùng chính bộ thẻ vừa để lọc vừa để chấm thì tỉ lệ vi phạm của hệ đề xuất sẽ bằng không theo định nghĩa. Phiếu "có vi phạm" có bằng chứng không tìm thấy nguyên văn trong công thức bị loại tự động; các phiếu còn lại được đưa vào một hàng duyệt mù cho người, không hiển thị cấu hình nào đã trả về công thức. Bản thân bộ kiểm cũng được đánh giá precision và recall trên cùng tập 200 công thức có nhãn bạc, để kết quả vi phạm được báo cáo kèm sai số của công cụ đo. Vi phạm nguyên liệu có tên được chấm bằng so khớp nguyên từ, còn vi phạm thời gian và ngưỡng dinh dưỡng được tính trực tiếp từ các cột của công thức, nên không cần bộ kiểm riêng.

Với nhánh hồ sơ, đáp án ràng buộc được lấy tự động từ các trường có cấu trúc của Synthea theo cùng bộ quy tắc P2 đến P6, tương tự cách các nghiên cứu trước lấy đáp án từ các tài nguyên đang hiệu lực. Để tránh vòng tròn ở bước ánh xạ, đáp án được dừng ở mức thực thể (dị ứng nào, bệnh nào, thuốc nào) chứ không ở mức ngưỡng dinh dưỡng; bước ánh xạ luật được kiểm tra riêng bằng unit test. Nhóm kiểm tra tay {{pq:manual_check_patients|int}} bệnh nhân để phát hiện lỗi trong chính bước lấy đáp án.

## 4.3. Các cấu hình so sánh

Mọi cấu hình là một tập cờ trong cùng một mã nguồn (Bảng 4.2). B0 là hệ Hybrid của A1 chạy lại trên bộ test của A3: câu hỏi đi thẳng vào truy hồi, không hiểu truy vấn, không lọc và không sinh câu trả lời. B1 là RAG đơn giản trên A1: B0 cộng bước sinh. S là hệ đề xuất đầy đủ. Mỗi cấu hình ablation tắt đúng một thành phần của S. Riêng S−Filter không bỏ ràng buộc mà nối ràng buộc vào câu truy vấn, tức là để truy hồi ngữ nghĩa tự xử lý; S−Norm vẫn lọc nhưng so khớp chuỗi trên dòng nguyên liệu thô thay vì thẻ đã chuẩn hóa. S−Conv chỉ có nghĩa trên tập hội thoại T4.

**Bảng 4.2. Các cấu hình so sánh**

| Cấu hình | Hiểu truy vấn | Trạng thái hội thoại | Lọc cứng | Chuẩn hóa | Rerank | Sinh | Hậu kiểm |
|---|---|---|---|---|---|---|---|
| B0 (A1 Hybrid) | – | – | – | – | ✓ | – | – |
| B1 (RAG trên A1) | – | – | – | – | ✓ | ✓ | – |
| S | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| S−QU | – | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| S−Filter | ✓ | ✓ | nối vào truy vấn | ✓ | ✓ | ✓ | ✓ |
| S−Norm | ✓ | ✓ | ✓ | chuỗi thô | ✓ | ✓ | ✓ |
| S−Rerank | ✓ | ✓ | ✓ | ✓ | – | ✓ | ✓ |
| S−Verify | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | – |
| S−Conv (T4) | ✓ | – | ✓ | ✓ | ✓ | ✓ | ✓ |

Với nhánh hồ sơ, bốn cách đọc hồ sơ được so sánh trên cùng pipeline: P-Direct đọc thẳng các trường có mã và là cận trên; P-Vectorless là thiết kế đề xuất (nút cố định đọc bằng code, nút theo ngữ cảnh do mô hình chọn); P-Vectorless-Fixed bỏ nút cố định, để mô hình chọn mọi nút; P-Vector là RAG vector trên chính hồ sơ (cắt hồ sơ thành chunk, lấy các chunk gần câu hỏi nhất rồi cho mô hình trích ràng buộc). S-Profile bỏ hoàn toàn ràng buộc hồ sơ, chỉ dùng ràng buộc trong hội thoại.

## 4.4. Độ đo

Độ đo chính của bài toán là tỉ lệ vi phạm. CVR@5 là tỉ lệ công thức vi phạm ít nhất một ràng buộc trong năm công thức đưa vào ngữ cảnh, trung bình theo câu; Safe@5 là tỉ lệ câu mà cả năm công thức đều không vi phạm. Vi phạm dị ứng và chế độ ăn được tính ở ba mức: strict (mọi phiếu "có" của bộ kiểm), lenient (bỏ phiếu không chắc chắn) và adjudicated (sau bước loại tự động và hàng duyệt của người). Báo cáo dùng mức adjudicated làm số chính.

Ở tầng truy hồi, nDCG@10′, Recall@10 và MRR được tính trên nhãn pooling với độ liên quan đã điều chỉnh rel′ = rel × 1[công thức thỏa ràng buộc của câu]: một công thức đúng món nhưng vi phạm dị ứng không được tính là liên quan. Với T1, công thức gốc của câu A1 được tính là rel 2 như A1. Ở tầng sinh, citation validity là tỉ lệ trích dẫn nằm trong ngữ cảnh; citation safety là tỉ lệ trích dẫn trỏ tới công thức không vi phạm; faithfulness và answer relevance được chấm theo kiểu RAGAS [12]; negative rejection là tỉ lệ câu T3 được từ chối đúng, còn false refusal là tỉ lệ câu T1 và T2 bị từ chối sai. Bước hiểu truy vấn được đo bằng độ chính xác ý định và slot F1 vi mô theo loại và giá trị chuẩn của ràng buộc. Độ trễ được đo theo từng module (p50 và p95) từ bảng truy vết.

Với nhánh hồ sơ, độ đo gồm precision, recall và F1 của dị ứng, bệnh và thuốc trích được so với đáp án Synthea; số ca bỏ sót dị ứng; Safe@5 theo dị ứng, theo ngưỡng dinh dưỡng và theo ràng buộc hội thoại; tỉ lệ chọn đúng nút theo ngữ cảnh; và chi phí gồm số lời gọi mô hình, số ký tự đọc và độ trễ của V1 đến V3.

So sánh giữa các cấu hình là so sánh ghép cặp theo câu (theo hội thoại với T4, theo bệnh nhân với nhánh hồ sơ). Khoảng tin cậy 95% được tính bằng paired bootstrap; giá trị p được tính bằng bootstrap và kiểm định Wilcoxon dấu hạng, hiệu chỉnh Holm trong từng họ so sánh (S so với mỗi cấu hình khác, theo từng độ đo).

## 4.5. Thiết lập thực nghiệm

Mọi thực nghiệm chạy trên một máy với GPU {{m6s:machine.gpu|raw}}, mô hình chạy cục bộ qua Ollama với seed {{m6s:seed|raw}}, temperature 0 cho hiểu truy vấn và chấm điểm, 0,2 cho sinh câu trả lời; mọi lời gọi mô hình được lưu đệm theo hash của đầu vào. Danh sách mô hình, prompt và tham số được ghi trong RAG Card (Phụ lục A). Do giới hạn thời gian, thực nghiệm trên bộ test A3 dùng một mẫu theo seed khoảng 10% mỗi tập: T1 {{d:sample.t1|int}}, T2 {{d:sample.t2|int}}, T3 {{d:sample.t3|int}} câu và T4 {{d:sample.t4|int}} hội thoại, chạy qua chín cấu hình, tổng cộng {{d:turns|int}} lượt. Thực nghiệm nhánh hồ sơ chạy trên toàn bộ {{pq:questions|int}} câu của {{pq:patients|int}} bệnh nhân, ở cả hai dạng đầu vào. Pool chấm độ liên quan gồm {{m6:pool.pairs|int}} cặp truy vấn – công thức. Hàng duyệt mù của bộ kiểm đã được người duyệt hết: {{m6:checker.by_status.confirmed|int}} phiếu được xác nhận là vi phạm, {{m6:checker.by_status.rejected|int}} phiếu bị bác, và {{m6:checker.by_status.dropped_flagged|int}} phiếu bị loại tự động vì bằng chứng không hợp lệ.

## 4.6. Kết quả, ablation và phân tích lỗi

### 4.6.1. Kết quả chính

Bảng 4.3 so sánh các cấu hình trên bộ test A3. So với hệ Hybrid của A1 (B0), hệ đề xuất S giảm CVR@5 trên tập ràng buộc một lượt từ {{m6:summary.[B0|t2].cvr_adj.mean|pct}} xuống {{m6:summary.[S|t2].cvr_adj.mean|pct}} và trên tập hội thoại từ {{m6:summary.[B0|t4].cvr_adj.mean|pct}} xuống {{m6:summary.[S|t4].cvr_adj.mean|pct}}. Mức giảm theo từng câu là {{m6:comparisons.cvr_adj.[S - B0].diff|sf3}} (KTC 95% [{{m6:comparisons.cvr_adj.[S - B0].ci_lo|f3}}; {{m6:comparisons.cvr_adj.[S - B0].ci_hi|f3}}], Wilcoxon sau Holm p = {{m6:comparisons.cvr_adj.[S - B0].p_wilcoxon_holm|p}}). Đồng thời nDCG@10′ trên T2 tăng từ {{m6:summary.[B0|t2].ndcg10.mean|f2}} lên {{m6:summary.[S|t2].ndcg10.mean|f2}} (chênh lệch {{m6:comparisons.ndcg10.[S - B0].diff|sf3}}, p = {{m6:comparisons.ndcg10.[S - B0].p_wilcoxon_holm|p}}), vì các công thức vi phạm bị loại khỏi danh sách và nhường chỗ cho công thức vừa đúng món vừa an toàn. Trên tập hồi quy T1, S không làm giảm chất lượng: nDCG@10′ tăng {{m6:comparisons.ndcg10_t1_only.[S - B0].diff|sf3}} (KTC [{{m6:comparisons.ndcg10_t1_only.[S - B0].ci_lo|f3}}; {{m6:comparisons.ndcg10_t1_only.[S - B0].ci_hi|f3}}]), dù với {{d:sample.t1|int}} câu thì kiểm định Wilcoxon chưa có ý nghĩa (p = {{m6:comparisons.ndcg10_t1_only.[S - B0].p_wilcoxon|p}}). B1 có cùng danh sách công thức với B0 nên cùng tỉ lệ vi phạm: thêm bước sinh mà không có hiểu truy vấn và lọc thì không làm hệ an toàn hơn, và chỉ {{m6:summary.[B1|all].citation_safety.mean|pct}} trích dẫn của B1 trỏ tới công thức an toàn.

**Bảng 4.3. Kết quả chính và ablation trên bộ test A3 (CVR, Safe: mức adjudicated)**

| Cấu hình | nDCG@10′ T1 | nDCG@10′ T2 | CVR@5 T2 | CVR@5 T4 | Safe@5 T2 | Trích dẫn an toàn | Từ chối đúng T3 | Từ chối sai T1+T2 |
|---|---|---|---|---|---|---|---|---|
| B0 | {{m6:summary.[B0|t1].ndcg10.mean|f2}} | {{m6:summary.[B0|t2].ndcg10.mean|f2}} | {{m6:summary.[B0|t2].cvr_adj.mean|pct}} | {{m6:summary.[B0|t4].cvr_adj.mean|pct}} | {{m6:summary.[B0|t2].safe_adj|kn}} | – | – | – |
| B1 | {{m6:summary.[B1|t1].ndcg10.mean|f2}} | {{m6:summary.[B1|t2].ndcg10.mean|f2}} | {{m6:summary.[B1|t2].cvr_adj.mean|pct}} | {{m6:summary.[B1|t4].cvr_adj.mean|pct}} | {{m6:summary.[B1|t2].safe_adj|kn}} | {{m6:summary.[B1|all].citation_safety.mean|pct}} | {{m6:summary.[B1|all].neg_rejection|kn}} | {{m6:summary.[B1|all].false_refusal|kn}} |
| **S** | **{{m6:summary.[S|t1].ndcg10.mean|f2}}** | **{{m6:summary.[S|t2].ndcg10.mean|f2}}** | **{{m6:summary.[S|t2].cvr_adj.mean|pct}}** | **{{m6:summary.[S|t4].cvr_adj.mean|pct}}** | **{{m6:summary.[S|t2].safe_adj|kn}}** | **{{m6:summary.[S|all].citation_safety.mean|pct}}** | {{m6:summary.[S|all].neg_rejection|kn}} | {{m6:summary.[S|all].false_refusal|kn}} |
| S−QU | {{m6:summary.[S-QU|t1].ndcg10.mean|f2}} | {{m6:summary.[S-QU|t2].ndcg10.mean|f2}} | {{m6:summary.[S-QU|t2].cvr_adj.mean|pct}} | {{m6:summary.[S-QU|t4].cvr_adj.mean|pct}} | {{m6:summary.[S-QU|t2].safe_adj|kn}} | {{m6:summary.[S-QU|all].citation_safety.mean|pct}} | {{m6:summary.[S-QU|all].neg_rejection|kn}} | {{m6:summary.[S-QU|all].false_refusal|kn}} |
| S−Filter | {{m6:summary.[S-Filter|t1].ndcg10.mean|f2}} | {{m6:summary.[S-Filter|t2].ndcg10.mean|f2}} | {{m6:summary.[S-Filter|t2].cvr_adj.mean|pct}} | {{m6:summary.[S-Filter|t4].cvr_adj.mean|pct}} | {{m6:summary.[S-Filter|t2].safe_adj|kn}} | {{m6:summary.[S-Filter|all].citation_safety.mean|pct}} | {{m6:summary.[S-Filter|all].neg_rejection|kn}} | {{m6:summary.[S-Filter|all].false_refusal|kn}} |
| S−Norm | {{m6:summary.[S-Norm|t1].ndcg10.mean|f2}} | {{m6:summary.[S-Norm|t2].ndcg10.mean|f2}} | {{m6:summary.[S-Norm|t2].cvr_adj.mean|pct}} | {{m6:summary.[S-Norm|t4].cvr_adj.mean|pct}} | {{m6:summary.[S-Norm|t2].safe_adj|kn}} | {{m6:summary.[S-Norm|all].citation_safety.mean|pct}} | {{m6:summary.[S-Norm|all].neg_rejection|kn}} | {{m6:summary.[S-Norm|all].false_refusal|kn}} |
| S−Rerank | {{m6:summary.[S-Rerank|t1].ndcg10.mean|f2}} | {{m6:summary.[S-Rerank|t2].ndcg10.mean|f2}} | {{m6:summary.[S-Rerank|t2].cvr_adj.mean|pct}} | {{m6:summary.[S-Rerank|t4].cvr_adj.mean|pct}} | {{m6:summary.[S-Rerank|t2].safe_adj|kn}} | {{m6:summary.[S-Rerank|all].citation_safety.mean|pct}} | {{m6:summary.[S-Rerank|all].neg_rejection|kn}} | {{m6:summary.[S-Rerank|all].false_refusal|kn}} |
| S−Verify | {{m6:summary.[S-Verify|t1].ndcg10.mean|f2}} | {{m6:summary.[S-Verify|t2].ndcg10.mean|f2}} | {{m6:summary.[S-Verify|t2].cvr_adj.mean|pct}} | {{m6:summary.[S-Verify|t4].cvr_adj.mean|pct}} | {{m6:summary.[S-Verify|t2].safe_adj|kn}} | {{m6:summary.[S-Verify|all].citation_safety.mean|pct}} | {{m6:summary.[S-Verify|all].neg_rejection|kn}} | {{m6:summary.[S-Verify|all].false_refusal|kn}} |
| S−Conv | – | – | – | {{m6:summary.[S-Conv|t4].cvr_adj.mean|pct}} | – | {{m6:summary.[S-Conv|all].citation_safety.mean|pct}} | – | – |

![Hình 4.2. CVR@5 và nDCG@10′ của các cấu hình (KTC 95%)](figures/fig_main.png)

### 4.6.2. Ablation

Bảng 4.4 trình bày mức thay đổi khi tắt từng thành phần. Hai thành phần quyết định là hiểu truy vấn và lọc cứng. Khi tắt hiểu truy vấn (S−QU), hệ không còn ràng buộc nào để lọc và quay về đúng kết quả của B0. Khi giữ hiểu truy vấn nhưng chỉ nối ràng buộc vào câu truy vấn (S−Filter), CVR@5 trên T2 vẫn ở mức {{m6:summary.[S-Filter|t2].cvr_adj.mean|pct}}: truy hồi ngữ nghĩa không xử lý được phủ định, đúng như nhận định ở mục 2.3. Xếp hạng lại cải thiện nDCG@10′ thêm {{m6:comparisons.ndcg10.[S - S-Rerank].diff|sf3}} (bootstrap sau Holm p = {{m6:comparisons.ndcg10.[S - S-Rerank].p_holm|p}}, Wilcoxon {{m6:comparisons.ndcg10.[S - S-Rerank].p_wilcoxon_holm|p}}). Lọc trên thẻ chuẩn hóa thay vì chuỗi thô làm giảm vi phạm trong hội thoại ({{m6:summary.[S-Norm|t4].cvr_adj.mean|pct}} so với {{m6:summary.[S|t4].cvr_adj.mean|pct}} trên T4), nhưng mẫu hiện tại chưa đủ để kết luận có ý nghĩa thống kê. Hậu kiểm M7 chạy sau truy hồi nên không đổi các độ đo truy hồi; tác dụng của nó nằm ở trích dẫn ({{m6:summary.[S-Verify|all].citation_safety.mean|pct}} lên {{m6:summary.[S|all].citation_safety.mean|pct}}). Trên T4, tắt trạng thái hội thoại làm CVR@5 tăng lên {{m6:summary.[S-Conv|t4].cvr_adj.mean|pct}} và độ chính xác ý định giảm từ {{m6:summary.[S|all].intent_ok.value|pct0}} xuống {{m6:summary.[S-Conv|all].intent_ok.value|pct0}}, với chỉ {{d:sample.t4|int}} hội thoại nên chỉ là xu hướng.

**Bảng 4.4. Chênh lệch theo từng câu, S trừ cấu hình (KTC 95%; p Wilcoxon sau Holm)**

| So sánh | ΔCVR@5 | p | ΔnDCG@10′ | p | ΔTrích dẫn an toàn | p |
|---|---|---|---|---|---|---|
| S − B0 | {{m6:comparisons.cvr_adj.[S - B0].diff|sf3}} | {{m6:comparisons.cvr_adj.[S - B0].p_wilcoxon_holm|p}} | {{m6:comparisons.ndcg10.[S - B0].diff|sf3}} | {{m6:comparisons.ndcg10.[S - B0].p_wilcoxon_holm|p}} | – | – |
| S − S−QU | {{m6:comparisons.cvr_adj.[S - S-QU].diff|sf3}} | {{m6:comparisons.cvr_adj.[S - S-QU].p_wilcoxon_holm|p}} | {{m6:comparisons.ndcg10.[S - S-QU].diff|sf3}} | {{m6:comparisons.ndcg10.[S - S-QU].p_wilcoxon_holm|p}} | {{m6:comparisons.citation_safety.[S - S-QU].diff|sf3}} | {{m6:comparisons.citation_safety.[S - S-QU].p_wilcoxon_holm|p}} |
| S − S−Filter | {{m6:comparisons.cvr_adj.[S - S-Filter].diff|sf3}} | {{m6:comparisons.cvr_adj.[S - S-Filter].p_wilcoxon_holm|p}} | {{m6:comparisons.ndcg10.[S - S-Filter].diff|sf3}} | {{m6:comparisons.ndcg10.[S - S-Filter].p_wilcoxon_holm|p}} | {{m6:comparisons.citation_safety.[S - S-Filter].diff|sf3}} | {{m6:comparisons.citation_safety.[S - S-Filter].p_wilcoxon_holm|p}} |
| S − S−Norm | {{m6:comparisons.cvr_adj.[S - S-Norm].diff|sf3}} | {{m6:comparisons.cvr_adj.[S - S-Norm].p_wilcoxon_holm|p}} | {{m6:comparisons.ndcg10.[S - S-Norm].diff|sf3}} | {{m6:comparisons.ndcg10.[S - S-Norm].p_wilcoxon_holm|p}} | {{m6:comparisons.citation_safety.[S - S-Norm].diff|sf3}} | {{m6:comparisons.citation_safety.[S - S-Norm].p_wilcoxon_holm|p}} |
| S − S−Rerank | {{m6:comparisons.cvr_adj.[S - S-Rerank].diff|sf3}} | {{m6:comparisons.cvr_adj.[S - S-Rerank].p_wilcoxon_holm|p}} | {{m6:comparisons.ndcg10.[S - S-Rerank].diff|sf3}} | {{m6:comparisons.ndcg10.[S - S-Rerank].p_wilcoxon_holm|p}} | {{m6:comparisons.citation_safety.[S - S-Rerank].diff|sf3}} | {{m6:comparisons.citation_safety.[S - S-Rerank].p_wilcoxon_holm|p}} |
| S − S−Verify | {{m6:comparisons.cvr_adj.[S - S-Verify].diff|sf3}} | {{m6:comparisons.cvr_adj.[S - S-Verify].p_wilcoxon_holm|p}} | {{m6:comparisons.ndcg10.[S - S-Verify].diff|sf3}} | {{m6:comparisons.ndcg10.[S - S-Verify].p_wilcoxon_holm|p}} | {{m6:comparisons.citation_safety.[S - S-Verify].diff|sf3}} | {{m6:comparisons.citation_safety.[S - S-Verify].p_wilcoxon_holm|p}} |
| S − S−Conv (T4) | {{m6:comparisons.cvr_adj.[S - S-Conv].diff|sf3}} | {{m6:comparisons.cvr_adj.[S - S-Conv].p_wilcoxon_holm|p}} | – | – | {{m6:comparisons.citation_safety.[S - S-Conv].diff|sf3}} | {{m6:comparisons.citation_safety.[S - S-Conv].p_wilcoxon_holm|p}} |

### 4.6.3. Chất lượng sinh và hiểu truy vấn

Nhờ hậu kiểm, {{m6:summary.[S|all].citation_validity.mean|pct}} trích dẫn của S nằm trong ngữ cảnh và {{m6:summary.[S|all].citation_safety.mean|pct}} trỏ tới công thức an toàn. S từ chối đúng {{m6:summary.[S|all].neg_rejection|kn}} câu không trả lời được và từ chối sai {{m6:summary.[S|all].false_refusal|kn}} câu có đáp án. Bước hiểu truy vấn nhận đúng ý định ở {{m6:summary.[S|all].intent_ok|kn}} lượt ({{m6:summary.[S|all].intent_ok.value|pct}}) với slot F1 vi mô {{m6:summary.[S|all].slot_f1_micro|f3}}.

Điểm yếu lớn nhất nằm ở nội dung chữ của câu trả lời. Judge chấm faithfulness của S chỉ {{m6:summary.[S|all].faithful.mean|pct}}, nhưng đối chiếu với nhãn của người cho thấy judge này không tin cậy (κ = {{m6:human_check.faithfulness.kappa|f2}}, Bảng 4.5). Theo nhãn của người trên {{d:human_faithful.n|int}} câu trả lời lấy mẫu, {{d:human_faithful.k|int}} câu ({{d:human_faithful.value|pct0}}) bám ngữ cảnh. Lỗi điển hình là mô hình tự khẳng định thuộc tính an toàn không có trong thẻ công thức, chẳng hạn nói món "không có sữa" trong khi nguyên liệu có heavy cream, hoặc gán nhãn "chay", "không gluten" cho món không được đánh dấu như vậy.

**Bảng 4.5. Đối chiếu công cụ chấm tự động với nhãn của người ({{d:human_items|int}} mục, gán mù)**

| Công cụ | Số mục | Độ khớp | Cohen's κ |
|---|---|---|---|
| Bộ kiểm độc lập (có chứa hay không) | {{m6:human_check.checker.n|int}} | {{m6:human_check.checker.accuracy|pct0}} | {{m6:human_check.checker.kappa|f2}} |
| Judge độ liên quan (0/1/2) | {{m6:human_check.relevance.n|int}} | {{m6:human_check.relevance.agree|pct0}} | {{m6:human_check.relevance.kappa|f2}} |
| Judge faithfulness | {{m6:human_check.faithfulness.n|int}} | – | {{m6:human_check.faithfulness.kappa|f2}} |

Bộ kiểm độc lập khớp tốt với người, và mọi chỗ lệch đều là bộ kiểm báo thừa (chẳng hạn coi mayonnaise là sữa, pancetta là cá, lạc là hạt cây), nên CVR mức strict là cận trên. Kết quả này nhất quán với đánh giá trên 200 công thức nhãn bạc: precision của bộ kiểm trên tập holdout thấp ở trứng ({{allergen:pr.label_yes.holdout.checker_strict.egg.precision.value|f2}}) và đậu phộng ({{allergen:pr.label_yes.holdout.checker_strict.peanut.precision.value|f2}}), trong khi bộ gắn thẻ dùng để lọc đạt recall {{allergen:pr.label_yes.holdout.tagger_definite.milk.recall.value|f2}} với sữa và {{allergen:pr.label_yes.holdout.tagger_definite.wheat.recall.value|f2}} với lúa mì, nhưng chỉ {{allergen:pr.label_yes.holdout.tagger_definite.soy.recall.value|f2}} với đậu nành (5 mẫu dương). Judge độ liên quan chỉ khớp vừa phải với người, nên nDCG@10′ nên được đọc như một ước lượng thô.

### 4.6.4. Nhánh hồ sơ bệnh nhân

Bảng 4.6 so sánh bốn cách đọc hồ sơ. Trên hồ sơ có mã, P-Vectorless trích đúng toàn bộ dị ứng, bệnh và thuốc như cận trên P-Direct, không bỏ sót ca dị ứng nào. Khi bỏ nút cố định (P-Vectorless-Fixed), recall dị ứng chỉ còn {{mv4:all.table.[coded|P-Vectorless-Fixed].food_allergy_substances.recall|pct}} và {{mv4:all.table.[coded|P-Vectorless-Fixed].patients_with_missed_allergy|int}} bệnh nhân bị bỏ sót dị ứng: mô hình 7B chọn nhánh không đủ tin cậy cho thông tin an toàn. Chênh lệch recall dị ứng theo bệnh nhân giữa hai cấu hình là {{mv4:all.comparisons.[coded|allergy_recall].[P-Vectorless - P-Vectorless-Fixed].diff|sf3}} (Wilcoxon sau Holm p = {{mv4:all.comparisons.[coded|allergy_recall].[P-Vectorless - P-Vectorless-Fixed].p_wilcoxon_holm|p}}). RAG vector trên chính hồ sơ (P-Vector) có recall dị ứng {{mv4:all.table.[coded|P-Vector].food_allergy_substances.recall|pct}}: dòng dị ứng ngắn hiếm khi lọt vào các chunk gần câu hỏi nhất về món ăn. Ở chế độ narrative, P-Vectorless vẫn tốt nhất (recall dị ứng {{mv4:all.table.[narrative|P-Vectorless].food_allergy_substances.recall|pct}}) nhưng còn bỏ sót {{mv4:all.table.[narrative|P-Vectorless].allergy_missed|int}} ca ở {{mv4:all.table.[narrative|P-Vectorless].patients_with_missed_allergy|int}} bệnh nhân.

**Bảng 4.6. Trích ràng buộc từ hồ sơ so với đáp án Synthea**

| Đầu vào | Cấu hình | Dị ứng P | Dị ứng R | Bỏ sót dị ứng (bệnh nhân) | Bệnh F1 | Thuốc F1 |
|---|---|---|---|---|---|---|
| có mã | P-Direct | {{mv4:all.table.[coded|P-Direct].food_allergy_substances.precision|pct0}} | {{mv4:all.table.[coded|P-Direct].food_allergy_substances.recall|pct0}} | {{mv4:all.table.[coded|P-Direct].patients_with_missed_allergy|int}} | {{mv4:all.table.[coded|P-Direct].conditions.f1|pct0}} | {{mv4:all.table.[coded|P-Direct].medications.f1|pct0}} |
| có mã | **P-Vectorless** | **{{mv4:all.table.[coded|P-Vectorless].food_allergy_substances.precision|pct0}}** | **{{mv4:all.table.[coded|P-Vectorless].food_allergy_substances.recall|pct0}}** | **{{mv4:all.table.[coded|P-Vectorless].patients_with_missed_allergy|int}}** | **{{mv4:all.table.[coded|P-Vectorless].conditions.f1|pct0}}** | **{{mv4:all.table.[coded|P-Vectorless].medications.f1|pct0}}** |
| có mã | P-Vectorless-Fixed | {{mv4:all.table.[coded|P-Vectorless-Fixed].food_allergy_substances.precision|pct0}} | {{mv4:all.table.[coded|P-Vectorless-Fixed].food_allergy_substances.recall|pct0}} | {{mv4:all.table.[coded|P-Vectorless-Fixed].patients_with_missed_allergy|int}} | {{mv4:all.table.[coded|P-Vectorless-Fixed].conditions.f1|pct0}} | {{mv4:all.table.[coded|P-Vectorless-Fixed].medications.f1|pct0}} |
| có mã | P-Vector | {{mv4:all.table.[coded|P-Vector].food_allergy_substances.precision|pct0}} | {{mv4:all.table.[coded|P-Vector].food_allergy_substances.recall|pct0}} | {{mv4:all.table.[coded|P-Vector].patients_with_missed_allergy|int}} | {{mv4:all.table.[coded|P-Vector].conditions.f1|pct0}} | {{mv4:all.table.[coded|P-Vector].medications.f1|pct0}} |
| narrative | **P-Vectorless** | {{mv4:all.table.[narrative|P-Vectorless].food_allergy_substances.precision|pct0}} | {{mv4:all.table.[narrative|P-Vectorless].food_allergy_substances.recall|pct0}} | {{mv4:all.table.[narrative|P-Vectorless].patients_with_missed_allergy|int}} | {{mv4:all.table.[narrative|P-Vectorless].conditions.f1|pct0}} | {{mv4:all.table.[narrative|P-Vectorless].medications.f1|pct0}} |
| narrative | P-Vectorless-Fixed | {{mv4:all.table.[narrative|P-Vectorless-Fixed].food_allergy_substances.precision|pct0}} | {{mv4:all.table.[narrative|P-Vectorless-Fixed].food_allergy_substances.recall|pct0}} | {{mv4:all.table.[narrative|P-Vectorless-Fixed].patients_with_missed_allergy|int}} | {{mv4:all.table.[narrative|P-Vectorless-Fixed].conditions.f1|pct0}} | {{mv4:all.table.[narrative|P-Vectorless-Fixed].medications.f1|pct0}} |
| narrative | P-Vector | {{mv4:all.table.[narrative|P-Vector].food_allergy_substances.precision|pct0}} | {{mv4:all.table.[narrative|P-Vector].food_allergy_substances.recall|pct0}} | {{mv4:all.table.[narrative|P-Vector].patients_with_missed_allergy|int}} | {{mv4:all.table.[narrative|P-Vector].conditions.f1|pct0}} | {{mv4:all.table.[narrative|P-Vector].medications.f1|pct0}} |

Ở mức đầu cuối (Bảng 4.7), ràng buộc từ hồ sơ đi qua đúng pipeline M1–M7 và được thực thi bằng bộ lọc. Với hồ sơ có mã, P-Vectorless đạt Safe@5 theo dị ứng {{mv4:all.table.[coded|P-Vectorless].safe_allergen_adj.value|pct0}} và theo ngưỡng dinh dưỡng {{mv4:all.table.[coded|P-Vectorless].safe_nutrition.value|pct0}}, trong khi bỏ hồ sơ (S-Profile) chỉ đạt {{mv4:all.table.[coded|S-Profile].safe_allergen_adj.value|pct0}} và {{mv4:all.table.[coded|S-Profile].safe_nutrition.value|pct0}}. Chênh lệch Safe@5 dinh dưỡng theo bệnh nhân là {{mv4:all.comparisons.[coded|safe_nutrition].[P-Vectorless - S-Profile].diff|sf3}} (Wilcoxon sau Holm p = {{mv4:all.comparisons.[coded|safe_nutrition].[P-Vectorless - S-Profile].p_wilcoxon_holm|p}}). Bước chọn nút theo ngữ cảnh chọn đúng nút ở {{mv4:all.table.[coded|P-Vectorless].node_hit.value|pct0}} câu cần ngữ cảnh.

**Bảng 4.7. Đầu cuối và chi phí của nhánh hồ sơ (top 5; chi phí: lượt đầu / các lượt sau)**

| Đầu vào | Cấu hình | Safe@5 dị ứng | Safe@5 dinh dưỡng | Safe@5 hội thoại | Lời gọi LLM (V1–V3) | Độ trễ V2 (ms) |
|---|---|---|---|---|---|---|
| có mã | P-Direct | {{mv4:all.table.[coded|P-Direct].safe_allergen_adj.value|pct0}} | {{mv4:all.table.[coded|P-Direct].safe_nutrition.value|pct0}} | {{mv4:all.table.[coded|P-Direct].safe_dialogue_adj.value|pct0}} | {{mv4:all.table.[coded|P-Direct].cost_first.v_calls|f1}} / {{mv4:all.table.[coded|P-Direct].cost_later.v_calls|f1}} | {{mv4:all.table.[coded|P-Direct].cost_first.lat_v2|int}} / {{mv4:all.table.[coded|P-Direct].cost_later.lat_v2|int}} |
| có mã | **P-Vectorless** | {{mv4:all.table.[coded|P-Vectorless].safe_allergen_adj.value|pct0}} | {{mv4:all.table.[coded|P-Vectorless].safe_nutrition.value|pct0}} | {{mv4:all.table.[coded|P-Vectorless].safe_dialogue_adj.value|pct0}} | {{mv4:all.table.[coded|P-Vectorless].cost_first.v_calls|f1}} / {{mv4:all.table.[coded|P-Vectorless].cost_later.v_calls|f1}} | {{mv4:all.table.[coded|P-Vectorless].cost_first.lat_v2|int}} / {{mv4:all.table.[coded|P-Vectorless].cost_later.lat_v2|int}} |
| có mã | P-Vectorless-Fixed | {{mv4:all.table.[coded|P-Vectorless-Fixed].safe_allergen_adj.value|pct0}} | {{mv4:all.table.[coded|P-Vectorless-Fixed].safe_nutrition.value|pct0}} | {{mv4:all.table.[coded|P-Vectorless-Fixed].safe_dialogue_adj.value|pct0}} | {{mv4:all.table.[coded|P-Vectorless-Fixed].cost_first.v_calls|f1}} / {{mv4:all.table.[coded|P-Vectorless-Fixed].cost_later.v_calls|f1}} | {{mv4:all.table.[coded|P-Vectorless-Fixed].cost_first.lat_v2|int}} / {{mv4:all.table.[coded|P-Vectorless-Fixed].cost_later.lat_v2|int}} |
| có mã | P-Vector | {{mv4:all.table.[coded|P-Vector].safe_allergen_adj.value|pct0}} | {{mv4:all.table.[coded|P-Vector].safe_nutrition.value|pct0}} | {{mv4:all.table.[coded|P-Vector].safe_dialogue_adj.value|pct0}} | {{mv4:all.table.[coded|P-Vector].cost_first.v_calls|f1}} / {{mv4:all.table.[coded|P-Vector].cost_later.v_calls|f1}} | {{mv4:all.table.[coded|P-Vector].cost_first.lat_v2|int}} / {{mv4:all.table.[coded|P-Vector].cost_later.lat_v2|int}} |
| có mã | S-Profile | {{mv4:all.table.[coded|S-Profile].safe_allergen_adj.value|pct0}} | {{mv4:all.table.[coded|S-Profile].safe_nutrition.value|pct0}} | {{mv4:all.table.[coded|S-Profile].safe_dialogue_adj.value|pct0}} | – | – |
| narrative | P-Vectorless | {{mv4:all.table.[narrative|P-Vectorless].safe_allergen_adj.value|pct0}} | {{mv4:all.table.[narrative|P-Vectorless].safe_nutrition.value|pct0}} | {{mv4:all.table.[narrative|P-Vectorless].safe_dialogue_adj.value|pct0}} | {{mv4:all.table.[narrative|P-Vectorless].cost_first.v_calls|f1}} / {{mv4:all.table.[narrative|P-Vectorless].cost_later.v_calls|f1}} | {{mv4:all.table.[narrative|P-Vectorless].cost_first.lat_v2|int}} / {{mv4:all.table.[narrative|P-Vectorless].cost_later.lat_v2|int}} |
| narrative | P-Vector | {{mv4:all.table.[narrative|P-Vector].safe_allergen_adj.value|pct0}} | {{mv4:all.table.[narrative|P-Vector].safe_nutrition.value|pct0}} | {{mv4:all.table.[narrative|P-Vector].safe_dialogue_adj.value|pct0}} | {{mv4:all.table.[narrative|P-Vector].cost_first.v_calls|f1}} / {{mv4:all.table.[narrative|P-Vector].cost_later.v_calls|f1}} | {{mv4:all.table.[narrative|P-Vector].cost_first.lat_v2|int}} / {{mv4:all.table.[narrative|P-Vector].cost_later.lat_v2|int}} |

Về chi phí, P-Vectorless trên hồ sơ có mã gần như không gọi mô hình ở lượt đầu, vì ràng buộc đến từ nút cố định đọc bằng code; ở các lượt sau, trung bình {{mv4:all.table.[coded|P-Vectorless].cost_later.v_calls|f1}} lời gọi mỗi lượt cho bước chọn nút khi câu hỏi cần ngữ cảnh. Ở chế độ narrative, mô hình phải đọc khoảng {{mv4:all.table.[narrative|P-Vectorless].cost_first.extract_chars|int}} ký tự để trích ràng buộc, nên V3 mất khoảng {{mv4:all.table.[narrative|P-Vectorless].cost_first.lat_v3|int}} ms ở lượt đầu, sau đó được lưu đệm.

![Hình 4.3. Recall dị ứng và Safe@5 của các cách đọc hồ sơ](figures/fig_mv4.png)

### 4.6.5. Phân tích lỗi

Các lượt lỗi của S được gắn tự động vào chín nhóm theo tầng phát sinh (Bảng 4.8). Nhóm lớn nhất là câu trả lời không bám ngữ cảnh: mô hình sinh nêu thuộc tính an toàn không có trong thẻ công thức. Hướng khắc phục là mở rộng M7 sang kiểm tra các khẳng định "không có X" dựa trên thẻ, hoặc thay các khẳng định này bằng câu do code viết từ thẻ. Lỗi trích ràng buộc thường gặp ở tên nguyên liệu tiếng Việt và câu có nhiều ràng buộc ngăn bằng dấu phẩy; hướng khắc phục là bổ sung bí danh tiếng Việt và tách ràng buộc theo luật trước khi gọi mô hình. Lỗi bộ gắn thẻ sót chủ yếu đến từ dòng nguyên liệu ghép nhiều thành phần mà bộ tách D4 đọc sai. Không có lượt nào rơi vào các nhóm lọc quá chặt, rerank sai hay mất trạng thái trên mẫu hiện tại.

**Bảng 4.8. Nhóm lỗi trên các lượt của S ({{m6:errors.turns|int}} lượt)**

| Nhóm lỗi | Số lượt | Ví dụ / nguyên nhân |
|---|---|---|
| Câu trả lời không bám ngữ cảnh | {{m6:errors.by_group.F7_unfaithful|int}} | khẳng định "không có sữa" khi món có heavy cream |
| Trích ràng buộc sai | {{m6:errors.by_group.F1_constraint_extraction|int}} | tên nguyên liệu tiếng Việt, câu nhiều ràng buộc |
| Từ chối sai | {{m6:errors.by_group.F8_refusal|int}} | từ chối câu có đáp án |
| Bộ gắn thẻ sót | {{m6:errors.by_group.F3_tagger_miss|int}} | dòng nguyên liệu ghép bị tách sai |
| Định tuyến sai ý định | {{m6:errors.by_group.F2_intent_routing|int}} | câu tinh chỉnh bị hiểu là câu mới |

### 4.6.6. Độ trễ

Bảng 4.9 phân rã độ trễ theo module. Lọc, truy hồi lai và xếp hạng lại của S chỉ tốn vài trăm mili giây, tương đương A1. Gần như toàn bộ độ trễ của S nằm ở hai lời gọi mô hình 7B chạy cục bộ: hiểu truy vấn và sinh câu trả lời. Thời gian đến token đầu tiên của M6 cao vì prompt chứa năm thẻ công thức phải được mô hình đọc hết trước khi sinh. Đây là cái giá của việc chạy cục bộ trên GPU laptop 8 GB; với GPU mạnh hơn hoặc mô hình nhỏ hơn cho M1, độ trễ có thể giảm đáng kể mà không đổi kiến trúc. Do các cấu hình ablation dùng chung bộ đệm M1 với S, độ trễ của chúng không được so sánh với nhau.

**Bảng 4.9. Độ trễ theo module (ms, p50 / p95)**

| Cấu hình | M1 | M4 | M5 | M6 (token đầu) | M6 | Tổng |
|---|---|---|---|---|---|---|
| B0 | – | {{m6:summary.[B0|all].latency_ms.m4.p50|int}} / {{m6:summary.[B0|all].latency_ms.m4.p95|int}} | {{m6:summary.[B0|all].latency_ms.m5.p50|int}} / {{m6:summary.[B0|all].latency_ms.m5.p95|int}} | – | – | {{m6:summary.[B0|all].latency_ms.total.p50|int}} / {{m6:summary.[B0|all].latency_ms.total.p95|int}} |
| B1 | – | {{m6:summary.[B1|all].latency_ms.m4.p50|int}} / {{m6:summary.[B1|all].latency_ms.m4.p95|int}} | {{m6:summary.[B1|all].latency_ms.m5.p50|int}} / {{m6:summary.[B1|all].latency_ms.m5.p95|int}} | {{m6:summary.[B1|all].latency_ms.m6_ttft.p50|int}} / {{m6:summary.[B1|all].latency_ms.m6_ttft.p95|int}} | {{m6:summary.[B1|all].latency_ms.m6.p50|int}} / {{m6:summary.[B1|all].latency_ms.m6.p95|int}} | {{m6:summary.[B1|all].latency_ms.total.p50|int}} / {{m6:summary.[B1|all].latency_ms.total.p95|int}} |
| S | {{m6:summary.[S|all].latency_ms.m1.p50|int}} / {{m6:summary.[S|all].latency_ms.m1.p95|int}} | {{m6:summary.[S|all].latency_ms.m4.p50|int}} / {{m6:summary.[S|all].latency_ms.m4.p95|int}} | {{m6:summary.[S|all].latency_ms.m5.p50|int}} / {{m6:summary.[S|all].latency_ms.m5.p95|int}} | {{m6:summary.[S|all].latency_ms.m6_ttft.p50|int}} / {{m6:summary.[S|all].latency_ms.m6_ttft.p95|int}} | {{m6:summary.[S|all].latency_ms.m6.p50|int}} / {{m6:summary.[S|all].latency_ms.m6.p95|int}} | {{m6:summary.[S|all].latency_ms.total.p50|int}} / {{m6:summary.[S|all].latency_ms.total.p95|int}} |

![Hình 4.4. Phân rã độ trễ theo module](figures/fig_latency.png)
