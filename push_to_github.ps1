# ==============================================================================
# Vertex Quote Automation System - PowerShell GitHub Push Automation
# ==============================================================================
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

Write-Host "==============================================================================" -ForegroundColor Cyan
Write-Host "       VERTEX QUOTE AUTOMATION SYSTEM - ONE-CLICK GITHUB PUSH" -ForegroundColor Yellow
Write-Host "==============================================================================" -ForegroundColor Cyan
Write-Host ""

$repoUrl = Read-Host ">> Nhập đường dẫn GitHub Repository URL (VD: https://github.com/username/vertex-quote-system.git)"

if ([string]::IsNullOrWhiteSpace($repoUrl)) {
    Write-Host ""
    Write-Host "[ERROR] Bạn chưa nhập đường dẫn GitHub URL. Vui lòng chạy lại script!" -ForegroundColor Red
    Read-Host "Bấm Enter để thoát"
    exit 1
}

Write-Host ""
Write-Host "[*] Đang cấu hình nhánh 'main'..." -ForegroundColor Gray
git branch -M main

Write-Host "[*] Đang liên kết Remote Origin tới: $repoUrl" -ForegroundColor Gray
git remote remove origin 2>$null
git remote add origin $repoUrl.Trim()

Write-Host ""
Write-Host "[*] Đang thực hiện 'git push -u origin main'..." -ForegroundColor Green
Write-Host "(Lưu ý: Nếu GitHub yêu cầu đăng nhập, hãy nhập Personal Access Token làm mật khẩu)" -ForegroundColor Yellow
Write-Host ""

git push -u origin main

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "==============================================================================" -ForegroundColor Green
    Write-Host "  [SUCCESS] ĐÃ PUSH MÃ NGUỒN LÊN GITHUB THÀNH CÔNG 100%!" -ForegroundColor Green
    Write-Host "  Anh Việt có thể gửi link Repository này cho Quản lý / Sếp Tiến kiểm tra." -ForegroundColor Cyan
    Write-Host "==============================================================================" -ForegroundColor Green
} else {
    Write-Host ""
    Write-Host "==============================================================================" -ForegroundColor Red
    Write-Host "  [!] Không thể push. Hãy kiểm tra kết nối mạng và Personal Access Token." -ForegroundColor Yellow
    Write-Host "  Tạo token mới tại: https://github.com/settings/tokens (chọn quyền 'repo')" -ForegroundColor Yellow
    Write-Host "==============================================================================" -ForegroundColor Red
}

Write-Host ""
Read-Host "Bấm Enter để đóng cửa sổ"
