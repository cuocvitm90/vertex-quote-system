/**
 * Vertex Construction & PCCC - Frontend Application Logic
 * Supports Master Template Management, Multi-stage AI Price Estimation,
 * Multi-language, PCCC Equipment BOQ Processing, Zalo OA Simulator & Admin User Management.
 */

document.addEventListener('DOMContentLoaded', () => {
    initDropzone();
    initForm();
    initCatalogSearch();
    loadQuotesList();
    calculateLiveMultiplier();

    // Check tab query parameter
    const urlParams = new URLSearchParams(window.location.search);
    const tabParam = urlParams.get('tab');
    if (tabParam) {
        switchScenarioMode(tabParam);
    }

    // Check language
    if (typeof currentLang !== 'undefined' && typeof setLanguage === 'function') {
        setLanguage(currentLang);
    }
});

let currentQuotes = [];
let activeFilter = 'ALL';
let currentSimulationQuote = null;

// ----------------------------------------------------
// 0. 3-Scenario Workflow Tab Switching
// ----------------------------------------------------
function switchScenarioMode(scenario) {
    const tabCad = document.getElementById('scenario-tab-cad');
    const tabSpec = document.getElementById('scenario-tab-specified');
    const tabCat = document.getElementById('scenario-tab-catalog');
    const hiddenInput = document.getElementById('selected_scenario_type');
    const badgeEl = document.getElementById('upload-scenario-badge');
    const hintText = document.getElementById('dropzone-hint-text');
    const fileInput = document.getElementById('file-input');

    if (tabCad) tabCad.classList.remove('active');
    if (tabSpec) tabSpec.classList.remove('active');
    if (tabCat) tabCat.classList.remove('active');

    if (scenario === 'SCENARIO_1_CAD_TAKEOFF' || scenario === 'cad') {
        if (tabCad) tabCad.classList.add('active');
        if (hiddenInput) hiddenInput.value = 'SCENARIO_1_CAD_TAKEOFF';
        if (badgeEl) badgeEl.innerHTML = '<i class="fa-solid fa-compass-drafting"></i> <span>Luồng 1: Bốc Tách CAD/BIM (.dwg, .dxf)</span>';
        if (hintText) hintText.textContent = 'Hỗ trợ bản vẽ CAD (.dwg, .dxf) & Revit (.rvt). Tự động phân loại Sprinkler, Vách Tường, Báo Cháy, Ống Gió';
        if (fileInput) fileInput.accept = '.dwg,.dxf,.rvt,.ifc,.xlsx,.xls,.csv';
    } else if (scenario === 'SCENARIO_2_SPECIFIED_BRAND' || scenario === 'specified') {
        if (tabSpec) tabSpec.classList.add('active');
        if (hiddenInput) hiddenInput.value = 'SCENARIO_2_SPECIFIED_BRAND';
        if (badgeEl) badgeEl.innerHTML = '<i class="fa-solid fa-file-contract"></i> <span>Luồng 2: Nhập BOQ & Chỉ Định Hãng</span>';
        if (hintText) hintText.textContent = 'Hồ sơ thầu CĐT có yêu cầu hãng chỉ định (Ebara, Viking, Hochiki, Notifier, Paragon, Hòa Phát...). Giữ nguyên thương hiệu!';
        if (fileInput) fileInput.accept = '.xlsx,.xls,.pdf,.csv';
    } else {
        if (tabCat) tabCat.classList.add('active');
        if (hiddenInput) hiddenInput.value = 'SCENARIO_3_STANDARD_CATALOG';
        if (badgeEl) badgeEl.innerHTML = '<i class="fa-solid fa-layer-group"></i> <span>Luồng 3: Nhập BOQ Thuần & Đề Xuất</span>';
        if (hintText) hintText.textContent = 'Bảng BOQ không chỉ định hãng. Hệ thống tự động so khớp Vertex Catalog và đề xuất nhãn hiệu tối ưu chào thầu.';
        if (fileInput) fileInput.accept = '.xlsx,.xls,.pdf,.csv';
    }
}

// ----------------------------------------------------
// 1. Dropzone & File Input Handling
// ----------------------------------------------------
function initDropzone() {
    const dropzone = document.getElementById('dropzone');
    const fileInput = document.getElementById('file-input');
    const fileInfo = document.getElementById('selected-file-info');
    const fileNameDisplay = document.getElementById('file-name-display');

    if (!dropzone || !fileInput) return;

    ['dragenter', 'dragover'].forEach(eventName => {
        dropzone.addEventListener(eventName, (e) => {
            e.preventDefault();
            e.stopPropagation();
            dropzone.classList.add('dragover');
        });
    });

    ['dragleave', 'drop'].forEach(eventName => {
        dropzone.addEventListener(eventName, (e) => {
            e.preventDefault();
            e.stopPropagation();
            dropzone.classList.remove('dragover');
        });
    });

    dropzone.addEventListener('drop', (e) => {
        const dt = e.dataTransfer;
        const files = dt.files;
        if (files && files.length > 0) {
            fileInput.files = files;
            updateFileDisplay(files[0]);
        }
    });

    fileInput.addEventListener('change', (e) => {
        if (fileInput.files && fileInput.files.length > 0) {
            updateFileDisplay(fileInput.files[0]);
        }
    });

    // Master Template Mini Dropzone Handling
    const tplDropzone = document.getElementById('template-mini-dropzone');
    const tplFileInput = document.getElementById('direct-template-file');

    if (tplDropzone && tplFileInput) {
        ['dragenter', 'dragover'].forEach(eventName => {
            tplDropzone.addEventListener(eventName, (e) => {
                e.preventDefault();
                e.stopPropagation();
                tplDropzone.classList.add('dragover');
            });
        });

        ['dragleave', 'drop'].forEach(eventName => {
            tplDropzone.addEventListener(eventName, (e) => {
                e.preventDefault();
                e.stopPropagation();
                tplDropzone.classList.remove('dragover');
            });
        });

        tplDropzone.addEventListener('drop', (e) => {
            const dt = e.dataTransfer;
            const files = dt.files;
            if (files && files.length > 0) {
                tplFileInput.files = files;
                handleDirectTemplateUpload(files[0]);
            }
        });
    }
}


function updateFileDisplay(file) {
    const fileInfo = document.getElementById('selected-file-info');
    const fileNameDisplay = document.getElementById('file-name-display');
    if (fileNameDisplay) {
        fileNameDisplay.textContent = `${file.name} (${(file.size / 1024).toFixed(1)} KB)`;
    }
    if (fileInfo) fileInfo.style.display = 'inline-flex';
}

function scrollToUpload() {
    const el = document.getElementById('upload-section');
    if (el) el.scrollIntoView({ behavior: 'smooth' });
}

// ----------------------------------------------------
// 2. Load Sample Files
// ----------------------------------------------------
async function loadSampleBOQ(type) {
    showToast(`Đang nạp file mẫu ${type.toUpperCase()}...`);
    try {
        const resp = await fetch(`/api/sample-files/${type}`);
        if (!resp.ok) {
            generateSampleFileOnClient(type);
            return;
        }
        const blob = await resp.blob();
        const filename = type === 'excel' ? 'BOQ_Thiet_Bi_PCCC_Vertex.xlsx' : 'Ban_Ve_CAD_PCCC.dxf';
        const file = new File([blob], filename, { type: blob.type });
        
        const dataTransfer = new DataTransfer();
        dataTransfer.items.add(file);
        document.getElementById('file-input').files = dataTransfer.files;
        updateFileDisplay(file);
        showToast(`Đã nạp file mẫu ${filename} thành công!`);
    } catch (e) {
        generateSampleFileOnClient(type);
    }
}

function generateSampleFileOnClient(type) {
    const filename = type === 'excel' ? 'BOQ_Thiet_Bi_PCCC_Vertex.xlsx' : 'Ban_Ve_CAD_PCCC.dxf';
    const dummyBlob = new Blob(["VERTEX PCCC SAMPLE BOQ DATA"], { type: "application/octet-stream" });
    const file = new File([dummyBlob], filename, { type: "application/octet-stream" });
    
    const dataTransfer = new DataTransfer();
    dataTransfer.items.add(file);
    document.getElementById('file-input').files = dataTransfer.files;
    updateFileDisplay(file);
    showToast(`Đã chọn file mẫu: ${filename}`);
}

// ----------------------------------------------------
// 3. Form Submit & AI Pipeline Trigger
// ----------------------------------------------------
function initForm() {
    const form = document.getElementById('quote-upload-form');
    const terminalBox = document.getElementById('agent-terminal');
    const terminalLogs = document.getElementById('terminal-logs');
    const btnSubmit = document.getElementById('btn-submit');

    if (!form) return;

    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        const fileInput = document.getElementById('file-input');
        if (!fileInput.files || fileInput.files.length === 0) {
            showToast('Vui lòng chọn file BOQ hoặc CAD trước khi tiếp tục!');
            return;
        }

        const lang = window.currentLanguage || 'vi';
        const templateSelect = document.getElementById('template_id');
        const templateId = templateSelect ? templateSelect.value : (window.ACTIVE_TEMPLATE_ID || '');

        const formData = new FormData();
        formData.append('file', fileInput.files[0]);
        formData.append('customer_name', document.getElementById('customer_name').value);
        formData.append('customer_phone', document.getElementById('customer_phone').value);
        formData.append('project_name', document.getElementById('project_name').value);
        formData.append('project_address', document.getElementById('project_address').value);
        if (templateId) {
            formData.append('template_id', templateId);
        }
        
        const disc = parseFloat(document.getElementById('discount_rate_display').value) / 100.0;
        const vat = parseFloat(document.getElementById('vat_rate_display').value) / 100.0;
        formData.append('discount_rate', disc);
        formData.append('vat_rate', vat);
        formData.append('language', lang);

        // UI state: Running AI Agent
        btnSubmit.disabled = true;
        btnSubmit.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> AI Agent Đang Xử Lý Quy Trình 4 Bước...';
        if (terminalBox) terminalBox.style.display = 'block';
        if (terminalLogs) terminalLogs.innerHTML = '';

        appendTerminalLog(`🚀 [Khởi Động] Kết nối FastAPI Endpoint /api/quotes/upload (Language: ${lang.toUpperCase()})...`);
        appendTerminalLog('📋 [Bước 1: So khớp File Mẫu] Đang đọc file BOQ và so khớp bảng giá chuẩn Vertex...');

        try {
            const response = await fetch('/api/quotes/upload', {
                method: 'POST',
                body: formData
            });

            const data = await response.json();
            if (!response.ok) {
                throw new Error(data.detail || 'Lỗi xử lý tạo báo giá');
            }

            const quote = data.quote;
            if (quote && quote.logs) {
                quote.logs.forEach(logLine => appendTerminalLog(logLine));
            }

            appendTerminalLog(`🎉 [Hoàn Tất 4 Bước] Đã tạo Báo giá dự thảo: ${quote.quote_code} & đưa vào trạng thái Chờ Duyệt (Zalo OA)!`);
            showToast(`Tạo báo giá dự thảo ${quote.quote_code} thành công!`);

            // Update Zalo Simulator with this new quote
            renderZaloSimulator(quote);

            // Refresh table & stats
            await loadQuotesList();
            
        } catch (err) {
            appendTerminalLog(`❌ [Lỗi] ${err.message}`);
            showToast(`Lỗi: ${err.message}`);
        } finally {
            btnSubmit.disabled = false;
            btnSubmit.innerHTML = '<i class="fa-solid fa-bolt"></i> KÍCH HOẠT AI BÓC TÁCH & BÁO GIÁ';
        }
    });
}

function appendTerminalLog(text) {
    const terminalLogs = document.getElementById('terminal-logs');
    if (!terminalLogs) return;
    const div = document.createElement('div');
    div.className = 'log-line';
    div.textContent = text;
    terminalLogs.appendChild(div);
    terminalLogs.scrollTop = terminalLogs.scrollHeight;
}

// ----------------------------------------------------
// 4. Quotes History & Table
// ----------------------------------------------------
async function loadQuotesList() {
    try {
        const resp = await fetch('/api/quotes');
        if (!resp.ok) return;
        currentQuotes = await resp.json();
        renderQuotesTable();
        updateStats();

        // Load most recent quote into Zalo Simulator if available
        if (currentQuotes.length > 0 && !currentSimulationQuote) {
            renderZaloSimulator(currentQuotes[0]);
        }
    } catch (e) {
        console.error('Error loading quotes:', e);
    }
}

let currentActiveModalQuoteId = null;
let currentQuoteModalTab = 'items';

function renderQuotesTable() {
    const tbody = document.getElementById('quotes-tbody');
    if (!tbody) return;

    let filtered = currentQuotes;
    if (activeFilter !== 'ALL') {
        filtered = currentQuotes.filter(q => q.status === activeFilter);
    }

    if (filtered.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="9" style="text-align: center; color: #94A3B8; padding: 24px;">
                    <i class="fa-regular fa-folder-open" style="font-size: 28px; margin-bottom: 8px; display:block;"></i>
                    Chưa có dữ liệu báo giá nào trong mục này.
                </td>
            </tr>
        `;
        return;
    }

    tbody.innerHTML = filtered.map(quote => {
        let statusBadge = '';
        if (quote.status === 'PENDING_APPROVAL') {
            statusBadge = '<span class="status-pill status-pending"><i class="fa-solid fa-clock"></i> Chờ TP Duyệt</span>';
        } else if (quote.status === 'PENDING_DIRECTOR_APPROVAL') {
            statusBadge = '<span class="status-pill" style="background:#FEF3C7; color:#B45309; border:1px solid #FCD34D;"><i class="fa-solid fa-shield-halved"></i> Chờ GĐ Duyệt</span>';
        } else if (quote.status === 'APPROVED') {
            statusBadge = '<span class="status-pill status-approved"><i class="fa-solid fa-circle-check"></i> Đã Duyệt</span>';
        } else if (quote.status === 'SENT_TO_CUSTOMER') {
            statusBadge = '<span class="status-pill status-sent"><i class="fa-solid fa-paper-plane"></i> Đã Gửi Khách</span>';
        } else {
            statusBadge = '<span class="status-pill status-rejected"><i class="fa-solid fa-circle-xmark"></i> Từ Chối</span>';
        }

        const langTag = (quote.language || 'vi').toUpperCase();
        const langFlag = quote.language === 'en' ? '🇬🇧' : (quote.language === 'zh' ? '🇨🇳' : (quote.language === 'ko' ? '🇰🇷' : '🇻🇳'));
        const versionBadge = `<span style="font-size:10px; background:#1B2234; color:#FFFFFF; border-radius:4px; padding:1px 5px; margin-left:4px; font-weight:700; font-family:'JetBrains Mono', monospace;">v${quote.version || 1}</span>`;

        return `
            <tr>
                <td>
                    <b>${quote.quote_code}</b>
                    ${versionBadge}
                    <span style="font-size:10px; background:#F1F5F9; border:1px solid #CBD5E1; padding:1px 5px; border-radius:4px; margin-left:4px;">${langFlag} ${langTag}</span>
                    <br><small style="color:#64748B;">${quote.items.length} mục thiết bị</small>
                </td>
                <td>
                    <b>${quote.customer_name}</b>
                    <br><small style="color:#64748B;">${quote.project_name}</small>
                </td>
                <td>
                    <span style="font-size:11px; background:#FFF7ED; color:#C2410C; border:1px solid #FDBA74; padding:2px 6px; border-radius:4px; font-weight:600;">
                        <i class="fa-solid fa-file-excel"></i> ${quote.template_name ? quote.template_name.slice(0, 20) + '...' : 'Mẫu Chuẩn'}
                    </span>
                </td>
                <td><small>${quote.created_at ? quote.created_at.slice(0, 16) : '---'}</small></td>
                <td>${quote.subtotal.toLocaleString('vi-VN')} đ</td>
                <td>
                    <span style="color:#16A34A; font-size:11px;">-${quote.discount_amount.toLocaleString('vi-VN')} đ (${(quote.discount_rate*100).toFixed(0)}%)</span><br>
                    <span style="color:#0284C7; font-size:11px;">+${quote.vat_amount.toLocaleString('vi-VN')} đ (${(quote.vat_rate*100).toFixed(0)}%)</span>
                </td>
                <td class="price-val">${quote.total_amount.toLocaleString('vi-VN')} đ</td>
                <td>${statusBadge}</td>
                <td>
                    <div class="table-actions">
                        <button class="btn-icon" title="Xem Chi Tiết & Lịch Sử Phiên Bản" onclick="viewQuoteDetail('${quote.id}')">
                            <i class="fa-regular fa-eye"></i>
                        </button>
                        <a href="/api/quotes/${quote.id}/download" class="btn-icon" title="Tải File Excel Chuẩn Vertex" target="_blank">
                            <i class="fa-solid fa-file-excel" style="color:#10B981;"></i>
                        </a>
                        <button class="btn-icon" title="Mô phỏng Duyệt Zalo OA" onclick="simulateZaloQuote('${quote.id}')">
                            <i class="fa-brands fa-whatsapp" style="color:#0068FF;"></i>
                        </button>
                    </div>
                </td>
            </tr>
        `;
    }).join('');
}

function updateStats() {
    const totalEl = document.getElementById('stat-total');
    const pendingEl = document.getElementById('stat-pending');
    const approvedEl = document.getElementById('stat-approved');

    if (totalEl) totalEl.textContent = currentQuotes.length;
    if (pendingEl) pendingEl.textContent = currentQuotes.filter(q => q.status === 'PENDING_APPROVAL' || q.status === 'PENDING_DIRECTOR_APPROVAL').length;
    if (approvedEl) approvedEl.textContent = currentQuotes.filter(q => q.status === 'APPROVED' || q.status === 'SENT_TO_CUSTOMER').length;
}

function filterQuotes(status) {
    activeFilter = status;
    document.querySelectorAll('.btn-filter').forEach(btn => {
        btn.classList.remove('active');
        if (btn.textContent.includes(status) || (status === 'ALL' && btn.textContent.includes('Tất Cả'))) {
            btn.classList.add('active');
        }
    });
    renderQuotesTable();
}

// ----------------------------------------------------
// 5. Zalo OA Simulator Interaction
// ----------------------------------------------------
function renderZaloSimulator(quote) {
    currentSimulationQuote = quote;
    const bubble = document.getElementById('zalo-bubble');
    if (!bubble) return;

    let statusText = 'Đang Chờ Quản Lý Duyệt';
    let statusColor = '#D97706';
    if (quote.status === 'PENDING_DIRECTOR_APPROVAL') {
        statusText = 'Trưởng Phòng Đã Thông Qua - Chờ Sếp Tiến Duyệt';
        statusColor = '#B45309';
    } else if (quote.status === 'APPROVED' || quote.status === 'SENT_TO_CUSTOMER') {
        statusText = 'Đã Phê Duyệt Chính Thức';
        statusColor = '#10B981';
    } else if (quote.status === 'REJECTED') {
        statusText = 'Đã Từ Chối Báo Giá';
        statusColor = '#EF4444';
    }

    const isHighValue = (quote.total_amount >= 100000000 || quote.discount_rate > 0.05);
    const approvalLevelBadge = isHighValue 
        ? `<span style="background:#FEF3C7; color:#92400E; border:1px solid #FCD34D; font-size:10.5px; padding:2px 6px; border-radius:4px; font-weight:700;"><i class="fa-solid fa-shield-halved"></i> Cấp Duyệt: Giám Đốc (Hạn Mức &gt;100Tr)</span>`
        : `<span style="background:#EFF6FF; color:#1E40AF; border:1px solid #BFDBFE; font-size:10.5px; padding:2px 6px; border-radius:4px; font-weight:700;"><i class="fa-solid fa-user-check"></i> Cấp Duyệt: Trưởng Phòng KD</span>`;

    bubble.innerHTML = `
        <div class="zalo-card-container">
            <div class="zalo-card-header">
                <h4><i class="fa-solid fa-shield-halved" style="color:#FF6B35;"></i> YÊU CẦU PHÊ DUYỆT BÁO GIÁ (v${quote.version || 1})</h4>
                <p>Mã: <b>${quote.quote_code}</b> • ${quote.created_at ? quote.created_at.slice(0, 16) : ''}</p>
                <div style="margin-top: 4px;">${approvalLevelBadge}</div>
            </div>
            <div class="zalo-card-body">
                <div class="zalo-detail-row">
                    <span style="color:#64748B;">Khách hàng:</span>
                    <b>${quote.customer_name}</b>
                </div>
                <div class="zalo-detail-row">
                    <span style="color:#64748B;">Dự án / Công trình:</span>
                    <span>${quote.project_name}</span>
                </div>
                <div class="zalo-detail-row">
                    <span style="color:#64748B;">Mẫu áp dụng:</span>
                    <span style="color:#EA580C; font-weight:600;">${quote.template_name || 'Mẫu Chuẩn Vertex'}</span>
                </div>
                <div class="zalo-detail-row">
                    <span style="color:#64748B;">Hạng mục thiết bị:</span>
                    <span>${quote.items.length} danh mục</span>
                </div>
                <div class="zalo-detail-row">
                    <span style="color:#64748B;">Tổng tiền hàng:</span>
                    <span>${quote.subtotal.toLocaleString('vi-VN')} đ</span>
                </div>
                <div class="zalo-detail-row">
                    <span style="color:#64748B;">Chiết khấu (${(quote.discount_rate * 100).toFixed(0)}%):</span>
                    <span style="color:#16A34A;">-${quote.discount_amount.toLocaleString('vi-VN')} đ</span>
                </div>
                <div class="zalo-detail-row">
                    <span style="color:#64748B;">Thuế VAT (${(quote.vat_rate * 100).toFixed(0)}%):</span>
                    <span>+${quote.vat_amount.toLocaleString('vi-VN')} đ</span>
                </div>
                <div class="zalo-detail-row">
                    <span>TỔNG THANH TOÁN:</span>
                    <span>${quote.total_amount.toLocaleString('vi-VN')} VNĐ</span>
                </div>
            </div>
            <div class="zalo-card-actions">
                ${quote.status === 'PENDING_APPROVAL' ? `
                    <button class="btn-zalo-approve" onclick="handleZaloAction('${quote.id}', 'approve', 'MANAGER')">
                        <i class="fa-solid fa-circle-check"></i> ✅ ANH VIỆT DUYỆT (TRƯỞNG PHÒNG)
                    </button>
                    <button class="btn-zalo-approve" style="background:#1B2234;" onclick="handleZaloAction('${quote.id}', 'approve', 'ADMIN')">
                        <i class="fa-solid fa-crown"></i> 👑 SẾP TIẾN DUYỆT (GIÁM ĐỐC)
                    </button>
                    <button class="btn-zalo-reject" onclick="handleZaloAction('${quote.id}', 'reject', 'MANAGER')">
                        <i class="fa-solid fa-circle-xmark"></i> ❌ TỪ CHỐI YÊU CẦU
                    </button>
                ` : (quote.status === 'PENDING_DIRECTOR_APPROVAL' ? `
                    <div style="background:#FEF3C7; padding:8px; border-radius:6px; font-size:11.5px; color:#92400E; margin-bottom:6px; text-align:center;">
                        <i class="fa-solid fa-info-circle"></i> Trưởng phòng KD đã thông qua. Đang chờ Giám đốc (Sếp Tiến) phê duyệt hạn mức.
                    </div>
                    <button class="btn-zalo-approve" style="background:#1B2234;" onclick="handleZaloAction('${quote.id}', 'approve', 'ADMIN')">
                        <i class="fa-solid fa-crown"></i> 👑 SẾP TIẾN DUYỆT BƯỚC CUỐI
                    </button>
                    <button class="btn-zalo-reject" onclick="handleZaloAction('${quote.id}', 'reject', 'ADMIN')">
                        <i class="fa-solid fa-circle-xmark"></i> ❌ TỪ CHỐI YÊU CẦU
                    </button>
                ` : `
                    <div style="text-align:center; padding: 6px; font-size:12px; font-weight:700; color:${statusColor};">
                        Đã xử lý bởi ${quote.approved_by || 'Quản lý'} (${statusText})
                    </div>
                `)}
                <a href="/api/quotes/${quote.id}/download" class="btn-zalo-download" target="_blank">
                    <i class="fa-solid fa-file-excel" style="color:#10B981;"></i> Tải File Excel Báo Giá
                </a>
            </div>
        </div>
    `;
}

function simulateZaloQuote(quoteId) {
    const q = currentQuotes.find(item => item.id === quoteId);
    if (q) {
        renderZaloSimulator(q);
        document.querySelector('.zalo-simulator-card').scrollIntoView({ behavior: 'smooth' });
    }
}

async function handleZaloAction(quoteId, action, role = 'MANAGER') {
    const managerName = role === 'ADMIN' ? "Sếp Tiến (Tổng Giám Đốc)" : "Anh Việt (Trưởng phòng KD PCCC)";
    showToast(`Đang xử lý ${action === 'approve' ? 'Duyệt' : 'Từ chối'} bởi ${managerName}...`);
    try {
        const resp = await fetch('/api/zalo/simulate-approval', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                quote_id: quoteId,
                action: action,
                manager_name: managerName,
                manager_role: role
            })
        });

        const data = await resp.json();
        if (!resp.ok) throw new Error(data.detail || 'Lỗi duyệt');

        showToast(data.message || 'Thao tác thành công!');
        await loadQuotesList();
        
        const updatedQuote = currentQuotes.find(q => q.id === quoteId);
        if (updatedQuote) renderZaloSimulator(updatedQuote);

    } catch (e) {
        showToast(`Lỗi: ${e.message}`);
    }
}

// ----------------------------------------------------
// 6. Quote Details Modal: Tabs, Version Control & Audit Trail
// ----------------------------------------------------
async function viewQuoteDetail(quoteId) {
    currentActiveModalQuoteId = quoteId;
    currentQuoteModalTab = 'items';
    
    // Reset active tab button
    document.querySelectorAll('.btn-modal-tab').forEach(b => b.classList.remove('active'));
    const itemsBtn = document.getElementById('modal-tab-items-btn');
    if (itemsBtn) itemsBtn.classList.add('active');

    const quote = currentQuotes.find(q => q.id === quoteId);
    if (!quote) return;

    document.getElementById('modal-title').innerHTML = `
        <i class="fa-solid fa-file-lines" style="color:var(--vertex-orange-main);"></i> 
        Báo Giá: <b>${quote.quote_code}</b> <span class="version-badge-lg">v${quote.version || 1}</span> - ${quote.customer_name}
    `;

    renderQuoteItemsTab(quote);
    document.getElementById('quote-modal').style.display = 'flex';

    // Prefetch version count for badge
    try {
        const vResp = await fetch(`/api/quotes/${quoteId}/versions`);
        if (vResp.ok) {
            const versions = await vResp.json();
            const countEl = document.getElementById('modal-version-count');
            if (countEl) countEl.textContent = versions.length || 1;
        }
    } catch(e) {}
}

function switchQuoteModalTab(tabName) {
    currentQuoteModalTab = tabName;
    document.querySelectorAll('.btn-modal-tab').forEach(b => b.classList.remove('active'));
    const btn = document.getElementById(`modal-tab-${tabName}-btn`);
    if (btn) btn.classList.add('active');

    const quote = currentQuotes.find(q => q.id === currentActiveModalQuoteId);
    if (!quote) return;

    if (tabName === 'items') {
        renderQuoteItemsTab(quote);
    } else if (tabName === 'versions') {
        renderQuoteVersionsTab(quote);
    } else if (tabName === 'audit') {
        renderQuoteAuditTab(quote);
    }
}

function renderQuoteItemsTab(quote) {
    let itemsTableRows = quote.items.map(it => {
        let sourceBadge = '';
        if (it.price_source === 'AI_MARKET_ESTIMATE') {
            sourceBadge = `<span style="background:#FFFBEB; color:#B45309; border:1px solid #FCD34D; font-size:10px; padding:2px 5px; border-radius:4px; font-weight:700; display:inline-block; margin-top:3px;"><i class="fa-solid fa-brain"></i> AI Tra Thị Trường</span>`;
        } else {
            sourceBadge = `<span style="background:#ECFDF5; color:#047857; border:1px solid #6EE7B7; font-size:10px; padding:2px 5px; border-radius:4px; font-weight:700; display:inline-block; margin-top:3px;"><i class="fa-solid fa-tag"></i> Catalog Chuẩn</span>`;
        }

        return `
            <tr>
                <td style="text-align:center;">${it.stt}</td>
                <td><code>${it.item_code}</code><br>${sourceBadge}</td>
                <td><b>${it.item_name}</b><br><small style="color:#64748B;">${it.spec || ''}</small></td>
                <td style="text-align:center;"><span class="unit-tag">${it.unit}</span></td>
                <td style="text-align:right;">${(it.area_m2 > 0 ? it.area_m2 : it.quantity).toLocaleString('vi-VN')}</td>
                <td style="text-align:right;">${it.unit_price.toLocaleString('vi-VN')} đ</td>
                <td class="price-val">${it.total_price.toLocaleString('vi-VN')} đ</td>
                <td><small style="font-size:11px;">${it.notes || ''}</small></td>
            </tr>
        `;
    }).join('');

    document.getElementById('modal-content').innerHTML = `
        <div style="display:grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 16px; background:#F8FAFC; padding:14px; border-radius:10px; border:1px solid #E2E8F0; font-size:13px;">
            <div>
                <div><b>Khách hàng:</b> ${quote.customer_name}</div>
                <div><b>Số điện thoại:</b> ${quote.customer_phone || '---'}</div>
                <div><b>Dự án:</b> ${quote.project_name}</div>
                <div><b>Địa chỉ:</b> ${quote.project_address || '---'}</div>
            </div>
            <div>
                <div><b>Mã báo giá:</b> ${quote.quote_code} <span class="version-badge-lg">v${quote.version || 1}</span></div>
                <div><b>Mẫu định mức:</b> <span style="color:#EA580C; font-weight:700;">${quote.template_name || 'Mẫu Chuẩn Vertex'}</span></div>
                <div><b>Trạng thái:</b> <b>${quote.status}</b> (${quote.required_approval_level === 'DIRECTOR' ? 'Cần Giám Đốc Duyệt' : 'Trưởng Phòng Duyệt'})</div>
                <div><b>File nguồn:</b> ${quote.input_file_name}</div>
            </div>
        </div>

        <h4 style="margin-bottom: 8px; font-size:13.5px;"><i class="fa-solid fa-list"></i> Bảng Danh Mục Vật Tư & Thiết Bị PCCC Bóc Tách:</h4>
        <div class="table-responsive" style="max-height: 280px; overflow-y:auto; margin-bottom: 16px;">
            <table class="data-table">
                <thead>
                    <tr>
                        <th style="width:35px;">STT</th>
                        <th>Mã & Nguồn</th>
                        <th>Tên Thiết Bị / Vật Tư & Quy Cách</th>
                        <th>ĐVT</th>
                        <th>Khối Lượng</th>
                        <th>Đơn Giá</th>
                        <th>Thành Tiền</th>
                        <th>Ghi Chú Nguồn Giá</th>
                    </tr>
                </thead>
                <tbody>
                    ${itemsTableRows}
                </tbody>
            </table>
        </div>

        <div style="background:#F8FAFC; border:1px solid #E2E8F0; border-radius:10px; padding:14px; font-size:13px;">
            <div style="display:flex; justify-content:space-between; margin-bottom: 5px;">
                <span>Tổng tiền hàng:</span>
                <b>${quote.subtotal.toLocaleString('vi-VN')} đ</b>
            </div>
            <div style="display:flex; justify-content:space-between; margin-bottom: 5px; color:#16A34A;">
                <span>Chiết khấu (${(quote.discount_rate*100).toFixed(0)}%):</span>
                <b>-${quote.discount_amount.toLocaleString('vi-VN')} đ</b>
            </div>
            <div style="display:flex; justify-content:space-between; margin-bottom: 5px; color:#0284C7;">
                <span>Thuế GTGT VAT (${(quote.vat_rate*100).toFixed(0)}%):</span>
                <b>+${quote.vat_amount.toLocaleString('vi-VN')} đ</b>
            </div>
            <div style="display:flex; justify-content:space-between; padding-top: 8px; border-top: 2px solid #CBD5E1; font-size: 15px; color:#1B2234; font-weight:800;">
                <span>TỔNG THANH TOÁN:</span>
                <span style="color:#FF6B35;">${quote.total_amount.toLocaleString('vi-VN')} VNĐ</span>
            </div>
            <div style="margin-top: 6px; font-style: italic; color:#475569;">
                Số tiền bằng chữ: <b>${quote.total_amount_in_words}</b>
            </div>
        </div>
    `;

    document.getElementById('modal-footer').innerHTML = `
        <a href="/api/quotes/${quote.id}/download" class="btn btn-primary" target="_blank">
            <i class="fa-solid fa-file-excel"></i> Tải File Excel Báo Giá
        </a>
        <button class="btn btn-outline-dark" onclick="closeQuoteModal()">Đóng</button>
    `;
}

async function renderQuoteVersionsTab(quote) {
    const modalContent = document.getElementById('modal-content');
    modalContent.innerHTML = `<div style="text-align:center; padding:30px;"><i class="fa-solid fa-spinner fa-spin" style="font-size:24px; color:var(--vertex-orange-main);"></i><br><br>Đang tải danh sách các phiên bản...</div>`;

    try {
        const resp = await fetch(`/api/quotes/${quote.id}/versions`);
        const versions = await resp.json();

        let versionsHtml = versions.map(v => {
            const isCurrent = (v.id === quote.id);
            return `
                <div class="version-card ${isCurrent ? 'current' : ''}">
                    <div style="display:flex; align-items:center; gap:12px;">
                        <span class="version-badge-lg">v${v.version || 1}</span>
                        <div>
                            <div style="font-weight:700; color:#1E293B; font-size:13.5px;">
                                ${v.quote_code} ${isCurrent ? '<span style="color:#FF6B35; font-size:11px; font-weight:700;">(Đang xem)</span>' : ''}
                            </div>
                            <div style="font-size:11.5px; color:#64748B;">
                                Tạo lúc: ${v.created_at} • Ghi chú: <i>${v.revision_note || 'Bản gốc'}</i>
                            </div>
                        </div>
                    </div>
                    <div style="display:flex; align-items:center; gap:16px;">
                        <div style="text-align:right;">
                            <div style="font-size:14px; font-weight:800; color:var(--vertex-navy-main);">${v.total_amount.toLocaleString('vi-VN')} đ</div>
                            <small style="color:#64748B;">CK: ${(v.discount_rate*100).toFixed(0)}% | VAT: ${(v.vat_rate*100).toFixed(0)}%</small>
                        </div>
                        ${!isCurrent ? `
                            <button class="btn btn-outline-dark" style="font-size:11px; padding:5px 10px;" onclick="viewQuoteDetail('${v.id}')">
                                Xem Bản Này
                            </button>
                        ` : `
                            <a href="/api/quotes/${v.id}/download" class="btn btn-primary" style="font-size:11px; padding:5px 10px;" target="_blank">
                                <i class="fa-solid fa-download"></i> Excel
                            </a>
                        `}
                    </div>
                </div>
            `;
        }).join('');

        modalContent.innerHTML = `
            <div style="margin-bottom:16px;">
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:10px;">
                    <h4 style="margin:0; font-size:14px;"><i class="fa-solid fa-code-branch" style="color:var(--vertex-orange-main);"></i> Cây Phả Hệ Phiên Bản Báo Giá (${versions.length} phiên bản)</h4>
                </div>
                ${versionsHtml}
            </div>

            <!-- Form Tạo Phiên Bản Mới (Revision Form) -->
            <div style="background:#F8FAFC; border:1px dashed #CBD5E1; border-radius:8px; padding:16px; margin-top:16px;">
                <h4 style="margin:0 0 10px 0; font-size:13.5px; color:#1E293B;">
                    <i class="fa-solid fa-plus-circle" style="color:#FF6B35;"></i> Tạo Phiên Bản Điều Chỉnh Mới (Revision v${(quote.version || 1) + 1})
                </h4>
                <div style="display:grid; grid-template-columns: 1fr 1fr 2fr; gap:12px; margin-bottom:12px;">
                    <div class="form-group" style="margin:0;">
                        <label style="font-size:11px; font-weight:700;">Chiết Khấu Mới (%)</label>
                        <input type="number" id="rev-discount" value="${(quote.discount_rate * 100).toFixed(0)}" min="0" max="50" step="1" style="padding:6px 10px; font-size:12.5px; border:1px solid #CBD5E1; border-radius:4px; width:100%;">
                    </div>
                    <div class="form-group" style="margin:0;">
                        <label style="font-size:11px; font-weight:700;">VAT (%)</label>
                        <input type="number" id="rev-vat" value="${(quote.vat_rate * 100).toFixed(0)}" min="0" max="20" step="1" style="padding:6px 10px; font-size:12.5px; border:1px solid #CBD5E1; border-radius:4px; width:100%;">
                    </div>
                    <div class="form-group" style="margin:0;">
                        <label style="font-size:11px; font-weight:700;">Lý Do / Ghi Chú Điều Chỉnh</label>
                        <input type="text" id="rev-notes" placeholder="VD: Tăng chiết khấu theo yêu cầu Sếp Tiến, điều chỉnh khối lượng..." style="padding:6px 10px; font-size:12.5px; border:1px solid #CBD5E1; border-radius:4px; width:100%;">
                    </div>
                </div>
                <div style="display:flex; justify-content:flex-end;">
                    <button type="button" class="btn btn-primary" onclick="submitCreateRevision('${quote.id}')" style="font-size:12px; padding:7px 14px;">
                        <i class="fa-solid fa-bolt"></i> Tạo Phiên Bản v${(quote.version || 1) + 1}
                    </button>
                </div>
            </div>
        `;
    } catch (e) {
        modalContent.innerHTML = `<div style="color:red; padding:20px;">Lỗi tải phiên bản: ${e.message}</div>`;
    }
}

async function submitCreateRevision(quoteId) {
    const discInput = document.getElementById('rev-discount');
    const vatInput = document.getElementById('rev-vat');
    const noteInput = document.getElementById('rev-notes');

    const disc = discInput ? parseFloat(discInput.value) / 100.0 : null;
    const vat = vatInput ? parseFloat(vatInput.value) / 100.0 : null;
    const note = noteInput ? noteInput.value.trim() : "Điều chỉnh phiên bản";

    showToast("Đang khởi tạo phiên bản mới...");
    try {
        const resp = await fetch(`/api/quotes/${quoteId}/revision`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                revision_note: note,
                discount_rate: disc,
                vat_rate: vat
            })
        });

        const newQuote = await resp.json();
        if (!resp.ok) throw new Error(newQuote.detail || 'Lỗi tạo revision');

        showToast(`Đã tạo thành công phiên bản ${newQuote.quote_code}!`);
        await loadQuotesList();
        await viewQuoteDetail(newQuote.id);
    } catch(e) {
        showToast(`Lỗi: ${e.message}`);
    }
}

async function renderQuoteAuditTab(quote) {
    const modalContent = document.getElementById('modal-content');
    modalContent.innerHTML = `<div style="text-align:center; padding:30px;"><i class="fa-solid fa-spinner fa-spin" style="font-size:24px; color:var(--vertex-orange-main);"></i><br><br>Đang tải nhật ký kiểm toán...</div>`;

    try {
        const resp = await fetch(`/api/quotes/${quote.id}/audit-logs`);
        const logs = await resp.json();

        if (!logs || logs.length === 0) {
            modalContent.innerHTML = `<div style="text-align:center; padding:20px; color:#94A3B8;">Chưa có bản ghi nhật ký kiểm toán nào cho báo giá này.</div>`;
            return;
        }

        const timelineItems = logs.map(l => {
            let dotClass = 'info';
            let iconClass = 'fa-solid fa-file-circle-check';
            if (l.action.includes('APPROVE')) {
                dotClass = 'success';
                iconClass = 'fa-solid fa-circle-check';
            } else if (l.action.includes('REJECT')) {
                dotClass = 'danger';
                iconClass = 'fa-solid fa-circle-xmark';
            } else if (l.action.includes('EXPORT')) {
                dotClass = 'info';
                iconClass = 'fa-solid fa-file-excel';
            } else if (l.action.includes('REVISION')) {
                dotClass = '';
                iconClass = 'fa-solid fa-code-branch';
            }

            return `
                <div class="timeline-item">
                    <div class="timeline-dot ${dotClass}">
                        <i class="${iconClass}"></i>
                    </div>
                    <div class="timeline-content">
                        <div class="timeline-header">
                            <div class="timeline-title">
                                <span>${l.action}</span>
                                <span class="unit-tag" style="background:#F1F5F9; color:#475569; font-size:10px; padding:1px 5px;">${l.user_role}</span>
                            </div>
                            <div class="timeline-time">${l.timestamp}</div>
                        </div>
                        <div class="timeline-details">${l.details}</div>
                        <div class="timeline-meta">
                            <span><i class="fa-solid fa-user"></i> <b>${l.user_name}</b></span>
                            ${l.ip_address ? `<span><i class="fa-solid fa-network-wired"></i> IP: <code>${l.ip_address}</code></span>` : ''}
                        </div>
                    </div>
                </div>
            `;
        }).join('');

        modalContent.innerHTML = `
            <div style="margin-bottom:12px;">
                <h4 style="margin:0 0 6px 0; font-size:14px;"><i class="fa-solid fa-clock-rotate-left" style="color:var(--vertex-orange-main);"></i> Dòng Thời Gian Nhật Ký Kiểm Toán (Immutable Audit Trail)</h4>
                <p style="font-size:12px; color:#64748B; margin:0 0 14px 0;">Ghi lại minh bạch và chi tiết mọi hành vi khởi tạo, chỉnh sửa, thẩm định và phê duyệt trên báo giá.</p>
                <div class="audit-timeline">
                    ${timelineItems}
                </div>
            </div>
        `;
    } catch(e) {
        modalContent.innerHTML = `<div style="color:red; padding:20px;">Lỗi tải Audit Trail: ${e.message}</div>`;
    }
}

function closeQuoteModal() {
    document.getElementById('quote-modal').style.display = 'none';
}


// ----------------------------------------------------
// 7. Master Template & Pricing Coefficients Modal
// ----------------------------------------------------
function openMasterTemplateModal() {
    const modal = document.getElementById('template-mgmt-modal');
    if (modal) {
        modal.style.display = 'flex';
        calculateLiveMultiplier();
    }
}

function closeMasterTemplateModal() {
    const modal = document.getElementById('template-mgmt-modal');
    if (modal) modal.style.display = 'none';
}

function calculateLiveMultiplier() {
    const waste = parseFloat(document.getElementById('coeff_waste')?.value || 5) / 100.0;
    const transport = parseFloat(document.getElementById('coeff_transport')?.value || 3) / 100.0;
    const labor = parseFloat(document.getElementById('coeff_labor')?.value || 15) / 100.0;
    const margin = parseFloat(document.getElementById('coeff_margin')?.value || 12) / 100.0;

    const mult = 1.0 + waste + transport + labor + margin;
    const markupPct = (mult - 1.0) * 100.0;

    const preview = document.getElementById('coeff_multiplier_preview');
    if (preview) {
        preview.textContent = `${mult.toFixed(2)}x (+${markupPct.toFixed(1)}%)`;
    }
}

async function saveTemplateCoefficients() {
    const waste = parseFloat(document.getElementById('coeff_waste')?.value || 5) / 100.0;
    const transport = parseFloat(document.getElementById('coeff_transport')?.value || 3) / 100.0;
    const labor = parseFloat(document.getElementById('coeff_labor')?.value || 15) / 100.0;
    const margin = parseFloat(document.getElementById('coeff_margin')?.value || 12) / 100.0;

    const templateId = window.ACTIVE_TEMPLATE_ID || 'tpl-vertex-master-default';
    showToast('Đang lưu khung hệ số định mức chi phí...');

    try {
        const resp = await fetch(`/api/templates/${templateId}/coefficients`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                waste_ratio: waste,
                transport_ratio: transport,
                labor_ratio: labor,
                margin_ratio: margin
            })
        });

        const data = await resp.json();
        if (!resp.ok) throw new Error(data.detail || 'Lỗi lưu hệ số');

        showToast('Đã lưu khung hệ số định mức thành công!');
        closeMasterTemplateModal();
    } catch (e) {
        showToast(`Lỗi: ${e.message}`);
    }
}

async function handleUploadNewTemplate(e) {
    e.preventDefault();
    const fileInput = document.getElementById('tpl-file-input');
    const nameInput = document.getElementById('tpl-name-input');

    if (!fileInput.files || fileInput.files.length === 0) {
        showToast('Vui lòng chọn file Excel template (.xlsx)!');
        return;
    }

    const formData = new FormData();
    formData.append('file', fileInput.files[0]);
    formData.append('name', nameInput.value || 'Mẫu Chuẩn Vertex');
    formData.append('waste_ratio', parseFloat(document.getElementById('coeff_waste')?.value || 5) / 100.0);
    formData.append('transport_ratio', parseFloat(document.getElementById('coeff_transport')?.value || 3) / 100.0);
    formData.append('labor_ratio', parseFloat(document.getElementById('coeff_labor')?.value || 15) / 100.0);
    formData.append('margin_ratio', parseFloat(document.getElementById('coeff_margin')?.value || 12) / 100.0);

    showToast('Đang tải lên và phân tích file mẫu chuẩn...');
    try {
        const resp = await fetch('/api/templates/upload', {
            method: 'POST',
            body: formData
        });
        const data = await resp.json();
        if (!resp.ok) throw new Error(data.detail || 'Lỗi tải lên mẫu');

        showToast(`Đã lưu file mẫu chuẩn '${data.name}' thành công!`);
        window.location.reload();
    } catch (err) {
        showToast(`Lỗi: ${err.message}`);
    }
}

function toggleTemplateUploadBox() {
    const container = document.getElementById('template-upload-container');
    const toggleLabel = document.getElementById('toggle-tpl-label');
    if (!container) return;
    if (container.style.display === 'none' || getComputedStyle(container).display === 'none') {
        container.style.display = 'block';
        if (toggleLabel) toggleLabel.textContent = 'Thu Gọn Khung Tải Mẫu';
    } else {
        container.style.display = 'none';
        if (toggleLabel) toggleLabel.textContent = 'Tải Lên Mẫu Mới (.xlsx, .pdf, .csv)';
    }
}

async function handleDirectTemplateUpload(file) {
    if (!file) return;

    const allowedExtensions = ['.xlsx', '.xls', '.pdf', '.csv'];
    const fileName = file.name.toLowerCase();
    const isAllowed = allowedExtensions.some(ext => fileName.endsWith(ext));

    if (!isAllowed) {
        showToast('Vui lòng chọn file mẫu định dạng .xlsx, .xls, .pdf hoặc .csv!');
        return;
    }

    const uploadingBar = document.getElementById('template-uploading-bar');
    if (uploadingBar) uploadingBar.style.display = 'flex';

    showToast(`Đang tải lên và lưu file mẫu: ${file.name}...`);

    const formData = new FormData();
    formData.append('file', file);
    formData.append('name', `Mẫu Chuẩn - ${file.name}`);
    formData.append('waste_ratio', parseFloat(document.getElementById('coeff_waste')?.value || 5) / 100.0);
    formData.append('transport_ratio', parseFloat(document.getElementById('coeff_transport')?.value || 3) / 100.0);
    formData.append('labor_ratio', parseFloat(document.getElementById('coeff_labor')?.value || 15) / 100.0);
    formData.append('margin_ratio', parseFloat(document.getElementById('coeff_margin')?.value || 12) / 100.0);
    formData.append('set_active', 'true');

    try {
        const resp = await fetch('/api/templates/upload', {
            method: 'POST',
            body: formData
        });
        const data = await resp.json();
        if (!resp.ok) throw new Error(data.detail || 'Lỗi khi tải file mẫu');

        // Update select dropdown immediately
        const tplSelect = document.getElementById('template_id');
        if (tplSelect) {
            let option = tplSelect.querySelector(`option[value="${data.id}"]`);
            if (!option) {
                option = document.createElement('option');
                option.value = data.id;
                tplSelect.insertBefore(option, tplSelect.firstChild);
            }
            const wastePct = Math.round((data.waste_ratio || 0.05) * 100);
            const transportPct = Math.round((data.transport_ratio || 0.03) * 100);
            const laborPct = Math.round((data.labor_ratio || 0.15) * 100);
            const marginPct = Math.round((data.margin_ratio || 0.12) * 100);
            option.textContent = `★ ${data.name} (Hao hụt: ${wastePct}%, Vận chuyển: ${transportPct}%, NC: ${laborPct}%, Lợi nhuận: ${marginPct}%)`;
            option.selected = true;
            tplSelect.value = data.id;
        }

        showToast(`Đã tải lên và kích hoạt Mẫu Chuẩn: '${data.name}' làm xương sống định mức!`);
        
        // Reset file input
        const fileInput = document.getElementById('direct-template-file');
        if (fileInput) fileInput.value = '';
    } catch (err) {
        showToast(`Lỗi: ${err.message}`);
    } finally {
        if (uploadingBar) uploadingBar.style.display = 'none';
    }
}

// ----------------------------------------------------
// 8. Catalog Search & Google Drive
// ----------------------------------------------------
function initCatalogSearch() {
    const searchInput = document.getElementById('catalog-search');
    if (!searchInput) return;

    searchInput.addEventListener('input', (e) => {
        const query = e.target.value.toLowerCase();
        const rows = document.querySelectorAll('#catalog-table tbody tr');
        rows.forEach(row => {
            const text = row.textContent.toLowerCase();
            row.style.display = text.includes(query) ? '' : 'none';
        });
    });
}

// ----------------------------------------------------
// 9. Admin User Management Modal
// ----------------------------------------------------
async function openUserManagementModal() {
    const modal = document.getElementById('user-mgmt-modal');
    if (!modal) return;
    modal.style.display = 'flex';
    await loadUsersList();
}

function closeUserManagementModal() {
    const modal = document.getElementById('user-mgmt-modal');
    if (modal) modal.style.display = 'none';
}

async function loadUsersList() {
    const tbody = document.getElementById('users-tbody');
    if (!tbody) return;

    tbody.innerHTML = `<tr><td colspan="7" style="text-align:center; padding:20px;"><i class="fa-solid fa-spinner fa-spin"></i> Đang tải danh sách người dùng...</td></tr>`;

    try {
        const resp = await fetch('/api/users');
        if (!resp.ok) {
            tbody.innerHTML = `<tr><td colspan="7" style="text-align:center; color:#EF4444; padding:20px;">Bạn không có quyền truy cập trang quản trị này (Yêu cầu quyền Admin / Manager).</td></tr>`;
            return;
        }
        const users = await resp.json();
        if (users.length === 0) {
            tbody.innerHTML = `<tr><td colspan="7" style="text-align:center; padding:20px;">Chưa có tài khoản nào.</td></tr>`;
            return;
        }

        tbody.innerHTML = users.map((u, idx) => {
            const isSelf = (window.CURRENT_USER_ID && window.CURRENT_USER_ID === u.id);
            const statusBadge = u.status === 'ACTIVE' 
                ? '<span style="color:#10B981; font-weight:700;"><i class="fa-solid fa-circle-check"></i> Đang Hoạt Động</span>'
                : (u.status === 'PENDING_APPROVAL' 
                    ? '<span style="color:#F59E0B; font-weight:700;"><i class="fa-solid fa-clock"></i> Chờ Duyệt</span>' 
                    : '<span style="color:#EF4444; font-weight:700;"><i class="fa-solid fa-ban"></i> Đã Khóa</span>');

            return `
                <tr>
                    <td style="text-align:center;">${idx + 1}</td>
                    <td>
                        <b>${u.full_name}</b><br>
                        <code>@${u.username}</code>
                    </td>
                    <td>${u.company_name || 'Vertex PCCC'}</td>
                    <td>
                        <small>${u.phone || '---'}</small><br>
                        <small style="color:#64748B;">${u.email || '---'}</small>
                    </td>
                    <td>
                        <select onchange="changeUserRole('${u.id}', this.value)" style="padding:4px 6px; font-size:12px; border-radius:4px; border:1px solid #CBD5E1;" ${isSelf ? 'disabled' : ''}>
                            <option value="ADMIN" ${u.role === 'ADMIN' ? 'selected' : ''}>ADMIN (Sếp tổng)</option>
                            <option value="MANAGER" ${u.role === 'MANAGER' ? 'selected' : ''}>MANAGER (Quản lý)</option>
                            <option value="STAFF" ${u.role === 'STAFF' ? 'selected' : ''}>STAFF (Kỹ sư)</option>
                            <option value="DEALER" ${u.role === 'DEALER' ? 'selected' : ''}>DEALER (Đại lý PCCC)</option>
                            <option value="PARTNER" ${u.role === 'PARTNER' ? 'selected' : ''}>PARTNER (Nhà thầu)</option>
                        </select>
                    </td>
                    <td>${statusBadge}</td>
                    <td>
                        ${!isSelf ? `
                            ${u.status === 'ACTIVE' ? `
                                <button class="btn btn-outline-dark" style="padding:3px 8px; font-size:11px; color:#EF4444; border-color:#FCA5A5;" onclick="toggleUserStatus('${u.id}', 'DISABLED')">
                                    <i class="fa-solid fa-lock"></i> Khóa
                                </button>
                            ` : `
                                <button class="btn btn-outline-dark" style="padding:3px 8px; font-size:11px; color:#10B981; border-color:#86EFAC;" onclick="toggleUserStatus('${u.id}', 'ACTIVE')">
                                    <i class="fa-solid fa-check"></i> Kích hoạt
                                </button>
                            `}
                        ` : `<span style="font-size:11px; color:#94A3B8;">(Tài khoản hiện tại)</span>`}
                    </td>
                </tr>
            `;
        }).join('');

    } catch (e) {
        tbody.innerHTML = `<tr><td colspan="7" style="text-align:center; color:#EF4444; padding:20px;">Lỗi: ${e.message}</td></tr>`;
    }
}

async function toggleUserStatus(userId, newStatus) {
    try {
        const resp = await fetch(`/api/users/${userId}/status`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ status: newStatus })
        });
        const data = await resp.json();
        if (!resp.ok) throw new Error(data.detail || 'Lỗi cập nhật');
        showToast(data.message || 'Cập nhật trạng thái thành công!');
        await loadUsersList();
    } catch (e) {
        showToast(`Lỗi: ${e.message}`);
    }
}

async function changeUserRole(userId, newRole) {
    try {
        const resp = await fetch(`/api/users/${userId}/role`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ role: newRole })
        });
        const data = await resp.json();
        if (!resp.ok) throw new Error(data.detail || 'Lỗi cập nhật');
        showToast(data.message || 'Cập nhật quyền thành công!');
        await loadUsersList();
    } catch (e) {
        showToast(`Lỗi: ${e.message}`);
    }
}

// ----------------------------------------------------
// 10. User Guide Modal (Hướng Dẫn Sử Dụng 4 Bước)
// ----------------------------------------------------
function openUserGuideModal() {
    const modal = document.getElementById('user-guide-modal');
    if (modal) modal.style.display = 'flex';
}

function closeUserGuideModal() {
    const modal = document.getElementById('user-guide-modal');
    if (modal) modal.style.display = 'none';
}

// Toast
function showToast(msg) {
    const toast = document.getElementById('toast');
    if (!toast) return;
    toast.textContent = msg;
    toast.style.display = 'block';
    setTimeout(() => {
        toast.style.display = 'none';
    }, 3500);
}

// ----------------------------------------------------
// 11. Full-width PCCC & MEP Equipment Catalog Filter
// ----------------------------------------------------
let activeCatalogCategory = 'all';

function filterCatalogTable() {
    const searchVal = (document.getElementById('catalog-search')?.value || '').toLowerCase().trim();
    const rows = document.querySelectorAll('#catalog-tbody tr');
    
    rows.forEach(row => {
        const text = row.textContent.toLowerCase();
        const cat = (row.getAttribute('data-category') || '').toLowerCase();
        
        const matchSearch = !searchVal || text.includes(searchVal);
        const matchCat = (activeCatalogCategory === 'all') || cat.includes(activeCatalogCategory.toLowerCase());
        
        if (matchSearch && matchCat) {
            row.style.display = '';
        } else {
            row.style.display = 'none';
        }
    });
}

function setCatalogCategoryFilter(cat, btn) {
    activeCatalogCategory = cat;
    document.querySelectorAll('.catalog-filter-pills .btn-filter-pill').forEach(b => b.classList.remove('active'));
    if (btn) btn.classList.add('active');
    filterCatalogTable();
}

function initCatalogSearch() {
    filterCatalogTable();
}

// ----------------------------------------------------
// 12. Global Material Ripple & Micro-interactions
// ----------------------------------------------------
document.addEventListener('click', function (e) {
    const target = e.target.closest('.btn, .btn-icon, .tab-btn-pill, .btn-filter-pill, .btn-checkin-pulse, .sample-file-chip');
    if (!target) return;

    const circle = document.createElement('span');
    const diameter = Math.max(target.clientWidth, target.clientHeight);
    const radius = diameter / 2;

    const rect = target.getBoundingClientRect();
    circle.style.width = circle.style.height = `${diameter}px`;
    circle.style.left = `${e.clientX - rect.left - radius}px`;
    circle.style.top = `${e.clientY - rect.top - radius}px`;
    circle.classList.add('ripple');

    const existingRipple = target.querySelector('.ripple');
    if (existingRipple) {
        existingRipple.remove();
    }

    target.appendChild(circle);
    setTimeout(() => circle.remove(), 600);
});



