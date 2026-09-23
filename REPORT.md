# Semantic Search cho công thức nấu ăn: BM25, Dense, Hybrid và Reranking trên PostgreSQL

**Môn học**: IS6303 — Assignment A1 · **Dataset**: [`ANDREEEWW/recipe-with-images`](https://huggingface.co/datasets/ANDREEEWW/recipe-with-images) · **Mã nguồn**: commit `e2b6cfa`, bộ query hash `285fa9fa1cbc5f9a`

## 1. Bài toán và phạm vi

Người dùng nhập truy vấn văn bản tự do (tên món, nguyên liệu có sẵn, hoặc mô tả
món muốn ăn) và hệ thống trả về **ảnh** các công thức phù hợp nhất. Bản chất là
bài toán `text → recipe → image`: so khớp diễn ra trên văn bản công thức, ảnh là
đầu ra hiển thị.

Chúng tôi chọn phạm vi **text-only ở cả phía query và phía index**. Yếu tố
multimodal nằm ở phía dữ liệu: mỗi document được index đều gắn một ảnh và kết
quả cuối cùng là ảnh. Chúng tôi không dùng CLIP/SigLIP, để dồn thời gian cho
việc đo đạc bốn cấu hình retrieval bắt buộc cùng bảy nhóm ablation có kiểm định
thống kê, thay vì mở rộng phạm vi mà không kết luận được gì chắc chắn.

Kiến trúc hai tầng: **tầng 1** dùng BM25 (`pg_search`) và dense cosine
(`pgvector`), hợp nhất bằng Reciprocal Rank Fusion; **tầng 2** dùng cross-encoder
xếp lại top-N. Toàn bộ index nằm trong một container ParadeDB (PostgreSQL 17 +
`pg_search` + `pgvector`); Gradio gọi trực tiếp các hàm Python in-process.

## 2. Dataset

### 2.1 Nguồn, schema và ba đặc điểm quyết định thiết kế

`ANDREEEWW/recipe-with-images` gồm 52.007 bản ghi (train 36.404 / test 15.603),
~2,57 GB sau giải nén, với bốn trường: `image` (ảnh món đã hoàn thành, JPEG
~680×454), `name` (tên công thức), `ingredients` (danh sách nguyên liệu dạng văn
bản thô nhiều dòng), `description` (mô tả ngắn).

Ba đặc điểm ảnh hưởng tới toàn bộ thiết kế:

1. **Không có trường `id`.** Chúng tôi gán `recipe_idx` ổn định khi dựng subset
   và dùng lại xuyên suốt index, đánh giá và UI.
2. **Không có nhãn category và không có ground truth cho retrieval** — không có
   trường query, không có nhãn liên quan. Đây là vấn đề lớn nhất của dataset này
   (mục 2.3).
3. **`ingredients` không phải danh sách danh từ nguyên liệu sạch.** Nó trộn số
   lượng, đơn vị, bước sơ chế và sub-header. Ví dụ thật:
   `"Eclair Shells (Pate a Choux):\n2 tablespoons water\n1/4 cup butter\n...\nCustard:\n6 1/2 tablespoons white sugar"`.
   Mọi việc dùng trường này như tập từ khoá nguyên liệu đều phải chuẩn hoá trước.

### 2.2 Subset và biểu diễn văn bản

Chúng tôi lấy **5.000 công thức** từ split `train`, shuffle seed 42 rồi cắt
5.000 mẫu đầu, cache xuống đĩa để mọi lần chạy lại đều cho đúng tập đó. Kích
thước này giữ thời gian embed lại ở mức vài chục giây trên laptop CPU, đủ để
chạy 23 cấu hình. Tính đa dạng được đảm bảo bởi việc lấy ngẫu nhiên từ toàn bộ
split — tập mẫu trải trên nhiều loại món và cả hai hệ đơn vị (cup/ounce và
gram/ml, tức cả nguồn kiểu allrecipes và BBC Food).

Văn bản tìm kiếm dựng theo thứ tự cố định `name + ingredients + description`,
trong đó `ingredients` được chuẩn hoá nhẹ nhưng **giữ nguyên số lượng và đơn
vị** — việc bỏ hay giữ để ablation quyết định chứ không quyết định trước.

Độ dài (đơn vị từ, trên 5.000 công thức): chunk gộp có median 71 / mean 77,0;
riêng `name` median 3; `ingredients` median 42; `description` median 23. Không
công thức nào thiếu `description`. **Điểm cần ghi nhớ cho mục 6.4: trong chunk
gộp, `description` chỉ chiếm trung bình 35,5% số từ**, phần còn lại gần như toàn
bộ là danh sách nguyên liệu.

Dữ liệu lưu vào ParadeDB theo **profile có phiên bản**: `chunk_profiles` khai
báo cách cắt chunk, `embedding_profiles` khai báo model kèm
`query_prefix`/`document_prefix`. Nhờ đó thêm một biến thể cho ablation chỉ là
thêm một hàng cấu hình, không phải sửa hàm SQL.

### 2.3 Tự xây ground truth

Vì dataset không có nhãn, chúng tôi tự dựng bộ query và gán nhãn, xuất ra file
có phiên bản `experiments/queries_v1.json` (300 query, seed 42). Bộ query đọc
trực tiếp từ bảng `raw.recipes`, nên chắc chắn được gán nhãn đúng trên tập
document đang được index. 300 query chia thành **4 family × 75 query, sinh từ
các công thức nguồn không trùng nhau**:

| Family | Cách sinh | Mô phỏng |
|---|---|---|
| `name_kw` | tên món, bỏ stopword và số thứ tự La Mã | người dùng biết tên món |
| `ingredient_combo` | 4 nguyên liệu mang tính phân biệt nhất | "tôi có sẵn X, Y, Z" |
| `desc_short` | description cắt còn 12 từ, **xoá từ trùng với tên món** | mô tả món muốn ăn |
| `synonym_hard` | như trên nhưng đổi ≥2 nguyên liệu sang từ đồng nghĩa **không** xuất hiện trong công thức gốc | người dùng dùng từ vựng khác |

Việc chọn nguyên liệu dựa trên tần suất tài liệu: loại bỏ nguyên liệu bếp phổ
thông (>10% công thức: muối, bơ, đường, nước…) và loại bỏ cả nguyên liệu chỉ có
ở đúng một công thức, nên query không quá chung chung mà cũng không thành khoá
định danh hiển nhiên. Family `synonym_hard` được thiết kế riêng để **đo thiên
lệch lexical** (shrimp→prawns, cilantro→coriander, graham cracker→digestive
biscuit, all-purpose flour→plain flour…).

Nhãn liên quan là công thức mà query được sinh ra từ đó, cộng thêm các công thức
có độ trùng tập nguyên liệu Jaccard ≥ 0,8 (8/300 query), để một món bị lặp trong
corpus không bị tính là lỗi.

### 2.4 Ba giới hạn của ground truth này

Phần này phải nói thẳng vì nó định hình mọi con số phía sau.

1. **Thiên lệch lexical.** Ba trong bốn family sinh từ chính văn bản được index,
   nên bộ so khớp từ khoá nhìn thấy độ trùng gần như nguyên văn. Đó là lý do
   BM25 đạt điểm rất cao, và là lý do **bảng chia theo family quan trọng hơn con
   số trung bình**.
2. **`synonym_hard` không xoá hết thiên lệch đó.** Đổi 2 trong 4 term vẫn để lại
   1–2 nguyên liệu hiếm, mà trong corpus 5.000 món một nguyên liệu hiếm
   ("amaretto liqueur", "beef consomme") gần như là khoá định danh duy nhất.
   BM25 vẫn đạt Recall@10 = 0,947 trên family này.
3. **Nhãn đơn.** Với query chung như `sugar cookies`, corpus có hàng chục công
   thức đều đúng nhưng chỉ công thức nguồn được tính. Một phần "lỗi" ghi nhận
   được thực chất là thiếu nhãn (mục 6.1).

## 3. Thiết lập đánh giá

**Metric**: Recall@1/5/10, MRR, nDCG@10, latency p50/p95 tách riêng phần encode
query và phần search.

**Giao thức**: mọi cấu hình dùng cùng corpus, cùng file query, cùng nhãn, cùng
độ sâu truy hồi 50, cùng quy tắc phá thế hoà (`score DESC, recipe_idx ASC`, áp
dụng cho cả SQL và Python). Hai chi tiết cần thiết để phép đo công bằng:
**3 query warm-up** chạy trước khi tính thời gian (để chi phí nạp model lười và
cache lạnh không bị tính cho cấu hình chạy đầu), và **tắt việc đọc ảnh** khi
đánh giá — với pool 100 ứng viên, decode 100 file JPEG tốn nhiều hơn bản thân
phép retrieval và sẽ lấn hết con số latency.

**Kiểm định ý nghĩa**: Recall@10 kèm khoảng tin cậy 95% bằng percentile
bootstrap; khi so hai cấu hình thì dùng **paired bootstrap** trên hiệu số từng
query. Với 300 query, chênh 1–2 điểm nằm trong nhiễu nên một con số trung bình
trần không đủ để kết luận.

Mỗi lần chạy lưu metric kèm provenance (git commit, dataset revision, subset
size/seed, tên model, tham số) và một file per-query record (thứ hạng, hạng của
công thức đúng, thời gian). Nhờ per-query record, mọi bảng và toàn bộ phần phân
tích lỗi dựng lại được mà không cần chạy lại retrieval.

## 4. Kết quả chính

Bốn cấu hình bắt buộc, trên chunk gộp + `all-MiniLM-L6-v2`:

| Cấu hình | R@1 | R@5 | R@10 | R@10 95% CI | MRR | nDCG@10 | p50 | p95 |
|---|---|---|---|---|---|---|---|---|
| BM25 | 0,824 | 0,956 | **0,973** | [0,955; 0,989] | 0,896 | 0,911 | 24 ms | 28 ms |
| Dense | 0,412 | 0,563 | 0,613 | [0,558; 0,670] | 0,490 | 0,512 | 30 ms | 38 ms |
| Hybrid (RRF) | 0,579 | 0,766 | 0,857 | [0,817; 0,895] | 0,679 | 0,712 | 47 ms | 57 ms |
| Hybrid + Rerank | **0,888** | **0,973** | **0,983** | [0,970; 0,995] | **0,934** | **0,942** | 263 ms | 487 ms |

Paired bootstrap trên Recall@10 so với BM25 (2.000 lần lấy mẫu lại) và Recall@10
tách theo family:

| So sánh với BM25 | Hiệu số | 95% CI | p | | Cấu hình | `name_kw` | `ing_combo` | `desc_short` | `synonym_hard` |
|---|---|---|---|---|---|---|---|---|---|
| Dense | −0,359 | [−0,416; −0,303] | 0,000 | | BM25 | 0,958 | 1,000 | 0,987 | 0,947 |
| Hybrid RRF | −0,116 | [−0,157; −0,077] | 0,000 | | Dense | 0,960 | 0,613 | 0,347 | 0,533 |
| Hybrid + Rerank | +0,011 | [−0,003; +0,027] | 0,155 | | Hybrid RRF | 0,974 | 0,853 | 0,880 | 0,720 |
| | | | | | Hybrid + Rerank | 0,974 | 1,000 | 0,973 | 0,987 |

**BM25 là tầng đơn mạnh nhất, và hybrid RRF làm nó xấu đi** — mất 11,6 điểm
Recall@10, khoảng tin cậy không chứa 0. Nguyên nhân là RRF cho hai danh sách đầu
vào trọng số bằng nhau, nên hợp nhất một bảng xếp hạng mạnh với một bảng yếu hơn
nhiều thì bảng mạnh bị kéo xuống. Đây vừa là tính chất của phương pháp, vừa là
tính chất của bộ query: ba trong bốn family sinh từ chính văn bản được index,
đúng tình huống mà so khớp từ khoá giỏi nhất.

**Cấu hình duy nhất vượt BM25 là BM25 cộng reranker, và mức vượt đó không có ý
nghĩa thống kê** (p = 0,155). Đóng góp thật của reranker nằm ở đỉnh bảng xếp
hạng: so với hybrid đơn, MRR tăng 0,679 → 0,934 và R@1 tăng 0,579 → 0,888. Nói
cách khác, reranker **sửa lại thứ tự mà fusion đã làm hỏng** chứ không tìm thêm
tài liệu mới. Giá phải trả là latency gấp ~11 lần BM25.

**Dense yếu nhưng không yếu đều**: ngang BM25 ở `name_kw` (0,960 vs 0,958) và
sụp ở `desc_short` (0,347). Mục 5.4 giải thích nguyên nhân.

## 5. Ablation

Bảy nhóm, mỗi nhóm đổi đúng một biến. Baseline: chunk gộp, `all-MiniLM-L6-v2`,
fusion pool 100, RRF k = 60. Xếp theo ảnh hưởng lên Recall@10: **trường nào được
index** (tới +60,6 điểm) > **chiến lược chunk** (+18,8 cho dense) > **model
embedding** (+14,5 cho dense) > **hằng số RRF k** (+8,6) > **pool rerank 20→50**
(+5,6) > **nơi đặt logic fusion** (0,0 — chỉ khác latency).

### 5.1 Nơi đặt logic fusion: trong SQL hay ở service layer

RRF giống nhau, đầu vào giống nhau, chỉ khác tầng thực thi.

| Cấu hình | R@10 | MRR | p50 | p95 | Round-trip | Dòng qua dây |
|---|---|---|---|---|---|---|
| RRF trong SQL (`match_hybrid`) | 0,857 | 0,679 | 47 ms | 57 ms | 1 | 10 |
| RRF ở service layer (Python) | 0,857 | 0,679 | 56 ms | 62 ms | 2 | 200 |

**Thứ hạng trùng khớp tuyệt đối: 300/300 query giống nhau ở cả top-1 và toàn bộ
top-10.** Để đạt được điều đó, chúng tôi phải cho hàm Python dùng đúng quy tắc
phá thế hoà của SQL. RRF tạo ra rất nhiều điểm hoà chính xác, nên nếu không
thống nhất thì hai đường tính ra cùng điểm nhưng xếp khác thứ tự — một cái bẫy
dễ bỏ qua khi so sánh hai cách triển khai "giống nhau".

Vì chất lượng bằng nhau, lựa chọn thuần về vận hành: SQL nhanh hơn 8 ms ở p50
(−15%) và tiết kiệm round-trip; service layer giữ logic xếp hạng trong code ứng
dụng, dễ unit-test và dễ sửa mà không cần migration. Ngược lại, cross-encoder
**bắt buộc** ở service layer vì cần batch inference và lý tưởng là GPU — 263 ms
p50 của nó là thời gian chạy model, không phải thời gian truy vấn.

### 5.2 Model embedding — so sánh ba model có sẵn

Giữ nguyên chunk profile, chỉ đổi encoder. Cả ba đều **384 chiều**, vừa khít cột
`vector(384)` và chữ ký `match_dense`, nên **không phải đổi schema**.

| Model | Dense R@10 | Dense MRR | Hybrid R@10 | Encode |
|---|---|---|---|---|
| `all-MiniLM-L6-v2` | 0,613 | 0,490 | 0,857 | 11,9 ms |
| `BAAI/bge-small-en-v1.5` | 0,733 | 0,596 | 0,907 | 15,3 ms |
| `intfloat/e5-small-v2` | **0,758** | **0,648** | **0,930** | 18,8 ms |

E5-small-v2 hơn MiniLM **14,5 điểm** Recall@10 với chi phí thêm ~7 ms mỗi query
— trade-off rất đáng đổi, không cần train hay fine-tune.

Điểm kỹ thuật đáng ghi lại: BGE và E5 là **model bất đối xứng**, cần prefix đúng
phía (`query: `/`passage: ` với E5, câu instruction phía query với BGE). Nếu
embed document mà không có prefix tương ứng thì chất lượng giảm **mà không có
lỗi nào báo ra**. Vì vậy `embedding_profiles` lưu `query_prefix` và
`document_prefix` theo từng profile, và encoder lúc truy vấn đọc lại đúng prefix
mà document đã được embed, thay vì giả định mọi model đều đối xứng.

Cả ba đều thuộc lớp "small" (~33M tham số) vì đây là ràng buộc của laptop CPU;
chúng tôi không thử model lớn hơn. Reranker dùng
`cross-encoder/ms-marco-MiniLM-L-6-v2`.

### 5.3 Biểu diễn văn bản — trường nào đáng được index

| Trường được index | BM25 R@10 | Dense R@10 | Hybrid R@10 |
|---|---|---|---|
| `name` | 0,367 | 0,348 | 0,355 |
| `name + ingredients` | 0,757 | 0,603 | 0,683 |
| `name + ingredients + description` | 0,973 | 0,613 | 0,857 |

Mọi trường đều đáng giá: thêm `ingredients` làm Recall@10 của BM25 tăng hơn gấp
đôi, thêm `description` tăng thêm 21,6 điểm. Một phần kết quả này do cách xây bộ
query (một family sinh từ description, một family từ ingredients), nên cách đọc
trung thực là: **mỗi trường là thứ làm cho family query tương ứng trả lời được,
bỏ nó đi thì mất xấp xỉ trọng số của family đó.**

Đáng chú ý là sự bất đối xứng: thêm `description` làm BM25 tăng 21,6 điểm nhưng
dense chỉ tăng 1,0 điểm (0,603 → 0,613). Description *có* được index nhưng gần
như không được biểu diễn trong vector — đó là điều mục 5.4 cô lập ra.

### 5.4 Chiến lược chunk — phát hiện đáng chú ý nhất

Chunk gộp (một chunk mỗi công thức) so với chunk theo trường (một chunk mỗi
trường, điểm gom về công thức bằng `MAX` để công thức nhiều chunk không được lợi
thế).

| Cấu hình | R@10 | MRR | nDCG@10 | p50 | | Dense theo family | Gộp | Theo trường | Chênh |
|---|---|---|---|---|---|---|---|---|---|
| BM25 / gộp | 0,973 | 0,896 | 0,911 | 24 ms | | `desc_short` | 0,347 | 0,733 | **+0,387** |
| BM25 / theo trường | 0,987 | 0,937 | 0,945 | 29 ms | | `ingredient_combo` | 0,613 | 0,787 | +0,173 |
| Dense / gộp | 0,613 | 0,490 | 0,512 | 30 ms | | `synonym_hard` | 0,533 | 0,707 | +0,173 |
| Dense / theo trường | **0,801** | **0,675** | **0,698** | 39 ms | | `name_kw` | 0,960 | 0,978 | +0,018 |
| Hybrid / gộp | 0,857 | 0,679 | 0,712 | 47 ms | | | | | |
| Hybrid / theo trường | 0,932 | 0,832 | 0,850 | 63 ms | | | | | |

**Đây là cải thiện lớn nhất trong toàn bộ nghiên cứu: +18,8 điểm Recall@10 cho
dense mà không đổi model.**

Nguyên nhân là **pha loãng tín hiệu**, không phải truncation. Một vector gộp
phải biểu diễn đồng thời `name + ingredients + description`, mà description chỉ
chiếm ~35% số từ (mục 2.2), nên vector bị danh sách nguyên liệu chi phối. Query
sinh từ description khi đó phải khớp với một vector mà phần lớn nội dung nói về
chuyện khác. Chunk theo trường cho mỗi trường một vector riêng, và phép `MAX`
cho phép query khớp đúng vào trường mà nó được sinh ra từ. Bảng bên phải xác
nhận: **mức tăng tỉ lệ nghịch với tỉ trọng của trường nguồn trong chunk gộp**,
và `name_kw` gần như không đổi vì tên món ngắn, rất đặc trưng, và đã ở 0,960.

**Giả thuyết đầu tiên của chúng tôi là truncation, và phép đo đã bác bỏ nó.**
Với cửa sổ 256 token của MiniLM-L6-v2, chunk gộp có median 109 token, chỉ 1,5%
công thức vượt cửa sổ, và description bị cắt hoàn toàn ở đúng 6/5.000 công thức
(0,1%) — quá hiếm để tạo ra 18,8 điểm chênh lệch. Chúng tôi ghi lại điều này vì
đó là bài học phương pháp: hai cơ chế rất khác nhau (mất dữ liệu vs pha loãng
biểu diễn) cho cùng một triệu chứng, và cách phân biệt là đo phân bố độ dài bằng
tokenizer thật rồi đối chiếu mức tăng theo từng family.

BM25 cũng tăng (+1,4 điểm) vì lý do liên quan: chunk ngắn theo trường chịu mức
phạt length-normalisation nhẹ hơn nhiều so với chunk chứa cả danh sách nguyên
liệu. Chi phí là gấp 3 số dòng (15.000 chunk và embedding thay vì 5.000) và
khoảng 30% latency.

### 5.5 Hằng số RRF k và kích thước pool cho reranker

| k | R@1 | R@10 | MRR | nDCG@10 | | Pool rerank | R@1 | R@10 | MRR | p50 |
|---|---|---|---|---|---|---|---|---|---|---|
| 20 | 0,586 | **0,943** | **0,712** | **0,762** | | 20 | 0,861 | 0,927 | 0,898 | 156 ms |
| 60 (mặc định) | 0,579 | 0,857 | 0,679 | 0,712 | | 50 | 0,888 | 0,983 | 0,934 | 339 ms |
| 120 | 0,576 | 0,843 | 0,672 | 0,703 | | 100 | 0,888 | **0,987** | 0,934 | 640 ms |

**k nhỏ tốt hơn**: hạ từ 60 xuống 20 được thêm 8,6 điểm Recall@10. Hằng số này
điều khiển tốc độ suy giảm của `1/(k + rank)`: k nhỏ làm đỉnh của mỗi danh sách
chi phối, k lớn làm các đóng góp phẳng ra đến mức vị trí sâu trong danh sách yếu
có thể áp đảo đỉnh của danh sách mạnh. Vì BM25 mạnh hơn dense rất nhiều ở đây,
bất cứ điều gì để danh sách mạnh chi phối đều có lợi. Kết luận thực tế: **giá
trị 60 được copy rộng rãi không phù hợp với một cặp retriever lệch nhau nhiều
như vậy**; cách sửa trực tiếp hơn là weighted RRF.

Về pool rerank (RRF luôn hợp nhất trên 100 ứng viên, chỉ số lượng đưa cho
cross-encoder thay đổi, nên ba pool là tập con lồng nhau): từ 20 lên 50 mua được
5,6 điểm Recall@10 với 2,2 lần latency; từ 50 lên 100 chỉ thêm 0,4 điểm với 1,9
lần latency nữa, và **R@1 cùng MRR không đổi** — cross-encoder không tìm thấy gì
mới trong ứng viên 51–100. Pool 50 là điểm vận hành được chọn.

**Ghi nhận về độ tin cậy của số latency**: cấu hình rerank pool 50 được chạy hai
lần; mọi metric chất lượng trùng khớp tuyệt đối nhưng p50 lệch 263 ms so với
339 ms (~29%). Con số chất lượng có tính tất định, con số latency phụ thuộc tải
máy. Vì vậy **latency trong báo cáo này nên đọc theo bậc độ lớn, không theo từng
phần trăm.**

## 6. Phân tích lỗi

Case được chọn tự động từ per-query record, phần diễn giải viết tay.

| Mẫu lỗi | Số query /300 | | Query bị trượt theo family | `name_kw` | `ing_combo` | `desc_short` | `synonym_hard` |
|---|---|---|---|---|---|---|---|
| BM25 tìm được, dense không | 109 | | BM25 | 2/75 | 0/75 | 0/75 | 4/75 |
| Cross-encoder đẩy kết quả đúng xuống | 10 | | Dense | 1/75 | 29/75 | 48/75 | 35/75 |
| Dense tìm được, BM25 không | 2 | | Hybrid RRF | 0/75 | 11/75 | 8/75 | 21/75 |
| Không cấu hình nào tìm được | 1 | | Hybrid + Rerank | 0/75 | 0/75 | 1/75 | 1/75 |
| RRF làm mất kết quả cả hai đầu vào đều có | **0** | | | | | | |

Hai điều nổi bật. **Dense gần như không đóng góp thứ gì BM25 bỏ sót (2 query)** —
đây là lý do định lượng cho việc fusion không "có lãi" trên bộ query này. Và
**RRF không bao giờ làm mất tài liệu mà cả hai đầu vào đều tìm được**: fusion an
toàn về recall, nó chỉ làm hỏng thứ tự, và đó đúng là thứ reranker sửa lại.

### 6.1 Case tốt — dense cứu một query bị chen chúc về từ khoá

```
Query (name_kw): "sugar cookies"          Nhãn: #4241 Sugar Cookies VI
Hạng: BM25 #24 · Dense #7 · Hybrid #9 · Hybrid+Rerank #5
Top-5 của BM25: Cookie Mold Sugar Cookies / Irish Shamrock Cookies /
                Becky's Sugary Sugar Cookies / Rum Raisin Cookies /
                Tender Crisp Sugar Cookies
```

Đây là kiểu query duy nhất mà dense encoder thực sự hữu ích. Corpus chứa hàng
chục công thức sugar cookie gần như giống nhau nên BM25 không còn tín hiệu từ
khoá để phân biệt và chỉ xếp theo thống kê term; embedding đặt công thức "thuần"
nhất gần với query "thuần" nhất.

Đồng thời đây là ví dụ rõ nhất về **thiếu nhãn, không phải lỗi retrieval**: cả 5
kết quả đầu của BM25 đều là công thức sugar cookie và đều làm người dùng thật
hài lòng, nhưng chỉ #4241 được tính đúng. Một phần trong 109 query "BM25 thắng"
là cùng artefact này.

### 6.2 Case xấu — thay từ đồng nghĩa hạ cả pipeline

```
Query (synonym_hard): "digestive biscuits, pecans, sour cream, cream cheese"
Sinh từ:              "graham crackers, pecans, sour cream, cream cheese"
Nhãn: #1204 Perfect Cheesecake Everytime
Hạng: BM25 #45 · Dense trượt · Hybrid trượt · Hybrid+Rerank trượt
Top-5 của BM25: Sour Cream Raisin Pie VI / Chocolate peanut butter cheesecake /
                Grape and Coconut Salad / White Chocolate Fudge with Pecans /
                Easy Cheddar Biscuits with Fresh Herbs
```

Query duy nhất mà mọi cấu hình đều trượt. Sau khi thay từ, query chỉ còn hai
term xuất hiện trong tài liệu (`pecans`, `sour cream`) và cả hai đều phổ biến,
nên BM25 không còn gì hiếm để neo vào và trôi về các công thức khớp lẻ từng
term; "digestive biscuits" còn chủ động dẫn nó sai hướng tới `Easy Cheddar
Biscuits`. Dense *đáng lẽ* phải xử lý được — đây chính là ca lệch từ vựng —
nhưng vector gộp của công thức cheesecake bao trùm toàn bộ danh sách nguyên
liệu, nên query 4 nguyên liệu bị so với một vector mà phần lớn nói về thứ khác.

Một query này chứa cả hai chế độ lỗi cùng lúc và cho thấy chúng **cộng dồn**:
tầng lexical thất bại vì từ vựng, tầng semantic thất bại vì pha loãng biểu diễn,
và fusion không cứu được thứ mà không đầu vào nào tìm ra.

### 6.3 Case xấu — reranker đẩy kết quả đúng xuống

```
Query (synonym_hard): "apples, sultanas, walnuts, icing sugar"
Sinh từ:              "apples, raisins, walnuts, confectioners sugar"
Nhãn: #2361 Apple Hermits
Hạng: BM25 #13 · Dense #5 · Hybrid #3 · Hybrid+Rerank #8
```

Fusion đã đưa nó lên hạng 3 và cross-encoder đẩy xuống hạng 8 — một trong 10
query như vậy. Reranker cho điểm cặp `(query, toàn văn công thức)`, mà văn bản
công thức vẫn ghi "raisins" và "confectioners' sugar" trong khi query ghi
"sultanas" và "icing sugar". Một cross-encoder huấn luyện trên passage web của
MS MARCO không có lý do đặc biệt nào để biết đây là cùng một nguyên liệu, nên nó
đọc cặp này như khớp một phần và cho điểm thấp hơn các công thức lặp lại đúng từ
mặt chữ của query. Tác động tổng thể vẫn rất tích cực (MRR 0,679 → 0,934), nhưng
**reranker kế thừa vấn đề từ vựng chứ không giải quyết nó.**

### 6.4 Các nhóm lỗi đặc thù của dataset này

- **Pha loãng khi pooling** — lỗi dense chủ đạo; đã sửa bằng chunk theo trường.
- **Lệch từ đồng nghĩa** — cách gọi Mỹ/Anh; ảnh hưởng cả BM25 lẫn cross-encoder,
  là lý lẽ mạnh nhất cho việc cần một tầng dense tốt hơn.
- **Thiếu nhãn** — làm phồng tỉ lệ lỗi biểu kiến của mọi cấu hình.
- **Nguyên liệu hiếm như khoá định danh** — mặt còn lại: trong corpus 5.000 món,
  một term hiếm định danh luôn công thức. Đây là lý do BM25 rất khó đánh bại ở
  đây, và là lý do **không nên ngoại suy kết quả này sang corpus lớn hơn vài bậc
  độ lớn**.
- **Nhiễu trong trường ingredients** — số lượng, đơn vị, sub-header pha loãng cả
  tín hiệu lexical lẫn embedding.

## 7. Kết luận

**Về hệ thống.** Cấu hình tốt nhất đo được là BM25 + dense + RRF + cross-encoder
rerank pool 50: Recall@10 = 0,983, MRR = 0,934, p50 ≈ 263 ms. Nhưng kết luận
trung thực hơn là: **trên bộ query này BM25 đơn đã đạt Recall@10 = 0,973 với
24 ms**, và toàn bộ tầng dense + fusion + rerank chỉ mua thêm 1 điểm recall
không có ý nghĩa thống kê, đổi lấy 11 lần latency. Giá trị thật của tầng hai nằm
ở chất lượng thứ tự (MRR 0,679 → 0,934), không ở khả năng tìm thêm tài liệu.

**Về phương pháp**, ba bài học có giá trị hơn bảng số:

1. **Cách biểu diễn dữ liệu quan trọng hơn cách chọn model.** Đổi chiến lược
   chunk mang lại +18,8 điểm cho dense; đổi MiniLM sang E5 mang lại +14,5. Cả
   hai đều rẻ hơn nhiều so với train.
2. **Tham số mặc định copy từ tài liệu cần được kiểm chứng lại.** RRF k = 60 là
   lựa chọn tệ ở đây; k = 20 hơn 8,6 điểm.
3. **Nơi đặt logic là quyết định vận hành, không phải quyết định chất lượng** —
   với điều kiện logic đó chỉ là phép cộng điểm. RRF ở hai tầng cho thứ hạng
   trùng khớp 300/300; chỉ inference model là bắt buộc ra khỏi database.

**Hạn chế.** Ground truth do nhóm tự xây và còn thiên lệch lexical (mục 2.4);
corpus 5.000 món nhỏ đủ để một nguyên liệu hiếm thành khoá định danh; mọi kết
quả là text-only; và các ablation chạy độc lập từng biến nên chúng tôi **chưa**
đo cấu hình kết hợp mọi cải thiện tốt nhất (chunk theo trường + `e5-small-v2` +
weighted RRF + rerank) — đó là bước tiếp theo rõ ràng nhất.

**Hướng phát triển.** Weighted RRF thay cho trọng số bằng nhau; bộ query có
người kiểm nhãn để giảm artefact nhãn đơn; đo trên corpus lớn hơn để kiểm tra ưu
thế của BM25 có giữ được không; và nếu mở rộng multimodal thì hướng khả thi nhất
là dùng CLIP/SigLIP ở tầng rerank để tận dụng chính những ảnh hệ thống đang trả
về.

---

**Tài liệu tham khảo.** Dataset: huggingface.co/datasets/ANDREEEWW/recipe-with-images ·
Cormack, Clarke, Buettcher (2009), *Reciprocal Rank Fusion outperforms Condorcet
and individual Rank Learning Methods*, SIGIR · Reimers & Gurevych (2019),
*Sentence-BERT*, EMNLP · Xiao et al. (2023), *C-Pack* (BGE) · Wang et al. (2022),
*Text Embeddings by Weakly-Supervised Contrastive Pre-training* (E5) ·
ParadeDB `pg_search`: github.com/paradedb/paradedb · pgvector:
github.com/pgvector/pgvector · Thiết kế chi tiết và số liệu đầy đủ: `docs/01`–`docs/13`,
`experiments/report.md`, `experiments/error_cases.md`
