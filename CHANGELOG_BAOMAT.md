# NHẬT KÝ KHẮC PHỤC LỖ HỔNG BẢO MẬT (SECURITY FIX CHANGELOG)
**Hệ thống Báo Giá Thông Minh & Quản Trị Hiện Trường Vertex (Vertex Construction & PCCC)**  
*Ngày thực hiện:* 29/08/2026  
*Tiêu chuẩn đối chiếu:* OWASP Top 10, NIST SP 800-53, CWE Top 25

---

## TỔNG QUAN KẾT QUẢ KHẮC PHỤC

| Mã Lỗi | Tên Lỗ Hổng & Phân Loại | Mức Độ | Trạng Thái | Commit ID | File Sửa Đổi |
| :--- | :--- | :---: | :---: | :---: | :--- |
| **VULN-01** | Missing Authentication / Signature on Quick Approval Link (CWE-306) | **CRITICAL** | **ĐÃ FIX** | `e82c370` | [`app/services/auth.py`](file:///f:/vertex-quote-system/app/services/auth.py), [`app/routers/quotes.py`](file:///f:/vertex-quote-system/app/routers/quotes.py) |
| **VULN-02** | Zalo Webhook Signature Bypass & Unprotected Simulator (CWE-287) | **CRITICAL** | **ĐÃ FIX** | `e82c370` | [`app/services/zalo_service.py`](file:///f:/vertex-quote-system/app/services/zalo_service.py), [`app/routers/zalo_webhook.py`](file:///f:/vertex-quote-system/app/routers/zalo_webhook.py) |
| **VULN-03** | Hardcoded AI API Secret Key in Source Code (CWE-798) | **HIGH** | **ĐÃ FIX** | `166771d` | [`app/config.py`](file:///f:/vertex-quote-system/app/config.py), [`main.py`](file:///f:/vertex-quote-system/main.py) |
| **VULN-04** | Insecure Direct Object References (IDOR) on Quote APIs (CWE-639) | **HIGH** | **ĐÃ FIX** | `24aa647` | [`app/dependencies.py`](file:///f:/vertex-quote-system/app/dependencies.py), [`app/routers/quotes.py`](file:///f:/vertex-quote-system/app/routers/quotes.py) |
| **VULN-05** | Stored Cross-Site Scripting (XSS) in HTML Approval Screen (CWE-79) | **HIGH** | **ĐÃ FIX** | `c8ee27f` | [`app/routers/quotes.py`](file:///f:/vertex-quote-system/app/routers/quotes.py) |
| **VULN-06** | Overly Permissive CORS Policy with Credentials (CWE-942) | **MEDIUM** | **ĐÃ FIX** | `d19e095` | [`main.py`](file:///f:/vertex-quote-system/main.py) |

---

## CHI TIẾT TỪNG BƯỚC KHẮC PHỤC & KIỂM THỬ

### 1. FIX 1: HMAC Token Phê Duyệt & Khóa Chặt Zalo Webhook (VULN-01 + VULN-02)
* **Vấn đề trước khi sửa:** 
  - Kẻ tấn công hoặc bot mạng quét link `GET /api/quotes/{id}/approve` có thể tự động phê duyệt khống báo giá mà không cần quyền.
  - Hàm `verify_webhook_signature` trả về `True` khi thiếu secret hoặc chữ ký Zalo.
  - Endpoint `/simulate-approval` không yêu cầu quyền Admin/Manager.
* **Giải pháp thực hiện:**
  - Viết hàm `generate_approval_token(quote_id, action, secret_key, expire_minutes)` và `verify_approval_token(...)` sử dụng HMAC-SHA256 kết hợp timestamp hết hạn (mặc định 60 phút).
  - Cập nhật endpoint `GET /api/quotes/{quote_id}/approve`: Bắt buộc truyền `?token=...`, kiểm tra chữ ký HMAC và raise `401 Unauthorized` nếu token thiếu/sai/hết hạn.
  - Hàm `verify_webhook_signature` mặc định trả về `False` khi thiếu chữ ký, chỉ cho phép bypass khi `APP_ENV == "development"` VÀ có biến môi trường `ALLOW_UNSIGNED_WEBHOOK=true`.
  - Khóa endpoint `/simulate-approval`: Bắt buộc quyền Manager/Admin và chặn hoàn toàn `HTTP 403 Forbidden` trên môi trường Production.
* **Test Case:** `test_security_hmac_approval_and_zalo_webhook` (Pass 100%).

---

### 2. FIX 2: Loại Bỏ Hardcoded Secret & Xác Thực Khởi Động Production (VULN-03)
* **Vấn đề trước khi sửa:**
  - Khóa API AI `gsk_...` bị gán cứng mặc định trong code `app/config.py`.
* **Giải pháp thực hiện:**
  - Chuyển `AI_API_KEY` thành `Field(default="", validation_alias="AI_API_KEY")` để đọc linh hoạt từ file `.env` hoặc hệ thống CI/CD/Kubernetes secrets.
  - Bổ sung kiểm tra an ninh trong hàm `lifespan` tại [`main.py`](file:///f:/vertex-quote-system/main.py): Nếu `APP_ENV == "production"` mà `SECRET_KEY` vẫn giữ giá trị mẫu hoặc `AI_API_KEY` bị rỗng, hệ thống sẽ chủ động ngắt tiến trình và raise `RuntimeError` ngay khi khởi động.
* **Test Case:** `test_security_production_startup_validation` (Pass 100%).

---

### 3. FIX 3: Ngăn Chặn Lỗ Hổng IDOR Bằng Dependency `can_access_quote` (VULN-04)
* **Vấn đề trước khi sửa:**
  - Người dùng có vai trò thấp (Đại lý `DEALER`, Đối tác `PARTNER`) có thể thay đổi `quote_id` trên URL để đọc trộm bảng giá, tải file Excel hoặc xem nhật ký bảo mật của đối thủ.
* **Giải pháp thực hiện:**
  - Xây dựng FastAPI Dependency chuẩn [`app/dependencies.py`](file:///f:/vertex-quote-system/app/dependencies.py) với hàm `can_access_quote`.
  - Phân quyền theo mô hình:
    - **Nội bộ (ADMIN, MANAGER, STAFF):** Toàn quyền truy cập nghiệp vụ báo giá của công ty.
    - **Bên ngoài (DEALER, PARTNER):** Bắt buộc phải là chủ sở hữu khởi tạo báo giá, khớp email/SĐT hoặc khớp tên đơn vị đối tác; nếu không sẽ trả về `HTTP 403 Forbidden`.
  - Áp dụng đồng bộ cho toàn bộ router báo giá: `GET /api/quotes/{id}`, `GET /api/quotes/{id}/download`, `GET /api/quotes/{id}/versions`, `GET /api/quotes/{id}/audit-logs`, `POST /api/quotes/{id}/revision`.
* **Test Case:** `test_security_idor_quote_access_protection` (Pass 100%).

---

### 4. FIX 4: Khử Nhiễm HTML & Chống Lỗ Hổng Stored XSS (VULN-05)
* **Vấn đề trước khi sửa:**
  - Trang HTML trả về sau khi duyệt (`approve_or_reject_quote_get`) nối trực tiếp chuỗi `customer_name`, `project_name`, `manager_name`, `reason` vào thẻ HTML khiến kẻ tấn công có thể chèn mã JavaScript độc hại.
* **Giải pháp thực hiện:**
  - Áp dụng `html.escape()` cho toàn bộ dữ liệu đầu vào người dùng trước khi render vào template HTML thông báo kết quả duyệt.
* **Test Case:** `test_security_xss_sanitization_in_approval_html` (Pass 100%).

---

### 5. FIX 5: Siết Chặt Chính Sách CORS Trên Môi Trường Production (VULN-06)
* **Vấn đề trước khi sửa:**
  - `CORSMiddleware` cấu hình `allow_origins=["*"]` kết hợp `allow_credentials=True`.
* **Giải pháp thực hiện:**
  - Trong [`main.py`](file:///f:/vertex-quote-system/main.py), khi chạy `APP_ENV == "production"`, chỉ cho phép `allow_origins=[settings.BASE_URL.rstrip("/")]` và giới hạn danh sách HTTP Methods rõ ràng (`GET, POST, PUT, DELETE, OPTIONS`).
* **Test Case:** `test_security_cors_configuration` (Pass 100%).

---

## KẾT QUẢ KIỂM THỬ TOÀN DIỆN (AUTOMATED TEST SUITE)

```text
============================= test session starts =============================
platform win32 -- Python 3.10.1, pytest-9.1.1, pluggy-1.6.0
rootdir: F:\vertex-quote-system
plugins: anyio-4.14.2
collected 39 items

tests/test_quote_system.py::test_auth_login_and_security PASSED          [  2%]
tests/test_quote_system.py::test_security_headers PASSED                 [  5%]
tests/test_quote_system.py::test_healthcheck_endpoint PASSED             [  7%]
tests/test_quote_system.py::test_jwt_route_protection PASSED             [ 10%]
tests/test_quote_system.py::test_file_validation_security PASSED         [ 12%]
tests/test_quote_system.py::test_user_registration_pending_and_admin_approval PASSED [ 15%]
tests/test_quote_system.py::test_pccc_catalog_lookup PASSED              [ 17%]
tests/test_quote_system.py::test_multilanguage_excel_and_i18n PASSED     [ 20%]
tests/test_quote_system.py::test_vietnamese_words_converter PASSED       [ 23%]
tests/test_quote_system.py::test_duct_area_calculator PASSED             [ 25%]
tests/test_quote_system.py::test_pure_python_financial_precision PASSED  [ 28%]
tests/test_quote_system.py::test_excel_extractor PASSED                  [ 30%]
tests/test_quote_system.py::test_cad_extractor PASSED                    [ 33%]
tests/test_quote_system.py::test_api_endpoints PASSED                    [ 35%]
tests/test_quote_system.py::test_gdrive_sync_endpoint PASSED             [ 38%]
tests/test_quote_system.py::test_master_template_and_coefficients_framework PASSED [ 41%]
tests/test_quote_system.py::test_ai_market_price_estimator_tool PASSED   [ 43%]
tests/test_quote_system.py::test_four_step_boq_pipeline_integration PASSED [ 46%]
tests/test_quote_system.py::test_cad_takeoff_standalone_module PASSED    [ 48%]
tests/test_quote_system.py::test_field_attendance_and_reports_module PASSED [ 51%]
tests/test_quote_system.py::test_field_personnel_dynamic_synchronization_from_user_management PASSED [ 53%]
tests/test_quote_system.py::test_geofencing_live_tracking_and_out_of_zone_alerts PASSED [ 56%]
tests/test_quote_system.py::test_quote_version_control_and_revisions PASSED [ 58%]
tests/test_quote_system.py::test_audit_trail_logging_and_retrieval PASSED [ 61%]
tests/test_quote_system.py::test_multilevel_approval_flow_and_matrix PASSED [ 64%]
tests/test_quote_system.py::test_cad_takeoff_engine_geometry_and_cross_checks PASSED [ 66%]
tests/test_quote_system.py::test_labor_cost_matrix PASSED                [ 69%]
tests/test_quote_system.py::test_commercial_pricing_output_formula PASSED [ 71%]
tests/test_quote_system.py::test_3_input_scenarios_and_brand_routing PASSED [ 74%]
tests/test_quote_system.py::test_quote_agent_end_to_end_3_scenarios PASSED [ 76%]
tests/test_quote_system.py::test_vietnamese_cad_text_decoder_legacy_encodings PASSED [ 79%]
tests/test_quote_system.py::test_cad_takeoff_with_legacy_vietnamese_text PASSED [ 82%]
tests/test_quote_system.py::test_cad_takeoff_auto_add_accessories_norm_calculation PASSED [ 84%]
tests/test_quote_system.py::test_cad_takeoff_apply_pricing_and_labor_direct_flow PASSED [ 87%]
tests/test_quote_system.py::test_security_hmac_approval_and_zalo_webhook PASSED [ 89%]
tests/test_quote_system.py::test_security_production_startup_validation PASSED [ 92%]
tests/test_quote_system.py::test_security_idor_quote_access_protection PASSED [ 94%]
tests/test_quote_system.py::test_security_xss_sanitization_in_approval_html PASSED [ 97%]
tests/test_quote_system.py::test_security_cors_configuration PASSED      [100%]

======================= 39 passed in 12.74s =======================
```
