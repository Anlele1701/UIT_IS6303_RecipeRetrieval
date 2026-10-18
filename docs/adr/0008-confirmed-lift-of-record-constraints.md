---
status: proposed (MV5, 18/10/2026; chờ Thy duyệt ở gate MV5)
---

# Ràng buộc từ hồ sơ bệnh nhân chỉ được gỡ bằng xác nhận trên giao diện, có lưu vết theo phiên

Một ràng buộc trong hồ sơ (ví dụ dị ứng giáp xác) là dữ liệu y tế. Một câu chat như "tôi ăn được tôm rồi" có thể là lời người dùng nói thật, nhưng cũng có thể là M1 hiểu sai, hoặc người dùng nói về người khác. Đặc tả (mục 5.6) đã chốt: tin nhắn chat không gỡ được ràng buộc hồ sơ, chỉ `PATCH` có `confirm=true` mới gỡ. MV3 đã làm phần chặn. MV5 làm phần gỡ.

**Quyết định:**
1. **Ràng buộc hồ sơ có một id ổn định:** `allergen:<nhóm>`, `ingredient:<tên>`, `nutrient:<cột>`, `soft:<cột>`. Đây cũng là khóa bằng chứng của `PatientProfile` (`api/patient/models.constraint_ids`), nên UI gắn được chip với bằng chứng `[H:node_id]`.
2. **Gỡ phải có `confirm=true`**, và id phải là một ràng buộc mà hồ sơ thật sự sinh ra. Sai một trong hai thì `RecordLiftRefused` (UI trả 409).
3. **Lưu vết:** mỗi lần gỡ là một dòng `session_record_lift(session_id, constraint_id, reason, confirmed_at)` (migration 009). Không sửa hay xóa hồ sơ, luật, hay cache hồ sơ.
4. **Phạm vi là một phiên.** Phiên mới về cùng bệnh nhân lại có đủ ràng buộc từ hồ sơ.
5. **Một chỗ áp dụng:** mỗi lượt, orchestrator lấy hồ sơ hiệu lực bằng `without(profile, lifted)`. M2 (state), M4 (lọc), M6 (khối `PATIENT_PROFILE`) và M7 (kiểm tra) đều đọc hồ sơ này, nên một mục đã gỡ biến mất khỏi mọi bước cùng lúc. `merge` vẫn là hàm thuần.
6. Người dùng **vẫn thêm lại được** ràng buộc bằng lời ("tôi dị ứng tôm"); khi đó nó là ràng buộc hội thoại.
7. **UI gom theo bằng chứng.** Một dòng dị ứng có thể sinh nhiều ràng buộc (giáp xác cộng 20 nguyên liệu nhuyễn thể). UI gỡ cả nhóm bằng nhiều lời gọi PATCH, mỗi lời gọi một id.

**Hệ quả:**
- Mọi lần gỡ đều truy được: ai gỡ (theo phiên), gỡ gì, vì sao, lúc nào.
- Chưa có danh tính người gỡ: M4 chưa có đăng nhập. Nếu sau này có, thêm cột `confirmed_by`.
- Sự kiện `patient_profile` có thêm trường `lifted`. Hợp đồng ở `docs/plan/A3_ke_hoach_build.md` mục 6.5.3.
