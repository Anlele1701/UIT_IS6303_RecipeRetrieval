# Chương 3. Phân tích và thiết kế hệ thống

## 3.1. Phân tích yêu cầu

Hệ thống phục vụ hai nhóm người dùng. Người dùng phổ thông có thể hỏi gợi ý món ăn kèm ràng buộc bằng tiếng Việt hoặc tiếng Anh, chẳng hạn "tôi dị ứng đậu phộng", "gợi ý món tráng miệng dưới 30 phút". Họ có thể hỏi tiếp để tinh chỉnh kết quả ở các lượt sau, xem và sửa các ràng buộc mà hệ đã hiểu, và gửi phản hồi về câu trả lời. Người dùng chuyên môn, gồm bác sĩ và chuyên gia dinh dưỡng, có thêm chức năng chọn hồ sơ bệnh nhân, xem hồ sơ ràng buộc mà hệ suy ra kèm bằng chứng từ hồ sơ, rồi hỏi gợi ý món cho bệnh nhân đó mà không phải nhắc lại ràng buộc. Chức năng tìm kiếm nâng cao của A1 được giữ lại.

Về yêu cầu phi chức năng, hệ phải không gợi ý món vi phạm ràng buộc cứng đã biết, dù ràng buộc đến từ câu hỏi hay từ hồ sơ. Hệ phải minh bạch bằng cách hiển thị ràng buộc đã hiểu, bằng chứng trong hồ sơ và trích dẫn công thức. Hệ phải trả lời theo dạng streaming để giảm thời gian chờ, phải tái lập được kết quả nhờ cố định seed và tham số, và phải chạy cục bộ để không gửi dữ liệu người dùng ra ngoài. Riêng với hồ sơ bệnh nhân, hệ phải tuân thủ nguyên tắc tối thiểu hóa dữ liệu: chỉ những mục liên quan đến ăn uống mới được đưa vào ngữ cảnh của mô hình ngôn ngữ.

## 3.2. Dữ liệu và pipeline xử lý offline

Hệ sử dụng hai nguồn dữ liệu: kho công thức Shengtao/recipe kế thừa từ A1, và hồ sơ bệnh nhân tổng hợp sinh bằng Synthea. Để khắc phục hạn chế về tính minh bạch của A1, mọi bước xử lý dữ liệu trong A3 được gán mã quy tắc, kèm lý do và số bản ghi bị ảnh hưởng. Các số liệu này được script xử lý ghi tự động ra tệp thống kê (`eval/corpus.json`, `eval/patient_corpus.json`), không nhập tay.

### 3.2.1. Kho công thức

Các quy tắc xử lý kho công thức được trình bày ở Bảng 3.1. Bước quan trọng nhất là gắn thẻ dị ứng cho từng công thức theo chín nhóm dị ứng chính được quy định tại Mỹ, gồm sữa, trứng, cá, động vật có vỏ giáp xác, hạt cây, đậu phộng, lúa mì, đậu nành và mè [15]. Nhóm chọn danh mục này vì corpus là công thức của Mỹ, và vì nó trùng với cách Synthea mã hóa dị ứng thực phẩm. Việc gắn thẻ áp dụng nguyên tắc bảo thủ với các thành phần ẩn: chẳng hạn bơ được tính là sữa, nước sốt Worcestershire được tính là cá, nước tương được tính là đậu nành và lúa mì. Thẻ "chắc chắn" (thành phần trực tiếp hoặc ẩn) được dùng để lọc, còn thẻ "có thể" (phụ thuộc nhãn hiệu, ví dụ sô-cô-la có thể chứa sữa) chỉ được cảnh báo.

**Bảng 3.1. Quy tắc làm sạch và gắn thẻ kho công thức (số đếm từ `eval/corpus.json`)**

| Mã | Quy tắc | Số đếm |
|---|---|---|
| D1 | Loại công thức trùng URL | 3 bản ghi; còn 32.719 công thức |
| D2 | Bỏ cột dinh dưỡng rỗng trên 99% | 13 cột |
| D3 | Chuẩn hóa thời gian về số phút, null khi không đọc được | tổng thời gian null ở 1.859 công thức |
| D4 | Tách dòng nguyên liệu thành số lượng, đơn vị và tên | 311.060 dòng; tách đủ 96,5% |
| D5 | Ánh xạ tên nguyên liệu về dạng chuẩn bằng từ điển đồng nghĩa | 2.005 nguyên liệu chuẩn; độ phủ 99,3% dòng |
| D6 | Gắn nhóm dị ứng cho nguyên liệu chuẩn (chắc chắn / có thể) | sữa 19.590, lúa mì 17.459, trứng 11.322 công thức… |
| D6b | Dòng ghi rõ "không chứa X" (gluten-free, dairy-free…) không mang nhóm X | 128 dòng ở 118 công thức |
| D7 | Suy ra cờ chay và thuần chay | chay 16.687; thuần chay 4.140 công thức |
| D8 | Đánh dấu nguyên liệu không ánh xạ được là unknown | 2.244 dòng; 6,1% công thức có dòng unknown |

Ngoài chín quy tắc trên, lượng mỗi chất dinh dưỡng trên khẩu phần và tỉ lệ năng lượng (chất béo bão hòa, đường) được tính từ các cột dinh dưỡng giữ lại, phục vụ lọc theo ngưỡng suy ra từ hồ sơ (mục 3.4.1).

### 3.2.2. Hồ sơ bệnh nhân Synthea

Hồ sơ bệnh nhân là tài liệu C-CDA R2.1 do Synthea sinh ra, gồm bộ hồ sơ mẫu công bố của Synthea và một nhóm hồ sơ nhóm tự sinh với seed cố định để bổ sung các trường hợp hiếm như dị ứng thực phẩm và bệnh thận mạn. Mỗi tài liệu có các section chuẩn (Allergies, Problems, Medications, Vital Signs, Results, Encounters) mang mã SNOMED CT, RxNorm và LOINC. Các quy tắc xử lý hồ sơ được trình bày ở Bảng 3.2.

**Bảng 3.2. Quy tắc xử lý hồ sơ bệnh nhân (số đếm từ `eval/patient_corpus.json`)**

| Mã | Quy tắc | Lý do | Số đếm |
|---|---|---|---|
| P1 | Nạp mọi tài liệu C-CDA, ghi nguồn và phiên bản | Tái lập được | 120 hồ sơ; 112 còn sống |
| P2 | Chỉ giữ dị ứng và vấn đề đang hiệu lực (chưa có ngày kết thúc) | Ràng buộc phải phản ánh hiện tại | 114 dị ứng; bỏ 4.019 vấn đề đã kết thúc |
| P3 | Phân loại dị ứng thực phẩm theo mã (SNOMED CT 414285001) và ánh xạ về chín nhóm của Bảng 3.1 | Tách dị ứng thực phẩm khỏi dị ứng môi trường một cách tất định | 21 mục |
| P4 | Giữ các vấn đề loại bệnh (disorder), loại các phát hiện xã hội | Giảm nhiễu trong danh sách vấn đề | giữ 411; bỏ 604 phát hiện |
| P5 | Giữ các thuốc đang dùng, theo mã RxNorm | Phục vụ luật tương tác thuốc và thực phẩm | 392 thuốc |
| P6 | Lấy giá trị gần nhất của cân nặng, BMI, huyết áp và các xét nghiệm | Ngưỡng theo cân nặng và mức độ bệnh | 925 chỉ số sinh hiệu |
| P7 | Không đưa vào ngữ cảnh mô hình các mục không liên quan ăn uống (sàng lọc tâm thần, chất gây nghiện, bạo lực, định danh) | Tối thiểu hóa dữ liệu | 2.149 nhóm sàng lọc tâm thần; 1.083 nhóm chất gây nghiện |
| P8 | Chọn tập bệnh nhân phân tầng: dị ứng thực phẩm, tiểu đường, tăng huyết áp, bệnh thận mạn, đa bệnh, không ràng buộc | Phủ mọi nhánh của bộ luật | 100 bệnh nhân |

Hồ sơ mẫu của bệnh nhân Barton704 Upton904 minh họa lý do của các quy tắc trên. Mục dị ứng của hồ sơ có tám mục đang hiệu lực, trong đó chỉ hai mục được mã là dị ứng thực phẩm (lúa mì và hải sản có vỏ, có phản ứng phù mạch); sáu mục còn lại là dị ứng môi trường như latex, nọc ong, nấm mốc và phấn hoa. Danh sách thuốc có bút tiêm epinephrine, cho thấy dị ứng có thể nghiêm trọng. Danh sách vấn đề lẫn các phát hiện xã hội như trình độ học vấn và tình trạng việc làm. Toàn bộ hồ sơ có 88 lần khám và 153 thủ thuật, phần lớn là các lần tiêm chủng lặp lại, trong khi thông tin cần cho việc chọn món chỉ nằm ở một vài mục. Hồ sơ cũng chứa điểm sàng lọc sức khỏe tâm thần, là loại thông tin mà quy tắc P7 giữ ngoài ngữ cảnh của mô hình. Riêng mục "Shellfish" của Synthea không phân biệt giáp xác và nhuyễn thể, nên được ánh xạ theo hướng an toàn: gắn nhóm giáp xác và bổ sung các nguyên liệu nhuyễn thể (nghêu, sò, hàu, mực) vào danh sách nguyên liệu cấm.

## 3.3. Kiến trúc tổng thể

Hệ thống được tổ chức theo kiến trúc bốn lớp [13] (Hình 3.1). Lớp Frontend là ứng dụng React gồm trang chatbox (có bộ chọn bệnh nhân và panel ràng buộc), trang tìm kiếm nâng cao kế thừa từ A1 và trang báo cáo kết quả thực nghiệm. Lớp Backend là dịch vụ FastAPI, chứa bộ điều phối pipeline, các module xử lý hội thoại, dịch vụ hồ sơ bệnh nhân gồm bộ đọc C-CDA, bộ dựng cây và bộ ánh xạ luật, cùng kết nối tới Ollama và mô hình xếp hạng lại. Lớp Data Infrastructure là ParadeDB, lưu kho công thức, chỉ mục BM25 và vector, cây hồ sơ và hồ sơ ràng buộc của bệnh nhân, phiên hội thoại, nhật ký truy vết và phản hồi người dùng; bộ luật ánh xạ được lưu thành các tệp có phiên bản. Lớp Governance gồm nhật ký truy vết từng bước, cơ chế phản hồi, banner miễn trừ trách nhiệm, bước kiểm tra an toàn sau khi sinh và quy tắc tối thiểu hóa dữ liệu hồ sơ. Các dịch vụ được đóng gói bằng Docker Compose và triển khai cục bộ.

![Hình 3.1. Kiến trúc bốn lớp của A3](figures/fig_architecture.png)

![Hình 3.2. Luồng xử lý tích hợp vectorless RAG trên hồ sơ bệnh nhân với truy hồi lai của A1](figures/fig_flow.png)

## 3.4. Pipeline xử lý trực tuyến

### 3.4.1. Nhánh vectorless trên hồ sơ bệnh nhân

Module V1 dựng cây mục lục cho từng bệnh nhân, chạy offline khi hồ sơ được nạp. Cây được dựng tất định từ cấu trúc sẵn có của C-CDA: nút gốc là bệnh nhân, các nút con là Dị ứng, Vấn đề đang điều trị, Thuốc đang dùng, Sinh hiệu gần nhất, Xét nghiệm và Lịch sử khám chia theo năm. Mô hình ngôn ngữ chỉ được dùng để viết một câu tóm tắt cho các nút xét nghiệm và lịch sử, chẳng hạn "hai lần khám thận năm 2025, eGFR giảm", giúp bước sau có thông tin chọn nhánh. Ở chế độ narrative dùng để đánh giá, các section được chuyển thành văn bản không mã và mô hình phải tự trích dị ứng, bệnh và thuốc từ văn bản đó.

Module V2 duyệt cây có giới hạn và chia các nút thành hai loại. Nút cố định gồm Dị ứng, Vấn đề đang điều trị, Thuốc đang dùng và Sinh hiệu gần nhất. Các nút này luôn được đọc bằng code, không qua bước chọn của mô hình, vì việc bỏ sót một dị ứng do mô hình chọn nhầm nhánh là không chấp nhận được. Nút theo ngữ cảnh gồm xét nghiệm cũ và lịch sử khám, chỉ được mở khi câu hỏi cần, chẳng hạn "gần đây chức năng thận của bệnh nhân thế nào". Khi đó mô hình nhận toàn bộ mục lục kèm ngày của hồ sơ, vốn đủ ngắn để nằm gọn trong ngữ cảnh, và trả về danh sách mã nút cần đọc trong một lần gọi duy nhất. Thiết kế này không có vòng lặp, nên vẫn tuân theo lựa chọn luồng tuyến tính ở trên.

Module V3 ánh xạ nội dung các nút đã đọc thành hồ sơ ràng buộc bằng luật tất định, không dùng mô hình ngôn ngữ. Dị ứng thực phẩm được ánh xạ thành nhóm dị ứng cần loại. Bệnh được ánh xạ thành ngưỡng dinh dưỡng theo các hướng dẫn ở mục 2.9. Thuốc được đối chiếu với bảng tương tác thuốc và thực phẩm do nhóm soạn. Bộ luật được trình bày ở Bảng 3.3. Mỗi ràng buộc được ghi kèm mã nút và dòng hồ sơ gốc đã sinh ra nó, để câu trả lời có thể trích dẫn, chẳng hạn "loại món có tôm theo mục Dị ứng của hồ sơ". Hồ sơ ràng buộc được tính một lần và lưu đệm theo mã bệnh nhân và phiên bản bộ luật, nên chi phí của nhánh vectorless chủ yếu phát sinh ở lượt đầu.

**Bảng 3.3. Luật ánh xạ từ hồ sơ bệnh nhân sang ràng buộc món ăn (`data/rules/`)**

| Điều kiện trong hồ sơ | Ràng buộc sinh ra | Cách áp dụng | Nguồn |
|---|---|---|---|
| Dị ứng thực phẩm (P3) | Loại công thức có nhóm dị ứng tương ứng; "Shellfish" mở rộng thêm nhuyễn thể | Lọc | Hồ sơ, [15] |
| Mọi bệnh nhân (mặc định) | Natri < 2 g/ngày | Lọc | WHO [21] |
| Mọi bệnh nhân (mặc định) | Đường < 10% năng lượng (dữ liệu chỉ có tổng đường) | Cảnh báo | WHO [22] |
| Tăng huyết áp | Natri ≤ 2.300 mg/ngày (bị ngưỡng mặc định 2 g chặt hơn thay thế); chất béo bão hòa ≤ 6% năng lượng | Lọc natri; xếp hạng và cảnh báo chất béo bão hòa | DASH [23] |
| Tiểu đường típ 2 | Chất xơ ≥ 14 g/1.000 kcal; natri < 2.300 mg/ngày | Xếp hạng và cảnh báo chất xơ; lọc natri | ADA [25] |
| Bệnh thận mạn | Natri < 2 g/ngày | Lọc | KDIGO [24] |
| Bệnh thận mạn giai đoạn 3–4 | Đạm ≤ 0,8 g/kg/ngày (cần cân nặng từ P6); kali và phốt pho | Lọc đạm; cảnh báo kali và phốt pho | KDIGO [24] |
| Đang dùng warfarin | Giữ lượng vitamin K ổn định (rau cải xoăn, rau bina, bông cải…) | Cảnh báo, không loại | Bảng tương tác do nhóm soạn |
| Đang dùng simvastatin hoặc atorvastatin | Loại công thức có bưởi chùm | Lọc | Bảng tương tác do nhóm soạn |

Bộ luật cần ba quy ước thiết kế, và nhóm ghi rõ cả ba là quyết định của đồ án chứ không phải khuyến nghị lâm sàng. Quy ước thứ nhất là đổi ngưỡng theo ngày thành ngưỡng một bữa: một khẩu phần không được vượt một phần ba giới hạn ngày, ví dụ natri 2 g/ngày tương ứng khoảng 667 mg mỗi khẩu phần; ngưỡng tính theo tỉ lệ năng lượng được tính trên calo của chính công thức. Một ngưỡng mà nếu dùng để lọc sẽ chỉ còn dưới một nửa kho công thức (chất béo bão hòa 6% năng lượng, chất xơ 14 g/1.000 kcal) được chuyển thành ràng buộc mềm: dùng để xếp hạng và cảnh báo thay vì loại. Quy ước thứ hai là xử lý ngưỡng theo cân nặng: nếu hồ sơ không có cân nặng gần đây, hệ chỉ cảnh báo mà không lọc. Quy ước thứ ba là xử lý mâu thuẫn khi bệnh nhân mắc nhiều bệnh: hệ áp dụng ngưỡng chặt hơn cho mỗi chất và hiển thị cảnh báo về các chất mà luật của các bệnh không thống nhất. Bảng tương tác thuốc và thực phẩm được giữ ở quy mô nhỏ, có phiên bản và cần chuyên gia xác nhận trước khi dùng ngoài môi trường thực nghiệm.

### 3.4.2. Nhánh hội thoại và truy hồi công thức

Module đầu tiên (M1) đảm nhận việc hiểu truy vấn. Mô hình ngôn ngữ đọc câu hỏi cùng lịch sử hội thoại và trả về một đối tượng JSON theo lược đồ định trước, gồm ý định (tìm mới, tinh chỉnh, hỏi chi tiết, hỏi về bệnh nhân, trò chuyện, ngoài phạm vi), câu truy vấn tiếng Anh độc lập ngữ cảnh, các ràng buộc như nhóm dị ứng cần tránh, nguyên liệu cần loại, chế độ ăn và thời gian tối đa, cùng các trường cho biết ràng buộc nào giữ lâu dài và ràng buộc nào người dùng muốn gỡ (lược đồ ở Phụ lục C). Câu truy vấn tiếng Anh được cố ý viết không chứa phủ định, vì phủ định chỉ được xử lý ở bộ lọc. Kết quả của mô hình sau đó được hậu xử lý bằng từ điển tiếng Việt – tiếng Anh để ánh xạ tên nguyên liệu về dạng chuẩn và loại bỏ các giá trị không hợp lệ. Với riêng ràng buộc dị ứng, kết quả của mô hình được hợp với kết quả tra từ điển trên câu gốc, vì thêm thừa một ràng buộc chỉ làm mất vài món còn bỏ sót thì nguy hiểm. Khi câu hỏi cần thông tin cũ trong hồ sơ, M1 bật cờ để V2 mở nút theo ngữ cảnh.

Module thứ hai (M2) quản lý trạng thái phiên. Trạng thái gồm hai lớp: ràng buộc từ hồ sơ (C_E) và ràng buộc từ hội thoại (C_t^dlg). Ràng buộc từ hồ sơ có hiệu lực trong suốt phiên và chỉ được gỡ khi người dùng chuyên môn xác nhận rõ trên giao diện, không thể bị gỡ bởi một câu nói mơ hồ trong hội thoại; khi người dùng cố gỡ bằng lời, hệ giữ ràng buộc và giải thích lý do. Ràng buộc dị ứng do người dùng nêu có hiệu lực cho tới khi người dùng gỡ bỏ, còn các ràng buộc tạm thời chỉ áp dụng cho lượt hiện tại. Trạng thái được lưu theo mã phiên, tách biệt giữa các người dùng. Module thứ ba (M3) định tuyến theo ý định: câu hỏi ngoài phạm vi được từ chối lịch sự, câu hỏi mơ hồ được hỏi lại, câu hỏi chi tiết về một món đã gợi ý được trả lời trực tiếp từ cơ sở dữ liệu, câu hỏi về thông tin bệnh nhân được trả lời từ các nút hồ sơ đã đọc, còn lại được chuyển sang truy hồi.

Module thứ tư (M4) truy hồi có lọc cứng. Ràng buộc hợp nhất C_t được chuyển thành điều kiện WHERE trên thẻ đã chuẩn hóa để loại trước mọi công thức chứa nhóm dị ứng hoặc nguyên liệu bị cấm, sai chế độ ăn, quá thời gian hoặc vượt ngưỡng dinh dưỡng, rồi mới chạy truy hồi lai BM25, dense và RRF như A1. Module thứ năm (M5) xếp hạng lại bằng cross-encoder mxbai-rerank-base-v1, mô hình đã cho kết quả tốt nhất trong ablation của A1, gom các chunk về cấp công thức để tránh hiện tượng chunk mất ngữ cảnh, cộng điểm phạt cho các ràng buộc mềm của hồ sơ, và chọn năm công thức tốt nhất đưa vào ngữ cảnh. Module thứ sáu (M6) sinh câu trả lời với prompt yêu cầu mô hình chỉ dùng thông tin trong ngữ cảnh, trả lời bằng ngôn ngữ của người hỏi, trích dẫn từng món bằng mã công thức và trích dẫn ràng buộc bằng mục hồ sơ tương ứng, trả lời "không tìm thấy" khi ngữ cảnh rỗng và không khẳng định món ăn an toàn tuyệt đối cho người dị ứng. Khi không có công thức thỏa, M6 gợi ý nới các ràng buộc mềm như thời gian hay loại món, và không bao giờ đề xuất nới ràng buộc dị ứng hay ràng buộc từ hồ sơ. Module cuối cùng (M7) hậu kiểm một cách tất định: mọi mã công thức được trích phải nằm trong ngữ cảnh, không công thức nào được trích được phép vi phạm trạng thái ràng buộc hợp nhất, văn bản sinh ra không được gợi ý thêm nguyên liệu thuộc nhóm bị cấm, và khi trả lời về bệnh nhân thì mọi con số phải khớp với hồ sơ. Nếu vi phạm, trích dẫn lỗi bị loại bỏ và câu trả lời được sinh lại một lần; nếu vẫn vi phạm, hệ bỏ các câu vi phạm hoặc thay bằng câu trả lời do code liệt kê. Mỗi module có cờ bật tắt riêng, nhờ đó mọi cấu hình ablation ở Chương 4 chạy trên cùng một mã nguồn.

Theo thiết kế trên, mô hình ngôn ngữ chỉ xuất hiện ở năm vị trí: viết tóm tắt nút lịch sử (V1), chọn nút theo ngữ cảnh (V2), hiểu truy vấn (M1), sinh câu trả lời (M6), và ngoài hệ thống là sinh câu hỏi test và chấm điểm khi đánh giá. Mọi bước quyết định công thức nào an toàn, gồm đọc nút cố định, ánh xạ luật, lọc, xếp hạng và hậu kiểm, đều là tất định.

## 3.5. Thiết kế cơ sở dữ liệu

Cơ sở dữ liệu giữ nguyên lược đồ chuẩn hóa của A1 cho công thức, danh mục, tác giả, dinh dưỡng, nguyên liệu thô và chunk (phân vùng theo chiến lược chunking), rồi bổ sung ba nhóm bảng mới (Hình 3.3). Nhóm thứ nhất phục vụ tri thức nguyên liệu: bảng nguyên liệu chuẩn (`ingredient`) kèm bí danh tiếng Việt (`ingredient_alias_vi`), bảng liên kết dòng nguyên liệu thô với nguyên liệu chuẩn (`recipe_ingredient_norm`), bảng nhóm dị ứng (`allergen`), bảng ánh xạ nguyên liệu – dị ứng (`ingredient_allergen`), và bảng thẻ tổng hợp của từng công thức (`recipe_tag`). Nhóm thứ hai phục vụ hồ sơ bệnh nhân: bảng bệnh nhân (`patient`: mã Synthea, nguồn, ngày hồ sơ), bảng nút của cây hồ sơ (`patient_node`: nút cha, loại nút cố định hay theo ngữ cảnh, tóm tắt, dữ kiện và tham chiếu tới entry gốc), và bảng lưu đệm hồ sơ ràng buộc (`patient_profile_cache`, theo phiên bản bộ luật). Nhóm thứ ba phục vụ hội thoại và vận hành: bảng phiên hội thoại (`chat_session`, có mã bệnh nhân tùy chọn), bảng tin nhắn (`chat_message`), bảng ràng buộc của phiên (`session_constraint`: nguồn, phạm vi hiệu lực và tin nhắn tạo ra ràng buộc), bảng gỡ ràng buộc hồ sơ có xác nhận (`session_record_lift`), bảng truy vết từng bước của pipeline kèm độ trễ (`retrieval_trace`), và bảng phản hồi của người dùng (`feedback`).

![Hình 3.3. Lược đồ cơ sở dữ liệu (các bảng mới của A3)](figures/fig_erd.png)

## 3.6. Thiết kế API

Hệ thống cung cấp dịch vụ qua REST API. Điểm truy cập chính là `POST /chat`, nhận tin nhắn của người dùng cùng mã phiên, cấu hình và mã bệnh nhân tùy chọn, và trả kết quả theo cơ chế Server-Sent Events gồm năm loại sự kiện nối tiếp: hồ sơ ràng buộc từ bệnh án (nếu có), ràng buộc hệ đã hiểu từ câu hỏi, danh sách công thức truy hồi được, từng phần câu trả lời, và sự kiện kết thúc chứa câu trả lời cuối, danh sách trích dẫn, số token sử dụng và độ trễ của từng bước (Hình 3.4). Nhóm điểm truy cập hồ sơ gồm `GET /patients` để liệt kê bệnh nhân, `GET /patients/{id}/tree` để xem cây mục lục, và `GET /patients/{id}/profile` để xem hồ sơ ràng buộc kèm bằng chứng. Hồ sơ được nạp và dựng cây offline bằng script. Các điểm truy cập phụ cho phép xem và đổi cấu hình của phiên (`GET/PATCH /sessions/{id}`), gỡ một ràng buộc (`PATCH /chat/{session}/constraints/{id}`, với ràng buộc từ hồ sơ bắt buộc có xác nhận), xem chi tiết công thức, gửi phản hồi và kiểm tra trạng thái hệ thống. Các điểm truy cập tìm kiếm của A1 được giữ lại để phục vụ so sánh.

![Hình 3.4. Trình tự xử lý một lượt POST /chat](figures/fig_sequence.png)

## 3.7. Thiết kế giao diện

Giao diện chuyển trọng tâm sang chatbox. Mỗi câu trả lời hiển thị dưới dạng streaming, kèm các thẻ công thức gắn với trích dẫn, trên đó có tiêu đề, thời gian chế biến, các nhóm dị ứng, các chỉ số dinh dưỡng liên quan và nút xem chi tiết. Một panel bên cạnh hiển thị các ràng buộc hệ đang áp dụng dưới dạng chip, chia thành hai nhóm. Nhóm ràng buộc từ hồ sơ có biểu tượng khóa, được gom theo mục dị ứng gốc và mở được bằng chứng trong hồ sơ; muốn gỡ phải xác nhận. Nhóm ràng buộc từ hội thoại có thể xóa trực tiếp. Panel này giúp hệ minh bạch, đồng thời cho người dùng tự sửa khi bước hiểu truy vấn sai. Ở chế độ chuyên môn, đầu trang có bộ chọn bệnh nhân. Giao diện luôn hiển thị banner nhắc rằng công cụ chỉ hỗ trợ chọn món, không thay lời khuyên y tế, và người dùng cần kiểm tra nhãn nguyên liệu trước khi nấu (Hình 3.5).

![Hình 3.5. Giao diện chatbox với bệnh nhân đã chọn](figures/fig_ui_chat.png)

## 3.8. An toàn, quyền riêng tư và đạo đức

Do bài toán liên quan trực tiếp đến sức khỏe, nhóm nhận diện năm rủi ro chính. Thứ nhất, bộ gắn thẻ có thể bỏ sót chất gây dị ứng ẩn, và rủi ro này được định lượng bằng recall trên tập 200 công thức có nhãn bạc (nhãn do mô hình gán mù theo hướng dẫn của nhóm). Thứ hai, nguy cơ nhiễm chéo trong chế biến nằm ngoài khả năng của dữ liệu. Thứ ba, mô hình ngôn ngữ có thể thêm nguyên liệu không có trong công thức, và rủi ro này được giảm bằng bước hậu kiểm và đo bằng faithfulness. Thứ tư, nhánh hồ sơ có thể bỏ sót hoặc hiểu sai một ràng buộc; rủi ro này được giảm bằng việc đọc nút cố định bằng code thay vì để mô hình chọn, và được định lượng bằng recall so với đáp án của Synthea. Thứ năm, bộ luật ánh xạ là sự đơn giản hóa các hướng dẫn lâm sàng; các ngưỡng một bữa và bảng tương tác thuốc là quy ước của đồ án, chưa được chuyên gia y khoa thẩm định.

Về quyền riêng tư, đồ án chỉ dùng hồ sơ tổng hợp nên không có dữ liệu của người thật. Dù vậy, hệ vẫn được thiết kế như thể xử lý dữ liệu thật: chỉ những mục liên quan ăn uống mới đi vào ngữ cảnh mô hình (quy tắc P7), mọi xử lý chạy cục bộ, và nhật ký dùng cho đánh giá không lưu mã phiên thật. Nếu sau này dùng bệnh án thật như MIMIC-IV, nhóm phải hoàn tất thủ tục chứng nhận, khóa đào tạo CITI và thỏa thuận sử dụng dữ liệu, và việc chạy mô hình cục bộ qua Ollama giúp dữ liệu không rời khỏi máy. Nội dung công thức và nội dung hồ sơ chỉ được coi là dữ liệu chứ không phải chỉ dẫn, nhằm phòng tấn công chèn lệnh vào prompt. Cuối cùng, corpus là công thức của Mỹ nên các món Việt hầu như không có, và hệ phải trả lời không tìm thấy thay vì bịa ra công thức.
