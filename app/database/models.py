"""
Data Models for Vertex Construction & PCCC Quote System
Includes User & RBAC Auth models, Master Template & Pricing Coefficients,
Quote, QuoteItem, PCCC Price Catalog, and Multi-language support.
"""
from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime


class UserRole(str, Enum):
    ADMIN = "ADMIN"          # Sếp Tiến (Giám đốc) - Toàn quyền hệ thống & quản trị user
    MANAGER = "MANAGER"      # Anh Việt (Trưởng phòng KD) - Duyệt giá, quản lý báo giá
    STAFF = "STAFF"          # Kỹ sư bóc tách / Nhân viên kinh doanh
    DEALER = "DEALER"        # Đại lý phân phối thiết bị PCCC
    PARTNER = "PARTNER"      # Đối tác nhà thầu thi công MEP/PCCC


class UserStatus(str, Enum):
    ACTIVE = "ACTIVE"
    PENDING_APPROVAL = "PENDING_APPROVAL"
    DISABLED = "DISABLED"


class User(BaseModel):
    id: str
    username: str
    full_name: str
    email: Optional[str] = ""
    phone: Optional[str] = ""
    company_name: Optional[str] = ""
    role: UserRole = UserRole.STAFF
    status: UserStatus = UserStatus.ACTIVE
    is_active: bool = True
    created_at: str = Field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))


class UserInDB(User):
    hashed_password: str


class UserLoginRequest(BaseModel):
    username: str
    password: str


class UserRegisterRequest(BaseModel):
    username: str
    password: str
    full_name: str
    email: Optional[str] = ""
    phone: Optional[str] = ""
    company_name: Optional[str] = ""
    account_type: Optional[str] = "STAFF"  # "STAFF", "DEALER", "PARTNER"


class UserUpdateStatusRequest(BaseModel):
    status: UserStatus


class UserUpdateRoleRequest(BaseModel):
    role: UserRole


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: User


# -------------------------------------------------------------
# Master Template & Pricing Coefficients Models
# -------------------------------------------------------------
class MasterTemplate(BaseModel):
    id: str
    name: str = "File Mẫu Chuẩn Vertex 2026 (PCCC & Ống Gió)"
    file_path: Optional[str] = ""
    file_name: Optional[str] = "Master_Template_Vertex.xlsx"
    description: Optional[str] = "Mẫu chuẩn tính giá bóc tách PCCC & Cơ điện với công thức định mức chi phí"
    
    # Pricing Coefficient Framework (% multipliers)
    waste_ratio: float = 0.05       # 5% Hao hụt vật tư
    transport_ratio: float = 0.03   # 3% Vận chuyển / Logistics
    labor_ratio: float = 0.15       # 15% Nhân công lắp đặt / phụ kiện
    margin_ratio: float = 0.12      # 12% Biên độ lợi nhuận công ty
    
    is_active: bool = True
    created_by: str = "Sếp Tiến (Admin)"
    created_at: str = Field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    updated_at: str = Field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))


class UpdateCoefficientsRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    waste_ratio: float = Field(0.05, ge=0.0, le=1.0)
    transport_ratio: float = Field(0.03, ge=0.0, le=1.0)
    labor_ratio: float = Field(0.15, ge=0.0, le=1.0)
    margin_ratio: float = Field(0.12, ge=0.0, le=1.0)


class QuoteStatus(str, Enum):
    DRAFT = "DRAFT"
    PENDING_APPROVAL = "PENDING_APPROVAL"
    PENDING_DIRECTOR_APPROVAL = "PENDING_DIRECTOR_APPROVAL"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    SENT_TO_CUSTOMER = "SENT_TO_CUSTOMER"


class QuoteItem(BaseModel):
    stt: int = 1
    category: str = "Thiết bị PCCC"  # "Thiết bị PCCC", "Bình chữa cháy", "Báo cháy", "Đèn Exit/Sự cố", "Ống gió", "Van gió"
    item_code: str = ""
    item_name: str = ""
    brand: Optional[str] = "Vertex Standard"
    brand_source: Optional[str] = "VERTEX_STANDARD"  # "CLIENT_SPECIFIED", "VERTEX_STANDARD", "CAD_TAKEOFF"
    spec: str = ""
    unit: str = "cái"
    width: Optional[float] = None
    height: Optional[float] = None
    diameter: Optional[float] = None
    length: Optional[float] = None
    thickness: Optional[float] = None
    material: Optional[str] = "Tiêu chuẩn PCCC"
    quantity: float = 1.0
    area_m2: float = 0.0
    
    # Cost Breakdown & Pricing fields
    material_unit_cost: float = 0.0
    labor_unit_cost: float = 0.0
    base_unit_cost: float = 0.0
    labor_description: Optional[str] = ""
    unit_price: float = 0.0
    total_price: float = 0.0
    price_source: str = "CATALOG"  # "CATALOG", "AI_MARKET_ESTIMATE", "MANUAL_INPUT"
    raw_market_price: Optional[float] = 0.0
    applied_coefficients: Optional[Dict[str, float]] = None
    
    confidence_score: float = 1.0
    notes: str = ""


class PriceCatalogItem(BaseModel):
    code: str
    name: str
    category: str
    material: str = "Tiêu chuẩn PCCC"
    thickness: float = 0.0
    unit: str = "cái"
    unit_price: float = 0.0
    keywords: List[str] = []
    notes: str = ""


class AuditLog(BaseModel):
    id: str
    quote_id: str
    user_id: Optional[str] = ""
    user_name: str = "Hệ thống"
    user_role: str = "STAFF"
    action: str  # "CREATE_QUOTE", "CREATE_REVISION", "UPDATE_ITEMS", "MANAGER_APPROVE", "DIRECTOR_APPROVE", "REJECT_QUOTE", "EXPORT_EXCEL"
    details: str = ""
    ip_address: Optional[str] = ""
    timestamp: str = Field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))


class Quote(BaseModel):
    id: str
    quote_code: str
    customer_name: str = "Quý Khách Hàng"
    customer_phone: str = ""
    customer_email: Optional[str] = ""
    customer_zalo_id: Optional[str] = ""
    project_name: str = "Công trình Tiêu chuẩn"
    project_address: Optional[str] = ""
    status: QuoteStatus = QuoteStatus.PENDING_APPROVAL
    language: str = "vi"  # "vi", "en", "zh", "ko"
    
    # Scenario Classification & Cost Breakdown
    scenario_type: str = "SCENARIO_3_STANDARD_CATALOG"  # "SCENARIO_1_CAD_TAKEOFF", "SCENARIO_2_SPECIFIED_BRAND", "SCENARIO_3_STANDARD_CATALOG"
    total_material_cost: float = 0.0
    total_labor_cost: float = 0.0
    
    # Version Control
    version: int = 1
    parent_quote_id: Optional[str] = None
    revision_note: Optional[str] = ""

    # Multi-level Approval Matrix
    required_approval_level: str = "MANAGER"  # "MANAGER" or "DIRECTOR"
    manager_approved_by: Optional[str] = None
    manager_approved_at: Optional[str] = None
    director_approved_by: Optional[str] = None
    director_approved_at: Optional[str] = None
    
    # Template & Pricing framework used
    template_id: Optional[str] = None
    template_name: Optional[str] = None
    
    subtotal: float = 0.0
    discount_rate: float = 0.05
    discount_amount: float = 0.0
    subtotal_after_discount: float = 0.0
    vat_rate: float = 0.08
    vat_amount: float = 0.0
    total_amount: float = 0.0
    total_amount_in_words: str = ""
    
    input_file_name: str = ""
    input_file_path: str = ""
    excel_quote_path: Optional[str] = ""
    
    created_at: str = Field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    updated_at: str = Field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    approved_by: Optional[str] = None
    approved_at: Optional[str] = None
    rejection_reason: Optional[str] = None
    
    items: List[QuoteItem] = []
    logs: List[str] = []


class QuoteRevisionRequest(BaseModel):
    revision_note: str = "Điều chỉnh số lượng / đơn giá / chiết khấu"
    discount_rate: Optional[float] = None
    vat_rate: Optional[float] = None
    items: Optional[List[QuoteItem]] = None


class ApprovalRequest(BaseModel):
    quote_id: str
    action: str  # "approve" or "reject"
    manager_name: str = "Quản lý Vertex"
    manager_id: Optional[str] = None
    manager_role: Optional[str] = "MANAGER"
    reason: Optional[str] = ""
    ip_address: Optional[str] = ""



class ZaloWebhookEvent(BaseModel):
    app_id: Optional[str] = None
    user_id_by_app: Optional[str] = None
    event_name: Optional[str] = None
    timestamp: Optional[int] = None
    sender: Optional[Dict[str, Any]] = None
    recipient: Optional[Dict[str, Any]] = None
    message: Optional[Dict[str, Any]] = None
    info: Optional[Dict[str, Any]] = None


# -------------------------------------------------------------
# Field Attendance & Daily Site Report Models
# -------------------------------------------------------------
class AttendanceCheckin(BaseModel):
    id: str
    user_id: str
    user_name: str
    project_site: str
    checkin_type: str = "IN"  # "IN", "OUT", "SITE_VISIT"
    latitude: float
    longitude: float
    accuracy_meters: Optional[float] = 10.0
    address_resolved: Optional[str] = ""
    status: str = "ON_TIME"  # "ON_TIME", "LATE", "OUT_OF_BOUNDS"
    notes: Optional[str] = ""
    created_at: str = Field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))


class AttendanceCheckinCreateRequest(BaseModel):
    project_site: str
    checkin_type: str = "IN"
    latitude: float
    longitude: float
    accuracy_meters: Optional[float] = 10.0
    address_resolved: Optional[str] = ""
    notes: Optional[str] = ""


class FieldDailyReport(BaseModel):
    id: str
    user_id: str
    user_name: str
    project_name: str
    report_date: str = Field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d"))
    weather_condition: str = "Nắng ráo"
    work_summary: str
    progress_percent: float = 0.0
    workforce_count: int = 1
    issues_and_risks: Optional[str] = ""
    next_plan: Optional[str] = ""
    photos_json: Optional[str] = "[]"
    supervisor_comment: Optional[str] = ""
    status: str = "SUBMITTED"  # "SUBMITTED", "APPROVED", "REJECTED"
    created_at: str = Field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))


class FieldDailyReportCreateRequest(BaseModel):
    project_name: str
    report_date: Optional[str] = None
    weather_condition: str = "Nắng ráo"
    work_summary: str
    progress_percent: float = 0.0
    workforce_count: int = 1
    issues_and_risks: Optional[str] = ""
    next_plan: Optional[str] = ""
    photos_json: Optional[str] = "[]"


class FieldReportCommentRequest(BaseModel):
    comment: str
    status: Optional[str] = "APPROVED"


class GeofenceCheckRequest(BaseModel):
    project_site: str
    latitude: float
    longitude: float
    checkin_type: Optional[str] = "IN"
    notes: Optional[str] = ""


class GeofenceAlertRecord(BaseModel):
    id: str
    user_id: str
    user_name: str
    project_site: str
    latitude: float
    longitude: float
    distance_meters: float
    radius_meters: float
    alert_message: str
    status: str = "UNRESOLVED"  # "UNRESOLVED", "RESOLVED", "EXEMPTED"
    created_at: str = Field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))


class GeofenceConfigUpdateRequest(BaseModel):
    project_site: str
    radius_meters: Optional[float] = 200.0
    lat: Optional[float] = None
    lng: Optional[float] = None
    address: Optional[str] = None


# -------------------------------------------------------------
# Inventory & BOM Management Models (Multi-Tier Pricing Engine)
# -------------------------------------------------------------
class WarehouseType(str, Enum):
    MANUFACTURING = "MANUFACTURING"    # Kho Sản Xuất (Vật tư thô, tôn, nhôm, tấm ốp gầm pin xe điện VinFast, ống gió EI, tủ điện)
    COMMERCIAL = "COMMERCIAL"          # Kho Thương Mại & Dự Án (Thiết bị PCCC, bình chữa cháy, van, sprinkler, báo cháy)


class CustomerTier(str, Enum):
    RETAIL = "RETAIL"                  # Khách Lẻ / Trực Tiếp (Áp dụng Giá Lẻ)
    DEALER = "DEALER"                  # Đại Lý Phân Phối (Áp dụng Giá Đại Lý)
    PROJECT = "PROJECT"                # Dự Án PCCC / Nhà Thầu MEP (Áp dụng Chiết Khấu Dự Án %)


class BOMComponent(BaseModel):
    material_name: str
    spec: Optional[str] = ""
    unit: str = "kg"
    quantity: float = 1.0
    unit_cost: float = 0.0
    total_cost: float = 0.0


class BOMBreakdown(BaseModel):
    raw_materials: List[BOMComponent] = []
    raw_material_cost: float = 0.0
    scrap_waste_ratio: float = 0.05    # 5% Phế liệu / Hao hụt
    scrap_waste_cost: float = 0.0
    labor_cost: float = 0.0            # Chi phí nhân công sản xuất / dập / hàn / sơn
    overhead_cost: float = 0.0         # Chi phí quản lý xưởng / khấu hao máy / vận chuyển
    calculated_cost_price: float = 0.0 # Giá vốn xuất xưởng thực tế
    margin_retail: float = 0.30        # 30% Biên độ bán lẻ
    margin_dealer: float = 0.15        # 15% Biên độ đại lý


class InventoryItem(BaseModel):
    id: str
    sku: str
    name: str
    warehouse_type: WarehouseType = WarehouseType.MANUFACTURING
    category: str = "Tôn & Kim loại tấm"
    unit: str = "cái"
    stock_quantity: float = 0.0
    
    # Multi-Tier Pricing System
    cost_price: float = 0.0            # 1. Giá Vốn (Factory / Import Cost)
    retail_price: float = 0.0          # 2. Giá Lẻ (Listed Price)
    dealer_price: float = 0.0          # 3. Giá Đại Lý (Distribution Price)
    project_discount_rate: float = 0.0 # 4. Chiết Khấu Dự Án % (Project Discount %)
    
    # Custom Dimensions (For Manufacturing Items like Ducts, VinFast EV Skid Plates, Enclosures)
    is_custom_dimensions: bool = False
    default_length: Optional[float] = None     # mm
    default_width: Optional[float] = None      # mm
    default_thickness: Optional[float] = None  # mm
    material_type: Optional[str] = None        # "THÉP_MẠ_KẼM", "NHÔM_AL5052", "INOX_304", "VỮA_CHỐNG_CHÁY"
    
    # BOM Definition (JSON string / dict)
    bom_data: Optional[Dict[str, Any]] = None
    spec: Optional[str] = ""
    notes: Optional[str] = ""
    created_at: str = Field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    updated_at: str = Field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))


class InventoryItemCreateRequest(BaseModel):
    sku: str
    name: str
    warehouse_type: WarehouseType
    category: str
    unit: str = "cái"
    stock_quantity: float = 0.0
    cost_price: float
    retail_price: float
    dealer_price: float
    project_discount_rate: float = 0.0
    is_custom_dimensions: bool = False
    default_length: Optional[float] = None
    default_width: Optional[float] = None
    default_thickness: Optional[float] = None
    material_type: Optional[str] = None
    bom_data: Optional[Dict[str, Any]] = None
    spec: Optional[str] = ""
    notes: Optional[str] = ""


class QuickQuoteLineItem(BaseModel):
    inventory_id: Optional[str] = None
    sku: str
    item_name: str
    warehouse_type: WarehouseType = WarehouseType.COMMERCIAL
    category: str = "Thiết bị PCCC"
    unit: str = "cái"
    quantity: float = 1.0
    
    # Custom Dimensions
    length_mm: Optional[float] = None
    width_mm: Optional[float] = None
    thickness_mm: Optional[float] = None
    calculated_area_m2: Optional[float] = None
    calculated_weight_kg: Optional[float] = None
    
    # Pricing & Margin
    cost_price: float = 0.0
    unit_price: float = 0.0
    total_price: float = 0.0
    gross_margin_amount: float = 0.0
    gross_margin_percent: float = 0.0
    applied_tier: str = "RETAIL"
    notes: Optional[str] = ""


class QuickQuoteCreateRequest(BaseModel):
    customer_name: str
    customer_phone: Optional[str] = ""
    customer_email: Optional[str] = ""
    project_name: str
    project_address: Optional[str] = ""
    customer_tier: CustomerTier = CustomerTier.RETAIL
    items: List[QuickQuoteLineItem]
    vat_rate: float = 0.08
    special_discount_percent: float = 0.0
    notes: Optional[str] = ""
