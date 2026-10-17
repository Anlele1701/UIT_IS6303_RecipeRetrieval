# Kịch bản thuyết trình - Nhóm 1 - Assignment 2

**Bài báo:** An Empirical Evaluation of Retrieval, Reranking, and Similarity for a Q&A-Based Retrieval Augmented Generation System (Elkiran & Rasheed, IEEE Access, 2026)

**Thời lượng gợi ý:** khoảng 30 phút (20 slide, trung bình 1,5 phút mỗi slide). Slide có đánh dấu (hình) cần thêm thời gian để chỉ vào bảng/hình.

**Quy ước:** phần trong dấu ngoặc vuông là ghi chú cho người nói, không đọc thành tiếng. Mục *[Chèn Table X]* nghĩa là bạn đã dán hình bảng vào khung, hãy chỉ vào bảng khi nói. Các con số kết quả không có trong slide, hãy đọc từ bảng đã dán, đừng nói từ trí nhớ.

---

## Slide 1 - Trang bìa (khoảng 0,5 phút)

Em chào cô và các bạn. Nhóm 1 xin trình bày Assignment 2 môn Thiết kế hệ thống thông tin truy hồi, do cô Phạm Đỗ Kim Chi hướng dẫn.

Bài báo nhóm chọn là *An Empirical Evaluation of Retrieval, Reranking, and Similarity for a Q&A-Based Retrieval Augmented Generation System*, đăng trên IEEE Access năm 2026. Bài báo đánh giá thực nghiệm xem từng thành phần trong một hệ thống RAG đóng góp bao nhiêu vào chất lượng chung.

[Giới thiệu tên bốn thành viên nếu cần.]

## Slide 2 - Mục lục (khoảng 0,5 phút)

Bài trình bày gồm bốn phần chính. Phần một là bài toán mà bài báo giải quyết. Phần hai là ý tưởng cốt lõi và phương pháp đề xuất. Phần ba là thiết kế thực nghiệm, gồm dữ liệu, thiết lập, công cụ thống kê và các độ đo. Phần bốn là kết quả, cùng đánh giá của tác giả và của nhóm. Cuối cùng là tài liệu tham khảo.

---

## Slide 3 - Bài toán: bối cảnh (khoảng 1,5 phút)

Các mô hình ngôn ngữ lớn đã làm rất tốt việc sinh văn bản, trả lời câu hỏi phức tạp và truy hồi thông tin. Tuy nhiên chúng vẫn gặp khó khi xử lý ngữ cảnh dài. Khi đó mô hình dễ dựa vào tri thức đã học từ lúc huấn luyện thay vì dựa vào ngữ cảnh của tác vụ đang làm, và kết quả là sinh ra thông tin sai lệch, hay còn gọi là hallucination.

Có hai hướng giải quyết. Hướng thứ nhất là mở rộng cửa sổ ngữ cảnh. Hướng này bị hạn chế về chi phí và vẫn dễ làm mô hình trả lời sai.

Hướng thứ hai là RAG, và đây là hướng bài báo chọn. RAG chỉ truy hồi phần thông tin liên quan nên hiệu quả hơn khi thông tin bị phân mảnh. RAG cũng cập nhật được thông tin gần nhất và có thể trích dẫn nguồn tài liệu.

## Slide 4 - Bài toán: khoảng trống và mục tiêu (khoảng 1,5 phút)

Hiệu quả của một pipeline RAG phụ thuộc vào bốn lựa chọn: chiến lược lập chỉ mục, phương pháp truy hồi, độ đo tương đồng và mô hình tái xếp hạng.

Vấn đề là phần lớn các nghiên cứu trước chỉ cải tiến một thành phần đơn lẻ, hoặc đánh giá các mô hình hiện đại nhất trên các bộ benchmark. Chưa ai trả lời rõ câu hỏi: khi các thành phần cùng tồn tại và tác động qua lại trong một pipeline, yếu tố nào mới thực sự chi phối hiệu năng?

Vì vậy mục tiêu của bài báo có hai ý. Một là đánh giá thực nghiệm có hệ thống mức đóng góp của từng thành phần vào hiệu năng tổng thể. Hai là chứng minh kết quả đó có ý nghĩa thống kê, chứ không chỉ là so sánh bằng mắt.

---

## Slide 5 - Ý tưởng cốt lõi (khoảng 1,5 phút)

Ý tưởng của nhóm tác giả có ba điểm.

Thứ nhất, họ xây một pipeline module hóa. Mỗi giai đoạn gồm lập chỉ mục, truy hồi, tái xếp hạng và độ đo tương đồng đều cấu hình được qua giao diện dòng lệnh. Nhờ vậy họ thay đổi từng tham số một cách có kiểm soát và độc lập.

Thứ hai, ở bước cuối họ cố ý chọn một mô hình sinh nhẹ, chi phí thấp. Mục đích là cô lập ảnh hưởng của truy hồi và tái xếp hạng, để chất lượng của mô hình sinh không gây nhiễu lên các phân tích thống kê.

Thứ ba, họ dùng đồng thời ba phương pháp kiểm định thống kê bổ trợ nhau. Nhờ đó kết luận mang tính giải thích, tức là biết vì sao, chứ không chỉ mô tả cấu hình nào cho điểm cao hơn.

## Slide 6 - Pipeline RAG đề xuất (khoảng 2 phút)

[Chỉ lần lượt theo mũi tên: hàng trên từ trái sang phải, rồi xuống hàng dưới từ phải sang trái.]

Pipeline có tám bước. Đầu tiên là phân đoạn tài liệu, sau đó biểu diễn các đoạn thành vector bằng mô hình embedding. Các vector được lưu và lập chỉ mục trong một cơ sở dữ liệu vector. Khi có câu hỏi, hệ thống embed câu hỏi bằng cùng mô hình, truy hồi top-k vector gần nhất, rồi tái xếp hạng bằng cross-encoder. Cuối cùng một mô hình ngôn ngữ nhẹ sinh câu trả lời. Hai bước sau cùng là đánh giá hiệu năng và kiểm định thống kê.

Các ô màu xanh đậm là ba thành phần được khảo sát: lập chỉ mục, truy hồi cùng độ đo tương đồng, và tái xếp hạng. Các ô viền nhạt như phân đoạn, embedding và sinh câu trả lời được giữ cố định, nhằm giảm độ phức tạp tổ hợp.

---

## Slide 7 - 3.1 Dataset (khoảng 1,5 phút)

Bài báo dùng bộ dữ liệu SQuAD. Mỗi mẫu gồm một đoạn văn Wikipedia, một câu hỏi và một hoặc nhiều câu trả lời chuẩn, do người chú thích tạo ra. Bộ gốc có khoảng một trăm nghìn mẫu.

Từ bộ gốc, nhóm tác giả lấy mẫu ngẫu nhiên tạo ba bộ con: 10 nghìn, 30 nghìn và 100 nghìn, gọi là Small, Medium và Large. Việc lấy mẫu có kiểm soát để tỷ lệ chủ đề và loại câu hỏi vẫn cân đối như bộ gốc. Nhờ vậy kích thước dữ liệu trở thành một yếu tố thực nghiệm riêng mà không làm lệch phân phối.

## Slide 8 - 3.2 Thiết lập thực nghiệm (khoảng 1,5 phút)

Các tham số sau được cố định cho mọi thí nghiệm. Văn bản chia chunk với cửa sổ 1.000 ký tự và overlap 200 ký tự. Embedding dùng mô hình text-embedding-3-large của OpenAI, không gian 3072 chiều, lưu và lập chỉ mục trong Milvus. Mỗi truy vấn lấy 10 đoạn gần nhất, tức top-k bằng 10.

Câu trả lời được sinh bằng gpt-4o-mini với temperature bằng 0, một system prompt cố định và giới hạn tối đa ba câu. Hệ thống cài bằng Python và LangChain, chạy trên CPU 8 nhân, 32 GB RAM, không dùng GPU.

Lý do cố định các tham số này là để giảm độ phức tạp tổ hợp, giúp tập trung vào các yếu tố cần khảo sát.

## Slide 9 - 3.2 Các yếu tố được khảo sát (khoảng 1,5 phút)

Bốn yếu tố được thay đổi, mỗi yếu tố có nhiều mức.

Lập chỉ mục có ba lựa chọn: HNSW dựa trên đồ thị phân tầng, IVF dựa trên chỉ mục file đảo, và ScaNN dùng lượng tử hóa vector. Độ đo tương đồng gồm cosine, inner product và khoảng cách L2. Chiến lược truy hồi có bốn lựa chọn là Fusion, Hierarchical, HyDE và HyPE, em sẽ giải thích ngay ở slide sau. Mô hình tái xếp hạng gồm hai cross-encoder là BGE và MiniLM.

Các mức của từng yếu tố được tổ hợp với nhau, cộng thêm yếu tố kích thước dữ liệu ở slide trước.

## Slide 10 - 3.2 Bốn chiến lược truy hồi (khoảng 2 phút)

Fusion kết hợp kết quả từ nhiều chiến lược hoặc nhiều biểu diễn truy hồi, bằng cộng có trọng số hoặc theo thứ hạng, để tăng khả năng tìm đủ tài liệu liên quan.

Hierarchical truy hồi thô ở cấp tài liệu trước, sau đó truy hồi chi tiết các đoạn trong những tài liệu đã chọn. Cách này tăng hiệu quả mà vẫn giữ độ chính xác.

HyDE và HyPE cùng ý tưởng: nhờ mô hình ngôn ngữ sinh ra một văn bản giả định rồi dùng embedding của nó làm truy vấn. HyDE sinh cả một tài liệu giả định. HyPE sinh một đoạn giả định, đại diện cho câu trả lời lý tưởng. Hai cách này thu hẹp khoảng cách ngữ nghĩa giữa câu hỏi và tài liệu lưu trữ.

---

## Slide 11 - 3.3 Công cụ thống kê (khoảng 2 phút)

Ba công cụ thống kê bổ trợ cho nhau, mỗi công cụ trả lời một câu hỏi khác nhau.

ANOVA trả lời: khác biệt hiệu năng giữa các cấu hình là thật hay chỉ do ngẫu nhiên. Nó so sánh phương sai giữa các nhóm với phương sai trong nhóm, cho ra F-statistic và p-value. Bài báo dùng cả ANOVA một chiều và đa yếu tố.

Kích thước hiệu ứng eta bình phương, ký hiệu η², trả lời: ảnh hưởng lớn đến mức nào trong thực tế. Nó bằng tổng bình phương của yếu tố chia cho tổng bình phương toàn phần. Công cụ này cần thiết vì khi cỡ mẫu lớn, p-value dễ cực nhỏ ngay cả khi ảnh hưởng thực tế không đáng kể.

Hồi quy tuyến tính đa biến trả lời: mỗi lựa chọn cụ thể làm tăng hay giảm hiệu năng, và mức nào, khi đã kiểm soát các yếu tố còn lại. Ví dụ ước lượng riêng tác động của mức L2 trong yếu tố độ đo tương đồng.

## Slide 12 - 3.4 Các độ đo đánh giá (khoảng 2 phút)

Độ đo chia làm ba nhóm.

Nhóm truy hồi và tái xếp hạng có bốn độ đo. Recall@1 xem tài liệu đúng có đứng ở vị trí đầu tiên hay không. MRR là trung bình nghịch đảo vị trí của kết quả đúng. nDCG@1 đo chất lượng xếp hạng có trọng số theo vị trí. Coverage là tỷ lệ truy vấn tìm được ít nhất một tài liệu liên quan.

Nhóm sinh văn bản có ba độ đo. Correctness đo độ chính xác của thông tin. Faithfulness đo mức bám sát ngữ cảnh đã truy xuất, phản ánh hallucination. Relevance đo việc câu trả lời có đúng ý định của câu hỏi hay không.

Nhóm hiệu suất gồm latency trung bình và chi phí API trung bình mỗi truy vấn.

Lưu ý quan trọng: bài báo không mô tả rõ cách chấm ba độ đo sinh văn bản, em sẽ quay lại điểm này ở phần đánh giá của nhóm.

---

## Slide 13 - 4.1 Mức độ ảnh hưởng của thành phần (khoảng 2 phút)

Đây là kết quả quan trọng nhất. Bài báo xếp hạng ảnh hưởng của bốn thành phần theo η², xét trên hai độ đo là Coverage và Correctness.

Chiến lược truy hồi có ảnh hưởng cao nhất. Độ đo tương đồng đứng thứ hai, ảnh hưởng lớn. Reranker ở mức trung bình. Còn lập chỉ mục có ảnh hưởng không đáng kể.

[Chỉ vào *Table 7* đã dán để đọc giá trị η² của từng yếu tố.]

Thông điệp chính: quyết định chọn retriever và độ đo tương đồng quan trọng hơn nhiều so với việc chọn thuật toán lập chỉ mục.

## Slide 14 - 4.1 Retriever và độ đo tương đồng (khoảng 2 phút)

Về chiến lược truy hồi, HyPE cho kết quả tốt nhất trên mọi độ đo, đồng thời có chi phí và latency thấp nhất. Fusion và Hierarchical kém hơn rõ rệt. [Chỉ vào *Table 3*.]

Về độ đo tương đồng, inner product và cosine cho kết quả gần tương đương nhau, và đều vượt trội hẳn L2 trên mọi độ đo. L2 còn làm giảm Coverage. [Chỉ vào *Table 5*.]

## Slide 15 - 4.1 Reranker và lập chỉ mục (khoảng 2 phút)

Về reranker, MiniLM vượt trội BGE sau bước tái xếp hạng, đồng thời nhanh hơn với chi phí tương đương. Một mô hình nhẹ lại tốt hơn mô hình lớn hơn là điểm đáng chú ý. [Chỉ vào *Table 4*.]

Về lập chỉ mục, chênh lệch chất lượng giữa HNSW, IVF và ScaNN là nhỏ và không có ý nghĩa thống kê. Khác biệt đáng kể duy nhất nằm ở độ trễ: ScaNN nhanh nhất, HNSW chậm nhất. [Chỉ vào *Table 2*.]

## Slide 16 - 4.1 Tương tác và ý nghĩa thống kê (khoảng 2 phút)

Các thành phần không hoạt động hoàn toàn độc lập. Nếu retriever yếu thì reranking bị hạn chế, bất kể chọn reranker nào. Ngược lại, retriever mạnh như HyPE cung cấp tập ứng viên tốt hơn nên reranking phát huy hiệu quả. Tương tự, ưu thế của inner product rõ nhất khi đi cùng các retriever dùng embedding giả định là HyDE và HyPE, và giảm đi dưới Hierarchical. Vì vậy tác giả cho rằng reranking và độ đo tương đồng là yếu tố khuếch đại có điều kiện, không tác động độc lập.

Một lưu ý thống kê: bài báo ghi nhận p-value cực nhỏ, vì cỡ mẫu lớn và phương sai trong nhóm thấp. Do đó tác giả nhấn mạnh phải dùng kích thước hiệu ứng và khoảng tin cậy 95% làm chỉ báo chính về ý nghĩa thực tiễn, không chỉ dựa vào p-value.

[Nếu cần, chỉ vào *Table 6* (ANOVA) và *Table 8* (hồi quy) trong bài báo gốc.]

---

## Slide 17 - 4.1 Khuyến nghị của tác giả (khoảng 1,5 phút)

Từ các phát hiện trên, tác giả đưa ra năm khuyến nghị.

Một, ưu tiên chọn chiến lược truy hồi trước khi tối ưu lập chỉ mục. Hai, dùng inner product hoặc cosine, tránh L2. Ba, áp dụng reranking có chọn lọc với mô hình nhẹ như MiniLM khi cần độ chính xác cao. Bốn, chọn index theo yêu cầu latency và bộ nhớ, đừng kỳ vọng nó tăng chất lượng. Năm, coi kích thước chunk là tham số đánh đổi giữa độ chính xác với chi phí và độ trễ, không có giá trị tối ưu tuyệt đối.

## Slide 18 - 4.2 Đánh giá của tác giả (khoảng 1,5 phút)

Chính các tác giả nêu bốn hạn chế. Thứ nhất, chỉ dùng một bộ dữ liệu tiếng Anh, miền tổng quát là SQuAD, nên kết quả có thể không đúng với dữ liệu đa ngôn ngữ hoặc chuyên biệt. Thứ hai, một số tham số bị cố định, thay đổi chúng có thể cho kết quả khác. Thứ ba, chỉ dùng generator gpt-4o-mini, trong khi mô hình mạnh hơn có thể sinh văn bản tốt hơn. Thứ tư, chỉ dùng một mô hình embedding là text-embedding-3-large. Nếu đổi sang họ embedding khác, như mã nguồn mở hoặc đa ngôn ngữ, thứ bậc ảnh hưởng của retriever hay độ đo tương đồng có thể thay đổi.

## Slide 19 - 4.3 Đánh giá của nhóm (khoảng 2 phút)

Về điểm đáng học hỏi, trước hết là cách kết hợp ba công cụ thống kê bổ trợ nhau trên cùng một thiết kế thực nghiệm có kiểm soát. Việc nhấn mạnh kích thước hiệu ứng thay vì chỉ dựa vào p-value cũng đáng tham khảo, vì với cỡ mẫu lớn p-value rất dễ nhỏ mà ảnh hưởng thực tế lại không lớn. Về ứng dụng, kết quả giúp người thiết kế ưu tiên nguồn lực. Ví dụ khi hạn chế thời gian và chi phí, ta tập trung vào chiến lược truy hồi và độ đo tương đồng, bỏ qua việc tối ưu index.

Về hạn chế, bài báo không mô tả rõ cơ chế chấm Correctness, Faithfulness và Relevance. Đây là các độ đo chủ quan, thường do mô hình ngôn ngữ hoặc con người chấm, nên khó tái lập. Ngoài ra, chính tác giả ghi nhận các thành phần không độc lập hoàn toàn, nên thứ bậc ảnh hưởng chỉ là mức trung bình trên toàn bộ tổ hợp cấu hình. Vì vậy khi triển khai thực tế, cần thực nghiệm lại trên dữ liệu và truy vấn của chính hệ thống.

## Slide 20 - Tài liệu tham khảo (khoảng 0,5 phút)

Đây là danh sách tài liệu tham khảo, trong đó tài liệu [1] là bài báo chính. Phần trình bày của nhóm đến đây là hết. Em xin cảm ơn cô và các bạn đã lắng nghe, nhóm sẵn sàng trả lời câu hỏi.

---

## Phụ lục - Câu hỏi có thể gặp

**Vì sao tác giả chọn generator nhẹ?** Để cô lập ảnh hưởng của truy hồi và tái xếp hạng. Chất lượng sinh văn bản tốt hơn có thể làm tăng điểm tuyệt đối, nhưng theo bài báo sẽ không đổi ý nghĩa thống kê hay kích thước hiệu ứng của các thành phần phía trước.

**Tại sao index gần như không ảnh hưởng chất lượng?** HNSW, IVF và ScaNN đều là thuật toán tìm láng giềng gần đúng. Chúng chỉ khác nhau ở tốc độ và bộ nhớ khi tìm vector, nên chất lượng truy hồi gần như giống nhau. Chênh lệch nằm ở độ trễ.

**Vì sao cần eta bình phương khi đã có p-value?** p-value chỉ cho biết khác biệt có thật hay không và bị kéo xuống rất nhỏ khi cỡ mẫu lớn. η² cho biết khác biệt đó lớn đến đâu trong thực tế.

**HyDE khác HyPE ở điểm nào?** HyDE sinh một tài liệu giả định, HyPE sinh một đoạn giả định đại diện cho câu trả lời lý tưởng. Cả hai embed văn bản giả định đó để làm truy vấn.

**Kết quả có áp dụng cho tiếng Việt không?** Chưa chắc. Tác giả tự nhận chỉ thử trên dữ liệu tiếng Anh miền tổng quát và một mô hình embedding duy nhất, nên cần thực nghiệm lại.
