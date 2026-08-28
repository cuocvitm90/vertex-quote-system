/**
 * Client-Side Multi-Language (i18n) Engine for Vertex Construction & PCCC
 * Languages: vi (Tiếng Việt), en (English), zh (简体中文), ko (한국어)
 */

const I18N_CLIENT = {
    vi: {
        flag: "🇻🇳",
        name: "Tiếng Việt",
        stat_total: "Tổng Báo Giá",
        stat_pending: "Chờ Duyệt (Zalo)",
        stat_approved: "Đã Duyệt / Gửi",
        nav_create_quote: "Tạo Báo Giá Mới",
        nav_cad_takeoff: "Bóc Tách CAD/Revit",
        nav_field_report: "Chấm Công & Báo Cáo",
        nav_user_mgmt: "Quản Trị Người Dùng",
        nav_user_guide: "Hướng Dẫn",
        user_guide_title: "Hướng Dẫn Sử Dụng Quy Trình Báo Giá Thông Minh Vertex",
        workflow_title: "Quy Trình Báo Giá Tự Động Vertex (FastAPI + Groq AI + Zalo OA)",
        badge_ai: "Groq AI (Llama-3.3-70B Định Tính)",
        badge_math: "Python Math 100% Thuần",
        step_1_title: "1. Nhận File BOQ",
        step_1_desc: "Excel, CAD DXF, PDF thiết bị PCCC",
        step_2_title: "2. Groq AI & Python Engine",
        step_2_desc: "Bóc tách định tính, tra giá & tính VAT",
        step_3_title: "3. Xuất Excel Vertex",
        step_3_desc: "Mẫu báo giá PCCC & MEP chuẩn nhận diện",
        step_4_title: "4. Duyệt Zalo OA",
        step_4_desc: "Gửi thẻ [Duyệt]/[Từ chối] cho sếp",
        step_5_title: "5. Gửi Khách Hàng",
        step_5_desc: "Tự động gửi báo giá khi sếp duyệt",
        upload_title: "Tải Lên BOQ / Bản Vẽ PCCC & Cơ Điện",
        upload_ai_badge: "AI Bóc Tách Tự Động",
        dropzone_title: "Kéo thả file vào đây hoặc",
        dropzone_browse: "chọn file từ máy tính",
        dropzone_hint: "Hỗ trợ định dạng: Excel (.xlsx, .xls), CAD (.dxf), PDF hoặc CSV",
        customer_name_lbl: "Tên Khách Hàng / Nhà Thầu",
        customer_phone_lbl: "Số Điện Thoại / Zalo",
        project_name_lbl: "Tên Dự Án / Công Trình PCCC",
        project_address_lbl: "Địa Chỉ Công Trình",
        discount_rate_lbl: "Chiết Khấu Thương Mại (%)",
        vat_rate_lbl: "Thuế Suất VAT (%)",
        select_lang_lbl: "Ngôn Ngữ Báo Giá (Excel)",
        sample_title: "Thử nhanh với file mẫu:",
        sample_btn_excel: "BOQ Thiết Bị PCCC Mẫu",
        sample_btn_cad: "Bản Vẽ CAD PCCC Mẫu",
        btn_activate_ai: "KÍCH HOẠT AI TẠO BÁO GIÁ & GỬI DUYỆT",
        zalo_sim_title: "Zalo OA Simulator (Duyệt Báo Giá PCCC)",
        zalo_sim_desc: "Giả lập thẻ duyệt báo giá tương tác trên Zalo OA của Anh Việt / Sếp Tiến.",
        zalo_empty: "Chưa có yêu cầu duyệt mới. Hãy tải lên file BOQ ở bên trái để kích hoạt gửi duyệt Zalo!",
        catalog_title: "Bảng Đơn Giá Thiết Bị PCCC & Ống Gió Chuẩn",
        catalog_search_ph: "Tìm kiếm thiết bị...",
        quotes_history_title: "Danh Sách Báo Giá Gần Đây",
        filter_all: "Tất Cả",
        filter_pending: "Chờ Duyệt",
        filter_approved: "Đã Duyệt",
        filter_sent: "Đã Gửi Khách",
        col_quote_code: "Mã Báo Giá",
        col_customer_project: "Khách Hàng & Dự Án",
        col_created_at: "Ngày Lập",
        col_subtotal: "Tổng Tiền Hàng",
        col_discount_vat: "Chiết Khấu / VAT",
        col_total_amount: "Tổng Thanh Toán",
        col_status: "Trạng Thái",
        col_actions: "Thao Tác"
    },
    en: {
        flag: "🇬🇧",
        name: "English",
        stat_total: "Total Quotes",
        stat_pending: "Pending (Zalo)",
        stat_approved: "Approved / Sent",
        nav_create_quote: "Create New Quote",
        nav_cad_takeoff: "CAD/Revit Takeoff",
        nav_field_report: "Attendance & Reports",
        nav_user_mgmt: "User Management",
        nav_user_guide: "User Guide",
        user_guide_title: "Vertex Intelligent Quotation 4-Step User Guide",
        workflow_title: "Vertex Automated Quotation Pipeline (FastAPI + Groq AI + Zalo OA)",
        badge_ai: "Groq AI (Llama-3.3-70B Qualitative)",
        badge_math: "100% Pure Python Math",
        step_1_title: "1. Receive BOQ",
        step_1_desc: "Excel, CAD DXF, PDF Fire Equipment",
        step_2_title: "2. Groq AI & Python Engine",
        step_2_desc: "Qualitative extraction, pricing & VAT",
        step_3_title: "3. Export Vertex Excel",
        step_3_desc: "Branded PCCC & MEP quotation template",
        step_4_title: "4. Manager Approval",
        step_4_desc: "Send [Approve]/[Reject] card to manager",
        step_5_title: "5. Send to Client",
        step_5_desc: "Automatic delivery upon approval",
        upload_title: "Upload BOQ / Fire Protection & MEP Drawing",
        upload_ai_badge: "Automated AI Extraction",
        dropzone_title: "Drag & drop files here or",
        dropzone_browse: "browse from computer",
        dropzone_hint: "Supported formats: Excel (.xlsx, .xls), CAD (.dxf), PDF or CSV",
        customer_name_lbl: "Client Name / Main Contractor",
        customer_phone_lbl: "Phone / Mobile Number",
        project_name_lbl: "Project Name / Site Location",
        project_address_lbl: "Site Delivery Address",
        discount_rate_lbl: "Commercial Discount (%)",
        vat_rate_lbl: "VAT Rate (%)",
        select_lang_lbl: "Quotation Language (Excel)",
        sample_title: "Quick test with sample files:",
        sample_btn_excel: "Sample Fire Equipment BOQ",
        sample_btn_cad: "Sample Fire CAD DXF",
        btn_activate_ai: "ACTIVATE AI TO GENERATE QUOTE & SUBMIT",
        zalo_sim_title: "Zalo OA Simulator (Manager Approval)",
        zalo_sim_desc: "Interactive quotation approval card mockup for Managers / Directors.",
        zalo_empty: "No pending approval requests. Upload a BOQ file on the left to trigger approval!",
        catalog_title: "Standard Fire Equipment & Ductwork Price Catalog",
        catalog_search_ph: "Search equipment...",
        quotes_history_title: "Recent Quotation History",
        filter_all: "All",
        filter_pending: "Pending",
        filter_approved: "Approved",
        filter_sent: "Sent to Client",
        col_quote_code: "Quote Code",
        col_customer_project: "Client & Project",
        col_created_at: "Date",
        col_subtotal: "Subtotal",
        col_discount_vat: "Discount / VAT",
        col_total_amount: "Total Amount",
        col_status: "Status",
        col_actions: "Actions"
    },
    zh: {
        flag: "🇨🇳",
        name: "简体中文",
        stat_total: "总报价单数",
        stat_pending: "待审批 (Zalo)",
        stat_approved: "已审批 / 已发送",
        nav_create_quote: "新建报价单",
        nav_cad_takeoff: "CAD/Revit 算量",
        nav_field_report: "GPS考勤与现场报告",
        nav_user_mgmt: "用户管理",
        nav_user_guide: "使用指南",
        user_guide_title: "Vertex 智能报价四步操作指南",
        workflow_title: "Vertex 自动化报价流程 (FastAPI + Groq AI + Zalo OA)",
        badge_ai: "Groq AI (Llama-3.3-70B 定性提取)",
        badge_math: "Python 100% 纯数学运算",
        step_1_title: "1. 接收工程量清单",
        step_1_desc: "Excel, CAD DXF, PDF 消防设备清单",
        step_2_title: "2. Groq AI 与 Python 引擎",
        step_2_desc: "定性结构化解析、精准计算增值税",
        step_3_title: "3. 导出标准 Excel",
        step_3_desc: "符合 Vertex 品牌标准的专业报价单",
        step_4_title: "4. 管理员在线审批",
        step_4_desc: "推送交互式卡片供主管审批",
        step_5_title: "5. 发送客户",
        step_5_desc: "审批通过后自动发送给业主",
        upload_title: "上传消防工程量清单 / CAD 图纸",
        upload_ai_badge: "AI 自动化提取",
        dropzone_title: "拖拽文件至此 或",
        dropzone_browse: "从电脑选择文件",
        dropzone_hint: "支持格式：Excel (.xlsx, .xls), CAD (.dxf), PDF 或 CSV",
        customer_name_lbl: "客户名称 / 总承包商",
        customer_phone_lbl: "联系电话 / Zalo",
        project_name_lbl: "项目名称 / 工程地点",
        project_address_lbl: "送货地址",
        discount_rate_lbl: "商业折扣率 (%)",
        vat_rate_lbl: "增值税率 VAT (%)",
        select_lang_lbl: "报价单导出语言 (Excel)",
        sample_title: "快速测试范例文件：",
        sample_btn_excel: "消防设备清单范例",
        sample_btn_cad: "消防 CAD DXF 范例",
        btn_activate_ai: "启动 AI 生成报价单并提交审批",
        zalo_sim_title: "Zalo OA 模拟器 (主管审批)",
        zalo_sim_desc: "面向企业主管与总经理的交互式报价审批卡片模拟。",
        zalo_empty: "暂无待审批请求。请在左侧上传文件触发审批！",
        catalog_title: "Vertex 消防设备与风管标准价格表",
        catalog_search_ph: "搜索设备...",
        quotes_history_title: "近期报价记录",
        filter_all: "全部",
        filter_pending: "待审批",
        filter_approved: "已审批",
        filter_sent: "已发送客户",
        col_quote_code: "报价单号",
        col_customer_project: "客户与项目",
        col_created_at: "创建日期",
        col_subtotal: "商品总额",
        col_discount_vat: "折扣 / 增值税",
        col_total_amount: "结算总额",
        col_status: "状态",
        col_actions: "操作"
    },
    ko: {
        flag: "🇰🇷",
        name: "한국어",
        stat_total: "총 견적 건수",
        stat_pending: "승인 대기 (Zalo)",
        stat_approved: "승인 / 발송 완료",
        nav_create_quote: "새 견적서 작성",
        nav_cad_takeoff: "CAD/Revit 수량산출",
        nav_field_report: "GPS근태 및 현장보고",
        nav_user_mgmt: "사용자 관리",
        nav_user_guide: "사용 가이드",
        user_guide_title: "Vertex 스마트 견적 4단계 사용 가이드",
        workflow_title: "Vertex 자동 견적 파이프라인 (FastAPI + Groq AI + Zalo OA)",
        badge_ai: "Groq AI (Llama-3.3-70B 정성 분석)",
        badge_math: "100% 순수 Python 수학 연산",
        step_1_title: "1. 내역서(BOQ) 접수",
        step_1_desc: "Excel, CAD DXF, PDF 소방 설비",
        step_2_title: "2. Groq AI & Python 엔진",
        step_2_desc: "정성적 물량 산출, 단가 매칭 및 부가세 계산",
        step_3_title: "3. 표준 Excel 출력",
        step_3_desc: "Vertex 브랜드 표준 소방 견적서",
        step_4_title: "4. 관리자 승인",
        step_4_desc": "[승인]/[반려] 대화형 카드 전송",
        step_5_title: "5. 고객 발송",
        step_5_desc: "관리자 승인 시 고객에게 즉시 발송",
        upload_title: "소방 내역서(BOQ) / CAD 도면 업로드",
        upload_ai_badge: "AI 자동 물량 산출",
        dropzone_title: "파일을 여기로 드래그하거나",
        dropzone_browse: "컴퓨터에서 파일 선택",
        dropzone_hint: "지원 형식: Excel (.xlsx, .xls), CAD (.dxf), PDF 또는 CSV",
        customer_name_lbl: "고객사명 / 원청사",
        customer_phone_lbl: "연락처 / Zalo",
        project_name_lbl: "프로젝트명 / 공사 현장",
        project_address_lbl: "납품 현장 주소",
        discount_rate_lbl: "할인율 (%)",
        vat_rate_lbl: "부가가치세율 VAT (%)",
        select_lang_lbl: "견적서 출력 언어 (Excel)",
        sample_title: "샘플 파일로 빠른 테스트:",
        sample_btn_excel: "소방 설비 샘플 BOQ",
        sample_btn_cad: "소방 CAD DXF 샘플",
        btn_activate_ai: "AI 자동 견적 산출 및 승인 요청",
        zalo_sim_title: "Zalo OA 시뮬레이터 (관리자 승인)",
        zalo_sim_desc: "부서장 및 대표이사용 인터랙티브 견적 승인 카드 시뮬레이터.",
        zalo_empty: "대기 중인 승인 요청이 없습니다. 좌측에서 파일을 업로드해 주세요!",
        catalog_title: "소방 설비 및 덕트 표준 단가표",
        catalog_search_ph: "설비 검색...",
        quotes_history_title: "최근 견적 내역",
        filter_all: "전체",
        filter_pending: "승인 대기",
        filter_approved: "승인 완료",
        filter_sent: "고객 발송",
        col_quote_code: "견적 번호",
        col_customer_project: "고객사 및 프로젝트",
        col_created_at: "작성일",
        col_subtotal: "공급가액",
        col_discount_vat: "할인 / 부가세",
        col_total_amount: "총 합계금액",
        col_status: "상태",
        col_actions: "작업"
    }
};

let currentLang = localStorage.getItem("vertex_lang") || "vi";

function setLanguage(langCode) {
    if (!I18N_CLIENT[langCode]) return;
    currentLang = langCode;
    localStorage.setItem("vertex_lang", langCode);

    // Sync Language Selector Select in Navbar
    const switcher = document.getElementById("language-switcher");
    if (switcher) switcher.value = langCode;

    // Update Form Select Language for Excel if present
    const excelLangSelect = document.getElementById("quote_language");
    if (excelLangSelect) excelLangSelect.value = langCode;

    // Apply translations to all DOM elements with data-i18n
    const dict = I18N_CLIENT[langCode];
    document.querySelectorAll("[data-i18n]").forEach(el => {
        const key = el.getAttribute("data-i18n");
        if (dict[key]) {
            if (el.tagName === "INPUT" && el.getAttribute("placeholder")) {
                el.placeholder = dict[key];
            } else {
                el.textContent = dict[key];
            }
        }
    });

    // Update catalog search placeholder
    const catSearch = document.getElementById("catalog-search");
    if (catSearch && dict["catalog_search_ph"]) {
        catSearch.placeholder = dict["catalog_search_ph"];
    }

    if (typeof showToast === "function") {
        showToast(`Đã chuyển ngôn ngữ sang ${dict.name} ${dict.flag}`);
    }
}

// Initialize language switcher on DOM load
document.addEventListener("DOMContentLoaded", () => {
    const savedLang = localStorage.getItem("vertex_lang") || "vi";
    const switcher = document.getElementById("language-switcher");
    if (switcher) {
        switcher.value = savedLang;
    }
});


