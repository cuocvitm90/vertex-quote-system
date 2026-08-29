"""
Comprehensive Test Suite for Vertex Construction & PCCC Quote Automation System
Includes Security Hardening, JWT Protection, Pending Registration Approval, Admin Management,
Multi-language (VI, EN, ZH, KO), PCCC Catalog & Pure Python Financial Precision.
"""
import io
import pytest
from pathlib import Path
from fastapi.testclient import TestClient

from main import app
from app.database.db import db
from app.tools.extractor import BOQExtractor
from app.tools.price_lookup import PriceLookupTool
from app.tools.calculator import QuoteCalculator, number_to_vietnamese_words
from app.tools.excel_generator import VertexExcelGenerator
from app.tools.sample_generator import create_sample_excel_boq, create_sample_cad_dxf
from app.database.models import Quote, QuoteItem, QuoteStatus, UserRole, UserStatus
from app.services.file_validator import FileValidator
from app.services.i18n import t

client = TestClient(app)


def test_auth_login_and_security():
    """Test Authentication, Login, JWT issuance, and RBAC"""
    # 1. Unauthenticated request to / should redirect to /login (302)
    res_unauth = client.get("/", follow_redirects=False)
    assert res_unauth.status_code == 302
    assert "/login" in res_unauth.headers["location"]

    # 2. Login with valid Manager credentials
    res_login = client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "Vertex@2026"}
    )
    assert res_login.status_code == 200
    token_data = res_login.json()
    assert "access_token" in token_data
    assert token_data["user"]["username"] == "admin"
    assert token_data["user"]["role"] == "MANAGER"

    token = token_data["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 3. Authenticated request to / with Bearer token
    res_auth = client.get("/", headers=headers)
    assert res_auth.status_code == 200
    assert "VERTEX" in res_auth.text
    assert "Anh Việt" in res_auth.text

    # 4. Login with invalid password -> 401
    res_bad = client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "WrongPassword"}
    )
    assert res_bad.status_code == 401


def test_security_headers():
    """Test that all responses contain OWASP Security Hardening Headers"""
    res = client.get("/api/health")
    assert res.status_code == 200
    assert res.headers.get("X-Content-Type-Options") == "nosniff"
    assert res.headers.get("X-Frame-Options") == "SAMEORIGIN"
    assert res.headers.get("X-XSS-Protection") == "1; mode=block"
    assert res.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"
    assert res.headers.get("Server") == "Vertex-Secure-Engine"


def test_healthcheck_endpoint():
    """Test Production Health Monitoring API (/api/health)"""
    res = client.get("/api/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] in ["healthy", "degraded"]
    assert "database" in data
    assert data["database"]["status"] == "healthy"
    assert data["database"]["catalog_items"] >= 20
    assert "uptime_seconds" in data
    assert "ai_provider" in data


def test_jwt_route_protection():
    """Test that all quotes and catalog routes strictly reject unauthenticated calls (401)"""
    client.cookies.clear()
    
    # 1. Unauthenticated GET /api/quotes -> 401
    res_quotes = client.get("/api/quotes")
    assert res_quotes.status_code == 401

    # 2. Unauthenticated GET /api/catalog -> 401
    res_cat = client.get("/api/catalog")
    assert res_cat.status_code == 401

    # 3. Unauthenticated POST /api/quotes/upload -> 401
    fake_file = io.BytesIO(b"PK\x03\x04 fake content")
    res_upload = client.post(
        "/api/quotes/upload",
        files={"file": ("test.xlsx", fake_file, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        data={"customer_name": "Unauthenticated Hacker"}
    )
    assert res_upload.status_code == 401



def test_file_validation_security():
    """Test file security validation (Extension Whitelist, Magic Bytes, Path Traversal)"""
    # Login as Staff first to get valid token
    res_login = client.post("/api/auth/login", json={"username": "staff", "password": "Vertex@2026"})
    token = res_login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Filename sanitization against path traversal
    clean1 = FileValidator.sanitize_filename("../../etc/passwd.xlsx")
    assert ".." not in clean1
    assert "/" not in clean1

    clean2 = FileValidator.sanitize_filename("valid_boq_2026.xlsx")
    assert clean2 == "valid_boq_2026.xlsx"

    # 2. Reject disallowed extensions (.exe, .sh)
    fake_exe = io.BytesIO(b"MZ executable content")
    res_exe = client.post(
        "/api/quotes/upload",
        files={"file": ("malware.exe", fake_exe, "application/octet-stream")},
        data={"customer_name": "Test Attacker"},
        headers=headers
    )
    assert res_exe.status_code == 400
    assert "không được hỗ trợ" in res_exe.json()["detail"]

    # 3. Reject fake extension with wrong magic bytes
    fake_xlsx = io.BytesIO(b"Plain text pretending to be Excel")
    res_fake = client.post(
        "/api/quotes/upload",
        files={"file": ("fake_file.xlsx", fake_xlsx, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        data={"customer_name": "Test Attacker"},
        headers=headers
    )
    assert res_fake.status_code == 400
    assert "không phải là định dạng chuẩn" in res_fake.json()["detail"]

    # 4. Accept valid DWG file header (AC1027 AutoCAD binary)
    valid_dwg_bytes = io.BytesIO(b"AC1027\x00\x00\x00AutoCAD Drawing Test Stream PCCC_PIPE_DN100 PCCC_SPRINKLER_PENDENT")
    res_dwg = client.post(
        "/api/cad-takeoff/process",
        files={"file": ("Ban_Ve_Mat_Bang.dwg", valid_dwg_bytes, "application/acad")},
        data={"scale": "1:100"},
        headers=headers
    )
    assert res_dwg.status_code == 200
    dwg_data = res_dwg.json()
    assert dwg_data["status"] == "success"
    assert len(dwg_data["data"]["items"]) > 0


def test_user_registration_pending_and_admin_approval():
    """
    Test that new registrations are set to PENDING_APPROVAL,
    prevented from logging in (403), and only allowed after Admin (Sếp Tiến) activates them.
    """
    import uuid
    uid = uuid.uuid4().hex[:6]
    test_uname = f"dealer_{uid}"
    test_pass = "Password@123"

    # 1. Register a new Dealer user
    reg_payload = {
        "username": test_uname,
        "password": test_pass,
        "full_name": "Nguyễn Hoàng Nam",
        "email": f"nam_{uid}@namha.vn",
        "phone": "0912.333.444",
        "company_name": "Công Ty PCCC Nam Hà",
        "account_type": "DEALER"
    }
    res_reg = client.post("/api/auth/register", json=reg_payload)
    assert res_reg.status_code == 200
    reg_data = res_reg.json()
    assert reg_data["status"] == "pending"
    assert reg_data["user"]["username"] == test_uname
    assert reg_data["user"]["role"] == "DEALER"
    assert reg_data["user"]["status"] == "PENDING_APPROVAL"
    assert "access_token" not in reg_data  # No token issued upon registration

    # 2. Try logging in as the newly registered user before approval -> 403 Forbidden
    res_login_pending = client.post(
        "/api/auth/login",
        json={"username": test_uname, "password": test_pass}
    )
    assert res_login_pending.status_code == 403
    assert "CHỜ DUYỆT" in res_login_pending.json()["detail"]

    # 3. Login as Admin (Sếp Tiến) to approve and activate the user
    res_admin_login = client.post("/api/auth/login", json={"username": "tien.boss", "password": "Vertex@2026"})
    admin_token = res_admin_login.json()["access_token"]
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    # Verify user appears in admin user list
    res_users = client.get("/api/users", headers=admin_headers)
    assert res_users.status_code == 200
    users_list = res_users.json()
    assert any(u["username"] == test_uname for u in users_list)

    # Activate user
    new_user_id = reg_data["user"]["id"]
    res_status = client.put(f"/api/users/{new_user_id}/status", json={"status": "ACTIVE"}, headers=admin_headers)
    assert res_status.status_code == 200

    # 4. Now the user can log in successfully!
    res_login_active = client.post(
        "/api/auth/login",
        json={"username": test_uname, "password": test_pass}
    )
    assert res_login_active.status_code == 200
    assert "access_token" in res_login_active.json()
    assert res_login_active.json()["user"]["status"] == "ACTIVE"


def test_pccc_catalog_lookup():
    """Test lookup for Fire Protection (PCCC) equipment"""
    # 1. Fire extinguisher 4kg
    res_ext = PriceLookupTool.lookup_price("Bình chữa cháy bột ABC 4kg MFZL4", "4kg có tem", "bình")
    assert res_ext["unit_price"] >= 250000

    # 2. Smoke detector
    res_smoke = PriceLookupTool.lookup_price("Đầu báo khói quang điện 24V", "kèm đế", "bộ")
    assert res_smoke["unit_price"] >= 300000

    # 3. Sprinkler
    res_spk = PriceLookupTool.lookup_price("Đầu phun chữa cháy tự động Sprinkler 68 độ", "DN15", "cái")
    assert res_spk["unit_price"] > 0


def test_multilanguage_excel_and_i18n():
    """Test multi-language translations and Excel generation in EN, ZH, KO, VI"""
    assert t("excel_title", "vi") == "BẢNG BÁO GIÁ THIẾT BỊ PCCC VÀ VẬT TƯ CƠ ĐIỆN"
    assert "FIRE PROTECTION" in t("excel_title", "en")
    assert "消防" in t("excel_title", "zh")
    assert "소방" in t("excel_title", "ko")

    item1 = QuoteItem(
        stt=1,
        category="Bình chữa cháy",
        item_code="PCCC-BCC-ABC4",
        item_name="Bình chữa cháy bột ABC 4kg MFZL4",
        spec="Có tem kiểm định BCA",
        unit="bình",
        quantity=30.0,
        area_m2=0.0,
        unit_price=280000,
        total_price=8400000,
        notes="Tem PCCC"
    )

    for lang_code in ["vi", "en", "zh", "ko"]:
        quote = Quote(
            id=f"test-quote-lang-{lang_code}",
            quote_code=f"VTX-PCCC-{lang_code.upper()}",
            customer_name="International Client Corp",
            project_name="Commercial Tower PCCC",
            status=QuoteStatus.APPROVED,
            language=lang_code,
            subtotal=8400000,
            discount_rate=0.05,
            discount_amount=420000,
            subtotal_after_discount=7980000,
            vat_rate=0.08,
            vat_amount=638400,
            total_amount=8618400,
            total_amount_in_words=number_to_vietnamese_words(8618400),
            items=[item1]
        )
        out_excel = VertexExcelGenerator.generate(quote)
        assert Path(out_excel).exists()
        assert Path(out_excel).stat().st_size > 1000


def test_vietnamese_words_converter():
    """Test number to Vietnamese words converter"""
    assert "Một trăm nghìn" in number_to_vietnamese_words(100000)
    assert "Một triệu năm trăm nghìn" in number_to_vietnamese_words(1500000)
    assert "đồng chẵn." in number_to_vietnamese_words(25400000)


def test_duct_area_calculator():
    """Test duct surface area calculations"""
    area_sq = QuoteCalculator.calculate_duct_area_m2(500, 300, None, 1.2, 10)
    assert abs(area_sq - 19.2) < 0.05

    area_rd = QuoteCalculator.calculate_duct_area_m2(None, None, 250, 3.0, 1)
    assert abs(area_rd - 2.36) < 0.05


def test_pure_python_financial_precision():
    """Test that financial math is 100% deterministic with zero precision drift"""
    items = [
        QuoteItem(stt=1, item_name="Item 1", unit_price=100000, quantity=10, area_m2=10, total_price=1000000),
        QuoteItem(stt=2, item_name="Item 2", unit_price=250000, quantity=4, area_m2=4, total_price=1000000),
        QuoteItem(stt=3, item_name="Item 3", unit_price=500000, quantity=2, area_m2=2, total_price=1000000)
    ]
    totals = QuoteCalculator.calculate_quote_totals(items, discount_rate=0.05, vat_rate=0.08)
    assert totals["subtotal"] == 3000000
    assert totals["discount_amount"] == 150000
    assert totals["subtotal_after_discount"] == 2850000
    assert totals["vat_amount"] == 228000
    assert totals["total_amount"] == 3078000
    assert "Ba triệu không trăm bảy mươi tám nghìn đồng chẵn." in totals["total_amount_in_words"]


def test_excel_extractor():
    """Test reading sample Excel BOQ"""
    excel_path = "storage/samples/BOQ_Mau_Ong_Gio_Vertex.xlsx"
    if not Path(excel_path).exists():
        create_sample_excel_boq(excel_path)

    items = BOQExtractor.extract(excel_path)
    assert len(items) >= 10


def test_cad_extractor():
    """Test reading sample CAD DXF"""
    cad_path = "storage/samples/Ban_Ve_CAD_Ong_Gio.dxf"
    if not Path(cad_path).exists():
        create_sample_cad_dxf(cad_path)

    items = BOQExtractor.extract(cad_path)
    assert len(items) >= 1


def test_api_endpoints():
    """Test FastAPI upload, list, download and approval endpoints with JWT auth"""
    # 1. Test Login Page HTML (No quick login buttons)
    res_login_page = client.get("/login")
    assert res_login_page.status_code == 200
    assert "VERTEX" in res_login_page.text
    assert "Đăng nhập nhanh với tài khoản mẫu" not in res_login_page.text

    # 2. Test Register Page HTML
    res_reg_page = client.get("/register")
    assert res_reg_page.status_code == 200
    assert "Chờ Duyệt" in res_reg_page.text

    # 3. Login to get Staff token
    res_login = client.post("/api/auth/login", json={"username": "staff", "password": "Vertex@2026"})
    token = res_login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 4. Test Upload Endpoint with PCCC BOQ
    excel_path = "storage/samples/BOQ_Mau_Ong_Gio_Vertex.xlsx"
    create_sample_excel_boq(excel_path)

    with open(excel_path, "rb") as f:
        res_upload = client.post(
            "/api/quotes/upload",
            files={"file": ("BOQ_Mau_Ong_Gio_Vertex.xlsx", f, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
            data={
                "customer_name": "Công Ty Xây Dựng & PCCC Thăng Long",
                "customer_phone": "0987.654.321",
                "project_name": "Tòa Nhà Thăng Long Complex",
                "project_address": "Cầu Giấy, Hà Nội",
                "discount_rate": 0.05,
                "vat_rate": 0.08,
                "language": "en"
            },
            headers=headers
        )
    assert res_upload.status_code == 200
    data = res_upload.json()
    assert data["status"] == "success"
    quote_id = data["quote"]["id"]
    quote_code = data["quote"]["quote_code"]
    assert quote_code.startswith("VTX-")
    assert len(data["quote"]["items"]) > 0

    # 5. Test Download Excel
    res_download = client.get(f"/api/quotes/{quote_id}/download", headers=headers)
    assert res_download.status_code == 200
    assert res_download.headers["content-type"] == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

    # 6. Test Zalo Simulator Approval (Protected by Manager/Admin auth)
    res_mgr_login = client.post("/api/auth/login", json={"username": "viet.manager", "password": "Vertex@2026"})
    mgr_token = res_mgr_login.json()["access_token"]
    mgr_headers = {"Authorization": f"Bearer {mgr_token}"}

    res_approve = client.post(
        "/api/zalo/simulate-approval",
        json={
            "quote_id": quote_id,
            "action": "approve",
            "manager_name": "Anh Việt (Trưởng phòng KD PCCC)",
            "manager_role": "MANAGER"
        },
        headers=mgr_headers
    )
    assert res_approve.status_code == 200
    assert res_approve.json()["status"] in ["success", "pending_director"]

    # Final stage: Admin / Director approval if required
    if res_approve.json()["status"] == "pending_director":
        res_admin_login = client.post("/api/auth/login", json={"username": "tien.boss", "password": "Vertex@2026"})
        admin_token = res_admin_login.json()["access_token"]
        admin_headers = {"Authorization": f"Bearer {admin_token}"}
        res_dir = client.post(
            "/api/zalo/simulate-approval",
            json={
                "quote_id": quote_id,
                "action": "approve",
                "manager_name": "Sếp Tiến (Tổng Giám Đốc)",
                "manager_role": "ADMIN"
            },
            headers=admin_headers
        )
        assert res_dir.status_code == 200
        assert res_dir.json()["status"] == "success"

    # 7. Verify Quote is now SENT_TO_CUSTOMER
    res_detail = client.get(f"/api/quotes/{quote_id}", headers=headers)
    assert res_detail.status_code == 200
    assert res_detail.json()["status"] == "SENT_TO_CUSTOMER"
    assert res_detail.json()["approved_by"] is not None


def test_gdrive_sync_endpoint():
    """Test Google Drive folder sync API endpoint (Admin/Manager protected)"""
    res_login = client.post("/api/auth/login", json={"username": "admin", "password": "Vertex@2026"})
    token = res_login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    res = client.post("/api/catalog/sync-gdrive", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert "1DPw8uKS-usaWTd7xob5EnTMZn_Vj4J5U" in data["folder_id"]


def test_master_template_and_coefficients_framework():
    """Test Master Template CRUD & Pure Python Pricing Coefficient Calculations"""
    # 1. Login as Admin
    res_login = client.post("/api/auth/login", json={"username": "tien.boss", "password": "Vertex@2026"})
    token = res_login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Get active template
    res_active = client.get("/api/templates/active", headers=headers)
    assert res_active.status_code == 200
    active_tpl = res_active.json()
    assert "id" in active_tpl
    assert active_tpl["waste_ratio"] == 0.05
    assert active_tpl["transport_ratio"] == 0.03
    assert active_tpl["labor_ratio"] == 0.15
    assert active_tpl["margin_ratio"] == 0.12

    # 3. Test Pure Python Coefficient Math
    # Multiplier = 1 + 0.05 + 0.03 + 0.15 + 0.12 = 1.35
    from app.database.models import MasterTemplate
    tpl_model = MasterTemplate(**active_tpl)
    raw_price = 100000.0
    final_price, breakdown = QuoteCalculator.apply_template_coefficients(raw_price, tpl_model)
    assert final_price == 135000.0
    assert breakdown["multiplier"] == 1.35
    assert breakdown["total_markup_percent"] == 35.0

    # 4. Update coefficients via API
    res_update = client.put(
        f"/api/templates/{active_tpl['id']}/coefficients",
        json={
            "waste_ratio": 0.06,
            "transport_ratio": 0.04,
            "labor_ratio": 0.15,
            "margin_ratio": 0.15
        },
        headers=headers
    )
    assert res_update.status_code == 200
    updated_tpl = res_update.json()["template"]
    assert updated_tpl["waste_ratio"] == 0.06
    assert updated_tpl["margin_ratio"] == 0.15

    # Reset back to default standard for consistency
    client.put(
        f"/api/templates/{active_tpl['id']}/coefficients",
        json={
            "waste_ratio": 0.05,
            "transport_ratio": 0.03,
            "labor_ratio": 0.15,
            "margin_ratio": 0.12
        },
        headers=headers
    )


def test_ai_market_price_estimator_tool():
    """Test AI Market Price Estimator tool on uncataloged items"""
    import asyncio
    from app.tools.market_estimator import AIMarketEstimator

    # Test item: Uncataloged Foam nozzle
    est = asyncio.run(AIMarketEstimator.estimate_market_price(
        item_name="Đầu phun foam chữa cháy D50 Viking",
        spec="DN50 nối bích PN16",
        unit="cái"
    ))

    assert "raw_market_price" in est
    assert est["raw_market_price"] > 0
    assert "confidence" in est
    assert est["confidence"] >= 0.70
    assert "market_notes" in est



def test_four_step_boq_pipeline_integration():
    """Test full 4-step pipeline: Catalog match, AI market estimation, Template coefficients, and Draft Quote"""
    # 1. Login
    res_login = client.post("/api/auth/login", json={"username": "admin", "password": "Vertex@2026"})
    token = res_login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Upload file
    excel_path = "storage/samples/BOQ_Mau_Ong_Gio_Vertex.xlsx"
    create_sample_excel_boq(excel_path)

    with open(excel_path, "rb") as f:
        res_upload = client.post(
            "/api/quotes/upload",
            files={"file": ("BOQ_Mau_Ong_Gio_Vertex.xlsx", f, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
            data={
                "customer_name": "Tập Đoàn Địa Ốc Masterise",
                "customer_phone": "0909.111.222",
                "project_name": "Khu Căn Hộ Cao Cấp Masterise Marina",
                "project_address": "TP. Thủ Đức, TP. Hồ Chí Minh",
                "discount_rate": 0.05,
                "vat_rate": 0.08,
                "language": "vi"
            },
            headers=headers
        )

    assert res_upload.status_code == 200
    quote_data = res_upload.json()["quote"]

    # Verify Step 4 Draft state (PENDING_APPROVAL)
    assert quote_data["status"] == "PENDING_APPROVAL"
    assert quote_data["template_name"] is not None

    # Verify item pricing sources
    items = quote_data["items"]
    assert len(items) > 0
    for item in items:
        assert item["price_source"] in ["CATALOG", "AI_MARKET_ESTIMATE"]
        assert item["unit_price"] > 0
        assert item["total_price"] > 0


def test_cad_takeoff_standalone_module():
    """Test dedicated standalone CAD & Revit Takeoff module routes and data APIs"""
    from app.services.auth import create_access_token
    # 1. Test unauthenticated redirect
    client.cookies.clear()
    res_unauth = client.get("/cad-takeoff", follow_redirects=False)
    assert res_unauth.status_code in [302, 307]
    assert "/login" in res_unauth.headers["location"]

    # 2. Authenticate as Admin/Manager using direct JWT
    user = db.get_user_by_username("admin")
    assert user is not None
    token = create_access_token(user)
    headers = {"Authorization": f"Bearer {token}"}
    client.cookies.set("access_token", token)

    # 3. Test authenticated page load
    client.cookies.set("access_token", token)
    res_page = client.get("/cad-takeoff", headers=headers)
    assert res_page.status_code == 200
    assert "Module Bóc Tách Bản Vẽ CAD" in res_page.text

    # 4. Test Sample Datasets (PCCC, HVAC, Revit BIM)
    for sample_key in ["cad_pccc", "cad_hvac", "revit_mep"]:
        res_sample = client.get(f"/api/cad-takeoff/sample/{sample_key}", headers=headers)
        assert res_sample.status_code == 200
        data = res_sample.json()["data"]
        assert "items" in data
        assert len(data["items"]) > 0
        assert "layers" in data
        assert len(data["layers"]) > 0
        assert "total_entities" in data

    # 5. Test Export Excel BOQ
    sample_data = client.get("/api/cad-takeoff/sample/cad_pccc", headers=headers).json()["data"]
    res_export = client.post("/api/cad-takeoff/export-excel", json=sample_data, headers=headers)
    assert res_export.status_code == 200
    assert "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" in res_export.headers["content-type"]
    assert len(res_export.content) > 1000

    # 6. Test Transfer to Quote Pipeline
    res_transfer = client.post("/api/cad-takeoff/transfer-to-quote", json=sample_data, headers=headers)
    assert res_transfer.status_code == 200
    trans_data = res_transfer.json()
    assert trans_data["status"] == "success"
    assert trans_data["file_name"].startswith("CAD_Takeoff_BOQ_")
    assert trans_data["total_items"] == len(sample_data["items"])


def test_field_attendance_and_reports_module():
    """Test dedicated Field Reports & GPS Attendance module routes, APIs, and Excel export"""
    from app.services.auth import create_access_token
    # 1. Test unauthenticated redirect
    client.cookies.clear()
    res_unauth = client.get("/field-reports", follow_redirects=False)
    assert res_unauth.status_code in [302, 307]
    assert "/login" in res_unauth.headers["location"]

    # 2. Authenticate as Admin
    user = db.get_user_by_username("admin")
    assert user is not None
    token = create_access_token(user)
    headers = {"Authorization": f"Bearer {token}"}
    client.cookies.set("access_token", token)

    # 3. Test authenticated page load
    res_page = client.get("/field-reports", headers=headers)
    assert res_page.status_code == 200
    assert "Chấm Công GPS" in res_page.text
    assert "Báo Cáo Hiện Trường" in res_page.text

    # 4. Test Project Sites List API
    res_sites = client.get("/api/field/sites", headers=headers)
    assert res_sites.status_code == 200
    sites_data = res_sites.json()["sites"]
    assert len(sites_data) >= 3

    # 5. Test GPS Check-in Submission
    checkin_payload = {
        "project_site": "Khách Sạn 5 Sao Delta Grand (Hà Nội)",
        "checkin_type": "IN",
        "latitude": 21.0568,
        "longitude": 105.7925,
        "accuracy_meters": 5.0,
        "notes": "Test checkin tự động trạm bơm"
    }
    res_chk = client.post("/api/field/checkin", json=checkin_payload, headers=headers)
    assert res_chk.status_code == 200
    chk_res = res_chk.json()
    assert chk_res["status"] == "success"
    assert "Check-in thành công" in chk_res["message"]
    assert chk_res["data"]["project_site"] == checkin_payload["project_site"]

    # 6. Test List Check-ins API
    res_list_chk = client.get("/api/field/checkins", headers=headers)
    assert res_list_chk.status_code == 200
    assert len(res_list_chk.json()["data"]) >= 1

    # 7. Test Submit Daily Field Report
    report_payload = {
        "project_name": "Khách Sạn 5 Sao Delta Grand",
        "weather_condition": "Nắng ráo",
        "work_summary": "Lắp đặt xong tủ điện điều khiển 3 máy bơm PCCC và thử áp lực đạt 16 bar.",
        "progress_percent": 85.0,
        "workforce_count": 10,
        "issues_and_risks": "Không có vướng mắc.",
        "next_plan": "Nghiệm thu chạy thử liên động với Cảnh sát PCCC."
    }
    res_rep = client.post("/api/field/report", json=report_payload, headers=headers)
    assert res_rep.status_code == 200
    rep_res = res_rep.json()
    assert rep_res["status"] == "success"
    rep_id = rep_res["data"]["id"]

    # 8. Test Manager Approval & Comment
    comment_payload = {
        "comment": "Đã duyệt tiến độ trạm bơm. Chuẩn bị hồ sơ nghiệm thu kỹ thuật.",
        "status": "APPROVED"
    }
    res_com = client.post(f"/api/field/report/{rep_id}/comment", json=comment_payload, headers=headers)
    assert res_com.status_code == 200
    com_res = res_com.json()
    assert com_res["status"] == "success"
    assert "Đã duyệt" in com_res["data"]["supervisor_comment"]

    # 9. Test Excel Export for Attendance & Daily Reports
    res_excel = client.get("/api/field/export-excel", headers=headers)
    assert res_excel.status_code == 200
    assert "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" in res_excel.headers["content-type"]
    assert len(res_excel.content) > 1000

    # 10. Test Personnel Sync API
    res_personnel = client.get("/api/field/personnel", headers=headers)
    assert res_personnel.status_code == 200
    per_data = res_personnel.json()
    assert per_data["status"] == "success"
    assert per_data["total_personnel"] >= 1
    assert any(u["username"] == "admin" for u in per_data["data"])


def test_field_personnel_dynamic_synchronization_from_user_management():
    """
    Test real-time automatic synchronization between User Management and Field Attendance Personnel Roster:
    1. Register new field engineer (starts in PENDING_APPROVAL).
    2. Verify user does NOT appear in active field personnel list yet.
    3. Admin approves user (status -> ACTIVE).
    4. Verify user automatically appears in field personnel API and HTML table.
    """
    import uuid
    from app.services.auth import create_access_token
    admin_user = db.get_user_by_username("admin")
    token = create_access_token(admin_user)
    headers = {"Authorization": f"Bearer {token}"}

    unique_user = f"engineer_{uuid.uuid4().hex[:6]}"
    reg_payload = {
        "username": unique_user,
        "password": "Password123@",
        "full_name": "Kỹ Sư Hiện Trường Trịnh Văn Cường",
        "email": f"{unique_user}@vertex.vn",
        "phone": "0912.888.999",
        "company_name": "Công Ty PCCC Miền Bắc"
    }

    # Step 1: Register new user
    res_reg = client.post("/api/auth/register", json=reg_payload)
    assert res_reg.status_code == 200
    reg_data = res_reg.json()
    assert reg_data["user"]["status"] == "PENDING_APPROVAL"
    new_uid = reg_data["user"]["id"]

    # Step 2: Check field personnel API before approval -> Should not include pending user
    res_per_before = client.get("/api/field/personnel", headers=headers)
    assert res_per_before.status_code == 200
    assert not any(u["id"] == new_uid for u in res_per_before.json()["data"])

    # Step 3: Admin approves the user
    res_approve = client.put(
        f"/api/users/{new_uid}/status",
        json={"status": "ACTIVE"},
        headers=headers
    )
    assert res_approve.status_code == 200

    # Step 4: Check field personnel API after approval -> Should immediately include the new engineer
    res_per_after = client.get("/api/field/personnel", headers=headers)
    assert res_per_after.status_code == 200
    after_data = res_per_after.json()["data"]
    matched_user = next((u for u in after_data if u["id"] == new_uid), None)
    assert matched_user is not None
    assert matched_user["full_name"] == "Kỹ Sư Hiện Trường Trịnh Văn Cường"
    assert matched_user["username"] == unique_user
    assert matched_user["role"] == "STAFF"
    assert matched_user["company_name"] == "Công Ty PCCC Miền Bắc"
    assert matched_user["phone"] == "0912.888.999"
    assert matched_user["status"] == "ACTIVE"

    # Step 5: Verify rendered HTML page /field-reports contains the new engineer
    client.cookies.set("access_token", token)
    res_html = client.get("/field-reports", headers=headers)
    assert res_html.status_code == 200
    assert "Trịnh Văn Cường" in res_html.text
    assert unique_user in res_html.text


def test_geofencing_live_tracking_and_out_of_zone_alerts():
    """
    Test Geofencing live tracking, Haversine distance, safe boundary checks,
    and automatic Out-of-Zone alert triggering with managerial resolution.
    """
    from app.routers.field_reports import calculate_haversine_distance_meters, evaluate_geofence_status, PROJECT_SITES
    from app.services.auth import create_access_token

    admin_user = db.get_user_by_username("admin")
    token = create_access_token(admin_user)
    headers = {"Authorization": f"Bearer {token}"}

    site = PROJECT_SITES[0]  # Delta Grand: 21.0568, 105.7925, radius: 200m

    # 1. Test Haversine formula precision
    # Point exactly at site center -> distance = 0
    d0 = calculate_haversine_distance_meters(21.0568, 105.7925, 21.0568, 105.7925)
    assert d0 == 0.0

    # Point ~110m away
    d_nearby = calculate_haversine_distance_meters(21.0568, 105.7925, 21.0578, 105.7925)
    assert 100 <= d_nearby <= 120

    # 2. Test evaluate_geofence_status
    # 2a. Inside safe radius (110m <= 200m)
    status_in, dist_in, alert_in, _ = evaluate_geofence_status(21.0578, 105.7925, site)
    assert status_in == "ON_SITE"
    assert not alert_in

    # 2b. Far outside radius (e.g. 5km away in Cầu Giấy: 21.0285, 105.7823) without survey notes
    status_out, dist_out, alert_out, msg_out = evaluate_geofence_status(21.0285, 105.7823, site)
    assert status_out == "OUT_OF_ZONE"
    assert alert_out
    assert dist_out > 2000
    assert "CẢNH BÁO RANH GIỚI" in msg_out

    # 2c. Far outside radius but WITH survey / procurement note exemption
    status_surv, dist_surv, alert_surv, _ = evaluate_geofence_status(
        21.0285, 105.7823, site, checkin_type="SITE_VISIT", notes="Đi khảo sát kho vật tư phụ kiện"
    )
    assert status_surv == "SITE_VISIT_APPROVED"
    assert not alert_surv

    # 3. Test Real-time Geofence Check API
    res_chk = client.post(
        "/api/field/geofence-check",
        json={
            "project_site": site["name"],
            "latitude": 21.0568,
            "longitude": 105.7925,
            "checkin_type": "IN"
        },
        headers=headers
    )
    assert res_chk.status_code == 200
    chk_json = res_chk.json()
    assert chk_json["geofence_status"] == "ON_SITE"
    assert not chk_json["is_alert"]
    assert chk_json["distance_meters"] == 0.0

    # 4. Test Check-in with Out-of-Zone Violation -> Trigger Geofence Alert
    res_breach = client.post(
        "/api/field/checkin",
        json={
            "project_site": site["name"],
            "latitude": 21.0100,  # Far away
            "longitude": 105.8000,
            "checkin_type": "IN",
            "notes": "Quên không bật vị trí đúng"
        },
        headers=headers
    )
    assert res_breach.status_code == 200
    breach_json = res_breach.json()
    assert breach_json["geofence_status"] == "OUT_OF_ZONE"
    assert breach_json["is_alert"] is True
    assert breach_json["distance_meters"] > 1000

    # 5. Verify Geofence Alert is recorded in Database & API list
    res_alerts = client.get("/api/field/geofence-alerts", headers=headers)
    assert res_alerts.status_code == 200
    alerts_data = res_alerts.json()["data"]
    assert len(alerts_data) >= 1
    recent_alert = alerts_data[0]
    assert recent_alert["status"] == "UNRESOLVED"
    assert recent_alert["project_site"] == site["name"]

    # 6. Test Geofence Alert Resolution by Manager
    alert_id = recent_alert["id"]
    res_resolve = client.post(f"/api/field/geofence-alerts/{alert_id}/resolve", headers=headers)
    assert res_resolve.status_code == 200
    assert res_resolve.json()["status"] == "success"

    # 7. Test Geofence Radius Configuration Update
    res_config = client.post(
        "/api/field/geofence-config",
        json={
            "project_site": site["name"],
            "radius_meters": 350.0
        },
        headers=headers
    )
    assert res_config.status_code == 200
    assert res_config.json()["site"]["radius_meters"] == 350.0

    # 8. Test Configuring custom project site coordinates & Geofencing binding
    res_new_site = client.post(
        "/api/field/geofence-config",
        json={
            "project_site": "Dự Án Nhà Máy Điện Tử SamSung Thái Nguyên",
            "lat": 21.4923,
            "lng": 105.8647,
            "radius_meters": 300.0,
            "address": "KCN Yên Bình, Phổ Yên, Thái Nguyên"
        },
        headers=headers
    )
    assert res_new_site.status_code == 200
    new_site_data = res_new_site.json()["site"]
    assert new_site_data["lat"] == 21.4923
    assert new_site_data["lng"] == 105.8647
    assert new_site_data["radius_meters"] == 300.0

    # Test check-in within new project site coordinates
    res_chk_new = client.post(
        "/api/field/checkin",
        json={
            "project_site": "Dự Án Nhà Máy Điện Tử SamSung Thái Nguyên",
            "latitude": 21.4925,
            "longitude": 105.8649,
            "checkin_type": "IN",
            "notes": "Vào ca thi công hệ thống sprinkler"
        },
        headers=headers
    )
    assert res_chk_new.status_code == 200
    assert res_chk_new.json()["geofence_status"] == "ON_SITE"
    assert res_chk_new.json()["is_alert"] is False



def test_quote_version_control_and_revisions():
    """Test Quote Version Control: v1 -> v2 creation, lineage, financial recalculation, and versions listing"""
    import uuid
    from app.services.auth import create_access_token
    admin_user = db.get_user_by_username("admin")
    token = create_access_token(admin_user)
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Create Base Quote (v1) in DB with unique id
    unique_suffix = uuid.uuid4().hex[:6]
    q_id = f"test_quote_v1_{unique_suffix}"
    item1 = QuoteItem(
        stt=1, item_code="VTX-PCCC-001", item_name="Bình bột chữa cháy ABC 4kg",
        unit="bình", quantity=10, unit_price=280000, total_price=2800000
    )
    item2 = QuoteItem(
        stt=2, item_code="VTX-PCCC-002", item_name="Đầu phun Sprinkler quay xuống",
        unit="bộ", quantity=50, unit_price=65000, total_price=3250000
    )
    base_quote = Quote(
        id=q_id,
        quote_code=f"VTX-2026-{unique_suffix}",
        customer_name="Công ty TNHH Thử Nghiệm",
        project_name="Dự án Tòa nhà Test",
        status=QuoteStatus.PENDING_APPROVAL,
        version=1,
        parent_quote_id="",
        subtotal=6050000,
        discount_rate=0.05,
        discount_amount=302500,
        subtotal_after_discount=5747500,
        vat_rate=0.08,
        vat_amount=459800,
        total_amount=6207300,
        total_amount_in_words="Sáu triệu hai trăm lẻ bảy nghìn ba trăm đồng",
        items=[item1, item2],
        logs=["[Initial] Tạo báo giá v1"]
    )
    db.save_quote(base_quote)

    # 3. Create Revision (v2) via API with increased discount to 10%
    rev_payload = {
        "revision_note": "Tăng chiết khấu 10% theo yêu cầu khách hàng",
        "discount_rate": 0.10,
        "vat_rate": 0.08
    }
    res_rev = client.post(f"/api/quotes/{q_id}/revision", json=rev_payload, headers=headers)
    assert res_rev.status_code == 200
    rev_data = res_rev.json()

    assert rev_data["version"] == 2
    assert "v2" in rev_data["quote_code"]
    assert rev_data["parent_quote_id"] == q_id
    assert rev_data["discount_rate"] == 0.10
    # Financial check: 6,050,000 * 0.10 = 605,000; after disc = 5,445,000; VAT 8% = 435,600; Total = 5,880,600
    assert rev_data["discount_amount"] == 605000
    assert rev_data["total_amount"] == 5880600

    # 4. Fetch Version Tree via API
    res_versions = client.get(f"/api/quotes/{q_id}/versions", headers=headers)
    assert res_versions.status_code == 200
    versions_list = res_versions.json()
    assert len(versions_list) >= 2
    assert any(v["version"] == 1 for v in versions_list)
    assert any(v["version"] == 2 for v in versions_list)


def test_audit_trail_logging_and_retrieval():
    """Test Immutable Audit Trail: records CREATE_QUOTE, CREATE_REVISION, EXPORT_EXCEL events"""
    import uuid
    from app.services.auth import create_access_token
    admin_user = db.get_user_by_username("admin")
    token = create_access_token(admin_user)
    headers = {"Authorization": f"Bearer {token}"}

    q_id = f"test_audit_quote_{uuid.uuid4().hex[:6]}"
    quote = Quote(
        id=q_id,
        quote_code=f"VTX-2026-{uuid.uuid4().hex[:6]}",
        customer_name="Công ty Kiểm Toán Test",
        project_name="Dự án Audit Trail",
        status=QuoteStatus.PENDING_APPROVAL,
        version=1,
        total_amount=15000000,
        items=[]
    )
    db.save_quote(quote)

    # 1. Log manual audit events
    db.add_audit_log(
        quote_id=q_id,
        user_name="Nguyễn Quốc Việt",
        user_role="MANAGER",
        action="CREATE_QUOTE",
        details="Khởi tạo báo giá thử nghiệm cho Audit Trail"
    )

    # 2. Trigger Excel download to record EXPORT_EXCEL event
    res_dl = client.get(f"/api/quotes/{q_id}/download", headers=headers)
    assert res_dl.status_code == 200

    # 3. Retrieve Audit Trail via API
    res_audit = client.get(f"/api/quotes/{q_id}/audit-logs", headers=headers)
    assert res_audit.status_code == 200
    logs = res_audit.json()
    assert len(logs) >= 2
    actions = [l["action"] for l in logs]
    assert "CREATE_QUOTE" in actions
    assert "EXPORT_EXCEL" in actions
    for log_item in logs:
        assert log_item["quote_id"] == q_id
        assert log_item["timestamp"] is not None


def test_multilevel_approval_flow_and_matrix():
    """Test Multi-level Approval: Manager threshold vs Director requirement for high value / discount quotes"""
    # 1. Standard Quote (< 100M, <= 5% discount) -> Manager can approve directly
    q_standard_id = "test_std_quote_unit"
    std_quote = Quote(
        id=q_standard_id,
        quote_code="VTX-2026-9003",
        customer_name="Khách Hàng Tiêu Chuẩn",
        project_name="Công trình PCCC vừa và nhỏ",
        status=QuoteStatus.PENDING_APPROVAL,
        required_approval_level="MANAGER",
        total_amount=45000000,
        discount_rate=0.05,
        items=[]
    )
    db.save_quote(std_quote)

    # Manager approves standard quote
    res_std_app = client.post(
        f"/api/zalo/simulate-approval",
        json={
            "quote_id": q_standard_id,
            "action": "approve",
            "manager_name": "Anh Việt",
            "manager_role": "MANAGER"
        }
    )
    assert res_std_app.status_code == 200
    assert res_std_app.json()["status"] == "success"
    updated_std = db.get_quote(q_standard_id)
    assert updated_std.status in [QuoteStatus.APPROVED, QuoteStatus.SENT_TO_CUSTOMER]

    # 2. High-Value Quote (>= 100M) -> Requires Director (Admin) approval
    q_high_id = "test_high_quote_unit"
    high_quote = Quote(
        id=q_high_id,
        quote_code="VTX-2026-9004",
        customer_name="Tập Đoàn Xây Dựng Lớn",
        project_name="Dự án Trung Tâm Thương Mại 200 Tỷ",
        status=QuoteStatus.PENDING_APPROVAL,
        required_approval_level="DIRECTOR",
        total_amount=250000000,  # 250 million > 100 million
        discount_rate=0.08,      # 8% > 5%
        items=[]
    )
    db.save_quote(high_quote)

    # Step 2a: Manager reviews and passes stage 1
    res_stage1 = client.post(
        f"/api/zalo/simulate-approval",
        json={
            "quote_id": q_high_id,
            "action": "approve",
            "manager_name": "Anh Việt (Trưởng phòng KD)",
            "manager_role": "MANAGER"
        }
    )
    assert res_stage1.status_code == 200
    assert res_stage1.json()["status"] == "pending_director"
    stage1_quote = db.get_quote(q_high_id)
    assert stage1_quote.status == QuoteStatus.PENDING_DIRECTOR_APPROVAL
    assert stage1_quote.manager_approved_by is not None

    # Step 2b: Director (Admin - Sếp Tiến) gives final executive approval
    res_stage2 = client.post(
        f"/api/zalo/simulate-approval",
        json={
            "quote_id": q_high_id,
            "action": "approve",
            "manager_name": "Sếp Tiến (Tổng Giám Đốc)",
            "manager_role": "ADMIN"
        }
    )
    assert res_stage2.status_code == 200
    assert res_stage2.json()["status"] == "success"
    stage2_quote = db.get_quote(q_high_id)
    assert stage2_quote.status in [QuoteStatus.APPROVED, QuoteStatus.SENT_TO_CUSTOMER]
    assert stage2_quote.director_approved_by is not None


def test_cad_takeoff_engine_geometry_and_cross_checks():
    """Test advanced CAD geometry parsing, layer grouping, waste ratios, and cross-checks"""
    from app.tools.cad_takeoff_engine import CADTakeoffEngine, CADTakeoffCrossChecker
    from app.services.auth import create_access_token

    # 1. Create CAD file with geometry, layers, and text tags
    cad_path = "storage/samples/Ban_Ve_CAD_Ong_Gio.dxf"
    create_sample_cad_dxf(cad_path)

    # 2. Run engine extraction
    result = CADTakeoffEngine.extract_dxf_takeoff(cad_path, scale_str="1:100", waste_ratio_duct=0.05, waste_ratio_pipe=0.03)
    assert result.total_entities >= 10
    assert len(result.layers) >= 3
    assert len(result.items) >= 5
    assert len(result.cross_checks) >= 3

    # Check metrics
    assert result.summary_metrics["total_boq_items"] == len(result.items)

    # Check waste ratio application in pipe items
    pipe_items = [it for it in result.items if it.get("category") == "Piping"]
    for p in pipe_items:
        assert p["waste_applied"] == "3%"

    # 3. Test API process upload with DXF
    admin_user = db.get_user_by_username("admin")
    token = create_access_token(admin_user)
    headers = {"Authorization": f"Bearer {token}"}

    with open(cad_path, "rb") as f:
        res_upload = client.post(
            "/api/cad-takeoff/process",
            files={"file": ("Ban_Ve_CAD_Ong_Gio.dxf", f, "application/dxf")},
            data={"scale": "1:100"},
            headers=headers
        )
    assert res_upload.status_code == 200
    res_json = res_upload.json()
    assert res_json["status"] == "success"
    assert "cross_checks" in res_json["data"]
    assert "summary_metrics" in res_json["data"]
    assert len(res_json["data"]["items"]) >= 5


def test_labor_cost_matrix():
    """Test LaborCostMatrix: validates exact labor rates for the 6 core mandated categories"""
    from app.tools.labor_cost import LaborCostMatrix

    # 1. Ống chữa cháy: 220.000 VNĐ / m
    rate1, _ = LaborCostMatrix.get_labor_rate_and_description("Ống thép đúc Sch40 DN100", unit="m")
    assert rate1 == 220000.0

    # 2. Thiết bị báo cháy: 350.000 VNĐ / thiết bị
    rate2, _ = LaborCostMatrix.get_labor_rate_and_description("Đầu báo khói quang địa chỉ 24V", unit="bộ")
    assert rate2 == 350000.0

    # 3. Đèn Exit / sự cố: 370.000 VNĐ / thiết bị
    rate3, _ = LaborCostMatrix.get_labor_rate_and_description("Đèn Exit LED 2 mặt chỉ hướng", unit="bộ")
    assert rate3 == 370000.0

    # 4. Ống gió thường: 100.000 VNĐ / m²
    rate4, _ = LaborCostMatrix.get_labor_rate_and_description("Ống gió vuông bích TDC tôn mạ kẽm Z80 500x300", unit="m2")
    assert rate4 == 100000.0

    # 5. Ống gió chống cháy EI30, EI45, EI60: 130.000 VNĐ / m²
    rate5, _ = LaborCostMatrix.get_labor_rate_and_description("Ống gió chống cháy EI60 bọc vữa 800x400", unit="m2")
    assert rate5 == 130000.0

    # 6. Ống gió chống cháy EI120: 155.000 VNĐ / m²
    rate6, _ = LaborCostMatrix.get_labor_rate_and_description("Ống gió chống cháy EI 120 cách nhiệt dày", unit="m2")
    assert rate6 == 155000.0


def test_commercial_pricing_output_formula():
    """Test Output Pricing Formula: Base Cost = Material + Labor; Final Price = Base Cost * (1 + waste + transport + margin)"""
    from app.tools.calculator import QuoteCalculator
    from app.database.models import MasterTemplate

    tpl = MasterTemplate(
        id="test_tpl",
        name="Test Template",
        waste_ratio=0.05,       # 5%
        transport_ratio=0.03,   # 3%
        labor_ratio=0.0,
        margin_ratio=0.12       # 12% -> Commercial Multiplier = 1 + 0.05 + 0.03 + 0.12 = 1.20
    )

    material_cost = 500000.0  # 500k
    labor_cost = 220000.0     # 220k (Pipe labor)
    # Base Cost = 720,000
    # Final Unit Price = 720,000 * 1.20 = 864,000

    final_price, base_cost, breakdown = QuoteCalculator.apply_commercial_pricing_formula(
        material_unit_cost=material_cost,
        labor_unit_cost=labor_cost,
        template=tpl
    )
    assert base_cost == 720000.0
    assert final_price == 864000.0
    assert breakdown["multiplier"] == 1.20
    assert breakdown["total_markup_percent"] == 20.0


def test_3_input_scenarios_and_brand_routing():
    """Test 3 Input Scenarios: CAD Takeoff (S1), Specified Brand (S2), and Pure BOQ Standard Catalog (S3)"""
    from app.tools.scenario_router import InputScenarioRouter

    # 1. Scenario 1: CAD Drawing (.dxf / .dwg)
    s1, _ = InputScenarioRouter.detect_scenario("Ban_Ve_PCCC.dwg", ["LINE", "PCCC_PIPE_DN100"])
    assert s1 == InputScenarioRouter.SCENARIO_1

    # 2. Scenario 2: Specified Brand & Technical Parameters (Ebara, Viking, Hochiki, Q=150, H=80, P=45kW)
    s2_texts = [
        "Bơm chữa cháy Ebara Model GS 100-250 Q=150m3/h H=80m P=45kW",
        "Đầu báo khói quang Hochiki SOC-24VN",
        "Đầu phun Sprinkler Viking K=5.6 68C"
    ]
    s2, _ = InputScenarioRouter.detect_scenario("BOQ_CDT_Chi_Dinh.xlsx", s2_texts)
    assert s2 == InputScenarioRouter.SCENARIO_2

    # Brand extraction check
    brand_pump, _ = InputScenarioRouter.extract_brand_from_text(s2_texts[0])
    assert brand_pump == "Ebara"

    brand_alarm, _ = InputScenarioRouter.extract_brand_from_text(s2_texts[1])
    assert brand_alarm == "Hochiki"

    # Technical params extraction check
    params = InputScenarioRouter.extract_technical_parameters(s2_texts[0])
    assert "flow_q" in params
    assert "head_h" in params
    assert "power" in params

    # 3. Scenario 3: Pure BOQ without Brand Specified
    s3_texts = [
        "Đầu phun chữa cháy Sprinkler hướng xuống",
        "Ống thép đúc mạ kẽm Sch40 DN100",
        "Ống gió vuông tôn mạ kẽm Z80 500x300",
        "Đèn Exit LED 2 mặt"
    ]
    s3, _ = InputScenarioRouter.detect_scenario("BOQ_Thuan_Chua_Hang.xlsx", s3_texts)
    assert s3 == InputScenarioRouter.SCENARIO_3

    # Check that Scenario 3 resolves optimal Vertex Standard Brands
    rec_sprinkler, src1 = InputScenarioRouter.resolve_item_brand("Đầu phun Sprinkler", scenario_type=s3)
    assert "Viking" in rec_sprinkler
    assert src1 == "VERTEX_STANDARD"

    rec_pipe, src2 = InputScenarioRouter.resolve_item_brand("Ống thép đúc mạ kẽm Sch40 DN100", scenario_type=s3)
    assert "Hòa Phát" in rec_pipe
    assert src2 == "VERTEX_STANDARD"


def test_quote_agent_end_to_end_3_scenarios():
    """Test full AI Agent quote generation workflow across all 3 scenarios with labor matrix & Excel output"""
    import asyncio
    import openpyxl
    from app.agent.orchestrator import VertexQuoteAgent
    from app.tools.sample_generator import create_sample_excel_boq, create_sample_cad_dxf

    # A. Test CAD Flow (Scenario 1)
    cad_path = "storage/samples/Ban_Ve_CAD_Ong_Gio.dxf"
    create_sample_cad_dxf(cad_path)
    quote1 = asyncio.run(VertexQuoteAgent.process_quote_request(
        file_path=cad_path,
        customer_name="Chủ Đầu Tư Bản Vẽ CAD",
        project_name="Dự án Bóc Tách Bản Vẽ S1"
    ))
    assert quote1.scenario_type == "SCENARIO_1_CAD_TAKEOFF"
    assert quote1.total_material_cost > 0
    assert quote1.total_labor_cost > 0
    assert len(quote1.items) > 0

    # B. Test Specified Brand Flow (Scenario 2)
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "BOQ"
    ws.append(["STT", "Tên Hàng / Thiết Bị", "Quy Cách Kỹ Thuật", "ĐVT", "Số Lượng"])
    ws.append([1, "Máy bơm chữa cháy điện Ebara", "Q=150m3/h H=80m P=45kW, Hãng Ebara", "bộ", 1])
    ws.append([2, "Đầu báo khói quang Hochiki", "Địa chỉ 24V tiêu chuẩn UL/FM, Hãng Hochiki", "bộ", 40])
    ws.append([3, "Đầu phun Sprinkler Viking", "K=5.6 68°C nối ren DN15, Hãng Viking", "bộ", 100])
    s2_file = "storage/samples/Test_BOQ_Specified_Brand.xlsx"
    Path(s2_file).parent.mkdir(parents=True, exist_ok=True)
    wb.save(s2_file)

    quote2 = asyncio.run(VertexQuoteAgent.process_quote_request(
        file_path=s2_file,
        customer_name="Tập Đoàn Xây Dựng ABC",
        project_name="Dự Án Chỉ Định Hãng S2"
    ))
    assert quote2.scenario_type == "SCENARIO_2_SPECIFIED_BRAND"
    # Check that brands are properly populated in QuoteItems
    brand_names = [it.brand for it in quote2.items]
    assert any("Ebara" in b for b in brand_names)
    assert any("Hochiki" in b for b in brand_names)
    assert any("Viking" in b for b in brand_names)

    # Check Excel generation contains Brand column
    from app.tools.excel_generator import VertexExcelGenerator
    excel_path2 = VertexExcelGenerator.generate_quote_excel(quote2)
    wb_read = openpyxl.load_workbook(excel_path2)
    ws_read = wb_read.active
    # Row 12 Col D should be Brand
    assert "Hãng" in str(ws_read["D12"].value) or "Brand" in str(ws_read["D12"].value)


def test_vietnamese_cad_text_decoder_legacy_encodings():
    """Test VietnameseCADTextDecoder across TCVN3, VNI-Windows, AutoCAD \\U+XXXX escapes, and fallback sanitization"""
    from app.tools.vietnamese_cad_decoder import VietnameseCADTextDecoder

    # 1. Test TCVN3 / ABC legacy encoded string
    # "¡ng th¡p m¡ k"m DN50" -> "Ống thép mạ kẽm DN50"
    tcvn3_text = "¡ng th¡p m¡ k\"m DN50"
    decoded_tcvn3 = VietnameseCADTextDecoder.decode_cad_string(tcvn3_text)
    assert "Ống thép mạ kẽm" in decoded_tcvn3
    assert "DN50" in decoded_tcvn3
    assert "¡" not in decoded_tcvn3

    # 2. Test VNI-Windows encoded string
    # "OÁng gioù choáng chaùy EI60" -> "Ống gió chống cháy EI60"
    vni_text = "OÁng gioù choáng chaùy EI60"
    decoded_vni = VietnameseCADTextDecoder.decode_cad_string(vni_text)
    assert "Ống gió chống cháy EI60" in decoded_vni

    # 3. Test AutoCAD \U+XXXX Unicode escape codes and special symbols
    autocad_escape_text = r"{\fArial;\A1;\U+1ED0ng th\U+00E9p DN100\P%%d60%%c50}"
    decoded_autocad = VietnameseCADTextDecoder.decode_cad_string(autocad_escape_text)
    assert "Ống thép DN100" in decoded_autocad
    assert "°60" in decoded_autocad
    assert "Ø50" in decoded_autocad
    assert r"\U+" not in decoded_autocad

    # 4. Test PCCC/HVAC Lexicon auto-repair
    lexicon_sample = "b×nh ch÷a ch¸y MFZL4 - 20 b×nh"
    decoded_lex = VietnameseCADTextDecoder.decode_cad_string(lexicon_sample)
    assert "Bình chữa cháy" in decoded_lex

    # 5. Test Fallback Sanitization (No junk characters like ¡, ¢, £...)
    junk_sample = "¡ng th¡p §¹t tiªu chuÈn PCCC"
    decoded_fallback = VietnameseCADTextDecoder.decode_cad_string(junk_sample)
    assert "¡" not in decoded_fallback
    assert "§" not in decoded_fallback
    assert "PCCC" in decoded_fallback


def test_cad_takeoff_with_legacy_vietnamese_text():
    """Test DXF CAD takeoff engine processing text entities with legacy Vietnamese encoding"""
    from app.tools.cad_takeoff_engine import CADTakeoffEngine
    import ezdxf

    # Create DXF with TCVN3 / VNI style text annotations
    doc = ezdxf.new("R2010")
    msp = doc.modelspace()
    doc.layers.add("PCCC_TEXT_TAGS")

    # Add text with legacy encoding
    msp.add_text("¡ng th¡p m¡ k\"m DN50 - 50 m", dxfattribs={"layer": "PCCC_TEXT_TAGS"})
    msp.add_text(r"{\fArial;\U+1ED0ng gi\U+00F3 vu\U+00F4ng TDC - 120 M2}", dxfattribs={"layer": "PCCC_TEXT_TAGS"})
    msp.add_text("b×nh ch÷a ch¸y MFZL4 - 15 bình", dxfattribs={"layer": "PCCC_TEXT_TAGS"})

    dxf_test_path = "storage/samples/test_legacy_vietnamese_takeoff.dxf"
    Path(dxf_test_path).parent.mkdir(parents=True, exist_ok=True)
    doc.saveas(dxf_test_path)

    result = CADTakeoffEngine.extract_dxf_takeoff(dxf_test_path)
    assert len(result.items) >= 3

    item_names = [it["name"] for it in result.items]
    # Check that names are decoded into proper readable Vietnamese
    assert any("Ống thép mạ kẽm" in n for n in item_names)
    assert any("Ống gió vuông TDC" in n or "Ống Gió Vuông Tdc" in n for n in item_names)
    assert any("Bình chữa cháy" in n or "Bình Chữa Cháy" in n for n in item_names)
    # Check that no corrupt ¡ character appears
    assert not any("¡" in n for n in item_names)


def test_cad_takeoff_auto_add_accessories_norm_calculation():
    """Test automated calculation and addition of PCCC & HVAC accessories based on pipe and duct norms"""
    from fastapi.testclient import TestClient
    from main import app
    from app.services.auth import create_access_token
    from app.database.db import db

    client = TestClient(app)
    admin_user = db.get_user_by_username("admin")
    admin_token = create_access_token(admin_user)

    payload = {
        "items": [
            {"stt": 1, "name": "Ống thép mạ kẽm Sch40 DN100", "spec": "ASTM A53", "unit": "m", "quantity": 250.0, "category": "Piping", "layer": "PCCC_PIPE"},
            {"stt": 2, "name": "Ống gió chống cháy EI60 800x400", "spec": "Tôn hoa sen bọc thạch cao", "unit": "m2", "quantity": 150.0, "category": "HVAC", "layer": "HVAC_DUCT"},
            {"stt": 3, "name": "Đầu phun Sprinkler D20", "spec": "Viking K=5.6", "unit": "bộ", "quantity": 80.0, "category": "PCCC", "layer": "PCCC_SPRINKLER"}
        ]
    }

    response = client.post(
        "/api/cad-takeoff/auto-add-accessories",
        json=payload,
        headers={"Authorization": f"Bearer {admin_token}"}
    )

    assert response.status_code == 200
    res = response.json()
    assert res["status"] == "success"
    assert res["added_count"] == 3
    assert len(res["items"]) == 6

    item_names = [it["name"] for it in res["items"]]
    # 1. Check pipe hangers (250m / 2.5m = 100 sets)
    assert any("Quang treo cùm omega" in n for n in item_names)
    hangers = next(it for it in res["items"] if "Quang treo cùm omega" in it["name"])
    assert hangers["quantity"] == 100.0
    assert hangers["unit"] == "bộ"

    # 2. Check pipe fittings (250m * 18% = 45 items)
    assert any("Phụ kiện nối ống PCCC" in n for n in item_names)
    fittings = next(it for it in res["items"] if "Phụ kiện nối ống PCCC" in it["name"])
    assert fittings["quantity"] == 45.0

    # 3. Check duct hangers (150m2 / 1.5m2 = 100 sets)
    assert any("Giá đỡ & quang treo cùm V" in n for n in item_names)
    duct_hangers = next(it for it in res["items"] if "Giá đỡ & quang treo cùm V" in it["name"])
    assert duct_hangers["quantity"] == 100.0


def test_cad_takeoff_apply_pricing_and_labor_direct_flow():
    """Test direct Takeoff-to-Quote pricing flow with fixed labor matrix and Excel export"""
    from fastapi.testclient import TestClient
    from main import app
    from app.services.auth import create_access_token
    from app.database.db import db

    client = TestClient(app)
    admin_user = db.get_user_by_username("admin")
    admin_token = create_access_token(admin_user)

    payload = {
        "customer_name": "Tập Đoàn Bất Động Sản SunGroup",
        "customer_phone": "0988.777.666",
        "project_name": "Tòa Tháp Đôi Sun Grand City Bóc Tách CAD",
        "project_address": "Tây Hồ, Hà Nội",
        "discount_rate": 5,
        "vat_rate": 8,
        "template_id": "tpl_pccc_standard_2026",
        "items": [
            {"name": "Ống thép mạ kẽm Sch40 DN50", "spec": "ASTM A53", "unit": "m", "quantity": 100.0, "category": "Piping", "layer": "PCCC_PIPE"},
            {"name": "Đầu báo khói quang học địa chỉ Hochiki", "spec": "Hãng Hochiki Japan", "unit": "bộ", "quantity": 20.0, "category": "Báo cháy", "layer": "ALARM"},
            {"name": "Đèn Exit thoát hiểm Paragon 2 mặt", "spec": "Hãng Paragon", "unit": "bộ", "quantity": 10.0, "category": "Chiếu sáng sự cố", "layer": "EXIT_LIGHT"},
            {"name": "Ống gió chống cháy EI60 600x400", "spec": "Tôn dày 0.75mm", "unit": "m2", "quantity": 50.0, "category": "HVAC", "layer": "DUCT"}
        ]
    }

    response = client.post(
        "/api/cad-takeoff/apply-pricing-and-labor",
        json=payload,
        headers={"Authorization": f"Bearer {admin_token}"}
    )

    assert response.status_code == 200
    res = response.json()
    assert res["status"] == "success"
    assert "quote_id" in res
    assert res["quote_code"].startswith("VTX-") or res["quote_code"].startswith("BG-")
    assert res["total_labor_cost"] > 0
    assert res["total_material_cost"] > 0
    assert res["total_amount"] > 0
    assert res["excel_download_url"].startswith("/api/quotes/")

    # Verify Labor Cost Matrix calculations:
    # Ống: 100m * 220,000 = 22,000,000
    # Báo cháy: 20 bộ * 350,000 = 7,000,000
    # Exit: 10 bộ * 370,000 = 3,700,000
    # Ống gió EI60: 50 đoạn 600x400x1.18m (118m2) * 130,000 = 15,340,000
    # Expected Labor = 22,000,000 + 7,000,000 + 3,700,000 + 15,340,000 = 48,040,000 VNĐ
    assert res["total_labor_cost"] == 48040000.0


def test_security_hmac_approval_and_zalo_webhook():
    """Test VULN-01 & VULN-02 fixes: HMAC approval token and Zalo webhook signature protection"""
    import hmac
    import hashlib
    from fastapi.testclient import TestClient
    from main import app
    from app.config import settings
    from app.database.db import db
    from app.database.models import Quote, QuoteStatus
    from app.services.auth import generate_approval_token, create_access_token

    client = TestClient(app)
    
    # 1. Create a dummy pending quote
    q_id = "test_quote_sec_001"
    quote = Quote(
        id=q_id,
        quote_code="VTX-SEC-001",
        customer_name="Khách Hàng Bảo Mật",
        project_name="Dự Án Bảo Mật",
        status=QuoteStatus.PENDING_APPROVAL,
        version=1,
        total_amount=10000000,
        items=[]
    )
    db.save_quote(quote)

    # 2. Test GET /approve without token -> Must return 422/401 (Missing/Invalid Token)
    res_no_tok = client.get(f"/api/quotes/{q_id}/approve?action=approve")
    assert res_no_tok.status_code in [401, 422]

    # 3. Test GET /approve with forged/tampered token -> Must return 401
    res_bad_tok = client.get(f"/api/quotes/{q_id}/approve?action=approve&token=9999999999.fake_sig")
    assert res_bad_tok.status_code == 401

    # 4. Test GET /approve with valid HMAC token -> Must return 200 HTML
    valid_token = generate_approval_token(q_id, "approve", settings.SECRET_KEY, expire_minutes=60)
    res_valid = client.get(f"/api/quotes/{q_id}/approve?action=approve&token={valid_token}&manager_name=Anh%20Việt")
    assert res_valid.status_code == 200
    assert "ĐÃ DUYỆT THÀNH CÔNG" in res_valid.text

    # 5. Test Zalo Webhook without signature -> Must return 403
    res_wh_no_sig = client.post("/api/zalo/webhook", json={"event_name": "user_submit_action"})
    assert res_wh_no_sig.status_code == 403

    # 6. Test /simulate-approval without Manager Auth -> Must return 401
    res_sim_no_auth = client.post("/api/zalo/simulate-approval", json={"quote_id": q_id, "action": "approve"})
    assert res_sim_no_auth.status_code == 401


def test_security_production_startup_validation():
    """Test VULN-03 fix: Production startup aborts if SECRET_KEY or AI_API_KEY is empty/insecure"""
    import pytest
    from main import lifespan, app
    from app.config import settings

    # Simulate production with empty AI key and custom secret key
    orig_env = settings.APP_ENV
    orig_key = settings.AI_API_KEY
    orig_sec = settings.SECRET_KEY
    try:
        settings.APP_ENV = "production"
        settings.SECRET_KEY = "super_secure_production_secret_key_vertex_2026"
        settings.AI_API_KEY = ""
        with pytest.raises(RuntimeError, match="AI_API_KEY"):
            import asyncio
            async def run_ls():
                async with lifespan(app):
                    pass
            asyncio.run(run_ls())
    finally:
        settings.APP_ENV = orig_env
        settings.AI_API_KEY = orig_key
        settings.SECRET_KEY = orig_sec


def test_security_idor_quote_access_protection():
    """Test VULN-04 fix: Low-privileged users cannot access other users' quotes (IDOR Protection)"""
    from fastapi.testclient import TestClient
    from main import app
    from app.database.db import db
    from app.database.models import Quote, QuoteStatus, User, UserRole, UserStatus, UserInDB
    from app.services.auth import create_access_token, hash_password

    client = TestClient(app)

    # 1. Create a private confidential quote for Customer Alpha created by Admin
    confidential_id = "quote_confidential_alpha_999"
    quote_alpha = Quote(
        id=confidential_id,
        quote_code="VTX-CONFIDENTIAL-999",
        customer_name="Tập Đoàn Bảo Mật Alpha",
        customer_email="alpha_ceo@company.com",
        customer_phone="0911223344",
        project_name="Dự án Tối Mật Quân Đội",
        status=QuoteStatus.PENDING_APPROVAL,
        version=1,
        total_amount=500000000,
        items=[],
        logs=["[Admin] Tạo báo giá nội bộ tối mật"]
    )
    db.save_quote(quote_alpha)

    # 2. Create and login an unauthorized Dealer / Partner user
    import uuid
    uniq = uuid.uuid4().hex[:6]
    dealer_user = UserInDB(
        id=f"user_dealer_test_{uniq}",
        username=f"dealer_competitor_{uniq}",
        full_name="Đại Lý Đối Thủ Beta",
        email=f"dealer_beta_{uniq}@competitor.com",
        phone="0988999888",
        company_name="Công Ty Phân Phối Beta",
        role=UserRole.DEALER,
        status=UserStatus.ACTIVE,
        hashed_password=hash_password("Vertex@2026"),
        is_active=True,
        created_at="2026-08-29 00:00:00"
    )
    db.create_user(dealer_user)

    dealer_token = create_access_token(
        User(
            id=dealer_user.id,
            username=dealer_user.username,
            full_name=dealer_user.full_name,
            email=dealer_user.email,
            phone=dealer_user.phone,
            company_name=dealer_user.company_name,
            role=dealer_user.role,
            status=dealer_user.status,
            is_active=True,
            created_at=dealer_user.created_at
        )
    )
    dealer_headers = {"Authorization": f"Bearer {dealer_token}"}

    # 3. Dealer attempts to access confidential quote -> Must be blocked 403
    res_idor_get = client.get(f"/api/quotes/{confidential_id}", headers=dealer_headers)
    assert res_idor_get.status_code == 403
    assert "IDOR Protection" in res_idor_get.json()["detail"]

    # 4. Dealer attempts to access audit logs -> Must be blocked 403
    res_idor_audit = client.get(f"/api/quotes/{confidential_id}/audit-logs", headers=dealer_headers)
    assert res_idor_audit.status_code == 403

    # 5. Dealer attempts to download excel -> Must be blocked 403
    res_idor_dl = client.get(f"/api/quotes/{confidential_id}/download", headers=dealer_headers)
    assert res_idor_dl.status_code == 403

    # 6. Admin / Manager accesses the quote -> Allowed 200 OK
    admin_user = db.get_user_by_username("admin")
    admin_token = create_access_token(admin_user)
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    res_admin_get = client.get(f"/api/quotes/{confidential_id}", headers=admin_headers)
    assert res_admin_get.status_code == 200
    assert res_admin_get.json()["id"] == confidential_id


def test_security_xss_sanitization_in_approval_html():
    """Test VULN-05 fix: Customer and project names with XSS scripts are safely escaped in approval HTML"""
    from fastapi.testclient import TestClient
    from main import app
    from app.config import settings
    from app.database.db import db
    from app.database.models import Quote, QuoteStatus
    from app.services.auth import generate_approval_token

    client = TestClient(app)

    # 1. Create quote with malicious XSS payloads in customer_name and project_name
    xss_quote_id = "quote_xss_test_payload_123"
    quote = Quote(
        id=xss_quote_id,
        quote_code="VTX-XSS-123",
        customer_name="<script>alert('Pwned')</script>",
        project_name="<img src=x onerror=document.location='http://evil.com'>",
        status=QuoteStatus.PENDING_APPROVAL,
        version=1,
        total_amount=25000000,
        items=[]
    )
    db.save_quote(quote)

    # 2. Access approval page with valid HMAC token
    token = generate_approval_token(xss_quote_id, "approve", settings.SECRET_KEY, expire_minutes=60)
    res = client.get(f"/api/quotes/{xss_quote_id}/approve?token={token}&action=approve&manager_name=<svg/onload=alert(1)>")

    assert res.status_code == 200
    # Must NOT contain raw unescaped script / onerror tags
    assert "<script>alert('Pwned')</script>" not in res.text
    assert "<img src=x onerror=" not in res.text
    assert "<svg/onload=alert(1)>" not in res.text

    # Must contain HTML escaped entities
    assert "&lt;script&gt;alert(&#x27;Pwned&#x27;)&lt;/script&gt;" in res.text or "&lt;script&gt;alert('Pwned')&lt;/script&gt;" in res.text
    assert "&lt;img" in res.text
    assert "&lt;svg/onload=alert(1)&gt;" in res.text or "&lt;svg" in res.text


def test_security_cors_configuration():
    """Test VULN-06 fix: CORS headers properly configured for production vs development"""
    from fastapi.testclient import TestClient
    from main import app
    from app.config import settings

    client = TestClient(app)

    # Test preflight OPTIONS request
    res = client.options(
        "/api/quotes",
        headers={
            "Origin": "http://localhost:8000",
            "Access-Control-Request-Method": "GET"
        }
    )
    assert res.status_code == 200
    assert "access-control-allow-origin" in res.headers


# ==============================================================================
# TESTS FOR INVENTORY, BOM & MULTI-TIER QUOTE BUILDER MODULES
# ==============================================================================

def test_inventory_warehouse_isolation_and_filtering():
    """Test warehouse isolation between Manufacturing and Commercial/Project stocks"""
    from app.services.auth import create_access_token
    from app.database.db import db
    from app.database.models import WarehouseType

    user = db.get_user_by_username("admin")
    token = create_access_token(user)
    headers = {"Authorization": f"Bearer {token}"}
    client.cookies.set("access_token", token)

    # 1. Test page access
    res_page = client.get("/inventory", headers=headers)
    assert res_page.status_code == 200
    assert "KHO SẢN XUẤT" in res_page.text
    assert "KHO THƯƠNG MẠI" in res_page.text

    # 2. Test API Manufacturing isolation
    res_mfg = client.get("/api/inventory/items?warehouse_type=MANUFACTURING", headers=headers)
    assert res_mfg.status_code == 200
    mfg_items = res_mfg.json()["items"]
    assert len(mfg_items) >= 12
    for item in mfg_items:
        assert item["warehouse_type"] == "MANUFACTURING"

    # Check presence of VinFast EV Skid Plates
    mfg_skus = [i["sku"] for i in mfg_items]
    assert "VTX-MFG-EV-VF8" in mfg_skus
    assert "VTX-MFG-EV-VF9" in mfg_skus
    assert "VTX-MFG-EV-VF5" in mfg_skus
    assert "VTX-MFG-DUCT-EI30" in mfg_skus

    # 3. Test API Commercial isolation
    res_com = client.get("/api/inventory/items?warehouse_type=COMMERCIAL", headers=headers)
    assert res_com.status_code == 200
    com_items = res_com.json()["items"]
    assert len(com_items) >= 12
    for item in com_items:
        assert item["warehouse_type"] == "COMMERCIAL"

    com_skus = [i["sku"] for i in com_items]
    assert "VTX-COM-EXT-001" in com_skus
    assert "VTX-COM-SPK-001" in com_skus
    assert "VTX-COM-VLV-001" in com_skus
    assert "VTX-COM-ALM-001" in com_skus

    # 4. Test Search filter
    res_search = client.get("/api/inventory/items?search=VinFast", headers=headers)
    assert res_search.status_code == 200
    search_items = res_search.json()["items"]
    assert len(search_items) >= 3


def test_bom_calculation_engine():
    """Test mathematical accuracy of factory cost aggregation and pricing margin targets"""
    from app.tools.bom_engine import calculate_bom_cost

    raw_mats = [
        {"material_name": "Tấm nhôm AL5052 (3.0mm)", "quantity": 25.0, "unit_cost": 115000.0},
        {"material_name": "Bulong Inox 304", "quantity": 1.0, "unit_cost": 180000.0}
    ]
    # Raw material cost = 25 * 115000 + 180000 = 2875000 + 180000 = 3055000
    # Scrap waste (5%) = 3055000 * 0.05 = 152750
    # Labor = 750000, Overhead = 475000
    # Expected Real Cost = 3055000 + 152750 + 750000 + 475000 = 4432750
    bom_res = calculate_bom_cost(
        raw_materials=raw_mats,
        scrap_waste_ratio=0.05,
        labor_cost=750000.0,
        overhead_cost=475000.0,
        margin_retail=0.30,
        margin_dealer=0.15
    )

    assert bom_res["raw_material_cost"] == 3055000.0
    assert bom_res["scrap_waste_cost"] == 152750.0
    assert bom_res["calculated_cost_price"] == 4432750.0
    assert bom_res["suggested_retail_price"] > bom_res["calculated_cost_price"]
    assert bom_res["suggested_dealer_price"] > bom_res["calculated_cost_price"]
    assert bom_res["suggested_retail_price"] > bom_res["suggested_dealer_price"]


def test_manufacturing_dimensions_and_weight_calculator():
    """Test custom dimension, area (m2) and weight (kg) formulas for manufactured goods"""
    from app.tools.bom_engine import calculate_manufacturing_dimensions

    # 1. Test VinFast VF8 Skid Plate (2150mm x 1450mm x 3.0mm AL5052)
    # Area = (2150 * 1450) / 10^6 = 3.1175 m2
    # Weight = 3.1175 m2 * 3.0mm * 2.70 kg/m2/mm = 25.25 kg
    vf8_res = calculate_manufacturing_dimensions(
        category="Tấm ốp gầm pin xe điện VinFast",
        material_type="NHÔM_AL5052",
        length_mm=2150,
        width_mm=1450,
        thickness_mm=3.0,
        base_cost_price=4850000,
        base_retail_price=7500000,
        base_dealer_price=6200000,
        quantity=2
    )
    assert vf8_res["area_per_unit_m2"] == 3.1175
    assert vf8_res["total_area_m2"] == round(3.1175 * 2, 4)
    assert vf8_res["weight_per_unit_kg"] == 25.25
    assert vf8_res["total_weight_kg"] == 50.5

    # 2. Test Rectangular Duct (1200mm L x 500mm W x 300mm H)
    # Area = 2 * (500 + 300) * 1200 / 10^6 = 2 * 800 * 1200 / 10^6 = 1.92 m2
    duct_res = calculate_manufacturing_dimensions(
        category="Ống gió chống cháy EI",
        material_type="THÉP_MẠ_KẼM",
        length_mm=1200,
        width_mm=500,
        height_mm=300,
        thickness_mm=0.75,
        base_cost_price=380000,
        base_retail_price=560000,
        base_dealer_price=480000,
        quantity=1
    )
    assert duct_res["area_per_unit_m2"] == 1.92
    assert duct_res["unit_cost_price"] == round(380000 * 1.92, 0)
    assert duct_res["unit_retail_price"] == round(560000 * 1.92, 0)


def test_multi_tier_pricing_rules():
    """Test 4-tier pricing engine for Retail, Dealer, and Project contracting tiers"""
    from app.tools.bom_engine import resolve_tier_price
    from app.database.models import CustomerTier

    cost = 1000000.0
    retail = 1500000.0
    dealer = 1250000.0
    proj_disc = 10.0

    # 1. Retail Tier
    u_ret, c_ret, d_ret = resolve_tier_price(cost, retail, dealer, proj_disc, CustomerTier.RETAIL)
    assert u_ret == 1500000.0
    assert d_ret == 0.0

    # 2. Dealer Tier
    u_dlr, c_dlr, d_dlr = resolve_tier_price(cost, retail, dealer, proj_disc, CustomerTier.DEALER)
    assert u_dlr == 1250000.0
    assert d_dlr == round(((1500000 - 1250000) / 1500000 * 100), 1)

    # 3. Project Tier (Standard < 500M)
    u_prj, c_prj, d_prj = resolve_tier_price(cost, retail, dealer, proj_disc, CustomerTier.PROJECT, total_quote_value=100000000)
    assert u_prj == round(1500000 * (1 - 0.10), 0)
    assert d_prj == 10.0

    # 4. Project Tier (Large contract >= 1B -> extra 4% discount)
    u_prj_large, _, d_prj_large = resolve_tier_price(cost, retail, dealer, proj_disc, CustomerTier.PROJECT, total_quote_value=1200000000)
    assert d_prj_large == 14.0
    assert u_prj_large == round(1500000 * (1 - 0.14), 0)


def test_quote_builder_interactive_line_item_and_save():
    """Test full workflow of the interactive Quote Builder workspace and quotation persistence"""
    from app.services.auth import create_access_token
    from app.database.db import db

    user = db.get_user_by_username("admin")
    token = create_access_token(user)
    headers = {"Authorization": f"Bearer {token}"}
    client.cookies.set("access_token", token)

    # 1. Test Quote Builder page load
    res_page = client.get("/quote-builder", headers=headers)
    assert res_page.status_code == 200
    assert "ĐỘNG CƠ GIÁ 4 TẦNG" in res_page.text or "Lập Báo Giá Thông Minh" in res_page.text

    # 2. Test Line Item calculation API for VinFast VF8 Skid plate with Dealer tier
    res_calc = client.post(
        "/api/quote-builder/calculate-line-item",
        json={
            "inventory_id": "inv-mfg-ev-001",
            "customer_tier": "DEALER",
            "quantity": 5
        },
        headers=headers
    )
    assert res_calc.status_code == 200
    calc_data = res_calc.json()["data"]
    assert calc_data["unit_price"] == 6200000.0
    assert calc_data["total_price"] == 31000000.0
    assert calc_data["margin_percent"] > 20.0

    # 3. Test saving a complete Quote via Quote Builder
    save_payload = {
        "customer_name": "Công Ty CP Giao Hàng & Taxi Xanh SM",
        "customer_phone": "0912.888.999",
        "customer_email": "taxixanh@vinfast.vn",
        "project_name": "Gói Tấm Ốp Bảo Vệ Gầm Pin VinFast VF8 & Thiết Bị PCCC",
        "project_address": "Khu Đô Thị Vinhomes Ocean Park, Gia Lâm, Hà Nội",
        "customer_tier": "DEALER",
        "vat_rate": 0.08,
        "special_discount_percent": 2.0,
        "items": [
            {
                "inventory_id": "inv-mfg-ev-001",
                "sku": "VTX-MFG-EV-VF8",
                "item_name": "Tấm ốp bảo vệ gầm pin xe điện VinFast VF8 (Nhôm AL5052 3.0mm)",
                "warehouse_type": "MANUFACTURING",
                "category": "Tấm ốp gầm pin xe điện VinFast",
                "unit": "tấm",
                "quantity": 10,
                "cost_price": 4850000.0,
                "unit_price": 6200000.0,
                "total_price": 62000000.0,
                "applied_tier": "DEALER"
            },
            {
                "inventory_id": "inv-com-ext-001",
                "sku": "VTX-COM-EXT-001",
                "item_name": "Bình chữa cháy bột ABC 4kg Tomoken",
                "warehouse_type": "COMMERCIAL",
                "category": "Bình chữa cháy",
                "unit": "bình",
                "quantity": 20,
                "cost_price": 215000.0,
                "unit_price": 275000.0,
                "total_price": 5500000.0,
                "applied_tier": "DEALER"
            }
        ]
    }

    res_save = client.post("/api/quote-builder/save-quote", json=save_payload, headers=headers)
    assert res_save.status_code == 200
    save_data = res_save.json()
    assert save_data["status"] == "success"
    assert "VTX-" in save_data["quote_code"]
    assert save_data["total_amount"] > 0
    assert save_data["margin_percent"] > 15.0

    # Verify quote saved in DB
    created_q = db.get_quote_by_id(save_data["quote_id"])
    assert created_q is not None
    assert created_q.customer_name == "Công Ty CP Giao Hàng & Taxi Xanh SM"
    assert len(created_q.items) == 2
    assert created_q.total_amount == save_data["total_amount"]














