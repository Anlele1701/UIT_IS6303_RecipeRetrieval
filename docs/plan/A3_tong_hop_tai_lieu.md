# A3 – Tổng hợp tài liệu tham khảo

**Môn:** IS6303 – Thiết kế HTTT thông minh dựa trên truy hồi (UIT)
**Đồ án:** A3, phát triển tiếp A1 (Recipe Retrieval) thành trợ lý RAG hội thoại hiểu ràng buộc của người dùng
**Phạm vi:** 21 file PDF trong `A3/ref/` (20 bài khác nhau), slide môn học (Chương 0, Chương 2) và các nguồn bổ sung cho những chỗ bộ ref còn thiếu
**Ngày lập:** 11/10/2026

> **Cách đọc file này.** Phần 1 là bảng tra nhanh. Phần 2 tóm tắt từng bài, ghi rõ điểm nào dùng được cho A3. Phần 3 tổng hợp chéo theo từng chủ đề của báo cáo. Phần 4 liệt kê các khoảng trống và nguồn bổ sung. Phần 5 là danh mục tham khảo theo chuẩn IEEE, giữ nguyên mã [Rxx]/[Sxx] để dán vào báo cáo.
>
> **Mức tin cậy:**
> - ★★★: tạp chí Q1, hoặc hội nghị hàng đầu (CORE A*/A) có phản biện.
> - ★★: có phản biện nhưng là mega-journal, hội nghị nhỏ, hoặc bài không đúng trọng tâm.
> - ★: preprint chưa qua phản biện. Chỉ dùng làm nguồn phụ, không dùng làm luận cứ chính.
>
> Quartile của các tạp chí lấy từ file `RAG_SLR_danh_sach_RAG_tap_trung.xlsx` của nhóm (SJR 2025). Những ô ghi "cần kiểm" là chưa xác minh trên scimagojr.com.

---

## 1. Bảng tra nhanh

| Mã | Bài (rút gọn) | Tác giả, năm | Nơi đăng | Loại | Tin cậy | Dùng cho chương |
|---|---|---|---|---|---|---|
| R01 | RAG for LLMs: Evolution, Architectures, Applications, and Challenges (2020–2025) | Faridi et al., 2026 | WIREs Data Mining & Knowledge Discovery 16:e70122 | SLR (PRISMA, 91 bài) | ★★★ Q1 | 1, 2, 4, 5 |
| R02 | Modular RAG: LEGO-like Reconfigurable Frameworks | Gao et al., 2026 | ACM TOIS 44(7), Art. 164 | Khung lý thuyết + thực nghiệm | ★★★ Q1 | 2, 3, 4 |
| R03 | A Survey on Knowledge-Oriented RAG | Cheng et al., 2025/26 | ACM TOIS (doi 10.1145/3833415) | Survey | ★★★ Q1 | 2 |
| R04 | A Survey of Personalization: From RAG to Agent | Li et al., 2026 | ACM TOIS 44(4), Art. 93 | Survey | ★★★ Q1 | 2, 3 |
| R05 | RAG for Natural Language Processing: A Survey | Wu et al., 2026 | Artificial Intelligence Review 59:192 | Survey | ★★★ Q1 | 2, 4 |
| R05b | (bản preprint của R05) | Wu et al., 2025 | Research Square | Preprint | trùng, **không trích** | – |
| R06 | RAG for AI-Generated Content: A Survey | Zhao et al., 2026 | Data Science and Engineering 11:1–29 | Survey | ★★★ (Q cần kiểm) | 2 |
| R07 | A Survey on RAG Meeting LLMs | Fan et al., 2024 | KDD '24, pp. 6491–6501 | Survey (hội nghị) | ★★★ (CORE A*) | 2 |
| R08 | Retrieval-Augmented Generation (RAG) – Catchword | Klesel & Wittmann, 2025 | Business & Information Systems Engineering 67(4):551–561 | Bài khái niệm (góc HTTT) | ★★★ Q1 | 1, 2 |
| R09 | Enhancing RAG: A Study of Best Practices | Li et al., 2025 | COLING 2025, pp. 6705–6717 | Thực nghiệm ablation | ★★★ (hội nghị ACL) | 2, 4 |
| R10 | A Comparative Evaluation of RAG Architectures for Cross-Domain LLM Applications | Ersoy & Erşahin, 2025 | IEEE Access 13 | Thực nghiệm | ★★ (Q1, mega-journal) | 2, 4 |
| R11 | LLMOps in Action: Designing, Deploying, and Governing Advanced Chatbots | Raghavan et al., 2026 | IEEE TKDE 38(7):4491–4510 | SLR (39 bài) | ★★★ Q1 | 1, 3, 5 |
| R12 | Exploring the Role of RAG in Cloud-Based Monolithic Chatbots | Billah & Yusof, 2025 | IEEE SCOReD 2025 (hội nghị sinh viên) | SLR (17 bài) | ★★ | 3 (phụ) |
| R13 | RAGO: Systematic Performance Optimization for RAG Serving | Jiang et al., 2025 | ISCA '25, pp. 974–989 | Hệ thống | ★★★ (hội nghị hàng đầu) | 3, 5 |
| R14 | RAGCache: Efficient Knowledge Caching for RAG | Jin et al., 2025 | ACM TOCS 44(1), Art. 2 | Hệ thống | ★★★ (Q cần kiểm) | 3, 5 |
| R15 | RAGPerf: End-to-End Benchmarking Framework for RAG | Li et al., 2026 | arXiv:2603.10765 | Hệ thống | ★ | 4 (phụ) |
| R16 | Engineering the RAG Stack: Architecture and Trust Frameworks | Wampler et al., 2025 | arXiv:2601.05264 | Review | ★ | 2 (phụ) |
| R17 | A Systematic Review of Key RAG Systems | Oche et al., 2025 | arXiv:2507.18910 | Review | ★ | 2 (phụ) |
| R18 | Deployment and Communication Patterns in Microservice Architectures: SLR | Aksakalli et al., 2021 | J. Systems & Software 180:111014 | SLR (38 bài) | ★★★ Q1, ngoài RAG | 3 |
| R19 | Assessment of Performance and Scalability in Microservice Architectures: SLR | Rodrigues et al., 2025 | J. Systems & Software 230:112500 | SLR (29 bài) | ★★★ Q1, ngoài RAG | 3, 4 (phụ) |
| R20 | Sometimes You Need to See Through Walls: A Field Study of APIs | de Souza et al., 2004 | CSCW '04 | Nghiên cứu thực địa | ★★ (cũ, ngoài RAG) | 3 (phụ) |

**Nhận xét về chất lượng bộ ref (cần biết trước khi trích dẫn):**

1. **Bài trùng.** `v1_covered_80b9…pdf` là bản preprint của R05, nên chỉ trích bản Artificial Intelligence Review (R05).
2. **Preprint.** R15, R16, R17 chưa qua phản biện. Ý nào lấy từ ba bài này mà quan trọng thì nên tìm nguồn đã xuất bản để thay. Riêng R06 trong file Excel đang ghi là "arXiv 2402.19473", nhưng PDF trong `ref/` là bản đã đăng trên *Data Science and Engineering* 2026, nên cần **cập nhật lại file Excel**.
3. **Lệch trọng tâm.** R18, R19, R20 nói về microservice/API, không về RAG. Chỉ nên dùng ở mục kiến trúc và API (chương 3), mỗi bài 1–2 câu. R12 là hội nghị sinh viên, nên dùng như ví dụ minh họa chứ không làm luận cứ.
4. **Thiếu bài gốc.** Bộ ref toàn survey và bài hệ thống, chưa có bài gốc cho các kỹ thuật A3 dùng trực tiếp: BM25, DPR, RRF, cross-encoder, RAGAS, viết lại truy vấn hội thoại, phủ định trong dense retrieval, gợi ý món ăn và dị ứng. Phần 4 bổ sung các nguồn này.
5. **Cảnh báo về R10.** Bài trên IEEE Access có văn phong không đều và bảng số không trích xuất được từ PDF. Chỉ nên dùng **thiết kế thí nghiệm** của bài (25% câu không trả lời được, Cohen's κ, bootstrap CI, Wilcoxon + Holm), không trích con số cụ thể nào.

---

## 2. Tóm tắt từng tài liệu

### Nhóm A – Khung lý thuyết và survey về RAG

**R02 – Modular RAG (Gao et al., TOIS 2026)** ★★★
- **Nội dung:** RAG được chia thành ba tầng trừu tượng: module (L1), sub-module (L2) và operator (L3). Có 8 module L1: Indexing, Pre-retrieval, Retrieval, Post-retrieval, Pre-Generation, Generation, Post-Generation và Orchestration. Naive RAG là trường hợp riêng của Advanced RAG, và Advanced RAG là trường hợp riêng của Modular RAG. Bài định nghĩa bốn mẫu luồng: linear, conditional, branching và loop.
- **Kết quả thực nghiệm (Qwen3-8B, RAGAS):** linear là baseline nên dùng mặc định vì tiết kiệm token và có độ trễ thấp nhất. Loop (Self-RAG) chỉ có lợi với mô hình lớn. Mô hình nhỏ tự đánh giá kém, nên lặp nhiều vòng tốn chi phí mà không cải thiện tương xứng. Conditional dễ dính lỗi định tuyến, nên chỉ dùng khi chất lượng router đã được kiểm chứng.
- **Dùng cho A3:**
  - Làm **khung đặt tên module** cho kiến trúc đề xuất.
  - Là luận cứ để **chọn luồng linear có thêm một nhánh conditional** (router theo ý định), thay vì agentic hay loop, vì A3 chạy LLM 7B cục bộ.
  - Là cơ sở để **phải báo cáo độ chính xác của router**.
  - Mục 4.2.3 *Query Construction* (chuyển truy vấn thành SQL hoặc metadata filter) là nền lý thuyết trực tiếp cho bước "trích ràng buộc → WHERE".
  - Mục 4.7.1 *Verification* là nền cho bước kiểm tra sau sinh.

**R01 – Faridi et al., WIREs DMKD 2026** ★★★
- **Nội dung:** SLR theo PRISMA trên 91 nghiên cứu giai đoạn 2020–2025. Bài so sánh sparse với dense ("bổ trợ nhau, không loại trừ"), retrieval với long-context, và pipeline cố định với agentic. Bài đề xuất giao thức đánh giá tối thiểu gồm 5 phần:
  1. Chỉ số IR: Recall@k, MRR, nDCG.
  2. Chất lượng câu trả lời.
  3. Faithfulness và attribution (citation precision/recall có kiểm tra entailment).
  4. Calibration và khả năng từ chối trả lời (abstention).
  5. Một quy trình đánh giá bởi người.
- Bài đề xuất **RAG Card**, liệt kê các thông tin bắt buộc công bố: snapshot ngày của corpus, giấy phép, thuật toán chunking, checkpoint retriever/reranker, k, prompt, chính sách decoding, giới hạn độ trễ.
- Box 1 giải thích vì sao đánh giá RAG dễ sai lệch: thành phần bị trộn lẫn khi đo end-to-end, nhiều "bậc tự do ẩn" (chunk size, rule lọc metadata, ngưỡng rerank, k), LLM-judge thiên vị câu trả lời trôi chảy, và attribution có thể lệch với correctness.
- Mục 8.4 về RAG đa ngôn ngữ: chiến lược *translate-then-retrieve* hiệu quả khi bằng chứng nằm ở ngôn ngữ giàu tài nguyên, nhưng yếu với thuật ngữ đặc thù văn hóa.
- **Dùng cho A3:**
  - Khung **giao thức đánh giá** ở chương 4.
  - Mẫu **RAG Card** đặt ở phụ lục, đồng thời là câu trả lời cho nhận xét "xử lý dữ liệu chưa rõ ràng" của GV.
  - Luận cứ cho thiết kế **truy vấn Việt → chuẩn hóa sang tiếng Anh**.

**R08 – Klesel & Wittmann, BISE 2025** ★★★
- **Nội dung:** Bài giới thiệu RAG từ góc nhìn hệ thống thông tin.
  - Phân biệt bộ nhớ tham số (LLM) với bộ nhớ phi tham số (CSDL ngoài).
  - Mô tả pipeline vanilla gồm Retrieval → Augmentation (template) → Generation.
  - Đưa ra khái niệm *grounding* (kèm tham chiếu), *misgrounded* và *knowledge-domain guardrails*.
  - Đặt tên **"blinkered chunk effect"**: một chunk bị tách khỏi tài liệu gốc thì mất ngữ cảnh.
  - Chỉ ra thách thức về quản trị dữ liệu và MLOps.
  - Có nhắc ví dụ trợ lý hội thoại về **công thức nấu ăn** (Jaber et al., CHI 2024).
- **Dùng cho A3:** Phần đặt vấn đề ở chương 1 (vì sao từ search chuyển sang hội thoại). Định nghĩa *grounding* và guardrail ở chương 2. Blinkered chunk effect giải thích lỗi E5 của A1 và là lý do A3 **gom chunk về cấp công thức** (parent) trước khi đưa vào LLM.

**R05 – Wu et al., AI Review 2026** ★★★
- **Nội dung:** Survey tập trung vào retriever và cách hợp nhất kết quả truy hồi vào mô hình (retrieval fusion), chia thành 4 loại: query-based, logits-based, latent, parametric. Chỉ fusion kiểu query-based (ghép text vào prompt) và logits-based mới dùng được với LLM hộp đen. Bài phân loại metric đánh giá RAG theo 4 nhóm: chất lượng truy hồi, chất lượng sinh (faithfulness ≠ correctness), độ bền end-to-end (noise robustness, negative rejection…) và hiệu năng hệ thống. Có mục riêng về hệ hội thoại, với các lỗi điển hình: bộ nhớ hội thoại lỗi thời gây mâu thuẫn giữa các lượt, và ý định người dùng thay đổi giữa chừng.
- **Dùng cho A3:** Giải thích vì sao A3 chọn fusion **query-based** (prompt có ngữ cảnh). Đây là lựa chọn duy nhất khả thi với Ollama và không cần fine-tune. Dùng bảng phân loại metric khi viết chương 4. Hai lỗi hội thoại trên là động lực cho module quản lý trạng thái ràng buộc qua các lượt.

**R06 – Zhao et al., DSE 2026** ★★★
- **Nội dung:** Phân loại các kỹ thuật cải tiến RAG theo 5 đối tượng: input (query transformation, data augmentation), retriever (chunk optimization, hybrid, rerank, **metadata filtering**), generator (prompt engineering, decoding tuning), result (output rewrite) và pipeline (adaptive retrieval).
- **Dùng cho A3:** Bản đồ để định vị từng cải tiến của A3 nằm ở tầng nào (bảng "cải tiến ↔ taxonomy" ở chương 3).

**R07 – Fan et al., KDD 2024** ★★★
- **Nội dung:** RA-LLM gồm ba trục: retrieval (loại retriever, độ hạt truy hồi), generation (mô hình hộp trắng hay hộp đen) và augmentation (tích hợp ở tầng input, output hay intermediate). Bài có nêu ứng dụng chatbot và hệ gợi ý.
- **Dùng cho A3:** Định nghĩa nền ở chương 2. Phân biệt *retrieval granularity*: A1 truy hồi theo chunk còn A3 trả lời theo công thức.

**R03 – Cheng et al., TOIS** ★★★
- **Nội dung:** Survey RAG hướng tri thức, gồm query decomposition và rewriting (RRR, HyDE, Step-Back, BEQUE cho truy vấn đuôi dài trong e-commerce), cấu trúc chỉ mục (structured, unstructured, hybrid index), chiến lược sinh trích dẫn (sinh đồng thời so với hậu kiểm) và độ hạt trích dẫn.
- **Dùng cho A3:** Mục *query rewriting* và *citation* ở chương 2. Khái niệm **hybrid index** (chỉ mục có cấu trúc cộng chỉ mục vector) mô tả đúng ParadeDB: BM25, vector và cột metadata nằm trong cùng một index.

**R04 – Li et al., TOIS 2026 (Personalization)** ★★★
- **Nội dung:** Cá nhân hóa diễn ra ở ba giai đoạn: pre-retrieval, retrieval và generation, rồi mở rộng sang agent. Pre-retrieval được hình thức hóa là q* = Q(q, p), trong đó p là thông tin cá nhân. Rewriting dùng để sửa và làm rõ ý định, còn expansion dùng để mở rộng phạm vi. Bài có mục riêng về hiểu hồ sơ người dùng (user-profile understanding).
- **Dùng cho A3:** Mô hình hóa **ràng buộc bền vững của phiên** ("tôi dị ứng đậu phộng" phải có hiệu lực ở mọi lượt sau). Ràng buộc chính là p trong q* = Q(q, p). Luận cứ để chọn rewriting (không chọn expansion) cho câu hỏi hội thoại.

**R16 – Wampler et al. (arXiv)** ★ / **R17 – Oche et al. (arXiv)** ★
- R16 phân loại RAG theo chiến lược truy hồi, phương thức (modality) của nguồn, mức thích ứng của pipeline và cách điều phối, có thêm phần về độ tin cậy và bảo mật.
- R17 tổng quan lịch sử RAG, metric, các thách thức (chọn k, độ trễ, hallucination) và nhắc đến benchmark đa lượt MTRAG.
- **Dùng cho A3:** Chỉ dùng làm nguồn phụ. MTRAG nên trích bài gốc (TACL 2025, [S21]) thay vì trích qua R17.

### Nhóm B – Thực nghiệm so sánh cấu hình RAG

**R09 – Li et al., COLING 2025** ★★★
- **Nội dung:** 74 lần chạy ablation trả lời 9 câu hỏi nghiên cứu: kích thước LLM, prompt, chunk size, kích thước kho, retrieval stride, query expansion, Contrastive ICL, kho đa ngôn ngữ và "Focus Mode" (chỉ lấy câu liên quan). Kết luận:
  - Contrastive ICL và Focus Mode cho kết quả tốt nhất.
  - **Kích thước kho không quyết định, chất lượng và độ liên quan của tài liệu mới quan trọng.**
  - Prompt vẫn rất quan trọng.
  - Kho đa ngôn ngữ không cải thiện kết quả.
- **Dùng cho A3:** Đây là **mẫu viết thí nghiệm ablation** (mỗi câu hỏi nghiên cứu ứng với một nhóm cấu hình). Kết luận "kho đa ngôn ngữ không giúp" là luận cứ cho việc **giữ corpus tiếng Anh và chuẩn hóa truy vấn tiếng Việt**, thay vì dịch corpus. Kết luận về Focus Mode ủng hộ việc chỉ đưa các trường cần thiết của công thức vào ngữ cảnh.

**R10 – Ersoy & Erşahin, IEEE Access 2025** ★★
- **Nội dung:** So sánh bốn kiểu truy hồi (sparse, dense, hybrid, fusion) với baseline zero-shot, chấm bằng RAGAS (faithfulness, answer relevancy, context precision, context recall), cộng thêm độ trễ và khả năng kiểm toán. Hybrid cân bằng precision và recall tốt nhất, còn fusion có faithfulness cao nhất nhưng chậm hơn. Bộ test 500 câu, trong đó **75% trả lời được và 25% cố ý không trả lời được**. Có hai người gán nhãn với Cohen's κ, báo cáo bootstrap 95% CI và kiểm định Wilcoxon cặp đôi với hiệu chỉnh Holm.
- **Dùng cho A3:** Mẫu **thiết kế bộ test có câu không trả lời được**, dùng để đo negative rejection. Ví dụ với A3: yêu cầu món mà không công thức nào trong kho thỏa mãn mọi ràng buộc. Bài cũng là mẫu báo cáo thống kê.

### Nhóm C – Kiến trúc hệ thống, chatbot, vận hành

**R11 – Raghavan et al., IEEE TKDE 2026** ★★★
- **Nội dung:** SLR 39 bài về chatbot LLM, đánh giá chất lượng bài theo hướng dẫn của Kitchenham. Hai kiến trúc phổ biến là client-server và RAG. Metric được chia làm 5 nhóm: accuracy, mức hài lòng của người dùng, chất lượng nội dung, an toàn và đạo đức, hiệu năng. Bài đề xuất **kiến trúc tham chiếu 4 lớp**:
  - Frontend.
  - Backend: preprocessing, core LLM, customization, agents, middleware.
  - Data Infrastructure.
  - Governance: giảm thiên lệch, giám sát.

  Thêm một khối External Information Retrieval.
- **Dùng cho A3:** Khung **kiến trúc tổng thể ở chương 3** (map các thành phần A3 vào 4 lớp này) và danh sách nhóm metric ở chương 4. Lớp Governance là chỗ đặt phần đạo đức/an toàn (chuẩn đầu ra G3.2).

**R12 – Billah & Yusof, SCOReD 2025** ★★
- **Nội dung:** SLR 17 bài. Đề xuất kiến trúc 3 lớp cho chatbot RAG dạng monolithic: Infrastructure (vector DB, orchestration), Retrieval-Generation, Application. Có thêm lưu đồ quyết định triển khai cloud, on-prem hay hybrid dựa trên yêu cầu riêng tư và tuân thủ.
- **Dùng cho A3:** Luận cứ phụ cho lựa chọn **triển khai monolithic, on-premise (Ollama cục bộ)** ở quy mô đồ án.

**R13 – RAGO (ISCA 2025)** ★★★ / **R14 – RAGCache (ACM TOCS 2025)** ★★★ / **R15 – RAGPerf (arXiv)** ★
- **RAGO:** Đưa ra trừu tượng **RAGSchema** để mô tả các biến thể RAG, và cho thấy đặc tính tải khác nhau rất nhiều giữa các biến thể. So với hệ dựng trên phần mở rộng của LLM system, RAGO tăng QPS/chip tới 2× và giảm TTFT 55%.
- **RAGCache:** Cache trạng thái trung gian của tri thức đã truy hồi, và chạy truy hồi gối đầu với sinh. So với vLLM + Faiss, TTFT giảm tới 4× và throughput tăng tới 2,1×.
- **RAGPerf:** Tách pipeline thành 5 module thay thế được (embedding, indexing, retrieval, reranking, generation) và đo cả hiệu năng lẫn chất lượng.
- **Dùng cho A3:** Luận cứ để **đo độ trễ theo từng bước** (trích ràng buộc, truy hồi, rerank, sinh), báo cáo TTFT, và dùng streaming. Ở mức đồ án chỉ cần trích ý, không cần tái hiện các tối ưu này.

**R18 – Aksakalli et al., JSS 2021** / **R19 – Rodrigues et al., JSS 2025** / **R20 – de Souza et al., CSCW 2004**
- **R18:** Tìm ra 3 cách triển khai microservice (serverless, mỗi service một VM, mỗi service một container) và 7 mẫu giao tiếp. Publish/subscribe phổ biến nhất, còn mỗi service một container là cách triển khai được ưa chuộng nhất.
- **R19:** Phần lớn nghiên cứu chỉ đánh giá cách triển khai và mở rộng, còn thiếu so sánh giữa các mẫu kiến trúc.
- **R20:** API đóng vai trò "hợp đồng" giữa các bên và vạch ranh giới tổ chức.
- **Dùng cho A3:** Mỗi bài 1–2 câu ở mục thiết kế API và triển khai: Docker Compose theo kiểu mỗi service một container, giao tiếp đồng bộ request/response qua REST cộng SSE để streaming, và hợp đồng API được định nghĩa bằng OpenAPI/Pydantic.

### Nhóm D – Tài liệu môn học (đã đọc slide)

- **Chương 0 (giới thiệu môn):**
  - Cách chấm A3: đề tài baseline 5đ, hệ thống hoàn chỉnh có front-end, back-end và thiết kế CSDL phù hợp 2.5đ, nâng cấp bằng kỹ thuật engineer/research 2.5đ.
  - Chuẩn đầu ra: G2.2 (sơ đồ data pipeline online và offline, sơ đồ kiến trúc hai tầng), G2.3 (cung cấp qua API), G3.1 (ablation và error analysis), G3.2 (đạo đức AI khi vận hành).
  - Giáo trình môn học: Manning et al. 2008, Huyen 2025, Aggarwal 2016. Bài tham khảo: DPR, RAG, pgvector.
- **Chương 2 (RAG):**
  - Pre-filter metadata bằng `WHERE` trước khi so vector, kèm trích nguồn.
  - Prompt RAG có ràng buộc "chỉ dùng CONTEXT, được phép trả lời *không tìm thấy*, bắt buộc trích nguồn".
  - Metric RAGAS: context recall, context precision, faithfulness, answer relevance. Slide nhấn mạnh **"luôn kiểm Context Recall trước"**.
  - Các kiểm tra ngoài RAGAS: noise robustness, negative rejection, information integration, counterfactual robustness.
  - LLM-as-judge kèm **human check 30–50 câu**.
  - Parent-child chunking, kiến trúc hai tầng (recall → precision), hiện tượng lost-in-the-middle.
  - API: `POST /query` trả về answer, citations, usage và latency. Có `POST /feedback` và SSE.
  - Caching. Các rủi ro cần tránh: prompt injection, không có trích dẫn.

> Phần lớn cấu trúc của A3 khớp với slide Chương 2, nên báo cáo nên **trích slide như một nguồn của môn học** và dùng đúng thuật ngữ của GV.

---

## 3. Tổng hợp chéo theo chủ đề của A3

### 3.1. Từ tìm kiếm sang RAG: vì sao A1 chưa đủ
- Hệ tìm kiếm trả về danh sách đoạn văn. Nó không tổng hợp được nhiều nguồn, không diễn đạt thành câu trả lời và không hiểu câu hỏi tự nhiên nhiều ý (slide Ch.2). RAG bổ sung bước sinh có grounding [R08][S02].
- Các mô hình tiến hóa theo thứ tự Naive → Advanced → Modular RAG [R02][R01]. A1 tương ứng **Advanced Retrieval**: hybrid + rerank nhưng chưa có generation. A3 đi lên **Modular RAG** với pre-retrieval (hiểu truy vấn), post-retrieval (lọc và gom theo công thức), generation có trích dẫn và post-generation (kiểm tra).
- Ba hạn chế A1 mà GV nhận xét ứng với ba nhóm module A3:

| Hạn chế A1 (GV + error analysis của A1) | Module A3 xử lý | Nguồn lý thuyết |
|---|---|---|
| Không hiểu ngôn ngữ tự nhiên: phủ định, ràng buộc (lỗi E2 "mất chi tiết chính xác"), không nhận câu tiếng Việt | Pre-retrieval: trích ý định và ràng buộc thành filter có cấu trúc (query construction), rồi viết lại truy vấn | [R02 §4.2.3][R03][R04][S11][S12] |
| Chưa phải RAG (chỉ trả danh sách) | Generation có grounding, trích dẫn và "không tìm thấy" | [R08][R05][S02][slide Ch.2] |
| Xử lý dữ liệu chưa rõ ràng (loại truy vấn không hợp lệ mà không giải thích quy tắc) | Data card và RAG Card, quy tắc hợp lệ được đánh mã và đếm số lượng | [R01 Box 1][R10][S05] |

### 3.2. Hiểu truy vấn: rewriting, expansion, construction
- **Rewriting** sửa và làm rõ ý định, phù hợp với hội thoại nhiều lượt. **Expansion** giữ ý định và mở rộng từ vựng [R04]. Các kỹ thuật tiêu biểu là RRR, HyDE, Step-Back [R02][R03] và Rewrite-Retrieve-Read [S11].
- **Query construction** chuyển truy vấn thành SQL hoặc metadata filter để truy cập dữ liệu có cấu trúc [R02 §4.2.3]. Metadata filtering được xếp vào nhóm "retriever enhancement" [R06].
- **Phủ định là điểm yếu đã biết của truy hồi neural** [S12], khớp với lỗi E2 của A1. Vì vậy A3 **không trông vào embedding để hiểu chữ "không"**, mà tách ràng buộc phủ định thành điều kiện loại trừ cứng trong SQL.
- Hội thoại: ràng buộc phải giữ qua các lượt [R04 q* = Q(q,p)]. Lỗi điển hình là trạng thái cũ hoặc ý định thay đổi [R05 §6.7]. Benchmark tham chiếu: MTRAG [S21]. Khung lý thuyết: Conversational Information Seeking [S13].

### 3.3. Truy hồi lai, lọc và xếp hạng lại
- Sparse và dense **bổ trợ nhau** [R01 §3.6.1][R10]. Có thể hợp nhất bằng RRF [S06]. Bruch et al. [S07] phân tích các hàm fusion (RRF so với tổ hợp lồi) và cho thấy kết quả nhạy với tham số, khớp với ablation `rrf_k` của A1.
- **Pre-filter hay post-filter.** Lọc trước khi xếp hạng (pre-filter) bảo đảm top-k không chứa món vi phạm, nhưng có thể làm tụt recall của chỉ mục ANN khi điều kiện lọc quá chặt [S08]. ParadeDB của A1 áp filter ngay trong index (ADR-0001), nên đã có sẵn nền để làm pre-filter.
- Rerank bằng cross-encoder giúp tăng precision ở tầng 2 [S09][slide Ch.2]. A1 đã chứng minh mxbai-rerank-base-v1 tốt hơn bge-reranker-base về MRR (+10 đến +12 điểm, có ý nghĩa thống kê).

### 3.4. Sinh câu trả lời có grounding
- Dùng fusion kiểu query-based vì LLM chạy qua Ollama được coi là hộp đen [R05].
- Prompt: chỉ dùng CONTEXT, cho phép "không tìm thấy", bắt buộc trích dẫn, temperature thấp (0–0,3) (slide Ch.2).
- Trích dẫn ở cấp công thức (ID và tiêu đề). Dùng cách sinh trích dẫn đồng thời với câu trả lời để giảm lệch giữa câu trả lời và nguồn [R03 §6.8].
- **Lost in the middle** [S14]: đặt công thức xếp hạng cao nhất ở đầu ngữ cảnh và giới hạn k. **Focus mode** [R09]: chỉ đưa vào các trường cần thiết.
- Hậu kiểm (verification) [R02 §4.7.1]: kiểm tra tất định rằng các ID được trích có nằm trong ngữ cảnh và không vi phạm ràng buộc.

### 3.5. Đánh giá
- **Truy hồi:** Recall@k, MRR, nDCG@k [S10][R01]. **Sinh:** faithfulness, answer relevance, context precision và context recall [S15][R10]. **Độ bền:** negative rejection, noise robustness [S16][R05][slide Ch.2]. **Hệ thống:** độ trễ từng bước, TTFT [R13][R14].
- **LLM-as-judge** có thiên lệch: ưa câu trả lời trôi chảy, và ưu ái mô hình cùng họ [R01 Box 1][S17]. Vì vậy cần **judge khác họ với mô hình sinh**, cộng **human check 30–50 mẫu** và báo cáo mức đồng thuận (κ) [R10][slide Ch.2].
- **Thống kê:** kiểm định cặp đôi, hiệu chỉnh Holm, bootstrap CI [R10][S18]. A1 đã làm phần này, nên giữ nguyên quy trình cho nhất quán.
- **Ablation:** mỗi lần bỏ đúng một thành phần so với hệ đầy đủ, trên cùng bộ truy vấn và trong cùng một run [R09][R02 §6.5 node-level ROI].

### 3.6. Kiến trúc và vận hành
- Kiến trúc tham chiếu 4 lớp: Frontend, Backend, Data Infrastructure, Governance [R11]. Triển khai monolithic on-prem ở quy mô đồ án [R12]. Mỗi service một container [R18].
- API là hợp đồng [R20]. Dùng REST + SSE và các endpoint `/chat`, `/feedback`, `/health` (slide Ch.2).
- Theo dõi độ trễ từng bước, có cache embedding và cache ngữ nghĩa (slide Ch.2) [R14].

### 3.7. An toàn và đạo đức (G3.2)
- Thông tin dị ứng ảnh hưởng trực tiếp đến sức khỏe, nên hệ **không được bảo đảm "an toàn tuyệt đối"**. Phải nêu giới hạn: gắn thẻ dị ứng từ nguyên liệu có thể sót, và không biết về nhiễm chéo trong chế biến. Danh mục dị ứng lấy theo quy định chính thức [S22][S23].
- Lớp Governance gồm giám sát, log và phản hồi người dùng [R11]. Coi nội dung truy hồi là dữ liệu chứ không phải lệnh, để chống prompt injection (slide Ch.2) [R01 §8.6].

---

## 4. Khoảng trống của bộ ref và nguồn bổ sung đề xuất

Quy tắc chọn: giáo trình; tạp chí có quartile SJR; hội nghị hàng đầu (ACL/EMNLP/NAACL/EACL, SIGIR, NeurIPS, KDD, SIGMOD, AAAI) cho các bài gốc mà trong lĩnh vực IR/NLP vốn được công bố ở hội nghị. **Không** dùng tạp chí ngoài Scopus/SCImago và MDPI (theo quyết định trước đó của nhóm). Venue và DOI của các bài dưới đây đã kiểm qua ACL Anthology, OpenAlex hoặc trang nhà xuất bản, trừ ô ghi "cần kiểm".

| Mã | Nguồn | Venue | Loại | Lấp khoảng trống nào |
|---|---|---|---|---|
| S01 | Manning, Raghavan, Schütze – *Introduction to Information Retrieval* | Cambridge Univ. Press, 2008 | Giáo trình môn | BM25/tf-idf, đánh giá IR, inverted index |
| S02 | Lewis et al. – Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks | NeurIPS 2020 | Bài gốc RAG | Định nghĩa RAG |
| S03 | Karpukhin et al. – Dense Passage Retrieval | EMNLP 2020 | Bài gốc DPR | Dense retrieval (bi-encoder) |
| S04 | Robertson & Zaragoza – The Probabilistic Relevance Framework: BM25 and Beyond | Found. Trends Inf. Retr. 3(4), 2009 | Chuyên khảo | Công thức BM25 |
| S05 | Huyen – *AI Engineering* | O'Reilly, 2025 | Giáo trình môn | Đánh giá LLM app, kiến trúc, guardrail |
| S06 | Cormack, Clarke, Büttcher – Reciprocal Rank Fusion | SIGIR 2009 | Bài gốc RRF | Công thức RRF |
| S07 | Bruch, Gai, Ingber – An Analysis of Fusion Functions for Hybrid Retrieval | ACM TOIS 42(1), 2023 | Tạp chí Q1 | RRF và tổ hợp lồi, độ nhạy tham số |
| S08 | Patel et al. – ACORN: Predicate-Agnostic Search over Vector Embeddings and Structured Data | SIGMOD 2024 (Proc. ACM Manag. Data) | Hội nghị hàng đầu | Lọc theo thuộc tính khi tìm vector (pre-filter hay post-filter) |
| S09 | Lin, Nogueira, Yates – *Pretrained Transformers for Text Ranking: BERT and Beyond* | Springer (Synthesis Lectures on HLT), 2021 | Sách chuyên khảo | Cross-encoder rerank, kiến trúc nhiều tầng |
| S10 | Järvelin & Kekäläinen – Cumulated Gain-Based Evaluation of IR Techniques | ACM TOIS 20(4), 2002 | Tạp chí Q1 | nDCG |
| S11 | Ma et al. – Query Rewriting for Retrieval-Augmented LLMs | EMNLP 2023 | Hội nghị | Rewrite-Retrieve-Read |
| S12 | Weller et al. – NevIR: Negation in Neural Information Retrieval | EACL 2024 | Hội nghị | **Phủ định trong truy hồi neural**, giải thích lỗi E2 của A1 |
| S13 | Zamani, Trippas, Dalton, Radlinski – *Conversational Information Seeking* | Found. Trends Inf. Retr. 17(3–4), 2023 | Chuyên khảo | Nền lý thuyết hội thoại tìm kiếm |
| S14 | Liu et al. – Lost in the Middle | TACL 12, 2024 | Tạp chí (ACL) | Vị trí ngữ cảnh trong prompt |
| S15 | Es et al. – RAGAS: Automated Evaluation of RAG | EACL 2024 (Demo) | Hội nghị | Faithfulness, answer relevance, context precision/recall |
| S16 | Chen et al. – Benchmarking LLMs in RAG (RGB) | AAAI 2024 | Hội nghị | Noise robustness, negative rejection |
| S17 | Zheng et al. – Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena | NeurIPS 2023 (D&B) | Hội nghị | Thiên lệch của LLM-judge |
| S18 | Smucker, Allan, Carterette – A Comparison of Statistical Significance Tests for IR Evaluation | CIKM 2007 | Hội nghị | Kiểm định thống kê trong IR |
| S19 | Min, Jiang, Jain – Food Recommendation: Framework, Existing Solutions, and Challenges | IEEE Trans. Multimedia 22(10):2659–2671, 2020 | Tạp chí Q1 | **Bối cảnh miền ẩm thực**, ràng buộc sức khỏe |
| S20 | Mohbat & Zaki – KERL: Knowledge-Enhanced Personalized Recipe Recommendation using LLMs | ACL 2025 (Long), pp. 19125–19141 | Hội nghị | **Công trình gần nhất**: trích thực thể từ câu hỏi, lấy ràng buộc từ KG cho LLM chọn công thức, có benchmark câu hỏi kèm ràng buộc |
| S21 | Katsis et al. – MTRAG: A Multi-Turn Conversational Benchmark for Evaluating RAG Systems | TACL 2025 | Tạp chí (ACL) | Đánh giá RAG nhiều lượt |
| S22 | Regulation (EU) No 1169/2011, Annex II | Official Journal of the EU, 2011 | Văn bản pháp lý | Danh mục 14 nhóm chất gây dị ứng |
| S23 | U.S. FDA – Food Allergies: What You Need to Know (FALCPA 2004 + FASTER Act 2021) | FDA | Văn bản chính thức | 9 nhóm dị ứng chính ở Mỹ (bộ dữ liệu là công thức Mỹ) |
| S24 | Dooley et al. – FoodOn: A Harmonized Food Ontology | npj Science of Food 2:23, 2018 | Tạp chí | Chuẩn hóa tên nguyên liệu và từ đồng nghĩa |
| S25 | Chen et al. – M3-Embedding (BGE-M3) | Findings of ACL 2024 | Hội nghị | Embedding đa ngôn ngữ, dùng cho nhánh ablation "không dịch" |
| S26 | Ji et al. – Survey of Hallucination in Natural Language Generation | ACM Computing Surveys 55(12), 2023 | Tạp chí Q1 | Định nghĩa hallucination |
| S27 | Aggarwal – *Recommender Systems: The Textbook* | Springer, 2016 | Giáo trình môn | Ràng buộc và knowledge-based recommendation, nếu nhóm muốn định vị A3 gần hệ gợi ý |

**Chưa tìm được nguồn đủ chuẩn (đã loại):** các bài "allergen-aware recipe recommendation with LLM" tìm thấy đều là preprint arXiv, luận văn hoặc báo cáo môn học. KERL [S20] là bài có phản biện gần nhất. Bản survey hội thoại tìm kiếm của Mo et al. (arXiv 2410.15576) chưa thấy bản đã xuất bản, nên dùng S13 thay.

> **Đề xuất cho nhóm:**
> 1. Tải PDF của S02, S06, S07, S12, S15, S19, S20 vào `ref/`. Đây là các nguồn sẽ được trích nhiều nhất.
> 2. Cập nhật file Excel: R06 đã có bản tạp chí, R05b là bản trùng.
> 3. Tự kiểm quartile của DSE (R06) và ACM TOCS (R14) trên scimagojr.com.

---

## 5. Danh mục tham khảo (IEEE)

**Tài liệu trong `ref/`**

- [R01] A. R. Faridi, F. Masood, Keshvi, and T. Yunus, "Retrieval-augmented generation for large language models: Evolution, architectures, applications, and challenges (2020–2025)," *WIREs Data Mining Knowl. Discov.*, vol. 16, no. 3, Art. e70122, 2026, doi: 10.1002/widm.70122.
- [R02] Y. Gao, Y. Xiong, M. Wang, and H. Wang, "Modular RAG: Transforming RAG systems into LEGO-like reconfigurable frameworks," *ACM Trans. Inf. Syst.*, vol. 44, no. 7, Art. 164, Sep. 2026, doi: 10.1145/3837856.
- [R03] M. Cheng *et al.*, "A survey on knowledge-oriented retrieval-augmented generation," *ACM Trans. Inf. Syst.*, 2025, doi: 10.1145/3833415.
- [R04] X. Li *et al.*, "A survey of personalization: From RAG to agent," *ACM Trans. Inf. Syst.*, vol. 44, no. 4, Art. 93, May 2026, doi: 10.1145/3802586.
- [R05] S. Wu *et al.*, "Retrieval-augmented generation for natural language processing: A survey," *Artif. Intell. Rev.*, vol. 59, Art. 192, 2026, doi: 10.1007/s10462-026-11605-7.
- [R06] P. Zhao *et al.*, "Retrieval-augmented generation for AI-generated content: A survey," *Data Sci. Eng.*, vol. 11, pp. 1–29, 2026, doi: 10.1007/s41019-025-00335-5.
- [R07] W. Fan *et al.*, "A survey on RAG meeting LLMs: Towards retrieval-augmented large language models," in *Proc. 30th ACM SIGKDD Conf. Knowl. Discov. Data Min. (KDD '24)*, 2024, pp. 6491–6501, doi: 10.1145/3637528.3671470.
- [R08] M. Klesel and H. F. Wittmann, "Retrieval-augmented generation (RAG)," *Bus. Inf. Syst. Eng.*, vol. 67, no. 4, pp. 551–561, 2025, doi: 10.1007/s12599-025-00945-3.
- [R09] S. Li, L. Stenzel, C. Eickhoff, and S. A. Bahrainian, "Enhancing retrieval-augmented generation: A study of best practices," in *Proc. 31st Int. Conf. Comput. Linguistics (COLING)*, 2025, pp. 6705–6717.
- [R10] P. Ersoy and M. Erşahin, "A comparative evaluation of RAG architectures for cross-domain LLM applications: Design, implementation, and assessment," *IEEE Access*, vol. 13, pp. 194185–194196, 2025, doi: 10.1109/ACCESS.2025.3632404.
- [R11] P. Raghavan, D. A. Tamburri, S. Fossati, and W.-J. Van Den Heuvel, "LLMOps in action: A framework for designing, deploying, and governing advanced chatbots," *IEEE Trans. Knowl. Data Eng.*, vol. 38, no. 7, pp. 4491–4510, Jul. 2026.
- [R12] S. M. Billah and R. J. B. R. Yusof, "Exploring the role of RAG in cloud-based monolithic chatbots: A systematic review," in *Proc. IEEE Student Conf. Res. Develop. (SCOReD)*, 2025.
- [R13] W. Jiang *et al.*, "RAGO: Systematic performance optimization for retrieval-augmented generation serving," in *Proc. 52nd Annu. Int. Symp. Comput. Archit. (ISCA '25)*, 2025, pp. 974–989, doi: 10.1145/3695053.3731093.
- [R14] C. Jin *et al.*, "RAGCache: Efficient knowledge caching for retrieval-augmented generation," *ACM Trans. Comput. Syst.*, vol. 44, no. 1, Art. 2, Nov. 2025, doi: 10.1145/3768628.
- [R15] S. Li *et al.*, "RAGPerf: An end-to-end benchmarking framework for retrieval-augmented generation systems," arXiv:2603.10765, 2026.
- [R16] D. Wampler, D. Nielson, and A. Seddighi, "Engineering the RAG stack: A comprehensive review of the architecture and trust frameworks for retrieval-augmented generation systems," arXiv:2601.05264, 2025.
- [R17] A. J. Oche, A. G. Folashade, T. Ghosal, and A. Biswas, "A systematic review of key retrieval-augmented generation (RAG) systems: Progress, gaps, and future directions," arXiv:2507.18910, 2025.
- [R18] I. K. Aksakalli, T. Çelik, A. B. Can, and B. Tekinerdoğan, "Deployment and communication patterns in microservice architectures: A systematic literature review," *J. Syst. Softw.*, vol. 180, Art. 111014, 2021.
- [R19] H. Rodrigues, A. Rito Silva, and A. Avritzer, "Assessment of performance and its scalability in microservice architectures: Systematic literature review," *J. Syst. Softw.*, vol. 230, Art. 112500, 2025.
- [R20] C. R. B. de Souza, D. Redmiles, L.-T. Cheng, D. Millen, and J. Patterson, "Sometimes you need to see through walls: A field study of application programming interfaces," in *Proc. ACM Conf. Comput. Supported Coop. Work (CSCW '04)*, 2004, pp. 63–71.

**Nguồn bổ sung**

- [S01] C. D. Manning, P. Raghavan, and H. Schütze, *Introduction to Information Retrieval*. Cambridge, U.K.: Cambridge Univ. Press, 2008.
- [S02] P. Lewis *et al.*, "Retrieval-augmented generation for knowledge-intensive NLP tasks," in *Adv. Neural Inf. Process. Syst. (NeurIPS)*, vol. 33, 2020, pp. 9459–9474.
- [S03] V. Karpukhin *et al.*, "Dense passage retrieval for open-domain question answering," in *Proc. EMNLP*, 2020, pp. 6769–6781.
- [S04] S. Robertson and H. Zaragoza, "The probabilistic relevance framework: BM25 and beyond," *Found. Trends Inf. Retr.*, vol. 3, no. 4, pp. 333–389, 2009.
- [S05] C. Huyen, *AI Engineering: Building Applications with Foundation Models*. Sebastopol, CA, USA: O'Reilly, 2025.
- [S06] G. V. Cormack, C. L. A. Clarke, and S. Büttcher, "Reciprocal rank fusion outperforms Condorcet and individual rank learning methods," in *Proc. 32nd ACM SIGIR*, 2009, pp. 758–759.
- [S07] S. Bruch, S. Gai, and A. Ingber, "An analysis of fusion functions for hybrid retrieval," *ACM Trans. Inf. Syst.*, vol. 42, no. 1, pp. 1–35, 2023, doi: 10.1145/3596512.
- [S08] L. Patel, P. Kraft, C. Guestrin, and M. Zaharia, "ACORN: Performant and predicate-agnostic search over vector embeddings and structured data," *Proc. ACM Manag. Data (SIGMOD)*, vol. 2, no. 3, 2024.
- [S09] J. Lin, R. Nogueira, and A. Yates, *Pretrained Transformers for Text Ranking: BERT and Beyond*. Cham, Switzerland: Springer, 2021.
- [S10] K. Järvelin and J. Kekäläinen, "Cumulated gain-based evaluation of IR techniques," *ACM Trans. Inf. Syst.*, vol. 20, no. 4, pp. 422–446, 2002.
- [S11] X. Ma, Y. Gong, P. He, H. Zhao, and N. Duan, "Query rewriting for retrieval-augmented large language models," in *Proc. EMNLP*, 2023, pp. 5303–5315.
- [S12] O. Weller, D. Lawrie, and B. Van Durme, "NevIR: Negation in neural information retrieval," in *Proc. 18th Conf. EACL*, 2024.
- [S13] H. Zamani, J. R. Trippas, J. Dalton, and F. Radlinski, "Conversational information seeking," *Found. Trends Inf. Retr.*, vol. 17, no. 3–4, pp. 244–456, 2023.
- [S14] N. F. Liu *et al.*, "Lost in the middle: How language models use long contexts," *Trans. Assoc. Comput. Linguist.*, vol. 12, pp. 157–173, 2024.
- [S15] S. Es, J. James, L. Espinosa-Anke, and S. Schockaert, "RAGAs: Automated evaluation of retrieval augmented generation," in *Proc. 18th Conf. EACL: System Demonstrations*, 2024.
- [S16] J. Chen, H. Lin, X. Han, and L. Sun, "Benchmarking large language models in retrieval-augmented generation," in *Proc. AAAI*, vol. 38, 2024.
- [S17] L. Zheng *et al.*, "Judging LLM-as-a-judge with MT-Bench and Chatbot Arena," in *Adv. Neural Inf. Process. Syst. (NeurIPS) Datasets and Benchmarks Track*, 2023.
- [S18] M. D. Smucker, J. Allan, and B. Carterette, "A comparison of statistical significance tests for information retrieval evaluation," in *Proc. 16th ACM CIKM*, 2007, pp. 623–632.
- [S19] W. Min, S. Jiang, and R. Jain, "Food recommendation: Framework, existing solutions, and challenges," *IEEE Trans. Multimedia*, vol. 22, no. 10, pp. 2659–2671, 2020, doi: 10.1109/TMM.2019.2958761.
- [S20] F. Mohbat and M. J. Zaki, "KERL: Knowledge-enhanced personalized recipe recommendation using large language models," in *Proc. 63rd Annu. Meeting ACL (Vol. 1: Long Papers)*, 2025, pp. 19125–19141, doi: 10.18653/v1/2025.acl-long.938.
- [S21] Y. Katsis *et al.*, "MTRAG: A multi-turn conversational benchmark for evaluating retrieval-augmented generation systems," *Trans. Assoc. Comput. Linguist.*, 2025.
- [S22] European Parliament and Council, "Regulation (EU) No 1169/2011 on the provision of food information to consumers," *Off. J. Eur. Union*, L 304, 2011, Annex II.
- [S23] U.S. Food and Drug Administration, "Food allergies: What you need to know," FDA (FALCPA 2004; FASTER Act 2021).
- [S24] D. M. Dooley *et al.*, "FoodOn: A harmonized food ontology to increase global food traceability, quality control and data integration," *npj Sci. Food*, vol. 2, Art. 23, 2018.
- [S25] J. Chen *et al.*, "M3-Embedding: Multi-linguality, multi-functionality, multi-granularity text embeddings through self-knowledge distillation," in *Findings of ACL*, 2024.
- [S26] Z. Ji *et al.*, "Survey of hallucination in natural language generation," *ACM Comput. Surv.*, vol. 55, no. 12, Art. 248, 2023.
- [S27] C. C. Aggarwal, *Recommender Systems: The Textbook*. Cham, Switzerland: Springer, 2016.

**Tài liệu môn học**

- [C0] Phạm Đỗ Kim Chi, "Chương 0 – Giới thiệu môn học," slide bài giảng IS6303, UIT, 2026.
- [C2] Phạm Đỗ Kim Chi, "Chương 2 – Retrieval Augmented Generation (RAG)," slide bài giảng IS6303, UIT, 2026.

> *Ghi chú kiểm chứng:* số trang của S11, S13 và venue chi tiết của S16, S21 lấy theo hiểu biết đến 06/2026 và kết quả tra cứu. Trước khi nộp nên đối chiếu lại trên ACL Anthology hoặc trang DOI.
