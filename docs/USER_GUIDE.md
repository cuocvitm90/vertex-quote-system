# HƯỚNG DẪN SỬ DỤNG HỆ THỐNG BÁO GIÁ THÔNG MINH VERTEX PCCC

Hệ thống được thiết kế tối ưu cho các kỹ sư QS và nhân viên kinh doanh để xử lý nhanh các gói thầu PCCC và M&E. Dưới đây là các bước thao tác chi tiết từ lúc nhận hồ sơ đến khi xuất báo giá hoàn chỉnh:

---

## Bước 1: Chọn phương thức tiếp nhận đầu vào (3 Tab Nghiệp Vụ)
Ngay tại giao diện chính, tùy thuộc vào hình thức hồ sơ do Chủ đầu tư (CĐT) cung cấp, hãy chọn một trong 3 tab phù hợp:
* **Tab 1: Bốc Tách CAD/BIM**
  * *Áp dụng khi:* Có bản vẽ thiết kế thi công dạng `.dwg`, `.dxf` hoặc mô hình Revit.
  * *Thao tác:* Kéo thả trực tiếp file bản vẽ vào vùng tải lên. Hệ thống sẽ tự động quét, bốc khối lượng và phân loại chi tiết các hạng mục (Hệ thống Sprinkler, chữa cháy vách tường, báo cháy, ống gió hút khói/tăng áp...).
* **Tab 2: Nhập BOQ & Chỉ Định Hãng**
  * *Áp dụng khi:* CĐT cung cấp sẵn file BOQ kèm theo các yêu cầu kỹ thuật hoặc nhãn hiệu cụ thể (ví dụ: Bơm Ebara, Van ARV, Cáp Cadisun...).
  * *Thao tác:* Tải lên file BOQ (Excel/CSV). Hệ thống tự động đọc các thông số (cột áp, lưu lượng, chủng loại) và map chính xác tên hãng theo đúng yêu cầu hồ sơ thầu.
* **Tab 3: Nhập BOQ Thuần & Đề Xuất**
  * *Áp dụng khi:* Chào giá cạnh tranh tự do, không bị ràng buộc thương hiệu từ CĐT.
  * *Thao tác:* Tải lên file BOQ thô. Hệ thống sẽ tự động đối chiếu với danh mục **Vertex Standard Catalog** để đề xuất các hãng vật tư tối ưu nhất về chi phí.

---

## Bước 2: Kiểm tra định mức vật tư, hao hụt & nhân công
* Sau khi dữ liệu hiển thị trên bảng chi tiết, hệ thống tự động áp dụng bộ đơn giá nhân công khoán thực tế theo chuẩn của công ty:
  * *Ống chữa cháy:* **220.000 VNĐ / mét (m)**
  * *Thiết bị báo cháy:* **350.000 VNĐ / thiết bị**
  * *Đèn Exit / sự cố:* **370.000 VNĐ / thiết bị**
  * *Ống gió thường:* **100.000 VNĐ / m²**
  * *Ống gió chống cháy (EI 30, EI 45, EI 60):* **130.000 VNĐ / m²**
  * *Ống gió chống cháy (EI 120):* **155.000 VNĐ / m²**
* Kiểm tra tỷ lệ phụ kiện, quang treo và tùy chỉnh hệ số hao hụt trực tiếp trên từng dòng vật tư nếu cần.

---

## Bước 3: Cấu hình thông tin thương mại & tính giá
* Điền đầy đủ thông tin khách hàng, tên dự án, địa chỉ công trình, tỷ lệ chiết khấu thương mại và thuế suất VAT (mặc định 8%).
* Hệ thống tự động tổng hợp công thức: `Giá gốc (Vật tư + Nhân công) x Hệ số thương mại` để ra đơn giá và thành tiền chính xác.

---

## Bước 4: Trình duyệt tự động & Xuất file báo giá
* **Trình duyệt đa cấp qua Zalo OA:** Bấm hoàn tất để hệ thống sinh mã báo giá và chuyển sang trạng thái phê duyệt:
  * *Báo giá tiêu chuẩn (dưới hạn mức, chiết khấu thông thường):* Trưởng phòng kinh doanh (Anh Việt) duyệt trực tiếp.
  * *Báo giá lớn (≥ 100 triệu) hoặc vượt hạn mức:* Hệ thống tự động đẩy thông báo chờ duyệt qua Zalo OA đến Giám đốc (Sếp Tiến) phê duyệt.
* **Xuất file Excel:** Sau khi báo giá được phê duyệt thành công, bấm nút **Xuất File Excel BOQ** để tải xuống bảng tính chi tiết (tách bạch rõ chi phí vật tư, nhân công và cột Hãng SX / Xuất xứ) để gửi khách hàng.
