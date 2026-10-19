# Chương 6. Kết luận và hướng phát triển

## 6.1. Trả lời các câu hỏi nghiên cứu

Với RQ1, hiểu truy vấn kết hợp lọc cứng giảm tỉ lệ công thức vi phạm ràng buộc so với hệ Hybrid của A1 từ 67,5% xuống 2,7% trên tập ràng buộc một lượt và từ 48,6% xuống 5,7% trên tập hội thoại, đồng thời tăng nDCG@10′ trên tập ràng buộc từ 0,21 lên 0,80 và không hồi quy trên tập của A1. Khi ràng buộc đến từ hồ sơ bệnh nhân, hệ đạt Safe@5 theo dị ứng 99% và theo ngưỡng dinh dưỡng 100%, so với 81% và 36% khi không dùng hồ sơ.

Với RQ2, hai thành phần quyết định là hiểu truy vấn và lọc cứng: tắt một trong hai thì tỉ lệ vi phạm quay về mức của A1. Xếp hạng lại cải thiện nhẹ chất lượng xếp hạng; chuẩn hóa nguyên liệu và trạng thái hội thoại có xu hướng giảm vi phạm trong hội thoại nhưng chưa có ý nghĩa thống kê trên mẫu hiện tại; hậu kiểm chủ yếu nâng độ an toàn của trích dẫn.

Với RQ3, trích dẫn gần như luôn hợp lệ (100,0%) và an toàn (98,5%), hệ từ chối đúng 4/6 câu không trả lời được và hiếm khi từ chối sai (1/27). Tuy nhiên nội dung chữ của câu trả lời chỉ bám ngữ cảnh ở 68% số câu theo nhãn của người: mô hình 7B hay tự khẳng định thuộc tính an toàn không có trong dữ liệu. Đây là điểm yếu lớn nhất của hệ.

Với RQ4, các bước lọc, truy hồi lai và xếp hạng lại chỉ tốn vài trăm mili giây như A1; gần như toàn bộ độ trễ khoảng 21.964 ms mỗi lượt của S nằm ở hai lời gọi mô hình 7B chạy cục bộ. Đánh đổi chính vì vậy là giữa mức độ hiểu ngôn ngữ và tài nguyên phần cứng, không phải giữa an toàn và tốc độ truy hồi.

Với RQ5, trên hồ sơ có mã, nhánh vectorless trích đúng toàn bộ dị ứng, bệnh và thuốc như việc đọc trực tiếp trường có cấu trúc, với trung bình dưới một lời gọi mô hình mỗi lượt, trong khi RAG vector trên chính hồ sơ chỉ đạt recall dị ứng 14,3%. Yếu tố quyết định là đọc các mục cố định bằng code: khi để mô hình chọn cả các mục này, recall dị ứng giảm còn 34,9%. Trên văn bản tự do, vectorless vẫn tốt nhất nhưng còn bỏ sót dị ứng ở 3 bệnh nhân.

## 6.2. Hạn chế

Về dữ liệu và nhãn, corpus chỉ gồm công thức của Mỹ bằng tiếng Anh nên hầu như không có món Việt, và thông tin dị ứng được suy ra từ nguyên liệu nên không phản ánh nhiễm chéo. Hồ sơ bệnh nhân là dữ liệu tổng hợp ở định dạng C-CDA, sạch hơn bệnh án thật, nên kết quả trích ràng buộc là cận trên; hệ chưa được thử trên FHIR, trên ghi chú lâm sàng thật hay trên một tập ghi chú tổng hợp độc lập. Nhãn của 200 công thức dùng để đo bộ gắn thẻ và bộ kiểm là nhãn bạc do mô hình gán; vì bộ gắn thẻ và mô hình gán nhãn cùng họ, precision và recall của bộ gắn thẻ có thể bị đánh giá cao hơn thực tế. Ràng buộc chuẩn của bộ test do mô hình soạn và thành viên nhóm xác nhận, phần lớn theo nhóm.

Về công cụ đo, judge độ liên quan chỉ khớp vừa phải với người (κ = 0,30) nên nDCG@10′ là ước lượng thô, và judge faithfulness không dùng được (κ = −0,02) nên faithfulness được báo cáo theo nhãn của người trên mẫu nhỏ. Bộ kiểm độc lập có xu hướng báo thừa; điều này đã được bù bằng hàng duyệt của người, nhưng 59 trên 649 phiếu của bộ kiểm vẫn lỗi do mô hình trả lời lặp và được tính là không vi phạm (phần lớn nằm trong ngữ cảnh của B0, nên kết luận S so với B0 không đổi).

Về quy mô thực nghiệm, bộ test A3 chỉ được chạy trên mẫu khoảng 10% (363 lượt), nên khoảng tin cậy rộng và một số ablation chỉ là xu hướng. Mọi thực nghiệm chạy trên một máy GPU laptop, và độ trễ của các cấu hình ablation bị ảnh hưởng bởi bộ đệm dùng chung.

Về hệ thống, hậu kiểm M7 chưa kiểm các khẳng định thuộc tính an toàn trong lời văn. Một số lỗi đã biết được giữ lại và ghi nhận: bộ tách nguyên liệu đọc sai một số dòng ghép bằng dấu phẩy, hậu kiểm báo động nhầm ở vài câu, câu trả lời đôi khi sai ngôn ngữ, và một ràng buộc nguyên liệu có thể còn sót lại sau khi gỡ dị ứng hồ sơ tương ứng. Bộ luật ánh xạ (ngưỡng một bữa, bảng tương tác thuốc) là quy ước của đồ án và chưa được chuyên gia y khoa thẩm định; hồ sơ được nạp offline bằng script, chưa có điểm truy cập nạp hồ sơ qua API.

## 6.3. Hướng phát triển

Hướng thứ nhất là giảm lỗi bịa thuộc tính an toàn, bằng cách mở rộng hậu kiểm sang các khẳng định "không có X" đối chiếu với thẻ, hoặc để code viết phần mô tả an toàn từ thẻ thay cho mô hình. Hướng thứ hai là mở rộng nhánh hồ sơ sang FHIR R4 và nạp hồ sơ qua API, rồi đánh giá trên ghi chú lâm sàng độc lập. Hướng thứ ba là cá nhân hóa bằng hồ sơ người dùng dài hạn và bổ sung đồ thị tri thức nguyên liệu để xử lý thành phần ẩn tốt hơn. Hướng thứ tư là mở rộng corpus món Việt. Hướng cuối cùng là tối ưu hiệu năng phục vụ, chẳng hạn dùng mô hình nhỏ hơn cho bước hiểu truy vấn và lưu đệm prompt, và chạy thực nghiệm trên toàn bộ bộ test với nhãn liên quan do người gán.
