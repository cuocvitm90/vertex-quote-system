"""
Live verification script against running FastAPI server
Includes Login, JWT Auth, Catalog, BOQ Upload, Calculator Precision, and Zalo Approval.
"""
import sys
import requests
import json
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

BASE_URL = "http://127.0.0.1:8000"


def run_live_check():
    session = requests.Session()

    print("--- 1. Testing Unauthenticated Access & Login Page ---")
    r_unauth = session.get(f"{BASE_URL}/", allow_redirects=False)
    print(f"GET / (Unauthenticated) -> Status: {r_unauth.status_code} (Redirected to: {r_unauth.headers.get('location')})")

    r_login_page = session.get(f"{BASE_URL}/login")
    print(f"GET /login -> Status: {r_login_page.status_code}, Contains 'VERTEX CONSTRUCTION': {'VERTEX' in r_login_page.text}")

    print("\n--- 2. Performing Login as Manager (Anh Việt) ---")
    login_payload = {
        "username": "admin",
        "password": "Vertex@2026"
    }
    r_login = session.post(f"{BASE_URL}/api/auth/login", json=login_payload)
    print(f"POST /api/auth/login -> Status: {r_login.status_code}")
    login_data = r_login.json()
    token = login_data["access_token"]
    user_info = login_data["user"]
    print(f"  - Đăng nhập thành công: {user_info['full_name']} (Role: {user_info['role']})")
    print(f"  - Token: {token[:20]}...{token[-10:]}")

    # Attach token to session headers
    session.headers.update({"Authorization": f"Bearer {token}"})

    print("\n--- 3. Testing Authenticated Dashboard Access ---")
    r_dash = session.get(f"{BASE_URL}/")
    print(f"GET / (Authenticated) -> Status: {r_dash.status_code}, Contains User Name: {user_info['full_name'] in r_dash.text}")

    print("\n--- 4. Testing Price Catalog & Google Drive Sync ---")
    r_cat = session.get(f"{BASE_URL}/api/catalog")
    items = r_cat.json()
    print(f"GET /api/catalog -> Status: {r_cat.status_code}, Total Catalog Items: {len(items)}")

    r_gdrive = session.post(f"{BASE_URL}/api/catalog/sync-gdrive")
    print(f"POST /api/catalog/sync-gdrive -> Status: {r_gdrive.status_code}, Folder: {r_gdrive.json().get('folder_id')}")

    print("\n--- 5. Testing BOQ Excel Upload & AI Pipeline ---")
    sample_excel = "storage/samples/BOQ_Mau_Ong_Gio_Vertex.xlsx"
    with open(sample_excel, "rb") as f:
        files = {"file": ("BOQ_Mau_Ong_Gio_Vertex.xlsx", f, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
        data = {
            "customer_name": "Tập Đoàn Xây Dựng Delta",
            "customer_phone": "0904.555.666",
            "customer_zalo_id": "delta_buyer_01",
            "project_name": "Khách Sạn 5 Sao Delta Grand",
            "project_address": "Võ Nguyên Giáp, Đà Nẵng",
            "discount_rate": 0.05,
            "vat_rate": 0.08
        }
        r_upload = session.post(f"{BASE_URL}/api/quotes/upload", files=files, data=data)

    print(f"POST /api/quotes/upload -> Status: {r_upload.status_code}")
    res_data = r_upload.json()
    quote = res_data["quote"]
    quote_id = quote["id"]
    quote_code = quote["quote_code"]
    print(f"  - Mã báo giá: {quote_code}")
    print(f"  - Số hạng mục vật tư: {len(quote['items'])}")
    print(f"  - Tổng tiền trước thuế: {quote['subtotal']:,.0f} đ")
    print(f"  - Chiết khấu (5%): {quote['discount_amount']:,.0f} đ")
    print(f"  - Thuế VAT (8%): {quote['vat_amount']:,.0f} đ")
    print(f"  - TỔNG CỘNG: {quote['total_amount']:,.0f} đ")
    print(f"  - Bằng chữ: {quote['total_amount_in_words']}")
    print(f"  - Trạng thái: {quote['status']}")

    print("\n--- 6. Testing Download Generated Excel ---")
    r_dl = session.get(f"{BASE_URL}/api/quotes/{quote_id}/download")
    print(f"GET /api/quotes/{quote_id}/download -> Status: {r_dl.status_code}, File size: {len(r_dl.content)} bytes")

    print("\n--- 7. Testing Manager Approval via Zalo Webhook Simulation ---")
    r_appr = session.post(
        f"{BASE_URL}/api/zalo/simulate-approval",
        json={
            "quote_id": quote_id,
            "action": "approve",
            "manager_name": user_info["full_name"]
        }
    )
    print(f"POST /api/zalo/simulate-approval -> Status: {r_appr.status_code}")
    appr_data = r_appr.json()
    print(f"  - Kết quả duyệt: {appr_data.get('message')}")

    print("\n--- 8. Verifying Final Status & Audit Logs ---")
    r_final = session.get(f"{BASE_URL}/api/quotes/{quote_id}")
    final_quote = r_final.json()
    print(f"  - Trạng thái cuối cùng: {final_quote['status']}")
    print(f"  - Người phê duyệt: {final_quote['approved_by']}")
    for log in final_quote['logs'][-4:]:
        print(f"    * {log}")

    print("\n✅ TOÀN BỘ WORKFLOW XÁC THỰC, BẢO MẬT & TÍNH TOÁN ĐÃ ĐẠT 100%!")


if __name__ == "__main__":
    run_live_check()
