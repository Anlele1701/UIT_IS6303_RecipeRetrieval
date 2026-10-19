# Chương 5. Triển khai và demo

## 5.1. Triển khai

Hệ thống chạy hoàn toàn cục bộ. ParadeDB chạy trong Docker Compose với project và volume riêng của A3, tách khỏi môi trường của A1. Ollama phục vụ ba mô hình: qwen2.5:7b cho hiểu truy vấn, chọn nút hồ sơ và sinh câu trả lời; llama3.1:8b cho bộ kiểm độc lập và judge khi đánh giá; nomic-embed-text cho embedding. Mô hình xếp hạng lại mxbai-rerank-base-v1 chạy trong tiến trình của API bằng PyTorch có CUDA. Backend là FastAPI quản lý bằng uv; giao diện là React, Vite và Tailwind kế thừa từ A1, gồm ba trang: chatbox (`/chat`), tìm kiếm nâng cao và báo cáo kết quả.

Quy trình dựng lại gồm năm bước, được mô tả chi tiết trong `GETTING_STARTED.md` của repo: khởi động cơ sở dữ liệu và áp các migration; tải các mô hình qua Ollama; chạy pipeline dữ liệu (`scripts/ingest.py`, `scripts/tag.py`) để tạo kho công thức, chunk, chỉ mục và thẻ; nạp hồ sơ bệnh nhân (`scripts/patient_ingest.py`) để dựng cây và tóm tắt nút; rồi chạy API và giao diện. Các thực nghiệm chạy lại bằng `scripts/eval_a3.py` (bộ test A3) và `scripts/eval_patient.py` (nhánh hồ sơ); mỗi lần chạy ghi thiết lập, commit, seed và thông tin máy vào thư mục kết quả riêng. Bộ test và bộ câu hỏi hồ sơ được kiểm tra sha256 trước mỗi lần chạy để bảo đảm không bị sửa sau khi đóng băng.

## 5.2. Kịch bản demo

Buổi demo gồm năm kịch bản, mỗi kịch bản chạy trên giao diện chatbox với trang truy vết mở bên cạnh để thấy từng bước của pipeline.

Kịch bản thứ nhất là một câu hỏi tiếng Việt có ràng buộc dị ứng, chẳng hạn xin món tráng miệng cho người dị ứng đậu phộng. Cùng câu hỏi được chạy ở cấu hình B0 (A1) và S: B0 trả về các món có đậu phộng hoặc bơ đậu phộng trong top 5, còn S hiển thị chip "dị ứng: đậu phộng" và chỉ trả về món không chứa nhóm này, kèm trích dẫn.

Kịch bản thứ hai là hội thoại ba lượt có bổ sung ràng buộc: người dùng hỏi món chay, sau đó thêm "không có nấm", rồi "dưới 30 phút". Mỗi lượt thêm một chip, và các ràng buộc của lượt trước vẫn được áp dụng.

Kịch bản thứ ba là một câu hỏi không có đáp án, ví dụ một tổ hợp ràng buộc mâu thuẫn hoặc một món Việt không có trong corpus. Hệ trả lời không tìm thấy, gợi ý nới ràng buộc mềm, và không bịa công thức.

Kịch bản thứ tư là người dùng sửa ràng buộc: xóa một chip hội thoại và quan sát danh sách công thức thay đổi ở lượt sau.

Kịch bản thứ năm dành cho người dùng chuyên môn: chọn một bệnh nhân có dị ứng hải sản và tăng huyết áp, rồi hỏi "gợi ý bữa tối" mà không nhắc ràng buộc nào. Panel hiển thị các chip có khóa sinh ra từ hồ sơ (giáp xác và nhuyễn thể, natri một bữa) kèm bằng chứng là dòng trong mục Dị ứng và Vấn đề đang điều trị. Khi người dùng gõ "bỏ qua dị ứng đi", hệ giữ nguyên ràng buộc và giải thích rằng ràng buộc từ hồ sơ chỉ gỡ được bằng xác nhận trên giao diện. Cuối cùng, câu hỏi "gần đây huyết áp của bệnh nhân thế nào" được trả lời từ nút sinh hiệu, với mọi con số khớp hồ sơ.
