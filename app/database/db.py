"""
Database & Storage Layer for Vertex Construction & PCCC Quote System
Provides persistence for Users (Auth, RBAC, Status), Master Templates & Pricing Coefficients,
Quotes, PCCC Price Catalog, and Audit Logs.
"""
import json
import sqlite3
import os
import uuid
import hashlib
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any
from app.config import settings
from app.database.models import (
    Quote, QuoteItem, PriceCatalogItem, QuoteStatus,
    User, UserRole, UserStatus, UserInDB, MasterTemplate,
    AttendanceCheckin, FieldDailyReport, AuditLog, GeofenceAlertRecord,
    InventoryItem, WarehouseType
)

DB_PATH = Path(settings.STORAGE_DIR) / "vertex_quotes.db"


def _hash_pwd(password: str, salt: str = "vertex_pccc_salt_2026") -> str:
    key = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt.encode('utf-8'), 100000)
    return f"{salt}${key.hex()}"


class Database:
    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        self._init_db()
        self._seed_catalog()
        self._seed_users()
        self._seed_master_template()
        self._seed_field_data()
        self._seed_inventory_data()

    def _get_connection(self):
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # 1. Users Table (Authentication, RBAC & Status)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                full_name TEXT NOT NULL,
                email TEXT,
                phone TEXT,
                company_name TEXT,
                role TEXT NOT NULL DEFAULT 'STAFF',
                status TEXT NOT NULL DEFAULT 'ACTIVE',
                hashed_password TEXT NOT NULL,
                is_active INTEGER DEFAULT 1,
                created_at TEXT
            )
            """)

            # Alter users table if older columns are missing
            cursor.execute("PRAGMA table_info(users)")
            user_cols = [col[1] for col in cursor.fetchall()]
            if "phone" not in user_cols:
                cursor.execute("ALTER TABLE users ADD COLUMN phone TEXT DEFAULT ''")
            if "company_name" not in user_cols:
                cursor.execute("ALTER TABLE users ADD COLUMN company_name TEXT DEFAULT ''")
            if "status" not in user_cols:
                cursor.execute("ALTER TABLE users ADD COLUMN status TEXT NOT NULL DEFAULT 'ACTIVE'")

            # 2. Master Templates & Pricing Coefficients Table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS master_templates (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                file_path TEXT,
                file_name TEXT,
                description TEXT,
                waste_ratio REAL DEFAULT 0.05,
                transport_ratio REAL DEFAULT 0.03,
                labor_ratio REAL DEFAULT 0.15,
                margin_ratio REAL DEFAULT 0.12,
                vat_rate REAL DEFAULT 0.08,
                default_discount_rate REAL DEFAULT 0.05,
                is_active INTEGER DEFAULT 1,
                created_by TEXT,
                created_at TEXT,
                updated_at TEXT
            )
            """)

            # 3. Quotes Table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS quotes (
                id TEXT PRIMARY KEY,
                quote_code TEXT UNIQUE,
                customer_name TEXT,
                customer_phone TEXT,
                customer_email TEXT,
                customer_zalo_id TEXT,
                project_name TEXT,
                project_address TEXT,
                status TEXT,
                language TEXT DEFAULT 'vi',
                version INTEGER DEFAULT 1,
                parent_quote_id TEXT DEFAULT '',
                revision_note TEXT DEFAULT '',
                required_approval_level TEXT DEFAULT 'MANAGER',
                manager_approved_by TEXT DEFAULT '',
                manager_approved_at TEXT DEFAULT '',
                director_approved_by TEXT DEFAULT '',
                director_approved_at TEXT DEFAULT '',
                template_id TEXT,
                template_name TEXT,
                subtotal REAL,
                discount_rate REAL,
                discount_amount REAL,
                subtotal_after_discount REAL,
                vat_rate REAL,
                vat_amount REAL,
                total_amount REAL,
                total_amount_in_words TEXT,
                input_file_name TEXT,
                input_file_path TEXT,
                excel_quote_path TEXT,
                created_at TEXT,
                updated_at TEXT,
                approved_by TEXT,
                approved_at TEXT,
                rejection_reason TEXT,
                items_json TEXT,
                logs_json TEXT
            )
            """)

            # Alter quotes table if columns are missing
            cursor.execute("PRAGMA table_info(quotes)")
            q_cols = [col[1] for col in cursor.fetchall()]
            if "language" not in q_cols:
                cursor.execute("ALTER TABLE quotes ADD COLUMN language TEXT DEFAULT 'vi'")
            if "version" not in q_cols:
                cursor.execute("ALTER TABLE quotes ADD COLUMN version INTEGER DEFAULT 1")
            if "parent_quote_id" not in q_cols:
                cursor.execute("ALTER TABLE quotes ADD COLUMN parent_quote_id TEXT DEFAULT ''")
            if "revision_note" not in q_cols:
                cursor.execute("ALTER TABLE quotes ADD COLUMN revision_note TEXT DEFAULT ''")
            if "required_approval_level" not in q_cols:
                cursor.execute("ALTER TABLE quotes ADD COLUMN required_approval_level TEXT DEFAULT 'MANAGER'")
            if "manager_approved_by" not in q_cols:
                cursor.execute("ALTER TABLE quotes ADD COLUMN manager_approved_by TEXT DEFAULT ''")
            if "manager_approved_at" not in q_cols:
                cursor.execute("ALTER TABLE quotes ADD COLUMN manager_approved_at TEXT DEFAULT ''")
            if "director_approved_by" not in q_cols:
                cursor.execute("ALTER TABLE quotes ADD COLUMN director_approved_by TEXT DEFAULT ''")
            if "director_approved_at" not in q_cols:
                cursor.execute("ALTER TABLE quotes ADD COLUMN director_approved_at TEXT DEFAULT ''")
            if "template_id" not in q_cols:
                cursor.execute("ALTER TABLE quotes ADD COLUMN template_id TEXT DEFAULT ''")
            if "template_name" not in q_cols:
                cursor.execute("ALTER TABLE quotes ADD COLUMN template_name TEXT DEFAULT ''")
            if "scenario_type" not in q_cols:
                cursor.execute("ALTER TABLE quotes ADD COLUMN scenario_type TEXT DEFAULT 'SCENARIO_3_STANDARD_CATALOG'")
            if "total_material_cost" not in q_cols:
                cursor.execute("ALTER TABLE quotes ADD COLUMN total_material_cost REAL DEFAULT 0.0")
            if "total_labor_cost" not in q_cols:
                cursor.execute("ALTER TABLE quotes ADD COLUMN total_labor_cost REAL DEFAULT 0.0")

            # 4. Audit Trail / Activity Log Table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS audit_logs (
                id TEXT PRIMARY KEY,
                quote_id TEXT,
                user_id TEXT,
                user_name TEXT,
                user_role TEXT,
                action TEXT,
                details TEXT,
                ip_address TEXT,
                timestamp TEXT
            )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_audit_logs_quote ON audit_logs(quote_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_audit_logs_time ON audit_logs(timestamp)")

            # 5. Price Catalog Table (PCCC Equipment & HVAC)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS catalog (
                code TEXT PRIMARY KEY,
                name TEXT,
                category TEXT,
                material TEXT,
                thickness REAL,
                unit TEXT,
                unit_price REAL,
                keywords_json TEXT,
                notes TEXT
            )
            """)

            # 6. Attendance Checkins Table (GPS Geolocation & Site Tracking)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS attendance_checkins (
                id TEXT PRIMARY KEY,
                user_id TEXT,
                user_name TEXT,
                project_site TEXT,
                checkin_type TEXT,
                latitude REAL,
                longitude REAL,
                accuracy_meters REAL,
                address_resolved TEXT,
                status TEXT,
                notes TEXT,
                created_at TEXT
            )
            """)

            # 7. Field Daily Reports Table (Progress, Workforce, Issues, Photos)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS field_daily_reports (
                id TEXT PRIMARY KEY,
                user_id TEXT,
                user_name TEXT,
                project_name TEXT,
                report_date TEXT,
                weather_condition TEXT,
                work_summary TEXT,
                progress_percent REAL,
                workforce_count INTEGER,
                issues_and_risks TEXT,
                next_plan TEXT,
                photos_json TEXT,
                supervisor_comment TEXT,
                status TEXT,
                created_at TEXT
            )
            """)

            # 8. Geofence Alerts Table (Out-of-zone incident log)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS geofence_alerts (
                id TEXT PRIMARY KEY,
                user_id TEXT,
                user_name TEXT,
                project_site TEXT,
                latitude REAL,
                longitude REAL,
                distance_meters REAL,
                radius_meters REAL,
                alert_message TEXT,
                status TEXT DEFAULT 'UNRESOLVED',
                created_at TEXT
            )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_geofence_alerts_time ON geofence_alerts(created_at)")

            # 9. Inventory Items & Manufacturing BOM Table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS inventory_items (
                id TEXT PRIMARY KEY,
                sku TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                warehouse_type TEXT NOT NULL DEFAULT 'MANUFACTURING',
                category TEXT NOT NULL,
                unit TEXT DEFAULT 'cái',
                stock_quantity REAL DEFAULT 0,
                cost_price REAL DEFAULT 0,
                retail_price REAL DEFAULT 0,
                dealer_price REAL DEFAULT 0,
                project_discount_rate REAL DEFAULT 0,
                is_custom_dimensions INTEGER DEFAULT 0,
                default_length REAL,
                default_width REAL,
                default_thickness REAL,
                material_type TEXT,
                bom_data TEXT,
                spec TEXT,
                notes TEXT,
                created_at TEXT,
                updated_at TEXT
            )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_inventory_warehouse ON inventory_items(warehouse_type)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_inventory_sku ON inventory_items(sku)")

            conn.commit()

    def _seed_master_template(self):
        """Seeds default Master Template with standard pricing coefficients"""
        default_tpl_id = "tpl-vertex-master-default"
        tpl_dir = Path(settings.STORAGE_DIR) / "templates"
        tpl_dir.mkdir(parents=True, exist_ok=True)
        default_file = tpl_dir / "Master_Template_Vertex.xlsx"

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM master_templates WHERE id = ?", (default_tpl_id,))
            if cursor.fetchone()[0] == 0:
                cursor.execute("""
                INSERT INTO master_templates 
                (id, name, file_path, file_name, description, waste_ratio, transport_ratio, labor_ratio, margin_ratio, is_active, created_by, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, 'Sếp Tiến (Giám đốc)', datetime('now'), datetime('now'))
                """, (
                    default_tpl_id,
                    "Mẫu Định Mức & Báo Giá Chuẩn Vertex 2026",
                    str(default_file),
                    "Master_Template_Vertex.xlsx",
                    "Mẫu chuẩn bóc tách PCCC & Cơ điện định lượng hệ số: 5% Hao hụt, 3% Vận chuyển, 15% Nhân công, 12% Lợi nhuận",
                    0.05,
                    0.03,
                    0.15,
                    0.12
                ))
                conn.commit()

    def _seed_users(self):
        """Seed default admin, manager and staff accounts"""
        default_users = [
            {
                "username": "admin",
                "full_name": "Anh Việt (Trưởng phòng KD PCCC)",
                "email": "viet.manager@vertexhvac.vn",
                "phone": "0912.888.999",
                "company_name": "Vertex Construction & PCCC",
                "role": UserRole.MANAGER.value,
                "status": UserStatus.ACTIVE.value,
                "password": "Vertex@2026"
            },
            {
                "username": "tien.boss",
                "full_name": "Sếp Tiến (Giám đốc Điều hành)",
                "email": "tien.boss@vertexhvac.vn",
                "phone": "0904.555.666",
                "company_name": "Vertex Construction & PCCC",
                "role": UserRole.ADMIN.value,
                "status": UserStatus.ACTIVE.value,
                "password": "Vertex@2026"
            },
            {
                "username": "staff",
                "full_name": "Kỹ Sư Dự Toán PCCC & MEP",
                "email": "kythuat@vertexhvac.vn",
                "phone": "0987.654.321",
                "company_name": "Vertex Construction & PCCC",
                "role": UserRole.STAFF.value,
                "status": UserStatus.ACTIVE.value,
                "password": "Vertex@2026"
            }
        ]

        with self._get_connection() as conn:
            cursor = conn.cursor()
            for u in default_users:
                cursor.execute("SELECT COUNT(*) FROM users WHERE username = ?", (u["username"],))
                if cursor.fetchone()[0] == 0:
                    user_id = str(uuid.uuid4())
                    hashed = _hash_pwd(u["password"])
                    cursor.execute("""
                    INSERT INTO users (id, username, full_name, email, phone, company_name, role, status, hashed_password, is_active, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, datetime('now'))
                    """, (user_id, u["username"], u["full_name"], u["email"], u["phone"], u["company_name"], u["role"], u["status"], hashed))
            conn.commit()

    def _seed_catalog(self):
        """Seed catalog from default_catalog.json (PCCC equipment and HVAC)"""
        json_path = Path(settings.DATA_DIR) / "default_catalog.json"
        if json_path.exists():
            try:
                with open(json_path, "r", encoding="utf-8") as f:
                    items = json.load(f)
                with self._get_connection() as conn:
                    cursor = conn.cursor()
                    for item in items:
                        cursor.execute("""
                        INSERT OR REPLACE INTO catalog 
                        (code, name, category, material, thickness, unit, unit_price, keywords_json, notes)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            item.get("code"),
                            item.get("name"),
                            item.get("category"),
                            item.get("material", "Tiêu chuẩn PCCC"),
                            float(item.get("thickness", 0.0)),
                            item.get("unit", "cái"),
                            float(item.get("unit_price", 0)),
                            json.dumps(item.get("keywords", []), ensure_ascii=False),
                            item.get("notes", "")
                        ))
                    conn.commit()
            except Exception as e:
                print(f"Error seeding catalog: {e}")

    # Master Template CRUD operations
    def get_active_template(self) -> MasterTemplate:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM master_templates WHERE is_active = 1 ORDER BY updated_at DESC LIMIT 1")
            row = cursor.fetchone()
            if not row:
                cursor.execute("SELECT * FROM master_templates ORDER BY created_at ASC LIMIT 1")
                row = cursor.fetchone()
            if row:
                return MasterTemplate(
                    id=row["id"],
                    name=row["name"],
                    file_path=row["file_path"] or "",
                    file_name=row["file_name"] or "Master_Template_Vertex.xlsx",
                    description=row["description"] or "",
                    waste_ratio=row["waste_ratio"] or 0.05,
                    transport_ratio=row["transport_ratio"] or 0.03,
                    labor_ratio=row["labor_ratio"] or 0.15,
                    margin_ratio=row["margin_ratio"] or 0.12,
                    is_active=bool(row["is_active"]),
                    created_by=row["created_by"] or "Admin",
                    created_at=row["created_at"] or "",
                    updated_at=row["updated_at"] or ""
                )
            # Default fallback
            return MasterTemplate(id="tpl-vertex-default")

    def list_templates(self) -> List[MasterTemplate]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM master_templates ORDER BY is_active DESC, updated_at DESC")
            rows = cursor.fetchall()
            return [
                MasterTemplate(
                    id=r["id"],
                    name=r["name"],
                    file_path=r["file_path"] or "",
                    file_name=r["file_name"] or "Master_Template_Vertex.xlsx",
                    description=r["description"] or "",
                    waste_ratio=r["waste_ratio"] or 0.05,
                    transport_ratio=r["transport_ratio"] or 0.03,
                    labor_ratio=r["labor_ratio"] or 0.15,
                    margin_ratio=r["margin_ratio"] or 0.12,
                    is_active=bool(r["is_active"]),
                    created_by=r["created_by"] or "Admin",
                    created_at=r["created_at"] or "",
                    updated_at=r["updated_at"] or ""
                )
                for r in rows
            ]

    def get_template_by_id(self, template_id: str) -> Optional[MasterTemplate]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM master_templates WHERE id = ?", (template_id,))
            r = cursor.fetchone()
            if not r:
                return None
            return MasterTemplate(
                id=r["id"],
                name=r["name"],
                file_path=r["file_path"] or "",
                file_name=r["file_name"] or "Master_Template_Vertex.xlsx",
                description=r["description"] or "",
                waste_ratio=r["waste_ratio"] or 0.05,
                transport_ratio=r["transport_ratio"] or 0.03,
                labor_ratio=r["labor_ratio"] or 0.15,
                margin_ratio=r["margin_ratio"] or 0.12,
                is_active=bool(r["is_active"]),
                created_by=r["created_by"] or "Admin",
                created_at=r["created_at"] or "",
                updated_at=r["updated_at"] or ""
            )

    def save_template(self, template: MasterTemplate) -> MasterTemplate:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if template.is_active:
                cursor.execute("UPDATE master_templates SET is_active = 0")
            cursor.execute("""
            INSERT OR REPLACE INTO master_templates
            (id, name, file_path, file_name, description, waste_ratio, transport_ratio, labor_ratio, margin_ratio, is_active, created_by, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                template.id,
                template.name,
                template.file_path,
                template.file_name,
                template.description,
                template.waste_ratio,
                template.transport_ratio,
                template.labor_ratio,
                template.margin_ratio,
                1 if template.is_active else 0,
                template.created_by,
                template.created_at,
                template.updated_at
            ))
            conn.commit()
        return template

    def update_template_coefficients(
        self,
        template_id: str,
        waste_ratio: float,
        transport_ratio: float,
        labor_ratio: float,
        margin_ratio: float,
        name: Optional[str] = None,
        description: Optional[str] = None
    ) -> bool:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if name:
                cursor.execute("""
                UPDATE master_templates
                SET waste_ratio = ?, transport_ratio = ?, labor_ratio = ?, margin_ratio = ?,
                    name = ?, description = COALESCE(?, description), updated_at = datetime('now')
                WHERE id = ?
                """, (waste_ratio, transport_ratio, labor_ratio, margin_ratio, name, description, template_id))
            else:
                cursor.execute("""
                UPDATE master_templates
                SET waste_ratio = ?, transport_ratio = ?, labor_ratio = ?, margin_ratio = ?,
                    description = COALESCE(?, description), updated_at = datetime('now')
                WHERE id = ?
                """, (waste_ratio, transport_ratio, labor_ratio, margin_ratio, description, template_id))
            conn.commit()
            return cursor.rowcount > 0

    def set_active_template(self, template_id: str) -> bool:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE master_templates SET is_active = 0")
            cursor.execute("UPDATE master_templates SET is_active = 1, updated_at = datetime('now') WHERE id = ?", (template_id,))
            conn.commit()
            return cursor.rowcount > 0

    # User Auth & Management CRUD
    def create_user(self, user_in_db: UserInDB) -> UserInDB:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            INSERT INTO users (id, username, full_name, email, phone, company_name, role, status, hashed_password, is_active, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                user_in_db.id,
                user_in_db.username,
                user_in_db.full_name,
                user_in_db.email,
                user_in_db.phone,
                user_in_db.company_name,
                user_in_db.role.value,
                user_in_db.status.value,
                user_in_db.hashed_password,
                1 if user_in_db.is_active else 0,
                user_in_db.created_at
            ))
            conn.commit()
        return user_in_db

    def get_user_by_username(self, username: str) -> Optional[UserInDB]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users WHERE username = ?", (username.strip(),))
            row = cursor.fetchone()
            if not row:
                return None
            return UserInDB(
                id=row["id"],
                username=row["username"],
                full_name=row["full_name"],
                email=row["email"] or "",
                phone=row["phone"] or "",
                company_name=row["company_name"] or "",
                role=UserRole(row["role"]),
                status=UserStatus(row["status"] or "ACTIVE"),
                hashed_password=row["hashed_password"],
                is_active=bool(row["is_active"]),
                created_at=row["created_at"]
            )

    def get_user_by_id(self, user_id: str) -> Optional[UserInDB]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
            row = cursor.fetchone()
            if not row:
                return None
            return UserInDB(
                id=row["id"],
                username=row["username"],
                full_name=row["full_name"],
                email=row["email"] or "",
                phone=row["phone"] or "",
                company_name=row["company_name"] or "",
                role=UserRole(row["role"]),
                status=UserStatus(row["status"] or "ACTIVE"),
                hashed_password=row["hashed_password"],
                is_active=bool(row["is_active"]),
                created_at=row["created_at"]
            )

    def list_all_users(self) -> List[User]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users ORDER BY created_at DESC")
            rows = cursor.fetchall()
            return [
                User(
                    id=row["id"],
                    username=row["username"],
                    full_name=row["full_name"],
                    email=row["email"] or "",
                    phone=row["phone"] or "",
                    company_name=row["company_name"] or "",
                    role=UserRole(row["role"]),
                    status=UserStatus(row["status"] or "ACTIVE"),
                    is_active=bool(row["is_active"]),
                    created_at=row["created_at"]
                )
                for row in rows
            ]

    def update_user_status(self, user_id: str, status: UserStatus) -> bool:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            is_active = 1 if status == UserStatus.ACTIVE else 0
            cursor.execute("UPDATE users SET status = ?, is_active = ? WHERE id = ?", (status.value, is_active, user_id))
            conn.commit()
            return cursor.rowcount > 0

    def update_user_role(self, user_id: str, role: UserRole) -> bool:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET role = ? WHERE id = ?", (role.value, user_id))
            conn.commit()
            return cursor.rowcount > 0

    # Quote CRUD operations
    def save_quote(self, quote: Quote) -> Quote:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            INSERT OR REPLACE INTO quotes (
                id, quote_code, customer_name, customer_phone, customer_email, customer_zalo_id,
                project_name, project_address, status, language, scenario_type, total_material_cost, total_labor_cost,
                version, parent_quote_id, revision_note,
                required_approval_level, manager_approved_by, manager_approved_at, director_approved_by, director_approved_at,
                template_id, template_name, subtotal, discount_rate, discount_amount, subtotal_after_discount,
                vat_rate, vat_amount, total_amount, total_amount_in_words, input_file_name, input_file_path,
                excel_quote_path, created_at, updated_at, approved_by, approved_at, rejection_reason, items_json, logs_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                quote.id,
                quote.quote_code,
                quote.customer_name,
                quote.customer_phone,
                quote.customer_email,
                quote.customer_zalo_id,
                quote.project_name,
                quote.project_address,
                quote.status.value if isinstance(quote.status, QuoteStatus) else str(quote.status),
                quote.language,
                quote.scenario_type or "SCENARIO_3_STANDARD_CATALOG",
                quote.total_material_cost or 0.0,
                quote.total_labor_cost or 0.0,
                quote.version,
                quote.parent_quote_id or "",
                quote.revision_note or "",
                quote.required_approval_level or "MANAGER",
                quote.manager_approved_by or "",
                quote.manager_approved_at or "",
                quote.director_approved_by or "",
                quote.director_approved_at or "",
                quote.template_id or "",
                quote.template_name or "",
                quote.subtotal,
                quote.discount_rate,
                quote.discount_amount,
                quote.subtotal_after_discount,
                quote.vat_rate,
                quote.vat_amount,
                quote.total_amount,
                quote.total_amount_in_words,
                quote.input_file_name,
                quote.input_file_path,
                quote.excel_quote_path,
                quote.created_at,
                quote.updated_at,
                quote.approved_by,
                quote.approved_at,
                quote.rejection_reason,
                json.dumps([item.model_dump() for item in quote.items], ensure_ascii=False),
                json.dumps(quote.logs, ensure_ascii=False)
            ))
            conn.commit()
        return quote

    def get_quote(self, quote_id_or_code: str) -> Optional[Quote]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM quotes WHERE id = ? OR quote_code = ?",
                (quote_id_or_code, quote_id_or_code)
            )
            row = cursor.fetchone()
            if not row:
                return None
            return self._row_to_quote(row)

    def get_quote_by_id(self, quote_id: str) -> Optional[Quote]:
        return self.get_quote(quote_id)

    def list_quotes(self, limit: int = 50, offset: int = 0) -> List[Quote]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM quotes ORDER BY created_at DESC LIMIT ? OFFSET ?",
                (limit, offset)
            )
            rows = cursor.fetchall()
            return [self._row_to_quote(row) for row in rows]

    def count_quotes(self) -> int:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM quotes")
            return cursor.fetchone()[0]

    def get_quote_versions(self, quote_id_or_code: str) -> List[Quote]:
        """Returns all versions belonging to a quote family (root and child revisions)"""
        target = self.get_quote(quote_id_or_code)
        if not target:
            return []

        # Find the root quote ID
        root_id = target.parent_quote_id if target.parent_quote_id else target.id
        root_code = target.quote_code.split(" (v")[0].split("-v")[0]

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            SELECT * FROM quotes 
            WHERE id = ? OR parent_quote_id = ? OR quote_code LIKE ?
            ORDER BY version ASC, created_at ASC
            """, (root_id, root_id, f"{root_code}%"))
            rows = cursor.fetchall()
            return [self._row_to_quote(row) for row in rows]

    def _row_to_quote(self, row: sqlite3.Row) -> Quote:
        items_data = json.loads(row["items_json"]) if row["items_json"] else []
        logs_data = json.loads(row["logs_json"]) if row["logs_json"] else []
        items = [QuoteItem(**item) for item in items_data]
        keys = row.keys()

        return Quote(
            id=row["id"],
            quote_code=row["quote_code"],
            customer_name=row["customer_name"] or "",
            customer_phone=row["customer_phone"] or "",
            customer_email=row["customer_email"] or "",
            customer_zalo_id=row["customer_zalo_id"] or "",
            project_name=row["project_name"] or "",
            project_address=row["project_address"] or "",
            status=QuoteStatus(row["status"]),
            language=row["language"] if "language" in keys and row["language"] else "vi",
            scenario_type=row["scenario_type"] if "scenario_type" in keys and row["scenario_type"] else "SCENARIO_3_STANDARD_CATALOG",
            total_material_cost=row["total_material_cost"] if "total_material_cost" in keys and row["total_material_cost"] is not None else 0.0,
            total_labor_cost=row["total_labor_cost"] if "total_labor_cost" in keys and row["total_labor_cost"] is not None else 0.0,
            version=row["version"] if "version" in keys and row["version"] is not None else 1,
            parent_quote_id=row["parent_quote_id"] if "parent_quote_id" in keys and row["parent_quote_id"] else None,
            revision_note=row["revision_note"] if "revision_note" in keys and row["revision_note"] else "",
            required_approval_level=row["required_approval_level"] if "required_approval_level" in keys and row["required_approval_level"] else "MANAGER",
            manager_approved_by=row["manager_approved_by"] if "manager_approved_by" in keys and row["manager_approved_by"] else None,
            manager_approved_at=row["manager_approved_at"] if "manager_approved_at" in keys and row["manager_approved_at"] else None,
            director_approved_by=row["director_approved_by"] if "director_approved_by" in keys and row["director_approved_by"] else None,
            director_approved_at=row["director_approved_at"] if "director_approved_at" in keys and row["director_approved_at"] else None,
            template_id=row["template_id"] if "template_id" in keys else "",
            template_name=row["template_name"] if "template_name" in keys else "",
            subtotal=row["subtotal"] or 0.0,
            discount_rate=row["discount_rate"] or 0.0,
            discount_amount=row["discount_amount"] or 0.0,
            subtotal_after_discount=row["subtotal_after_discount"] or 0.0,
            vat_rate=row["vat_rate"] or 0.0,
            vat_amount=row["vat_amount"] or 0.0,
            total_amount=row["total_amount"] or 0.0,
            total_amount_in_words=row["total_amount_in_words"] or "",
            input_file_name=row["input_file_name"] or "",
            input_file_path=row["input_file_path"] or "",
            excel_quote_path=row["excel_quote_path"] or "",
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            approved_by=row["approved_by"],
            approved_at=row["approved_at"],
            rejection_reason=row["rejection_reason"],
            items=items,
            logs=logs_data
        )

    # ---------------------------------------------------------
    # Audit Trail & Activity Log Operations
    # ---------------------------------------------------------
    def add_audit_log(
        self,
        quote_id: str,
        user_name: str = "Hệ thống",
        user_role: str = "STAFF",
        action: str = "ACTION",
        details: str = "",
        ip_address: Optional[str] = None,
        user_id: Optional[str] = None
    ) -> AuditLog:
        """Appends a new immutable audit log record for a quote"""
        log_id = f"aud-{uuid.uuid4().hex[:10]}"
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        log = AuditLog(
            id=log_id,
            quote_id=quote_id,
            user_id=user_id or "",
            user_name=user_name,
            user_role=user_role,
            action=action,
            details=details,
            ip_address=ip_address or "",
            timestamp=now_str
        )

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            INSERT INTO audit_logs (id, quote_id, user_id, user_name, user_role, action, details, ip_address, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                log.id,
                log.quote_id,
                log.user_id,
                log.user_name,
                log.user_role,
                log.action,
                log.details,
                log.ip_address,
                log.timestamp
            ))
            conn.commit()

        return log

    def get_quote_audit_logs(self, quote_id: str) -> List[AuditLog]:
        """Retrieves chronological audit trail for a quote"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM audit_logs WHERE quote_id = ? ORDER BY timestamp ASC",
                (quote_id,)
            )
            rows = cursor.fetchall()
            return [
                AuditLog(
                    id=r["id"],
                    quote_id=r["quote_id"],
                    user_id=r["user_id"] or "",
                    user_name=r["user_name"] or "Hệ thống",
                    user_role=r["user_role"] or "STAFF",
                    action=r["action"] or "",
                    details=r["details"] or "",
                    ip_address=r["ip_address"] or "",
                    timestamp=r["timestamp"] or ""
                )
                for r in rows
            ]


    # Catalog operations
    def get_catalog(self) -> List[PriceCatalogItem]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM catalog ORDER BY category, code")
            rows = cursor.fetchall()
            catalog_list = []
            for r in rows:
                keywords = json.loads(r["keywords_json"]) if r["keywords_json"] else []
                catalog_list.append(PriceCatalogItem(
                    code=r["code"],
                    name=r["name"],
                    category=r["category"],
                    material=r["material"],
                    thickness=r["thickness"],
                    unit=r["unit"],
                    unit_price=r["unit_price"],
                    keywords=keywords,
                    notes=r["notes"] or ""
                ))
            return catalog_list

    def save_catalog_item(self, item: PriceCatalogItem) -> PriceCatalogItem:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            INSERT OR REPLACE INTO catalog 
            (code, name, category, material, thickness, unit, unit_price, keywords_json, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                item.code,
                item.name,
                item.category,
                item.material,
                item.thickness,
                item.unit,
                item.unit_price,
                json.dumps(item.keywords, ensure_ascii=False),
                item.notes
            ))
    def _seed_field_data(self):
        """Seeds initial realistic sample check-ins and field reports for staff"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM attendance_checkins")
            if cursor.fetchone()[0] == 0:
                sample_checkins = [
                    (
                        "chk-seed-001",
                        "user-staff-001",
                        "Kỹ Sư Dự Toán PCCC & MEP",
                        "Khách Sạn 5 Sao Delta Grand (Bắc Từ Liêm, Hà Nội)",
                        "IN",
                        21.0568,
                        105.7925,
                        8.5,
                        "Lô B2, KĐT Ngoại Giao Đoàn, Bắc Từ Liêm, Hà Nội",
                        "ON_TIME",
                        "Check-in giám sát lắp đặt cụm bơm cứu hỏa 75kW",
                        "2026-08-28 07:45:00"
                    ),
                    (
                        "chk-seed-002",
                        "user-staff-002",
                        "Nguyễn Văn Tuấn (Kỹ sư Hiện trường)",
                        "Khu Căn Hộ Masterise Marina (TP. Thủ Đức, TP.HCM)",
                        "IN",
                        10.7826,
                        106.7029,
                        6.2,
                        "Số 2 Tôn Đức Thắng, P. Bến Nghé, Quận 1, TP.HCM",
                        "ON_TIME",
                        "Nghiệm thu tuyến ống gió chống cháy EI45 tầng hầm B1",
                        "2026-08-28 07:55:00"
                    ),
                    (
                        "chk-seed-003",
                        "user-staff-003",
                        "Trần Hoàng Nam (Giám sát MEP)",
                        "Nhà Máy Dược Phẩm Dược Hậu Giang (VSIP 1, Bình Dương)",
                        "SITE_VISIT",
                        10.9582,
                        106.6985,
                        12.0,
                        "Đường số 6, KCN VSIP 1, Thuận An, Bình Dương",
                        "ON_TIME",
                        "Khảo sát đo đạc thực tế hệ thống chữa cháy FM200 phòng máy chủ",
                        "2026-08-28 08:15:00"
                    )
                ]
                cursor.executemany("""
                INSERT INTO attendance_checkins 
                (id, user_id, user_name, project_site, checkin_type, latitude, longitude, accuracy_meters, address_resolved, status, notes, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, sample_checkins)

            cursor.execute("SELECT COUNT(*) FROM field_daily_reports")
            if cursor.fetchone()[0] == 0:
                sample_reports = [
                    (
                        "rep-seed-001",
                        "user-staff-001",
                        "Kỹ Sư Dự Toán PCCC & MEP",
                        "Khách Sạn 5 Sao Delta Grand",
                        "2026-08-28",
                        "Nắng ráo",
                        "1. Lắp đặt hoàn thiện cụm 3 máy bơm PCCC (Bơm chính điện 75kW, Bơm Diesel dự phòng 75kW, Bơm bù áp 5.5kW).\n2. Căn chỉnh đồng trục động cơ và đấu nối đường ống hút xả DN150.\n3. Thử áp lực tuyến ống chính khu vực trạm bơm đạt 16 bar duy trì 2 giờ không rò rỉ.",
                        65.0,
                        8,
                        "Vật tư van bướm tín hiệu DN150 về chậm 1 ngày do bên vận chuyển, đã điều phối tổ thi công chuyển sang làm giá đỡ đường ống.",
                        "Tiến hành đấu nối tủ điện điều khiển bơm và kết nối tín hiệu liên động về tủ trung tâm báo cháy.",
                        json.dumps(["/static/images/pccc_field_1.jpg", "/static/images/pccc_field_2.jpg"]),
                        "Tiến độ lắp đặt bơm tốt. Lưu ý che chắn động cơ cẩn thận tránh bụi xi măng khi hoàn thiện nền trạm.",
                        "APPROVED",
                        "2026-08-28 17:30:00"
                    ),
                    (
                        "rep-seed-002",
                        "user-staff-002",
                        "Nguyễn Văn Tuấn (Kỹ sư Hiện trường)",
                        "Khu Căn Hộ Masterise Marina",
                        "2026-08-28",
                        "Nắng ráo",
                        "1. Gia công và lắp đặt 145m² ống gió vuông bích TDC bọc chống cháy EI45 tầng hầm B1.\n2. Lắp đặt 8 van chặn lửa cầu chì nhiệt FD kích thước 800x400.\n3. Định vị 12 miệng gió hút khói hành lang.",
                        45.0,
                        6,
                        "Vướng tuyến ống cấp nước của nhà thầu nước tại trục 5-B, đã phối hợp xử lý cao độ uốn lượn theo đúng bản vẽ điều chỉnh.",
                        "Tiếp tục bọc bông cách nhiệt bảo ôn và hoàn thiện tuyến ống gió hút khói tầng hầm B2.",
                        json.dumps(["/static/images/pccc_field_3.jpg"]),
                        "Đã duyệt. Nhắc nhở anh em công nhân tuân thủ nghiêm ngặt đồ bảo hộ khi bọc bông khoáng.",
                        "APPROVED",
                        "2026-08-28 17:45:00"
                    )
                ]
                cursor.executemany("""
                INSERT INTO field_daily_reports
                (id, user_id, user_name, project_name, report_date, weather_condition, work_summary, progress_percent, workforce_count, issues_and_risks, next_plan, photos_json, supervisor_comment, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, sample_reports)
            conn.commit()

    # Attendance CRUD
    def create_checkin(self, checkin_dict: Dict[str, Any]) -> AttendanceCheckin:
        item = AttendanceCheckin(**checkin_dict)
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            INSERT INTO attendance_checkins
            (id, user_id, user_name, project_site, checkin_type, latitude, longitude, accuracy_meters, address_resolved, status, notes, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                item.id, item.user_id, item.user_name, item.project_site, item.checkin_type,
                item.latitude, item.longitude, item.accuracy_meters, item.address_resolved,
                item.status, item.notes, item.created_at
            ))
            conn.commit()
        return item

    def list_checkins(self, limit: int = 100, user_id: Optional[str] = None) -> List[AttendanceCheckin]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if user_id:
                cursor.execute("SELECT * FROM attendance_checkins WHERE user_id = ? ORDER BY created_at DESC LIMIT ?", (user_id, limit))
            else:
                cursor.execute("SELECT * FROM attendance_checkins ORDER BY created_at DESC LIMIT ?", (limit,))
            rows = cursor.fetchall()
            return [AttendanceCheckin(
                id=r["id"],
                user_id=r["user_id"],
                user_name=r["user_name"],
                project_site=r["project_site"],
                checkin_type=r["checkin_type"],
                latitude=r["latitude"],
                longitude=r["longitude"],
                accuracy_meters=r["accuracy_meters"],
                address_resolved=r["address_resolved"],
                status=r["status"],
                notes=r["notes"] or "",
                created_at=r["created_at"]
            ) for r in rows]

    # Field Reports CRUD
    def create_field_report(self, report_dict: Dict[str, Any]) -> FieldDailyReport:
        item = FieldDailyReport(**report_dict)
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            INSERT INTO field_daily_reports
            (id, user_id, user_name, project_name, report_date, weather_condition, work_summary, progress_percent, workforce_count, issues_and_risks, next_plan, photos_json, supervisor_comment, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                item.id, item.user_id, item.user_name, item.project_name, item.report_date,
                item.weather_condition, item.work_summary, item.progress_percent, item.workforce_count,
                item.issues_and_risks, item.next_plan, item.photos_json, item.supervisor_comment,
                item.status, item.created_at
            ))
            conn.commit()
        return item

    def list_field_reports(self, limit: int = 100, user_id: Optional[str] = None, project_name: Optional[str] = None) -> List[FieldDailyReport]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            query = "SELECT * FROM field_daily_reports WHERE 1=1"
            params = []
            if user_id:
                query += " AND user_id = ?"
                params.append(user_id)
            if project_name:
                query += " AND project_name = ?"
                params.append(project_name)
            query += " ORDER BY created_at DESC LIMIT ?"
            params.append(limit)
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            return [FieldDailyReport(
                id=r["id"],
                user_id=r["user_id"],
                user_name=r["user_name"],
                project_name=r["project_name"],
                report_date=r["report_date"],
                weather_condition=r["weather_condition"],
                work_summary=r["work_summary"],
                progress_percent=r["progress_percent"],
                workforce_count=r["workforce_count"],
                issues_and_risks=r["issues_and_risks"] or "",
                next_plan=r["next_plan"] or "",
                photos_json=r["photos_json"] or "[]",
                supervisor_comment=r["supervisor_comment"] or "",
                status=r["status"],
                created_at=r["created_at"]
            ) for r in rows]

    def get_field_report(self, report_id: str) -> Optional[FieldDailyReport]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM field_daily_reports WHERE id = ?", (report_id,))
            r = cursor.fetchone()
            if not r:
                return None
            return FieldDailyReport(
                id=r["id"],
                user_id=r["user_id"],
                user_name=r["user_name"],
                project_name=r["project_name"],
                report_date=r["report_date"],
                weather_condition=r["weather_condition"],
                work_summary=r["work_summary"],
                progress_percent=r["progress_percent"],
                workforce_count=r["workforce_count"],
                issues_and_risks=r["issues_and_risks"] or "",
                next_plan=r["next_plan"] or "",
                photos_json=r["photos_json"] or "[]",
                supervisor_comment=r["supervisor_comment"] or "",
                status=r["status"],
                created_at=r["created_at"]
            )

    def update_field_report_comment(self, report_id: str, comment: str, status: str = "APPROVED") -> Optional[FieldDailyReport]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            UPDATE field_daily_reports 
            SET supervisor_comment = ?, status = ?
            WHERE id = ?
            """, (comment, status, report_id))
            conn.commit()
        return self.get_field_report(report_id)

    # -------------------------------------------------------------
    # Geofencing Alerts & Out-of-Zone Incident Tracking
    # -------------------------------------------------------------
    def create_geofence_alert(self, alert_dict: Dict[str, Any]) -> GeofenceAlertRecord:
        item = GeofenceAlertRecord(**alert_dict)
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            INSERT INTO geofence_alerts
            (id, user_id, user_name, project_site, latitude, longitude, distance_meters, radius_meters, alert_message, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                item.id, item.user_id, item.user_name, item.project_site,
                item.latitude, item.longitude, item.distance_meters, item.radius_meters,
                item.alert_message, item.status, item.created_at
            ))
            conn.commit()
        return item

    def list_geofence_alerts(self, limit: int = 50, user_id: Optional[str] = None, project_site: Optional[str] = None) -> List[GeofenceAlertRecord]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            query = "SELECT * FROM geofence_alerts WHERE 1=1"
            params = []
            if user_id:
                query += " AND user_id = ?"
                params.append(user_id)
            if project_site:
                query += " AND project_site = ?"
                params.append(project_site)
            query += " ORDER BY created_at DESC LIMIT ?"
            params.append(limit)

            cursor.execute(query, params)
            rows = cursor.fetchall()
            return [GeofenceAlertRecord(
                id=r["id"],
                user_id=r["user_id"],
                user_name=r["user_name"],
                project_site=r["project_site"],
                latitude=r["latitude"],
                longitude=r["longitude"],
                distance_meters=r["distance_meters"],
                radius_meters=r["radius_meters"],
                alert_message=r["alert_message"],
                status=r["status"],
                created_at=r["created_at"]
            ) for r in rows]

    def resolve_geofence_alert(self, alert_id: str, status: str = "RESOLVED") -> bool:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE geofence_alerts SET status = ? WHERE id = ?", (status, alert_id))
            conn.commit()
            return cursor.rowcount > 0

    # -------------------------------------------------------------
    # Inventory & Manufacturing BOM Methods
    # -------------------------------------------------------------
    def _seed_inventory_data(self):
        """Seeds standard inventory items with 4-tier pricing & BOM data"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM inventory_items")
            if cursor.fetchone()[0] > 0:
                return

            seed_items = [
                # 1. Kho Sản Xuất - Vật tư thô (Raw Materials)
                InventoryItem(
                    id="inv-mfg-raw-001",
                    sku="VTX-MFG-RAW-001",
                    name="Tôn cuộn mạ kẽm Z12 Hoa Sen (Dày 0.75mm)",
                    warehouse_type=WarehouseType.MANUFACTURING,
                    category="Tôn & Kim loại cuộn",
                    unit="kg",
                    stock_quantity=15000.0,
                    cost_price=24500.0,
                    retail_price=32000.0,
                    dealer_price=28000.0,
                    project_discount_rate=5.0,
                    material_type="THÉP_MẠ_KẼM",
                    default_thickness=0.75,
                    spec="Tiêu chuẩn JIS G3302 Z120, độ mạ kẽm 120g/m2",
                    notes="Vật tư thô chính để gia công ống gió PCCC và vỏ tủ điện"
                ),
                InventoryItem(
                    id="inv-mfg-raw-002",
                    sku="VTX-MFG-RAW-002",
                    name="Tấm nhôm hợp kim AL5052-H32 (Dày 3.0mm)",
                    warehouse_type=WarehouseType.MANUFACTURING,
                    category="Tấm kim loại tấm cao cấp",
                    unit="kg",
                    stock_quantity=8500.0,
                    cost_price=115000.0,
                    retail_price=155000.0,
                    dealer_price=135000.0,
                    project_discount_rate=6.0,
                    material_type="NHÔM_AL5052",
                    default_thickness=3.0,
                    spec="Hợp kim nhôm Magie AL5052-H32 chịu lực uốn và chống ăn mòn cực cao",
                    notes="Nguyên liệu chuyên dụng dập tấm ốp bảo vệ gầm pin xe điện VinFast"
                ),
                InventoryItem(
                    id="inv-mfg-raw-003",
                    sku="VTX-MFG-RAW-003",
                    name="Vữa cách nhiệt chống cháy Vertex Maku EI",
                    warehouse_type=WarehouseType.MANUFACTURING,
                    category="Vật liệu chống cháy",
                    unit="kg",
                    stock_quantity=25000.0,
                    cost_price=12000.0,
                    retail_price=18000.0,
                    dealer_price=15000.0,
                    project_discount_rate=8.0,
                    material_type="VỮA_CHỐNG_CHÁY",
                    spec="Vữa nhẹ gốc khoáng vô cơ chịu nhiệt >1200°C theo QCVN 06:2022/BXD",
                    notes="Phun bọc cách nhiệt ống gió tiêu chuẩn EI30, EI45, EI60"
                ),
                InventoryItem(
                    id="inv-mfg-raw-004",
                    sku="VTX-MFG-RAW-004",
                    name="Bông khoáng Rockwool chống cháy tỷ trọng 100kg/m3",
                    warehouse_type=WarehouseType.MANUFACTURING,
                    category="Vật liệu chống cháy",
                    unit="m2",
                    stock_quantity=3200.0,
                    cost_price=85000.0,
                    retail_price=125000.0,
                    dealer_price=105000.0,
                    project_discount_rate=5.0,
                    material_type="ROCKWOOL",
                    default_thickness=50.0,
                    spec="Dày 50mm, tỷ trọng 100kg/m3, hệ số dẫn nhiệt k=0.034 W/mK",
                    notes="Cách nhiệt ống gió và tiêu âm phòng máy bơm PCCC"
                ),

                # 2. Kho Sản Xuất - Tấm ốp bảo vệ gầm pin xe điện VinFast (VinFast EV Battery Skid Plates)
                InventoryItem(
                    id="inv-mfg-ev-001",
                    sku="VTX-MFG-EV-VF8",
                    name="Tấm ốp bảo vệ gầm pin xe điện VinFast VF8 (Nhôm AL5052 3.0mm dập gân cường lực)",
                    warehouse_type=WarehouseType.MANUFACTURING,
                    category="Tấm ốp gầm pin xe điện VinFast",
                    unit="tấm",
                    stock_quantity=120.0,
                    cost_price=4850000.0,
                    retail_price=7500000.0,
                    dealer_price=6200000.0,
                    project_discount_rate=10.0,
                    is_custom_dimensions=True,
                    default_length=2150.0,
                    default_width=1450.0,
                    default_thickness=3.0,
                    material_type="NHÔM_AL5052",
                    bom_data={
                        "raw_materials": [
                            {"material_name": "Tấm nhôm AL5052-H32 (3.0mm)", "spec": "Khổ 1500x2200mm", "unit": "kg", "quantity": 25.2, "unit_cost": 115000.0, "total_cost": 2898000.0},
                            {"material_name": "Bulong Inox 304 M8x35 kèm long đen chống xoay", "spec": "Bộ 24 con", "unit": "bộ", "quantity": 1.0, "unit_cost": 180000.0, "total_cost": 180000.0},
                            {"material_name": "Sơn tĩnh điện Anodizing đen mờ chống xước", "spec": "Tiêu chuẩn ô tô", "unit": "m2", "quantity": 3.12, "unit_cost": 120000.0, "total_cost": 374400.0}
                        ],
                        "scrap_waste_ratio": 0.05,
                        "scrap_waste_cost": 172620.0,
                        "labor_cost": 750000.0,
                        "overhead_cost": 475000.0,
                        "calculated_cost_price": 4850020.0
                    },
                    spec="Thiết kế nguyên khối chuẩn form gầm pin VinFast VF8, lỗ thoáng tản nhiệt CNC, chống va đập đá văng",
                    notes="Sản phẩm dập định hình cao cấp tại xưởng cơ khí chính xác Vertex"
                ),
                InventoryItem(
                    id="inv-mfg-ev-002",
                    sku="VTX-MFG-EV-VF9",
                    name="Tấm ốp bảo vệ gầm pin xe điện VinFast VF9 (Nhôm AL5052 3.5mm dập gân cường lực)",
                    warehouse_type=WarehouseType.MANUFACTURING,
                    category="Tấm ốp gầm pin xe điện VinFast",
                    unit="tấm",
                    stock_quantity=85.0,
                    cost_price=5950000.0,
                    retail_price=9200000.0,
                    dealer_price=7800000.0,
                    project_discount_rate=10.0,
                    is_custom_dimensions=True,
                    default_length=2400.0,
                    default_width=1550.0,
                    default_thickness=3.5,
                    material_type="NHÔM_AL5052",
                    bom_data={
                        "raw_materials": [
                            {"material_name": "Tấm nhôm AL5052-H32 (3.5mm)", "spec": "Khổ 1600x2500mm", "unit": "kg", "quantity": 35.1, "unit_cost": 115000.0, "total_cost": 4036500.0},
                            {"material_name": "Phụ kiện gá treo gia cố chịu lực khung gầm", "spec": "Thép mạ kẽm", "unit": "bộ", "quantity": 1.0, "unit_cost": 250000.0, "total_cost": 250000.0}
                        ],
                        "scrap_waste_ratio": 0.05,
                        "scrap_waste_cost": 214325.0,
                        "labor_cost": 900000.0,
                        "overhead_cost": 550000.0,
                        "calculated_cost_price": 5950825.0
                    },
                    spec="Form chuẩn xe SUV Full-size VinFast VF9, gia cố bảo vệ cụm pack pin 123kWh",
                    notes="Chống ngập nước, bảo vệ pin tuyệt đối khỏi cạ gầm"
                ),
                InventoryItem(
                    id="inv-mfg-ev-003",
                    sku="VTX-MFG-EV-VF5",
                    name="Tấm ốp bảo vệ gầm pin xe điện VinFast VF5 / VFe34 (Thép mạ kẽm 2.5mm dập sóng)",
                    warehouse_type=WarehouseType.MANUFACTURING,
                    category="Tấm ốp gầm pin xe điện VinFast",
                    unit="tấm",
                    stock_quantity=160.0,
                    cost_price=2650000.0,
                    retail_price=4200000.0,
                    dealer_price=3500000.0,
                    project_discount_rate=8.0,
                    is_custom_dimensions=True,
                    default_length=1850.0,
                    default_width=1250.0,
                    default_thickness=2.5,
                    material_type="THÉP_MẠ_KẼM",
                    bom_data={
                        "raw_materials": [
                            {"material_name": "Thép tấm mạ kẽm cường độ cao 2.5mm", "spec": "Khổ 1300x1900mm", "unit": "kg", "quantity": 45.4, "unit_cost": 28000.0, "total_cost": 1271200.0},
                            {"material_name": "Sơn tĩnh điện nhúng chống rỉ 2 mặt", "spec": "Dày 80 micron", "unit": "m2", "quantity": 4.6, "unit_cost": 85000.0, "total_cost": 391000.0}
                        ],
                        "scrap_waste_ratio": 0.05,
                        "scrap_waste_cost": 83110.0,
                        "labor_cost": 550000.0,
                        "overhead_cost": 355000.0,
                        "calculated_cost_price": 2650310.0
                    },
                    spec="Dập gân chữ X chịu lực đè 3 tấn, bảo vệ đáy pin xe taxi và gia đình",
                    notes="Dòng sản phẩm bán chạy nhất cho đại lý và gara dịch vụ"
                ),

                # 3. Kho Sản Xuất - Ống Gió & Vỏ Tủ Điện PCCC (Manufacturing Ductwork & Enclosures)
                InventoryItem(
                    id="inv-mfg-duct-ei30",
                    sku="VTX-MFG-DUCT-EI30",
                    name="Ống gió chống cháy EI30 (Tôn 0.75mm + Vữa cách nhiệt Maku)",
                    warehouse_type=WarehouseType.MANUFACTURING,
                    category="Ống gió chống cháy EI",
                    unit="m2",
                    stock_quantity=500.0,
                    cost_price=380000.0,
                    retail_price=560000.0,
                    dealer_price=480000.0,
                    project_discount_rate=8.0,
                    is_custom_dimensions=True,
                    material_type="THÉP_MẠ_KẼM",
                    default_thickness=0.75,
                    bom_data={
                        "raw_materials": [
                            {"material_name": "Tôn mạ kẽm 0.75mm", "spec": "Hoa Sen Z12", "unit": "kg", "quantity": 6.8, "unit_cost": 24500.0, "total_cost": 166600.0},
                            {"material_name": "Vữa Maku EI30", "spec": "Dày 18mm", "unit": "kg", "quantity": 8.5, "unit_cost": 12000.0, "total_cost": 102000.0}
                        ],
                        "scrap_waste_ratio": 0.05,
                        "scrap_waste_cost": 13430.0,
                        "labor_cost": 65000.0,
                        "overhead_cost": 33000.0,
                        "calculated_cost_price": 380030.0
                    },
                    spec="Giới hạn chịu lửa EI 30 phút theo QCVN 06:2022/BXD",
                    notes="Sử dụng cho hệ thống hút khói hành lang và tăng áp cầu thang"
                ),
                InventoryItem(
                    id="inv-mfg-duct-ei60",
                    sku="VTX-MFG-DUCT-EI60",
                    name="Ống gió chống cháy EI60 (Tôn 0.95mm + Tấm Magie bọc ngoài)",
                    warehouse_type=WarehouseType.MANUFACTURING,
                    category="Ống gió chống cháy EI",
                    unit="m2",
                    stock_quantity=420.0,
                    cost_price=520000.0,
                    retail_price=780000.0,
                    dealer_price=660000.0,
                    project_discount_rate=10.0,
                    is_custom_dimensions=True,
                    material_type="THÉP_MẠ_KẼM",
                    default_thickness=0.95,
                    spec="Giới hạn chịu lửa EI 60 phút theo QCVN 06:2022/BXD",
                    notes="Dùng cho trục hút khói tầng hầm và gian thương mại"
                ),
                InventoryItem(
                    id="inv-mfg-duct-ei120",
                    sku="VTX-MFG-DUCT-EI120",
                    name="Ống gió chống cháy EI120 (Tôn 1.15mm + Bông gốm Ceramic + Tấm bọc kép)",
                    warehouse_type=WarehouseType.MANUFACTURING,
                    category="Ống gió chống cháy EI",
                    unit="m2",
                    stock_quantity=280.0,
                    cost_price=780000.0,
                    retail_price=1180000.0,
                    dealer_price=980000.0,
                    project_discount_rate=12.0,
                    is_custom_dimensions=True,
                    material_type="THÉP_MẠ_KẼM",
                    default_thickness=1.15,
                    spec="Giới hạn chịu lửa EI 120 phút theo QCVN 06:2022/BXD",
                    notes="Dùng cho gian lánh nạn và trục kỹ thuật xuyên tầng"
                ),
                InventoryItem(
                    id="inv-mfg-cab-001",
                    sku="VTX-MFG-CAB-001",
                    name="Vỏ tủ điện PCCC 1200x800x300mm (Thép 1.5mm sơn tĩnh điện đỏ)",
                    warehouse_type=WarehouseType.MANUFACTURING,
                    category="Vỏ tủ điện & Tủ PCCC",
                    unit="cái",
                    stock_quantity=95.0,
                    cost_price=1250000.0,
                    retail_price=1950000.0,
                    dealer_price=1600000.0,
                    project_discount_rate=8.0,
                    is_custom_dimensions=True,
                    default_length=1200.0,
                    default_width=800.0,
                    default_thickness=300.0,
                    material_type="THÉP_MẠ_KẼM",
                    spec="Thép cán nguội dày 1.5mm, khóa bật tay nắm, gioăng cao su chống bụi IP54",
                    notes="Tủ điều khiển bơm chữa cháy chính và bơm bù áp"
                ),
                InventoryItem(
                    id="inv-mfg-box-001",
                    sku="VTX-MFG-BOX-001",
                    name="Hộp tủ chữa cháy vách tường âm tường 600x500x180mm kèm kính & khóa bật",
                    warehouse_type=WarehouseType.MANUFACTURING,
                    category="Vỏ tủ điện & Tủ PCCC",
                    unit="cái",
                    stock_quantity=250.0,
                    cost_price=320000.0,
                    retail_price=490000.0,
                    dealer_price=410000.0,
                    project_discount_rate=6.0,
                    is_custom_dimensions=False,
                    spec="Thép sơn tĩnh điện đỏ tiêu chuẩn PCCC, kính in chữ CHỮA CHÁY",
                    notes="Đựng vừa cuộn vòi D50/D65 và lăng phun chữa cháy"
                ),

                # 4. Kho Thương Mại & Dự Án (Commercial & Project Warehouse)
                InventoryItem(
                    id="inv-com-ext-001",
                    sku="VTX-COM-EXT-001",
                    name="Bình chữa cháy bột ABC 4kg Tomoken TMK-VJ-ABC/4kg (Tem kiểm định BCA)",
                    warehouse_type=WarehouseType.COMMERCIAL,
                    category="Bình chữa cháy",
                    unit="bình",
                    stock_quantity=450.0,
                    cost_price=215000.0,
                    retail_price=340000.0,
                    dealer_price=275000.0,
                    project_discount_rate=5.0,
                    spec="Thương hiệu Tomoken liên doanh Nhật Bản, dán sẵn tem kiểm định PCCC",
                    notes="Bình chữa cháy phổ thông cho văn phòng, căn hộ và nhà xưởng"
                ),
                InventoryItem(
                    id="inv-com-ext-002",
                    sku="VTX-COM-EXT-002",
                    name="Bình chữa cháy bột ABC 8kg Tomoken TMK-VJ-ABC/8kg (Tem kiểm định BCA)",
                    warehouse_type=WarehouseType.COMMERCIAL,
                    category="Bình chữa cháy",
                    unit="bình",
                    stock_quantity=320.0,
                    cost_price=340000.0,
                    retail_price=520000.0,
                    dealer_price=420000.0,
                    project_discount_rate=6.0,
                    spec="Trọng lượng bột 8kg, hiệu quả dập tắt đám cháy rắn, lỏng, khí",
                    notes="Trang bị khu vực kho hàng và trạm biến áp"
                ),
                InventoryItem(
                    id="inv-com-ext-003",
                    sku="VTX-COM-EXT-003",
                    name="Bình chữa cháy khí CO2 3kg Tomoken TMK-VJ-CO2/3kg",
                    warehouse_type=WarehouseType.COMMERCIAL,
                    category="Bình chữa cháy",
                    unit="bình",
                    stock_quantity=180.0,
                    cost_price=410000.0,
                    retail_price=620000.0,
                    dealer_price=510000.0,
                    project_discount_rate=6.0,
                    spec="Khí CO2 nguyên chất không để lại cặn, bảo vệ thiết bị điện tử",
                    notes="Phù hợp phòng máy chủ Server, phòng điện nhẹ"
                ),
                InventoryItem(
                    id="inv-com-ext-004",
                    sku="VTX-COM-EXT-004",
                    name="Bình chữa cháy khí CO2 5kg Tomoken TMK-VJ-CO2/5kg",
                    warehouse_type=WarehouseType.COMMERCIAL,
                    category="Bình chữa cháy",
                    unit="bình",
                    stock_quantity=140.0,
                    cost_price=610000.0,
                    retail_price=890000.0,
                    dealer_price=740000.0,
                    project_discount_rate=7.0,
                    spec="Trọng lượng khí 5kg, vòi phun loa kèn cách điện",
                    notes="Trang bị phòng máy phát điện và tủ phân phối tổng MSB"
                ),
                InventoryItem(
                    id="inv-com-spk-001",
                    sku="VTX-COM-SPK-001",
                    name="Đầu phun Sprinkler quay xuống Tyco TY325 K=5.6 68°C DN15",
                    warehouse_type=WarehouseType.COMMERCIAL,
                    category="Đầu phun Sprinkler",
                    unit="cái",
                    stock_quantity=3500.0,
                    cost_price=68000.0,
                    retail_price=115000.0,
                    dealer_price=92000.0,
                    project_discount_rate=8.0,
                    spec="Tyco Pendent K5.6, nhiệt độ kích hoạt 68°C (ống thủy tinh đỏ)",
                    notes="Đầu phun tiêu chuẩn phổ biến nhất trong hệ thống chữa cháy tự động"
                ),
                InventoryItem(
                    id="inv-com-spk-002",
                    sku="VTX-COM-SPK-002",
                    name="Đầu phun Sprinkler quay lên Tyco TY315 K=5.6 68°C DN15",
                    warehouse_type=WarehouseType.COMMERCIAL,
                    category="Đầu phun Sprinkler",
                    unit="cái",
                    stock_quantity=2100.0,
                    cost_price=72000.0,
                    retail_price=120000.0,
                    dealer_price=95000.0,
                    project_discount_rate=8.0,
                    spec="Tyco Upright K5.6, lắp đặt trên trần mở, tầng hầm hoặc nhà xưởng",
                    notes="Bảo vệ không gian trần mở không đóng thạch cao"
                ),
                InventoryItem(
                    id="inv-com-vlv-001",
                    sku="VTX-COM-VLV-001",
                    name="Van bướm tín hiệu điện kèm công tắc giám sát DN100 ARV Malaysia",
                    warehouse_type=WarehouseType.COMMERCIAL,
                    category="Van & Thiết bị đường ống PCCC",
                    unit="cái",
                    stock_quantity=45.0,
                    cost_price=1850000.0,
                    retail_price=2750000.0,
                    dealer_price=2250000.0,
                    project_discount_rate=8.0,
                    spec="Thân gang cầu, đĩa inox 304, tín hiệu tiếp điểm khô NO/NC truyền về tủ báo cháy",
                    notes="Lắp đặt trên các nhánh cấp nước chữa cháy từng tầng"
                ),
                InventoryItem(
                    id="inv-com-vlv-002",
                    sku="VTX-COM-VLV-002",
                    name="Van báo động Alarm Valve DN100 kèm chuông nước & công tắc áp lực ARV",
                    warehouse_type=WarehouseType.COMMERCIAL,
                    category="Van & Thiết bị đường ống PCCC",
                    unit="bộ",
                    stock_quantity=22.0,
                    cost_price=4650000.0,
                    retail_price=6850000.0,
                    dealer_price=5600000.0,
                    project_discount_rate=10.0,
                    spec="Cụm van báo động Sprinkler trọn bộ: Thân van, chuông cơ, đồng hồ áp, switch áp lực",
                    notes="Cụm van điều khiển trung tâm hệ thống Sprinkler"
                ),
                InventoryItem(
                    id="inv-com-alm-001",
                    sku="VTX-COM-ALM-001",
                    name="Tủ trung tâm báo cháy địa chỉ 1 Loop Hochiki FireNET Plus 1127",
                    warehouse_type=WarehouseType.COMMERCIAL,
                    category="Hệ thống báo cháy địa chỉ",
                    unit="bộ",
                    stock_quantity=15.0,
                    cost_price=1850000.0,
                    retail_price=26500000.0,
                    dealer_price=22000000.0,
                    project_discount_rate=12.0,
                    spec="1 Loop mở rộng lên 2 Loop, quản lý tới 127 đầu báo + 127 module địa chỉ",
                    notes="Trung tâm điều khiển báo cháy cao cấp Hochiki Mỹ/Nhật"
                ),
                InventoryItem(
                    id="inv-com-alm-002",
                    sku="VTX-COM-ALM-002",
                    name="Đầu báo khói quang địa chỉ Hochiki ALN-V kèm đế YBN-NSA-4",
                    warehouse_type=WarehouseType.COMMERCIAL,
                    category="Hệ thống báo cháy địa chỉ",
                    unit="cái",
                    stock_quantity=680.0,
                    cost_price=380000.0,
                    retail_price=560000.0,
                    dealer_price=460000.0,
                    project_discount_rate=8.0,
                    spec="Cảm biến quang học buồng khói thế hệ mới, tự động bù bụi bẩn",
                    notes="Đầu báo địa chỉ chính xác vị trí phát sinh sự cố cháy"
                ),
                InventoryItem(
                    id="inv-com-lgt-001",
                    sku="VTX-COM-LGT-001",
                    name="Đèn Exit thoát hiểm 2 mặt LED Paragon PEAC26G (Pin lưu điện 2 giờ)",
                    warehouse_type=WarehouseType.COMMERCIAL,
                    category="Đèn Exit & Chiếu sáng sự cố",
                    unit="cái",
                    stock_quantity=220.0,
                    cost_price=360000.0,
                    retail_price=540000.0,
                    dealer_price=440000.0,
                    project_discount_rate=6.0,
                    spec="Nguồn tự sạc, pin Ni-Cd 2 giờ, bóng LED siêu sáng tiết kiệm điện",
                    notes="Chỉ dẫn lối thoát nạn hành lang và cầu thang thoát hiểm"
                ),
                InventoryItem(
                    id="inv-com-lgt-002",
                    sku="VTX-COM-LGT-002",
                    name="Đèn chiếu sáng sự cố khẩn cấp 2 mắt LED Kentom KT-2200EL",
                    warehouse_type=WarehouseType.COMMERCIAL,
                    category="Đèn Exit & Chiếu sáng sự cố",
                    unit="cái",
                    stock_quantity=310.0,
                    cost_price=280000.0,
                    retail_price=430000.0,
                    dealer_price=350000.0,
                    project_discount_rate=6.0,
                    spec="2 bóng LED xoay chỉnh góc linh hoạt, tự động sáng khi mất điện lưới",
                    notes="Chiếu sáng khẩn cấp lối thoát hiểm khi xảy ra hỏa hoạn"
                )
            ]

            for item in seed_items:
                bom_json = json.dumps(item.bom_data, ensure_ascii=False) if item.bom_data else ""
                cursor.execute("""
                INSERT OR REPLACE INTO inventory_items (
                    id, sku, name, warehouse_type, category, unit,
                    stock_quantity, cost_price, retail_price, dealer_price, project_discount_rate,
                    is_custom_dimensions, default_length, default_width, default_thickness, material_type,
                    bom_data, spec, notes, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    item.id, item.sku, item.name, item.warehouse_type.value if hasattr(item.warehouse_type, "value") else str(item.warehouse_type),
                    item.category, item.unit, item.stock_quantity, item.cost_price, item.retail_price, item.dealer_price, item.project_discount_rate,
                    1 if item.is_custom_dimensions else 0, item.default_length, item.default_width, item.default_thickness, item.material_type,
                    bom_json, item.spec, item.notes, item.created_at, item.updated_at
                ))
            conn.commit()

    def get_inventory_items(
        self,
        warehouse_type: Optional[str] = None,
        category: Optional[str] = None,
        search: Optional[str] = None
    ) -> List[InventoryItem]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            query = "SELECT * FROM inventory_items WHERE 1=1"
            params = []

            if warehouse_type:
                query += " AND warehouse_type = ?"
                params.append(warehouse_type.upper())
            if category:
                query += " AND category = ?"
                params.append(category)
            if search:
                query += " AND (name LIKE ? OR sku LIKE ? OR spec LIKE ?)"
                kw = f"%{search.strip()}%"
                params.extend([kw, kw, kw])

            query += " ORDER BY category ASC, sku ASC"
            cursor.execute(query, params)
            rows = cursor.fetchall()
            
            items = []
            for r in rows:
                bom_d = None
                if r["bom_data"]:
                    try:
                        bom_d = json.loads(r["bom_data"])
                    except Exception:
                        bom_d = None
                items.append(InventoryItem(
                    id=r["id"],
                    sku=r["sku"],
                    name=r["name"],
                    warehouse_type=WarehouseType(r["warehouse_type"]),
                    category=r["category"],
                    unit=r["unit"],
                    stock_quantity=r["stock_quantity"] or 0.0,
                    cost_price=r["cost_price"] or 0.0,
                    retail_price=r["retail_price"] or 0.0,
                    dealer_price=r["dealer_price"] or 0.0,
                    project_discount_rate=r["project_discount_rate"] or 0.0,
                    is_custom_dimensions=bool(r["is_custom_dimensions"]),
                    default_length=r["default_length"],
                    default_width=r["default_width"],
                    default_thickness=r["default_thickness"],
                    material_type=r["material_type"],
                    bom_data=bom_d,
                    spec=r["spec"] or "",
                    notes=r["notes"] or "",
                    created_at=r["created_at"] or "",
                    updated_at=r["updated_at"] or ""
                ))
            return items

    def get_inventory_item_by_id(self, item_id: str) -> Optional[InventoryItem]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM inventory_items WHERE id = ?", (item_id,))
            r = cursor.fetchone()
            if not r:
                return None
            bom_d = None
            if r["bom_data"]:
                try:
                    bom_d = json.loads(r["bom_data"])
                except Exception:
                    bom_d = None
            return InventoryItem(
                id=r["id"],
                sku=r["sku"],
                name=r["name"],
                warehouse_type=WarehouseType(r["warehouse_type"]),
                category=r["category"],
                unit=r["unit"],
                stock_quantity=r["stock_quantity"] or 0.0,
                cost_price=r["cost_price"] or 0.0,
                retail_price=r["retail_price"] or 0.0,
                dealer_price=r["dealer_price"] or 0.0,
                project_discount_rate=r["project_discount_rate"] or 0.0,
                is_custom_dimensions=bool(r["is_custom_dimensions"]),
                default_length=r["default_length"],
                default_width=r["default_width"],
                default_thickness=r["default_thickness"],
                material_type=r["material_type"],
                bom_data=bom_d,
                spec=r["spec"] or "",
                notes=r["notes"] or "",
                created_at=r["created_at"] or "",
                updated_at=r["updated_at"] or ""
            )

    def get_inventory_item_by_sku(self, sku: str) -> Optional[InventoryItem]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM inventory_items WHERE sku = ?", (sku,))
            r = cursor.fetchone()
            if not r:
                return None
            bom_d = None
            if r["bom_data"]:
                try:
                    bom_d = json.loads(r["bom_data"])
                except Exception:
                    bom_d = None
            return InventoryItem(
                id=r["id"],
                sku=r["sku"],
                name=r["name"],
                warehouse_type=WarehouseType(r["warehouse_type"]),
                category=r["category"],
                unit=r["unit"],
                stock_quantity=r["stock_quantity"] or 0.0,
                cost_price=r["cost_price"] or 0.0,
                retail_price=r["retail_price"] or 0.0,
                dealer_price=r["dealer_price"] or 0.0,
                project_discount_rate=r["project_discount_rate"] or 0.0,
                is_custom_dimensions=bool(r["is_custom_dimensions"]),
                default_length=r["default_length"],
                default_width=r["default_width"],
                default_thickness=r["default_thickness"],
                material_type=r["material_type"],
                bom_data=bom_d,
                spec=r["spec"] or "",
                notes=r["notes"] or "",
                created_at=r["created_at"] or "",
                updated_at=r["updated_at"] or ""
            )

    def create_inventory_item(self, item: InventoryItem) -> InventoryItem:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            bom_json = json.dumps(item.bom_data, ensure_ascii=False) if item.bom_data else ""
            cursor.execute("""
            INSERT INTO inventory_items (
                id, sku, name, warehouse_type, category, unit,
                stock_quantity, cost_price, retail_price, dealer_price, project_discount_rate,
                is_custom_dimensions, default_length, default_width, default_thickness, material_type,
                bom_data, spec, notes, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                item.id, item.sku, item.name, item.warehouse_type.value if hasattr(item.warehouse_type, "value") else str(item.warehouse_type),
                item.category, item.unit, item.stock_quantity, item.cost_price, item.retail_price, item.dealer_price, item.project_discount_rate,
                1 if item.is_custom_dimensions else 0, item.default_length, item.default_width, item.default_thickness, item.material_type,
                bom_json, item.spec, item.notes, item.created_at, item.updated_at
            ))
            conn.commit()
            return item

    def update_inventory_item(self, item_id: str, updates: Dict[str, Any]) -> Optional[InventoryItem]:
        item = self.get_inventory_item_by_id(item_id)
        if not item:
            return None
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            set_clauses = []
            params = []
            
            for k, v in updates.items():
                if k == "warehouse_type" and hasattr(v, "value"):
                    v = v.value
                elif k == "bom_data" and isinstance(v, dict):
                    v = json.dumps(v, ensure_ascii=False)
                elif k == "is_custom_dimensions":
                    v = 1 if v else 0
                set_clauses.append(f"{k} = ?")
                params.append(v)
            
            set_clauses.append("updated_at = ?")
            params.append(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            params.append(item_id)
            
            query = f"UPDATE inventory_items SET {', '.join(set_clauses)} WHERE id = ?"
            cursor.execute(query, params)
            conn.commit()
            
        return self.get_inventory_item_by_id(item_id)

    def delete_inventory_item(self, item_id: str) -> bool:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM inventory_items WHERE id = ?", (item_id,))
            conn.commit()
            return cursor.rowcount > 0


db = Database()


