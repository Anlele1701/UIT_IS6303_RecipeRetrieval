# Chương 4. Thực nghiệm và đánh giá

## 4.1. Xây dựng bộ test

Bộ test của A3 gồm năm tập (Bảng 4.1). Tập hồi quy T1 lấy mẫu từ bộ truy vấn của A1, dùng để bảo đảm A3 không làm giảm chất lượng ở loại truy vấn mà A1 đã xử lý tốt. Tập ràng buộc một lượt T2 (một nửa bằng tiếng Việt) chứa các yêu cầu về dị ứng, loại trừ nguyên liệu, chế độ ăn hoặc thời gian. Tập không trả lời được T3 gồm các tổ hợp ràng buộc mà không công thức nào thỏa mãn và các câu hỏi ngoài phạm vi. Tập hội thoại nhiều lượt T4 gồm các hội thoại trong đó ràng buộc được nêu ở lượt trước và phải còn hiệu lực ở lượt sau.

Tập mới là tập hồ sơ bệnh nhân. Nhóm chọn 100 bệnh nhân Synthea còn sống theo phân tầng của quy tắc P8 và gắn cho mỗi bệnh nhân ba câu hỏi, tổng cộng 300 truy vấn (151 tiếng Việt, 149 tiếng Anh). Tập này cố ý gồm ba loại câu với số lượng bằng nhau: câu không nhắc ràng buộc nào, để kiểm tra ràng buộc từ hồ sơ có được tự động áp dụng; câu thêm ràng buộc mới bên cạnh ràng buộc của hồ sơ; và câu cần ngữ cảnh thời gian trong hồ sơ, để kiểm tra bước chọn nút theo ngữ cảnh. Để so sánh các cách đọc hồ sơ khi đầu vào là văn bản tự do, cùng bộ câu hỏi được chạy thêm ở chế độ narrative (mục 3.4.1).

Truy vấn được tạo bằng ba nguồn: ghép mẫu câu kết hợp diễn đạt lại bằng mô hình ngôn ngữ, viết tay bởi thành viên nhóm (32 câu), và các câu tiếng Việt tự nhiên có cả lỗi chính tả hay viết không dấu. Vì qwen2.5:7b vừa là mô hình hiểu truy vấn của hệ, phần câu do mô hình diễn đạt lại được sinh bằng llama3.1:8b, để tránh kết quả F1 bị đẹp hơn thực tế do mô hình quen với cách diễn đạt của chính nó.

Mọi truy vấn ứng viên phải qua bảy quy tắc hợp lệ, mỗi quy tắc được báo cáo số câu bị loại. V1 yêu cầu truy vấn không chép nguyên tiêu đề công thức. V2 yêu cầu truy vấn có ít nhất một công thức thỏa ràng buộc (với tập không trả lời được thì ngược lại). V3 kiểm tra câu tiếng Việt có dấu và đúng ngôn ngữ đã định. V4 loại các câu gần trùng nhau. V5 giới hạn độ dài từ 3 đến 40 từ. V6 yêu cầu ràng buộc chuẩn của mỗi câu phải được người xác nhận; ở A3, bản nháp ràng buộc chuẩn do mô hình soạn và thành viên nhóm xác nhận từng câu hoặc chấp nhận theo nhóm. V7 yêu cầu với câu gắn hồ sơ, tập ràng buộc chuẩn phải bằng hợp của ràng buộc lấy từ đáp án Synthea và ràng buộc trong câu hỏi, và phải còn ít nhất một công thức thỏa tập này. Kết quả được trình bày ở Bảng 4.1 và Hình 4.1. Bộ test được đóng băng (lưu sha256) trước khi chạy thực nghiệm.

**Bảng 4.1. Luồng lọc bộ test A3 (`eval/testset/testset_flow.json`)**

| Tập | Sinh ra | Loại ở V2 | Loại ở V4 | Còn lại | Sau V6 (đóng băng) |
|---|---|---|---|---|---|
| T1 hồi quy | 150 | 0 | 0 | 150 | 105 |
| T2 ràng buộc một lượt | 240 | 4 | 48 | 188 | 172 |
| T3 không trả lời được | 98 | 34 | 0 | 64 | 55 |
| T4 hội thoại (số hội thoại) | 65 | 3 | 22 | 40 | 40 |
| Hồ sơ bệnh nhân | – | – | – | – | 300 |

V1, V3 và V5 không loại câu nào ở bốn tập. Sau khi lọc, các tập được cắt về chỉ tiêu theo seed, rồi cộng các câu viết tay.

![Hình 4.1. Sơ đồ luồng lọc bộ test](figures/fig_testset_flow.png)

## 4.2. Gán nhãn và bộ kiểm độc lập

Nhãn độ liên quan được xây dựng bằng phương pháp pooling: gộp mười kết quả đầu của mọi cấu hình, rồi gán nhãn theo thang 0, 1, 2. Việc gán nhãn do một mô hình ngôn ngữ khác họ với mô hình sinh (llama3.1:8b) thực hiện, nhằm tránh thiên lệch giám khảo ưu ái câu trả lời của mô hình cùng họ [9]. Nhóm kiểm tra lại 50 mẫu bằng tay và báo cáo hệ số Cohen's κ giữa người và mô hình.

Vi phạm ràng buộc được chấm bằng một bộ kiểm độc lập: mô hình ngôn ngữ đọc toàn văn danh sách nguyên liệu và trả lời công thức có chứa nhóm dị ứng hoặc vi phạm chế độ ăn hay không, kèm dòng nguyên liệu làm bằng chứng. Bộ kiểm không sử dụng từ điển hay thẻ của bộ gắn thẻ, và một unit test kiểm tra rằng mã của bộ kiểm không import mã của bộ gắn thẻ. Thiết kế này tránh đánh giá vòng tròn: nếu dùng chính bộ thẻ vừa để lọc vừa để chấm thì tỉ lệ vi phạm của hệ đề xuất sẽ bằng không theo định nghĩa. Phiếu "có vi phạm" có bằng chứng không tìm thấy nguyên văn trong công thức bị loại tự động; các phiếu còn lại được đưa vào một hàng duyệt mù cho người, không hiển thị cấu hình nào đã trả về công thức. Bản thân bộ kiểm cũng được đánh giá precision và recall trên cùng tập 200 công thức có nhãn bạc, để kết quả vi phạm được báo cáo kèm sai số của công cụ đo. Vi phạm nguyên liệu có tên được chấm bằng so khớp nguyên từ, còn vi phạm thời gian và ngưỡng dinh dưỡng được tính trực tiếp từ các cột của công thức, nên không cần bộ kiểm riêng.

Với nhánh hồ sơ, đáp án ràng buộc được lấy tự động từ các trường có cấu trúc của Synthea theo cùng bộ quy tắc P2 đến P6, tương tự cách các nghiên cứu trước lấy đáp án từ các tài nguyên đang hiệu lực. Để tránh vòng tròn ở bước ánh xạ, đáp án được dừng ở mức thực thể (dị ứng nào, bệnh nào, thuốc nào) chứ không ở mức ngưỡng dinh dưỡng; bước ánh xạ luật được kiểm tra riêng bằng unit test. Nhóm kiểm tra tay 20 bệnh nhân để phát hiện lỗi trong chính bước lấy đáp án.

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

Mọi thực nghiệm chạy trên một máy với GPU NVIDIA GeForce RTX 4060 Laptop GPU, 8188 MiB, mô hình chạy cục bộ qua Ollama với seed 42, temperature 0 cho hiểu truy vấn và chấm điểm, 0,2 cho sinh câu trả lời; mọi lời gọi mô hình được lưu đệm theo hash của đầu vào. Danh sách mô hình, prompt và tham số được ghi trong RAG Card (Phụ lục A). Do giới hạn thời gian, thực nghiệm trên bộ test A3 dùng một mẫu theo seed khoảng 10% mỗi tập: T1 10, T2 17, T3 6 câu và T4 4 hội thoại, chạy qua chín cấu hình, tổng cộng 363 lượt. Thực nghiệm nhánh hồ sơ chạy trên toàn bộ 300 câu của 100 bệnh nhân, ở cả hai dạng đầu vào. Pool chấm độ liên quan gồm 1.096 cặp truy vấn – công thức. Hàng duyệt mù của bộ kiểm đã được người duyệt hết: 137 phiếu được xác nhận là vi phạm, 54 phiếu bị bác, và 42 phiếu bị loại tự động vì bằng chứng không hợp lệ.

## 4.6. Kết quả, ablation và phân tích lỗi

### 4.6.1. Kết quả chính

Bảng 4.3 so sánh các cấu hình trên bộ test A3. So với hệ Hybrid của A1 (B0), hệ đề xuất S giảm CVR@5 trên tập ràng buộc một lượt từ 67,5% xuống 2,7% và trên tập hội thoại từ 48,6% xuống 5,7%. Mức giảm theo từng câu là −0,602 (KTC 95% [−0,749; −0,451], Wilcoxon sau Holm p = 0,001). Đồng thời nDCG@10′ trên T2 tăng từ 0,21 lên 0,80 (chênh lệch +0,465, p = < 0,001), vì các công thức vi phạm bị loại khỏi danh sách và nhường chỗ cho công thức vừa đúng món vừa an toàn. Trên tập hồi quy T1, S không làm giảm chất lượng: nDCG@10′ tăng +0,256 (KTC [0,018; 0,521]), dù với 10 câu thì kiểm định Wilcoxon chưa có ý nghĩa (p = 0,188). B1 có cùng danh sách công thức với B0 nên cùng tỉ lệ vi phạm: thêm bước sinh mà không có hiểu truy vấn và lọc thì không làm hệ an toàn hơn, và chỉ 63,2% trích dẫn của B1 trỏ tới công thức an toàn.

**Bảng 4.3. Kết quả chính và ablation trên bộ test A3 (CVR, Safe: mức adjudicated)**

| Cấu hình | nDCG@10′ T1 | nDCG@10′ T2 | CVR@5 T2 | CVR@5 T4 | Safe@5 T2 | Trích dẫn an toàn | Từ chối đúng T3 | Từ chối sai T1+T2 |
|---|---|---|---|---|---|---|---|---|
| B0 | 0,60 | 0,21 | 67,5% | 48,6% | 1/16 | – | – | – |
| B1 | 0,60 | 0,21 | 67,5% | 48,6% | 1/16 | 63,2% | 2/6 | 2/27 |
| **S** | **0,86** | **0,80** | **2,7%** | **5,7%** | **14/15** | **98,5%** | 4/6 | 1/27 |
| S−QU | 0,60 | 0,21 | 67,5% | 48,6% | 1/16 | 61,8% | 3/6 | 2/27 |
| S−Filter | 0,86 | 0,36 | 65,3% | 60,0% | 2/15 | 84,9% | 4/6 | 3/27 |
| S−Norm | 0,86 | 0,78 | 6,7% | 22,9% | 12/15 | 100,0% | 5/6 | 1/27 |
| S−Rerank | 0,81 | 0,74 | 2,7% | 5,7% | 14/15 | 100,0% | 4/6 | 0/27 |
| S−Verify | 0,86 | 0,80 | 2,7% | 5,7% | 14/15 | 96,9% | 3/6 | 1/27 |
| S−Conv | – | – | – | 34,3% | – | 75,0% | – | – |

![Hình 4.2. CVR@5 và nDCG@10′ của các cấu hình (KTC 95%)](figures/fig_main.png)

### 4.6.2. Ablation

Bảng 4.4 trình bày mức thay đổi khi tắt từng thành phần. Hai thành phần quyết định là hiểu truy vấn và lọc cứng. Khi tắt hiểu truy vấn (S−QU), hệ không còn ràng buộc nào để lọc và quay về đúng kết quả của B0. Khi giữ hiểu truy vấn nhưng chỉ nối ràng buộc vào câu truy vấn (S−Filter), CVR@5 trên T2 vẫn ở mức 65,3%: truy hồi ngữ nghĩa không xử lý được phủ định, đúng như nhận định ở mục 2.3. Xếp hạng lại cải thiện nDCG@10′ thêm +0,055 (bootstrap sau Holm p = 0,037, Wilcoxon 0,092). Lọc trên thẻ chuẩn hóa thay vì chuỗi thô làm giảm vi phạm trong hội thoại (22,9% so với 5,7% trên T4), nhưng mẫu hiện tại chưa đủ để kết luận có ý nghĩa thống kê. Hậu kiểm M7 chạy sau truy hồi nên không đổi các độ đo truy hồi; tác dụng của nó nằm ở trích dẫn (96,9% lên 98,5%). Trên T4, tắt trạng thái hội thoại làm CVR@5 tăng lên 34,3% và độ chính xác ý định giảm từ 98% xuống 73%, với chỉ 4 hội thoại nên chỉ là xu hướng.

**Bảng 4.4. Chênh lệch theo từng câu, S trừ cấu hình (KTC 95%; p Wilcoxon sau Holm)**

| So sánh | ΔCVR@5 | p | ΔnDCG@10′ | p | ΔTrích dẫn an toàn | p |
|---|---|---|---|---|---|---|
| S − B0 | −0,602 | 0,001 | +0,465 | < 0,001 | – | – |
| S − S−QU | −0,602 | 0,001 | +0,465 | < 0,001 | +0,314 | 0,029 |
| S − S−Filter | −0,618 | 0,001 | +0,273 | 0,008 | +0,125 | 0,833 |
| S − S−Norm | −0,049 | 1,000 | +0,012 | 0,712 | −0,018 | 1,000 |
| S − S−Rerank | +0,000 | 1,000 | +0,055 | 0,092 | −0,019 | 1,000 |
| S − S−Verify | +0,000 | 1,000 | +0,000 | 1,000 | +0,006 | 1,000 |
| S − S−Conv (T4) | −0,200 | 1,000 | – | – | +0,219 | 1,000 |

### 4.6.3. Chất lượng sinh và hiểu truy vấn

Nhờ hậu kiểm, 100,0% trích dẫn của S nằm trong ngữ cảnh và 98,5% trỏ tới công thức an toàn. S từ chối đúng 4/6 câu không trả lời được và từ chối sai 1/27 câu có đáp án. Bước hiểu truy vấn nhận đúng ý định ở 43/44 lượt (97,7%) với slot F1 vi mô 0,889.

Điểm yếu lớn nhất nằm ở nội dung chữ của câu trả lời. Judge chấm faithfulness của S chỉ 12,8%, nhưng đối chiếu với nhãn của người cho thấy judge này không tin cậy (κ = −0,02, Bảng 4.5). Theo nhãn của người trên 50 câu trả lời lấy mẫu, 34 câu (68%) bám ngữ cảnh. Lỗi điển hình là mô hình tự khẳng định thuộc tính an toàn không có trong thẻ công thức, chẳng hạn nói món "không có sữa" trong khi nguyên liệu có heavy cream, hoặc gán nhãn "chay", "không gluten" cho món không được đánh dấu như vậy.

**Bảng 4.5. Đối chiếu công cụ chấm tự động với nhãn của người (160 mục, gán mù)**

| Công cụ | Số mục | Độ khớp | Cohen's κ |
|---|---|---|---|
| Bộ kiểm độc lập (có chứa hay không) | 60 | 90% | 0,80 |
| Judge độ liên quan (0/1/2) | 50 | 54% | 0,30 |
| Judge faithfulness | 50 | – | −0,02 |

Bộ kiểm độc lập khớp tốt với người, và mọi chỗ lệch đều là bộ kiểm báo thừa (chẳng hạn coi mayonnaise là sữa, pancetta là cá, lạc là hạt cây), nên CVR mức strict là cận trên. Kết quả này nhất quán với đánh giá trên 200 công thức nhãn bạc: precision của bộ kiểm trên tập holdout thấp ở trứng (0,75) và đậu phộng (0,25), trong khi bộ gắn thẻ dùng để lọc đạt recall 1,00 với sữa và 0,96 với lúa mì, nhưng chỉ 0,40 với đậu nành (5 mẫu dương). Judge độ liên quan chỉ khớp vừa phải với người, nên nDCG@10′ nên được đọc như một ước lượng thô.

### 4.6.4. Nhánh hồ sơ bệnh nhân

Bảng 4.6 so sánh bốn cách đọc hồ sơ. Trên hồ sơ có mã, P-Vectorless trích đúng toàn bộ dị ứng, bệnh và thuốc như cận trên P-Direct, không bỏ sót ca dị ứng nào. Khi bỏ nút cố định (P-Vectorless-Fixed), recall dị ứng chỉ còn 34,9% và 12 bệnh nhân bị bỏ sót dị ứng: mô hình 7B chọn nhánh không đủ tin cậy cho thông tin an toàn. Chênh lệch recall dị ứng theo bệnh nhân giữa hai cấu hình là +0,694 (Wilcoxon sau Holm p = 0,001). RAG vector trên chính hồ sơ (P-Vector) có recall dị ứng 14,3%: dòng dị ứng ngắn hiếm khi lọt vào các chunk gần câu hỏi nhất về món ăn. Ở chế độ narrative, P-Vectorless vẫn tốt nhất (recall dị ứng 85,7%) nhưng còn bỏ sót 9 ca ở 3 bệnh nhân.

**Bảng 4.6. Trích ràng buộc từ hồ sơ so với đáp án Synthea**

| Đầu vào | Cấu hình | Dị ứng P | Dị ứng R | Bỏ sót dị ứng (bệnh nhân) | Bệnh F1 | Thuốc F1 |
|---|---|---|---|---|---|---|
| có mã | P-Direct | 100% | 100% | 0 | 100% | 100% |
| có mã | **P-Vectorless** | **100%** | **100%** | **0** | **100%** | **100%** |
| có mã | P-Vectorless-Fixed | 100% | 35% | 12 | 40% | 34% |
| có mã | P-Vector | 29% | 14% | 11 | 77% | 88% |
| narrative | **P-Vectorless** | 82% | 86% | 3 | 49% | 78% |
| narrative | P-Vectorless-Fixed | 82% | 14% | 12 | 9% | 0% |
| narrative | P-Vector | 100% | 17% | 12 | 17% | 43% |

Ở mức đầu cuối (Bảng 4.7), ràng buộc từ hồ sơ đi qua đúng pipeline M1–M7 và được thực thi bằng bộ lọc. Với hồ sơ có mã, P-Vectorless đạt Safe@5 theo dị ứng 99% và theo ngưỡng dinh dưỡng 100%, trong khi bỏ hồ sơ (S-Profile) chỉ đạt 81% và 36%. Chênh lệch Safe@5 dinh dưỡng theo bệnh nhân là +0,640 (Wilcoxon sau Holm p = < 0,001). Bước chọn nút theo ngữ cảnh chọn đúng nút ở 78% câu cần ngữ cảnh.

**Bảng 4.7. Đầu cuối và chi phí của nhánh hồ sơ (top 5; chi phí: lượt đầu / các lượt sau)**

| Đầu vào | Cấu hình | Safe@5 dị ứng | Safe@5 dinh dưỡng | Safe@5 hội thoại | Lời gọi LLM (V1–V3) | Độ trễ V2 (ms) |
|---|---|---|---|---|---|---|
| có mã | P-Direct | 99% | 100% | 86% | 0,0 / 0,0 | 0 / 0 |
| có mã | **P-Vectorless** | 99% | 100% | 86% | 0,0 / 0,5 | 46 / 523 |
| có mã | P-Vectorless-Fixed | 91% | 96% | 84% | 1,0 / 1,0 | 4.396 / 957 |
| có mã | P-Vector | 82% | 98% | 84% | 1,0 / 1,0 | 153 / 14 |
| có mã | S-Profile | 81% | 36% | 80% | – | – |
| narrative | P-Vectorless | 97% | 100% | 86% | 2,1 / 2,6 | 36 / 167 |
| narrative | P-Vector | 86% | 94% | 83% | 1,0 / 1,0 | 1.464 / 934 |

Về chi phí, P-Vectorless trên hồ sơ có mã gần như không gọi mô hình ở lượt đầu, vì ràng buộc đến từ nút cố định đọc bằng code; ở các lượt sau, trung bình 0,5 lời gọi mỗi lượt cho bước chọn nút khi câu hỏi cần ngữ cảnh. Ở chế độ narrative, mô hình phải đọc khoảng 19.534 ký tự để trích ràng buộc, nên V3 mất khoảng 16.099 ms ở lượt đầu, sau đó được lưu đệm.

![Hình 4.3. Recall dị ứng và Safe@5 của các cách đọc hồ sơ](figures/fig_mv4.png)

### 4.6.5. Phân tích lỗi

Các lượt lỗi của S được gắn tự động vào chín nhóm theo tầng phát sinh (Bảng 4.8). Nhóm lớn nhất là câu trả lời không bám ngữ cảnh: mô hình sinh nêu thuộc tính an toàn không có trong thẻ công thức. Hướng khắc phục là mở rộng M7 sang kiểm tra các khẳng định "không có X" dựa trên thẻ, hoặc thay các khẳng định này bằng câu do code viết từ thẻ. Lỗi trích ràng buộc thường gặp ở tên nguyên liệu tiếng Việt và câu có nhiều ràng buộc ngăn bằng dấu phẩy; hướng khắc phục là bổ sung bí danh tiếng Việt và tách ràng buộc theo luật trước khi gọi mô hình. Lỗi bộ gắn thẻ sót chủ yếu đến từ dòng nguyên liệu ghép nhiều thành phần mà bộ tách D4 đọc sai. Không có lượt nào rơi vào các nhóm lọc quá chặt, rerank sai hay mất trạng thái trên mẫu hiện tại.

**Bảng 4.8. Nhóm lỗi trên các lượt của S (44 lượt)**

| Nhóm lỗi | Số lượt | Ví dụ / nguyên nhân |
|---|---|---|
| Câu trả lời không bám ngữ cảnh | 34 | khẳng định "không có sữa" khi món có heavy cream |
| Trích ràng buộc sai | 7 | tên nguyên liệu tiếng Việt, câu nhiều ràng buộc |
| Từ chối sai | 3 | từ chối câu có đáp án |
| Bộ gắn thẻ sót | 2 | dòng nguyên liệu ghép bị tách sai |
| Định tuyến sai ý định | 1 | câu tinh chỉnh bị hiểu là câu mới |

### 4.6.6. Độ trễ

Bảng 4.9 phân rã độ trễ theo module. Lọc, truy hồi lai và xếp hạng lại của S chỉ tốn vài trăm mili giây, tương đương A1. Gần như toàn bộ độ trễ của S nằm ở hai lời gọi mô hình 7B chạy cục bộ: hiểu truy vấn và sinh câu trả lời. Thời gian đến token đầu tiên của M6 cao vì prompt chứa năm thẻ công thức phải được mô hình đọc hết trước khi sinh. Đây là cái giá của việc chạy cục bộ trên GPU laptop 8 GB; với GPU mạnh hơn hoặc mô hình nhỏ hơn cho M1, độ trễ có thể giảm đáng kể mà không đổi kiến trúc. Do các cấu hình ablation dùng chung bộ đệm M1 với S, độ trễ của chúng không được so sánh với nhau.

**Bảng 4.9. Độ trễ theo module (ms, p50 / p95)**

| Cấu hình | M1 | M4 | M5 | M6 (token đầu) | M6 | Tổng |
|---|---|---|---|---|---|---|
| B0 | – | 144 / 730 | 95 / 146 | – | – | 238 / 862 |
| B1 | – | 86 / 102 | 86 / 132 | 386 / 522 | 1.818 / 3.219 | 2.000 / 3.372 |
| S | 10.890 / 11.354 | 184 / 478 | 67 / 91 | 9.040 / 9.334 | 10.676 / 12.674 | 21.964 / 24.034 |

![Hình 4.4. Phân rã độ trễ theo module](figures/fig_latency.png)
