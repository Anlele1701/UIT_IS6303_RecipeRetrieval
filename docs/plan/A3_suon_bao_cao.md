# A3 – Sườn báo cáo

**Đề tài:** Trợ lý ẩm thực hội thoại dựa trên RAG, nhận biết ràng buộc của người dùng (dị ứng, chế độ ăn, thời gian), phát triển từ hệ truy hồi công thức A1

**Môn:** IS6303 – Thiết kế HTTT thông minh dựa trên truy hồi, UIT

> **Ghi chú cho nhóm (không đưa vào báo cáo).** Nhóm đã thống nhất các điểm sau. Baseline chính là hệ Hybrid của A1, chạy lại trên bộ test của A3 để trả lời câu hỏi "tốt hơn A1 bao nhiêu". Người dùng nhập tiếng Việt hoặc tiếng Anh, còn corpus vẫn giữ tiếng Anh. Mô hình ngôn ngữ chạy cục bộ qua Ollama. Giao diện chuyển sang dạng chatbox. Vi phạm ràng buộc được chấm bằng một bộ kiểm độc lập với bộ gắn thẻ dùng để lọc, và nhóm báo cáo thêm precision/recall của bộ gắn thẻ trên 200 công thức gán nhãn tay. Hai điểm còn mở cần chốt trước khi viết bản chính thức: giới hạn số trang của báo cáo, và có thêm người thứ hai gán lại 50 mẫu để tính độ đồng thuận giữa hai người hay không. Chi tiết triển khai xem `A3_ke_hoach_build.md`. Tóm tắt từng nguồn tham khảo xem `A3_tong_hop_tai_lieu.md`.

---

## Chương 1. Giới thiệu

### 1.1. Bối cảnh và động lực

Hệ tìm kiếm truyền thống mà nhóm đã thực hiện ở đồ án A1 chỉ trả về danh sách món ăn, không hiểu ý định thực sự trong truy vấn của người dùng và không thể tích hợp ngữ cảnh vào truy vấn. Vì vậy, ở đồ án A3 nhóm em phân tích và thiết kế trợ lý hội thoại (chatbot) cho phép người dùng hỏi bằng ngôn ngữ tự nhiên [1], kết hợp với hệ RAG truy xuất thông tin dữ liệu để tạo sinh câu trả lời cho người dùng, giảm tỉ lệ mô hình sinh câu trả lời sai và cho phép trích nguồn thông tin đầy đủ [2-4]. Ngoài ra, lĩnh vực ẩm thực có nhiều ràng buộc liên quan sức khỏe (dị ứng, chế độ ăn) cùng với sở thích mềm (khẩu vị, thời gian) [5] nên việc hệ truy vấn hiểu ý định thực sự của người dùng để xếp hạng quyết định độ chính xác của mô hình.

### 1.2. Hạn chế của A1 và động lực cải tiến

Hệ A1 truy hồi trên bộ dữ liệu Shengtao/recipe gồm 32.719 công thức thuộc 22 danh mục, chỉ sử dụng phần văn bản. Hệ kết hợp BM25, truy hồi dày đặc với mô hình `nomic-embed-text`, hợp nhất bằng Reciprocal Rank Fusion và xếp hạng lại bằng cross-encoder trên ParadeDB [6]. Trên bộ 298 truy vấn, cấu hình Hybrid đạt Recall@5 từ 0,913 đến 0,919 và MRR từ 0,758 đến 0,767 tùy chiến lược chunking, với độ trễ trung vị khoảng 750 ms. Kết quả này cho thấy A1 truy hồi tốt khi truy vấn mô tả món ăn một cách trực tiếp. Tuy nhiên, A1 có ba hạn chế mà giảng viên đã chỉ ra và cũng thể hiện rõ trong phần phân tích lỗi của chính A1.

Hạn chế thứ nhất là hệ không hiểu ngôn ngữ tự nhiên. Nhóm lỗi lớn nhất của nhánh dense trong A1 là "mất chi tiết chính xác": các ràng buộc cụ thể, con số hay phủ định trong truy vấn bị bỏ qua, xảy ra ở 17 đến 19 truy vấn với mỗi chiến lược chunking. Bộ lọc của A1 chỉ hỗ trợ danh mục và các khoảng giá trị số, không lọc được theo nguyên liệu hay chất gây dị ứng, và hệ cũng không xử lý câu hỏi tiếng Việt. Hạn chế thứ hai là A1 chưa phải hệ RAG: đầu ra chỉ là danh sách công thức, không có câu trả lời tổng hợp, không trích dẫn và không biết từ chối khi không có kết quả phù hợp. Hạn chế thứ ba là quy trình xử lý dữ liệu chưa minh bạch. Báo cáo A1 có nêu một số công thức bị bỏ qua khi sinh truy vấn và 57 truy vấn được viết lại bằng tay, nhưng không đưa ra quy tắc định nghĩa được cho từng trường hợp loại bỏ hay sửa đổi, kèm số lượng tương ứng. Ngoài ra, A1 còn gặp lỗi chunk bị tách khỏi ngữ cảnh của công thức gốc, hiện tượng được gọi là "blinkered chunk effect" [2]. Ba hạn chế trên lần lượt là động lực cho ba nhóm cải tiến của A3: hiểu truy vấn và lọc theo ràng buộc, sinh câu trả lời có căn cứ, và pipeline dữ liệu có quy tắc rõ ràng.

### 1.3. Phát biểu bài toán

Đầu vào của hệ là chuỗi hội thoại H_t = (u_1, a_1, …, u_t), trong đó mỗi lượt hỏi u_t có thể viết bằng tiếng Việt hoặc tiếng Anh. Đầu ra là câu trả lời a_t bằng ngôn ngữ của người hỏi, kèm danh sách tối đa k công thức R_t lấy từ kho D có trích dẫn. Mọi công thức trong R_t phải thỏa tập ràng buộc cứng C_t tích lũy đến lượt t, và được xếp hạng theo mức độ đáp ứng nhu cầu. Khi không có công thức nào thỏa C_t, hệ phải trả lời rằng không tìm thấy thay vì gợi ý một món vi phạm ràng buộc. Theo cách hình thức hóa của cá nhân hóa ở bước tiền truy hồi, truy vấn thực sự được dùng để truy hồi là q*_t = Q(u_t, H_{t−1}, p_t), trong đó p_t là trạng thái ràng buộc của phiên hội thoại [7].

### 1.4. Câu hỏi nghiên cứu

Đồ án trả lời bốn câu hỏi nghiên cứu. Câu hỏi thứ nhất (RQ1) là so với hệ Hybrid của A1, việc hiểu truy vấn kết hợp lọc cứng giảm tỉ lệ công thức vi phạm ràng buộc được bao nhiêu, đồng thời có giữ được hoặc cải thiện chất lượng xếp hạng hay không. Câu hỏi thứ hai (RQ2) là từng thành phần của hệ đề xuất đóng góp bao nhiêu vào kết quả chung, được đo bằng thí nghiệm ablation. Câu hỏi thứ ba (RQ3) là câu trả lời sinh ra có bám đúng ngữ cảnh truy hồi, trích dẫn đúng công thức và từ chối đúng lúc hay không. Câu hỏi thứ tư (RQ4) là mỗi bước của pipeline làm tăng độ trễ bao nhiêu, và sự đánh đổi giữa chất lượng với độ trễ diễn ra như thế nào.

### 1.5. Đóng góp và phạm vi

Đóng góp chính của đồ án gồm một kiến trúc RAG module hóa cho miền công thức nấu ăn, trong đó ràng buộc phủ định và dị ứng được chuyển thành truy vấn có cấu trúc thay vì phụ thuộc vào embedding. Đồ án cũng xây dựng một pipeline dữ liệu có quy tắc làm sạch và gắn thẻ được đánh mã, đếm số lượng và kiểm định độ chính xác. Bên cạnh đó là bộ test song ngữ có ràng buộc, có hội thoại nhiều lượt và có câu không trả lời được, cùng thí nghiệm ablation có kiểm định thống kê so với A1. Cuối cùng là một hệ thống hoàn chỉnh gồm API, cơ sở dữ liệu và giao diện chatbox. Phạm vi của đồ án giới hạn ở dữ liệu văn bản, không fine-tune mô hình, và corpus là công thức nấu ăn của Mỹ viết bằng tiếng Anh. Hệ thống chỉ mang tính hỗ trợ, không thay thế tư vấn y tế, vì thông tin dị ứng được suy ra từ danh sách nguyên liệu và không phản ánh được nguy cơ nhiễm chéo trong chế biến.

---

## Chương 2. Tổng quan và cơ sở lý thuyết

### 2.1. Truy hồi thông tin và tìm kiếm lai

BM25 là hàm xếp hạng xác suất, cho điểm tài liệu bằng tổng trọng số IDF của các từ trong truy vấn, trong đó tần suất từ được bão hòa theo tham số k₁ và độ dài tài liệu được chuẩn hóa theo tham số b [8]. Truy hồi dày đặc (dense retrieval) là phương pháp mã hóa truy vấn và tài liệu một cách độc lập vào cùng một không gian vector bằng bi-encoder, rồi xếp hạng theo độ tương đồng cosine. Hai cách tiếp cận này bổ trợ cho nhau: truy hồi thưa mạnh khi truy vấn chứa đúng từ khóa hoặc thuật ngữ hiếm, còn truy hồi dày đặc mạnh khi người dùng diễn đạt cùng một ý bằng từ khác [9]. Tìm kiếm lai hợp nhất hai danh sách kết quả bằng Reciprocal Rank Fusion, với điểm của mỗi tài liệu là RRF(d) = Σ_m 1/(k + rank_m(d)). Sau đó, một cross-encoder đọc đồng thời từng cặp truy vấn và ứng viên để xếp hạng lại tập ứng viên nhỏ. Kiến trúc hai tầng này, gồm tầng truy hồi ưu tiên recall và tầng xếp hạng lại ưu tiên precision, đã được A1 hiện thực và đánh giá [6], và được A3 giữ nguyên làm lõi truy hồi.

### 2.2. Retrieval-Augmented Generation

Retrieval-Augmented Generation (RAG) là kiến trúc kết hợp bộ nhớ tham số của mô hình ngôn ngữ với bộ nhớ phi tham số bên ngoài, truy hồi bằng chứng tại thời điểm suy luận và đưa bằng chứng đó vào quá trình sinh để câu trả lời có căn cứ và trích nguồn được [3]. Ở góc nhìn hệ thống thông tin, giá trị của RAG nằm ở khả năng grounding, tức là gắn câu trả lời với tham chiếu để người dùng tự kiểm chứng, và ở khả năng giới hạn phạm vi trả lời trong miền tri thức của tổ chức [2]. Hallucination là hiện tượng mô hình sinh ra nội dung trôi chảy nhưng không nhất quán với nguồn đầu vào hoặc với sự thật [4], và RAG làm giảm nhưng không loại bỏ hoàn toàn hiện tượng này. Các hệ RAG phát triển từ Naive RAG (truy hồi rồi sinh), qua Advanced RAG (thêm viết lại truy vấn trước truy hồi và xếp hạng lại sau truy hồi), đến Modular RAG. Modular RAG tổ chức hệ thống thành tám module gồm Indexing, Pre-retrieval, Retrieval, Post-retrieval, Pre-generation, Generation, Post-generation và Orchestration, với bốn mẫu luồng điều phối là tuyến tính, có điều kiện, rẽ nhánh và vòng lặp [10]. Theo khung này, A1 tương ứng với một hệ Advanced RAG chưa có bước sinh, còn A3 bổ sung các module tiền truy hồi, hậu truy hồi, sinh và hậu kiểm.

### 2.3. Hiểu truy vấn và hội thoại

Viết lại truy vấn (query rewriting) là phép biến đổi truy vấn gốc thành một truy vấn độc lập ngữ cảnh và khớp hơn với kho tri thức trước khi truy hồi. Xây dựng truy vấn có cấu trúc (query construction) là phép chuyển nhu cầu thông tin bằng ngôn ngữ tự nhiên thành ngôn ngữ truy vấn hình thức như SQL hoặc bộ lọc metadata để truy cập dữ liệu có cấu trúc [10]. Hướng thứ hai đặc biệt quan trọng với A3 vì các mô hình truy hồi neural xử lý phủ định kém: một truy vấn như "món không có đậu phộng" vẫn có thể có embedding gần với các công thức chứa đậu phộng [11]. Đây cũng là cơ sở lý thuyết giải thích lỗi "mất chi tiết chính xác" của A1. Trong hội thoại nhiều lượt, các ràng buộc người dùng nêu ở lượt trước phải tiếp tục có hiệu lực ở lượt sau. Khảo sát về cá nhân hóa trong RAG mô hình hóa điều này bằng việc bổ sung thông tin người dùng p vào bước tiền truy hồi, dưới dạng q* = Q(q, p), đồng thời chỉ ra rằng viết lại phù hợp với nhu cầu làm rõ ý định trong hội thoại hơn là mở rộng truy vấn [7]. A3 áp dụng quan điểm này bằng cách tách câu hỏi thành hai phần: phần mô tả nhu cầu được viết lại để truy hồi ngữ nghĩa, còn phần ràng buộc được chuyển thành điều kiện lọc có cấu trúc và lưu trong trạng thái phiên.

### 2.4. Đánh giá hệ RAG

Chất lượng của một hệ RAG cần được đo tách biệt ở tầng truy hồi và tầng sinh, vì một câu trả lời sai có thể bắt nguồn từ việc truy hồi bỏ sót hoặc từ việc mô hình sinh không bám ngữ cảnh. Ở tầng truy hồi, các độ đo Recall@k, MRR và nDCG@k đánh giá thứ hạng của tài liệu liên quan, trong đó nDCG@k chuẩn hóa DCG@k = Σ_{i≤k} (2^{rel_i} − 1)/log₂(i+1) theo giá trị lý tưởng [8]. Ở tầng sinh, khung RAGAS đề xuất các độ đo faithfulness (mức câu trả lời được ngữ cảnh hỗ trợ), answer relevance, context precision và context recall [12]. Một tổng quan có hệ thống về RAG còn đề xuất giao thức đánh giá tối thiểu, gồm thêm độ đo về trích dẫn, khả năng từ chối trả lời và kiểm tra bởi con người. Tổng quan này cũng cảnh báo rằng LLM khi làm giám khảo có xu hướng ưu ái câu trả lời trôi chảy, nên cần đối chiếu với nhãn của người. Ngoài ra, các tác giả đề xuất mỗi nghiên cứu công bố một "RAG Card" mô tả snapshot dữ liệu, cách chunking, mô hình, prompt và tham số để kết quả có thể tái lập [9]. A3 áp dụng giao thức này và bổ sung độ đo riêng cho bài toán là tỉ lệ công thức vi phạm ràng buộc.

### 2.5. Kiến trúc hệ thống chatbot dựa trên LLM

Một tổng quan có hệ thống về chatbot dựa trên LLM tổng hợp kiến trúc tham chiếu gồm bốn lớp [13]. Lớp Frontend tiếp nhận yêu cầu của người dùng. Lớp Backend gồm tiền xử lý, mô hình ngôn ngữ lõi và middleware kết nối dịch vụ. Lớp Data Infrastructure lưu trữ dữ liệu, cơ sở tri thức và pipeline dữ liệu. Lớp Governance đảm nhận giám sát, giảm thiên lệch và tuân thủ. Cũng theo tổng quan này, các độ đo đánh giá chatbot thường được chia thành năm nhóm: độ chính xác, mức hài lòng của người dùng, chất lượng nội dung, an toàn và hiệu năng. A3 dùng kiến trúc bốn lớp này làm khung để trình bày thiết kế ở Chương 3.

### 2.6. Công trình liên quan trong miền ẩm thực

Bài toán gợi ý món ăn khác các bài toán gợi ý thông thường ở chỗ phải cân bằng giữa sở thích của người dùng và các yếu tố sức khỏe như dinh dưỡng, chế độ ăn hay dị ứng [5]. Gần với A3 nhất là KERL, hệ thống trích xuất thực thể từ câu hỏi ngôn ngữ tự nhiên, truy hồi đồ thị con từ đồ thị tri thức ẩm thực và đưa vào mô hình ngôn ngữ để chọn công thức thỏa các ràng buộc của người dùng [14]. Ở hướng tương tác, Jaber và cộng sự nghiên cứu thiết kế trợ lý nấu ăn bằng giọng nói có nhận biết ngữ cảnh [1]. So với các công trình này, A3 khác ở bốn điểm. Thứ nhất, ràng buộc cứng được thực thi bằng truy vấn SQL thay vì để mô hình ngôn ngữ tự quyết định. Thứ hai, hệ hỗ trợ truy vấn tiếng Việt trên corpus tiếng Anh. Thứ ba, trạng thái ràng buộc được duy trì qua nhiều lượt hội thoại. Thứ tư, mọi thành phần chỉ dùng mô hình có sẵn chạy cục bộ, không fine-tune.

---

## Chương 3. Phân tích và thiết kế hệ thống

### 3.1. Phân tích yêu cầu

Hệ thống phục vụ năm nhóm chức năng chính. Người dùng có thể hỏi gợi ý món ăn kèm ràng buộc bằng tiếng Việt hoặc tiếng Anh, chẳng hạn "tôi dị ứng đậu phộng, gợi ý món tráng miệng dưới 30 phút". Người dùng có thể hỏi tiếp để tinh chỉnh kết quả ở các lượt sau, xem và sửa các ràng buộc mà hệ đã hiểu, và gửi phản hồi về câu trả lời. Chức năng tìm kiếm nâng cao của A1 được giữ lại. Về yêu cầu phi chức năng, hệ phải không gợi ý món vi phạm ràng buộc cứng đã biết, phải minh bạch bằng cách hiển thị ràng buộc đã hiểu và trích dẫn nguồn, phải trả lời theo dạng streaming để giảm thời gian chờ, phải tái lập được kết quả nhờ cố định seed và tham số, và phải chạy cục bộ để không gửi dữ liệu người dùng ra ngoài.

### 3.2. Dữ liệu và pipeline xử lý offline

Để khắc phục hạn chế về tính minh bạch của A1, mọi bước xử lý dữ liệu trong A3 được gán mã quy tắc, kèm lý do và số bản ghi bị ảnh hưởng. Các số liệu này được script xử lý ghi tự động ra tệp thống kê, không nhập tay. Các quy tắc được trình bày ở Bảng 3.1. Bước quan trọng nhất là gắn thẻ dị ứng cho từng công thức theo chín nhóm dị ứng chính được quy định tại Mỹ, gồm sữa, trứng, cá, động vật có vỏ giáp xác, hạt cây, đậu phộng, lúa mì, đậu nành và mè [15]. Nhóm chọn danh mục này vì corpus là công thức của Mỹ. Việc gắn thẻ áp dụng nguyên tắc bảo thủ với các thành phần ẩn: chẳng hạn bơ được tính là sữa, nước sốt Worcestershire được tính là cá, nước tương được tính là đậu nành và lúa mì.

**Bảng 3.1. Quy tắc làm sạch và gắn thẻ dữ liệu**

| Mã | Quy tắc | Lý do |
|---|---|---|
| D1 | Loại công thức trùng URL (3 bản ghi, theo A1) | Khử trùng lặp |
| D2 | Bỏ 13 cột dinh dưỡng rỗng trên 99% | Không có giá trị sử dụng |
| D3 | Chuẩn hóa thời gian về số phút, gán null khi không đọc được | Phục vụ lọc theo thời gian |
| D4 | Tách dòng nguyên liệu thành số lượng, đơn vị và tên nguyên liệu | Nền tảng cho chuẩn hóa |
| D5 | Ánh xạ tên nguyên liệu về dạng chuẩn bằng từ điển đồng nghĩa | Gom các cách viết khác nhau |
| D6 | Gắn nhóm dị ứng cho nguyên liệu chuẩn | Lọc theo dị ứng |
| D7 | Suy ra cờ chế độ ăn chay và thuần chay | Lọc theo chế độ ăn |
| D8 | Đánh dấu nguyên liệu không ánh xạ được là `unknown` | Đo độ phủ và hỗ trợ chế độ lọc an toàn |

Vì độ an toàn của bộ lọc không thể vượt quá độ chính xác của bộ gắn thẻ, nhóm lấy ngẫu nhiên 200 công thức, phân tầng theo 22 danh mục, và gán nhãn tay các nhóm dị ứng mà không xem kết quả của máy. Precision và recall của bộ gắn thẻ được báo cáo theo từng nhóm dị ứng trên tập mẫu này, trong đó recall được ưu tiên vì bỏ sót một chất gây dị ứng nguy hiểm hơn loại nhầm một món. Sau bước gắn thẻ, dữ liệu được chunk, embedding và đánh chỉ mục như A1. Riêng các cột thẻ dị ứng, nguyên liệu chuẩn và chế độ ăn được sao xuống từng chunk để bộ lọc chạy ngay trong chỉ mục (Hình 3.1).

### 3.3. Kiến trúc tổng thể

Hệ thống được tổ chức theo kiến trúc bốn lớp [13] (Hình 3.2). Lớp Frontend là ứng dụng React gồm trang chatbox, trang tìm kiếm nâng cao kế thừa từ A1 và trang báo cáo kết quả thực nghiệm. Lớp Backend là dịch vụ FastAPI, chứa bộ điều phối pipeline, các module xử lý, kết nối tới Ollama và mô hình xếp hạng lại. Lớp Data Infrastructure là ParadeDB, lưu kho công thức, chỉ mục BM25 và vector, phiên hội thoại, nhật ký truy vết và phản hồi người dùng. Lớp Governance gồm nhật ký truy vết từng bước, cơ chế phản hồi, banner miễn trừ trách nhiệm và bước kiểm tra an toàn sau khi sinh. Các dịch vụ được đóng gói bằng Docker Compose và triển khai cục bộ.

### 3.4. Pipeline xử lý trực tuyến

Pipeline trực tuyến gồm bảy module, đặt tên theo khung Modular RAG [10], và được điều phối theo luồng tuyến tính có một nhánh điều kiện (Hình 3.3). Nhóm không chọn luồng vòng lặp hay agentic vì thực nghiệm trong khung Modular RAG cho thấy với mô hình ngôn ngữ cỡ nhỏ, khả năng tự đánh giá kém khiến các vòng lặp tốn chi phí mà không cải thiện tương xứng, và luồng tuyến tính nên là lựa chọn mặc định [10]. Mô hình `qwen2.5:7b` chạy cục bộ là trường hợp như vậy.

Module đầu tiên (M1) đảm nhận việc hiểu truy vấn. Mô hình ngôn ngữ đọc câu hỏi cùng lịch sử hội thoại và trả về một đối tượng JSON theo lược đồ định trước, gồm ý định (tìm mới, tinh chỉnh, hỏi chi tiết, ngoài phạm vi), câu truy vấn tiếng Anh độc lập ngữ cảnh, và các ràng buộc như nhóm dị ứng cần tránh, nguyên liệu cần loại, chế độ ăn, thời gian tối đa và lượng calo. Câu truy vấn tiếng Anh được cố ý viết không chứa phủ định, vì phủ định chỉ được xử lý ở bộ lọc. Kết quả của mô hình sau đó được hậu xử lý bằng từ điển tiếng Việt – tiếng Anh để ánh xạ tên nguyên liệu về dạng chuẩn và loại bỏ các giá trị không hợp lệ. Module thứ hai (M2) quản lý trạng thái phiên: ràng buộc dị ứng có hiệu lực trong suốt phiên cho tới khi người dùng gỡ bỏ, còn các ràng buộc tạm thời chỉ áp dụng cho lượt hiện tại. Module thứ ba (M3) định tuyến theo ý định: câu hỏi ngoài phạm vi được từ chối lịch sự, câu hỏi chi tiết về một món đã gợi ý được trả lời trực tiếp từ cơ sở dữ liệu, còn lại được chuyển sang truy hồi.

Module thứ tư (M4) truy hồi có lọc cứng. Các ràng buộc được chuyển thành điều kiện WHERE để loại trước mọi công thức chứa nhóm dị ứng hoặc nguyên liệu bị cấm, rồi mới chạy truy hồi lai BM25, dense và RRF như A1. Module thứ năm (M5) xếp hạng lại bằng cross-encoder `mxbai-rerank-base-v1`, mô hình đã cho kết quả tốt nhất trong ablation của A1, rồi gom các chunk về cấp công thức để tránh hiện tượng chunk mất ngữ cảnh, và chọn năm công thức tốt nhất đưa vào ngữ cảnh. Module thứ sáu (M6) sinh câu trả lời với prompt yêu cầu mô hình chỉ dùng thông tin trong ngữ cảnh, trả lời bằng ngôn ngữ của người hỏi, trích dẫn từng món bằng mã công thức, trả lời "không tìm thấy" khi ngữ cảnh rỗng và không khẳng định món ăn an toàn tuyệt đối cho người dị ứng. Module cuối cùng (M7) hậu kiểm một cách tất định: mọi mã công thức được trích phải nằm trong ngữ cảnh, và không công thức nào được trích được phép vi phạm trạng thái ràng buộc. Nếu vi phạm, trích dẫn lỗi bị loại bỏ hoặc câu trả lời được sinh lại một lần. Mỗi module có cờ bật tắt riêng, nhờ đó mọi cấu hình ablation ở Chương 4 chạy trên cùng một mã nguồn.

### 3.5. Thiết kế cơ sở dữ liệu

Cơ sở dữ liệu giữ nguyên lược đồ chuẩn hóa của A1 cho công thức, danh mục, tác giả, dinh dưỡng, nguyên liệu thô và chunk, rồi bổ sung hai nhóm bảng mới (Hình 3.4). Nhóm thứ nhất phục vụ tri thức nguyên liệu: bảng nguyên liệu chuẩn kèm từ đồng nghĩa và bí danh tiếng Việt, bảng liên kết dòng nguyên liệu thô với nguyên liệu chuẩn, bảng nhóm dị ứng, bảng ánh xạ nguyên liệu – dị ứng, và bảng thẻ tổng hợp của từng công thức. Nhóm thứ hai phục vụ hội thoại và vận hành: bảng phiên hội thoại, bảng tin nhắn, bảng ràng buộc của phiên (ghi rõ phạm vi hiệu lực và tin nhắn tạo ra ràng buộc), bảng truy vết từng bước của pipeline kèm độ trễ, và bảng phản hồi của người dùng.

### 3.6. Thiết kế API

Hệ thống cung cấp dịch vụ qua REST API. Điểm truy cập chính là `POST /chat`, nhận tin nhắn của người dùng và trả kết quả theo cơ chế Server-Sent Events gồm bốn loại sự kiện nối tiếp: ràng buộc hệ đã hiểu, danh sách công thức truy hồi được, từng phần câu trả lời, và sự kiện kết thúc chứa danh sách trích dẫn, số token sử dụng và độ trễ của từng bước. Các điểm truy cập phụ cho phép xem và sửa ràng buộc của phiên, xem chi tiết công thức, gửi phản hồi và kiểm tra trạng thái hệ thống. Các điểm truy cập tìm kiếm của A1 được giữ lại để phục vụ so sánh.

### 3.7. Thiết kế giao diện

Theo góp ý của giảng viên, giao diện chuyển trọng tâm sang chatbox. Mỗi câu trả lời hiển thị dưới dạng streaming, kèm các thẻ công thức gắn với trích dẫn, trên đó có tiêu đề, thời gian chế biến, các nhóm dị ứng và nút xem chi tiết. Một panel bên cạnh hiển thị các ràng buộc hệ đang áp dụng dưới dạng chip có thể sửa hoặc xóa. Panel này giúp hệ minh bạch, đồng thời cho người dùng tự sửa khi bước hiểu truy vấn sai. Giao diện luôn hiển thị banner nhắc rằng thông tin dị ứng được suy ra từ nguyên liệu và không thay thế tư vấn y tế (Hình 3.5).

### 3.8. An toàn và đạo đức

Do bài toán liên quan trực tiếp đến sức khỏe, nhóm nhận diện ba rủi ro chính. Thứ nhất, bộ gắn thẻ có thể bỏ sót chất gây dị ứng ẩn, và rủi ro này được định lượng bằng recall trên tập 200 mẫu. Thứ hai, nguy cơ nhiễm chéo trong chế biến nằm ngoài khả năng của dữ liệu. Thứ ba, mô hình ngôn ngữ có thể thêm nguyên liệu không có trong công thức, và rủi ro này được giảm bằng bước hậu kiểm và độ đo faithfulness. Nội dung công thức chỉ được coi là dữ liệu chứ không phải chỉ dẫn, nhằm phòng tấn công chèn lệnh vào prompt. Hệ chạy cục bộ nên dữ liệu hội thoại không rời khỏi máy chủ. Cuối cùng, corpus là công thức của Mỹ nên các món Việt hầu như không có, và hệ phải trả lời không tìm thấy thay vì bịa ra công thức.

---

## Chương 4. Thực nghiệm và đánh giá

### 4.1. Xây dựng bộ test

Bộ test của A3 gồm bốn tập. Tập hồi quy (khoảng 100 truy vấn) lấy mẫu từ bộ truy vấn của A1, dùng để bảo đảm A3 không làm giảm chất lượng ở loại truy vấn mà A1 đã xử lý tốt. Tập ràng buộc một lượt (khoảng 150 truy vấn, một nửa bằng tiếng Việt) chứa các yêu cầu về dị ứng, loại trừ nguyên liệu, chế độ ăn hoặc thời gian. Tập không trả lời được (khoảng 50 truy vấn) gồm các tổ hợp ràng buộc mà không công thức nào thỏa mãn và các câu hỏi ngoài phạm vi. Tập hội thoại nhiều lượt gồm 40 đến 60 hội thoại, trong đó ràng buộc được nêu ở lượt trước. Truy vấn được tạo bằng ba nguồn: ghép mẫu câu kết hợp diễn đạt lại bằng mô hình ngôn ngữ, viết tay bởi thành viên nhóm, và các câu tiếng Việt tự nhiên có cả lỗi chính tả hay viết không dấu.

Mọi truy vấn ứng viên phải qua sáu quy tắc hợp lệ, mỗi quy tắc được báo cáo số câu bị loại. V1 yêu cầu truy vấn không chép nguyên tiêu đề công thức. V2 yêu cầu truy vấn có ít nhất một công thức thỏa ràng buộc (với tập không trả lời được thì ngược lại). V3 yêu cầu nhận diện đúng ngôn ngữ. V4 loại các câu gần trùng nhau. V5 giới hạn độ dài từ 3 đến 40 từ. V6 yêu cầu ràng buộc chuẩn của mỗi câu phải được người xác nhận. Kết quả được trình bày dưới dạng sơ đồ luồng, từ số câu sinh ra, qua số câu bị loại ở từng quy tắc, đến số câu còn lại. Bộ test được đóng băng trước khi chạy thực nghiệm.

### 4.2. Gán nhãn và bộ kiểm độc lập

Nhãn độ liên quan được xây dựng bằng phương pháp pooling: gộp mười kết quả đầu của mọi cấu hình, rồi gán nhãn theo thang 0, 1, 2. Việc gán nhãn do một mô hình ngôn ngữ khác họ với mô hình sinh (`llama3.1:8b`) thực hiện, nhằm tránh thiên lệch giám khảo ưu ái câu trả lời của mô hình cùng họ [9]. Nhóm kiểm tra lại 50 mẫu bằng tay và báo cáo hệ số Cohen's κ giữa người và mô hình.

Vi phạm ràng buộc được chấm bằng một bộ kiểm độc lập: mô hình ngôn ngữ đọc toàn văn danh sách nguyên liệu và trả lời công thức có chứa nhóm dị ứng hoặc nguyên liệu bị cấm hay không. Bộ kiểm không sử dụng từ điển hay thẻ của bộ gắn thẻ. Thiết kế này tránh đánh giá vòng tròn: nếu dùng chính bộ thẻ vừa để lọc vừa để chấm thì tỉ lệ vi phạm của hệ đề xuất sẽ bằng không theo định nghĩa. Bản thân bộ kiểm cũng được đánh giá precision và recall trên cùng tập 200 công thức gán nhãn tay, để kết quả vi phạm được báo cáo kèm sai số của công cụ đo.

### 4.3. Các cấu hình so sánh

Nhóm so sánh hệ đề xuất với hai baseline và sáu cấu hình ablation (Bảng 4.1). Mỗi cấu hình ablation chỉ thay đổi đúng một thành phần so với hệ đầy đủ, chạy trên cùng bộ truy vấn và trong cùng một lần chạy, như quy trình đã áp dụng ở A1.

**Bảng 4.1. Các cấu hình thực nghiệm**

| Mã | Cấu hình | Mục đích |
|---|---|---|
| B0 | Hybrid của A1 trên truy vấn thô | Baseline chính |
| B1 | B0 cộng bước sinh câu trả lời, không hiểu truy vấn, không lọc, không hậu kiểm | Tách lợi ích của việc có sinh khỏi lợi ích của việc hiểu ràng buộc |
| S | Hệ đầy đủ M1–M7 | Hệ đề xuất |
| S−QU | Bỏ hiểu truy vấn | Đóng góp của M1 |
| S−Filter | Ràng buộc chỉ ghép vào văn bản truy vấn, không thành điều kiện lọc | Lọc cứng so với dựa vào ngữ nghĩa |
| S−Norm | Lọc trên chuỗi nguyên liệu thô, không dùng thẻ chuẩn hóa | Đóng góp của pipeline dữ liệu |
| S−Conv | Mỗi lượt xử lý độc lập, không dùng lịch sử | Đóng góp của quản lý trạng thái |
| S−Rerank | Bỏ xếp hạng lại | Chi phí và lợi ích của cross-encoder |
| S−Verify | Bỏ hậu kiểm | Đóng góp của M7 |

### 4.4. Độ đo

Ở tầng hiểu truy vấn, nhóm đo độ chính xác phân loại ý định và F1 của các ràng buộc trích xuất được so với ràng buộc chuẩn. Ở tầng truy hồi, nhóm dùng Recall@10, MRR và nDCG@10, trong đó độ liên quan được điều chỉnh để một công thức chỉ được tính là liên quan khi thỏa mọi ràng buộc của truy vấn. Độ đo trọng tâm của đồ án là tỉ lệ vi phạm ràng buộc CVR@k, bằng trung bình trên các truy vấn có ràng buộc của tỉ lệ công thức vi phạm trong k kết quả đầu, cùng với Safe@k, là tỉ lệ truy vấn có k kết quả đầu hoàn toàn không vi phạm. Ở tầng sinh, nhóm đo faithfulness và answer relevance theo khung RAGAS [12], tỉ lệ trích dẫn hợp lệ (mã được trích nằm trong ngữ cảnh) và tỉ lệ trích dẫn an toàn (công thức được trích thỏa ràng buộc). Ở khía cạnh độ bền, nhóm đo tỉ lệ từ chối đúng trên tập không trả lời được và tỉ lệ từ chối sai trên các tập còn lại. Về hiệu năng, nhóm đo độ trễ trung vị và phân vị 95 của từng module, thời gian tới token đầu tiên và độ trễ toàn trình. Khác biệt giữa các cấu hình được kiểm định bằng Wilcoxon signed-rank theo từng truy vấn với hiệu chỉnh Holm, kèm khoảng tin cậy bootstrap 95%. Kết luận "tốt hơn" chỉ được đưa ra khi khác biệt còn có ý nghĩa sau hiệu chỉnh.

### 4.5. Thiết lập thực nghiệm

Phần này mô tả phần cứng, phiên bản Ollama, các mô hình và mức lượng tử hóa, seed, nhiệt độ sinh, số ứng viên truy hồi (50) và số công thức đưa vào ngữ cảnh (5). Toàn bộ thông tin được tổng hợp thành RAG Card ở phụ lục theo đề xuất của [9].

### 4.6. Kết quả, ablation và phân tích lỗi

Kết quả chính so sánh B0, B1 và S trên bốn tập test theo các độ đo ở mục 4.4, kèm biểu đồ chất lượng theo độ trễ. Kỳ vọng cần kiểm chứng là S giảm rõ tỉ lệ vi phạm so với hai baseline, không làm giảm nDCG@10 trên tập ràng buộc, và không hồi quy trên tập của A1. Bảng ablation trình bày mức thay đổi của từng cấu hình so với S, kèm giá trị p đã hiệu chỉnh. Phân tích lỗi phân loại các trường hợp sai theo tầng phát sinh, gồm trích ràng buộc sai (đặc biệt khi dịch tên nguyên liệu tiếng Việt), định tuyến sai ý định, bộ gắn thẻ sót hoặc thừa, lọc quá chặt dẫn đến không còn kết quả, truy hồi bỏ sót, xếp hạng lại sai, câu trả lời không bám ngữ cảnh, từ chối sai và mất trạng thái ở lượt sau.

Mỗi nhóm lỗi có số lượng, ví dụ minh họa và hướng khắc phục. Phần cuối phân rã độ trễ theo từng module để trả lời RQ4.

---

## Chương 5. Triển khai và demo

Chương này hướng dẫn cài đặt bằng Docker Compose, tải mô hình qua Ollama, chạy pipeline dữ liệu và chạy đánh giá. Buổi demo gồm bốn kịch bản. Kịch bản thứ nhất là một câu hỏi tiếng Việt có ràng buộc dị ứng, so sánh baseline trả về món chứa chất gây dị ứng với hệ đề xuất lọc đúng. Kịch bản thứ hai là hội thoại ba lượt có bổ sung ràng buộc. Kịch bản thứ ba là một câu hỏi không có đáp án, để thấy hệ từ chối đúng. Kịch bản thứ tư là người dùng sửa chip ràng buộc và quan sát kết quả thay đổi.

## Chương 6. Kết luận và hướng phát triển

Chương kết luận trả lời từng câu hỏi nghiên cứu bằng số liệu thực nghiệm, sau đó nêu các hạn chế. Bộ test do nhóm tự xây dựng. Nhãn liên quan chủ yếu do mô hình ngôn ngữ gán. Thông tin dị ứng được suy ra từ nguyên liệu. Corpus chỉ gồm món ăn của Mỹ. Thực nghiệm chạy trên một máy. Hướng phát triển gồm cá nhân hóa bằng hồ sơ người dùng dài hạn, bổ sung đồ thị tri thức nguyên liệu, mở rộng corpus món Việt và tối ưu hiệu năng phục vụ.

## Phụ lục

Phụ lục gồm RAG Card mô tả snapshot dữ liệu, các quy tắc xử lý, mô hình, prompt và tham số; thẻ dữ liệu của bộ test kèm sơ đồ luồng lọc; nguyên văn các prompt của bước hiểu truy vấn, bước sinh câu trả lời và bước chấm điểm; lược đồ JSON đầu ra của bước hiểu truy vấn; và bảng phân công thành viên.

---

## Tài liệu tham khảo

[1] R. Jaber *et al.*, "Cooking with agents: Designing context-aware voice interaction," in *Proc. CHI Conf. Human Factors Comput. Syst. (CHI '24)*, 2024.

[2] M. Klesel and H. F. Wittmann, "Retrieval-augmented generation (RAG)," *Bus. Inf. Syst. Eng.*, vol. 67, no. 4, pp. 551–561, 2025, doi: 10.1007/s12599-025-00945-3.

[3] P. Lewis *et al.*, "Retrieval-augmented generation for knowledge-intensive NLP tasks," in *Adv. Neural Inf. Process. Syst. (NeurIPS)*, vol. 33, 2020, pp. 9459–9474.

[4] Z. Ji *et al.*, "Survey of hallucination in natural language generation," *ACM Comput. Surv.*, vol. 55, no. 12, Art. 248, 2023.

[5] W. Min, S. Jiang, and R. Jain, "Food recommendation: Framework, existing solutions, and challenges," *IEEE Trans. Multimedia*, vol. 22, no. 10, pp. 2659–2671, 2020, doi: 10.1109/TMM.2019.2958761.

[6] Nhóm 1, "Truy hồi công thức nấu ăn: BM25, Dense, Hybrid và Reranking trên ParadeDB," Báo cáo bài tập A1, môn IS6303, Trường ĐH Công nghệ Thông tin – ĐHQG-HCM, 2026. [Online]. Available: https://github.com/Anlele1701/UIT_IS6303_RecipeRetrieval

[7] X. Li *et al.*, "A survey of personalization: From RAG to agent," *ACM Trans. Inf. Syst.*, vol. 44, no. 4, Art. 93, May 2026, doi: 10.1145/3802586.

[8] C. D. Manning, P. Raghavan, and H. Schütze, *Introduction to Information Retrieval*. Cambridge, U.K.: Cambridge Univ. Press, 2008.

[9] A. R. Faridi, F. Masood, Keshvi, and T. Yunus, "Retrieval-augmented generation for large language models: Evolution, architectures, applications, and challenges (2020–2025)," *WIREs Data Mining Knowl. Discov.*, vol. 16, no. 3, Art. e70122, 2026, doi: 10.1002/widm.70122.

[10] Y. Gao, Y. Xiong, M. Wang, and H. Wang, "Modular RAG: Transforming RAG systems into LEGO-like reconfigurable frameworks," *ACM Trans. Inf. Syst.*, vol. 44, no. 7, Art. 164, Sep. 2026, doi: 10.1145/3837856.

[11] O. Weller, D. Lawrie, and B. Van Durme, "NevIR: Negation in neural information retrieval," in *Proc. 18th Conf. EACL*, 2024.

[12] S. Es, J. James, L. Espinosa-Anke, and S. Schockaert, "RAGAs: Automated evaluation of retrieval augmented generation," in *Proc. 18th Conf. EACL: System Demonstrations*, 2024.

[13] P. Raghavan, D. A. Tamburri, S. Fossati, and W.-J. Van Den Heuvel, "LLMOps in action: A framework for designing, deploying, and governing advanced chatbots," *IEEE Trans. Knowl. Data Eng.*, vol. 38, no. 7, pp. 4491–4510, Jul. 2026.

[14] F. Mohbat and M. J. Zaki, "KERL: Knowledge-enhanced personalized recipe recommendation using large language models," in *Proc. 63rd Annu. Meeting ACL (Vol. 1: Long Papers)*, 2025, pp. 19125–19141, doi: 10.18653/v1/2025.acl-long.938.

[15] U.S. Food and Drug Administration, "Food allergies: What you need to know," FDA (FALCPA 2004; FASTER Act 2021).
