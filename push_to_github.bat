@echo off
chcp 65001 >nul
title Vertex Quote System - Push to GitHub Automation

echo ==============================================================================
echo       VERTEX QUOTE AUTOMATION SYSTEM - ONE-CLICK GITHUB PUSH
echo ==============================================================================
echo.

set /p REPO_URL=">> Nhập đường dẫn GitHub Repository URL (VD: https://github.com/username/vertex-quote-system.git): "

if "%REPO_URL%"=="" (
    echo.
    echo [ERROR] Bạn chưa nhập đường dẫn GitHub URL. Vui lòng chạy lại script!
    pause
    exit /b 1
)

echo.
echo [*] Đang thiết lập nhánh main...
git branch -M main

echo [*] Đang cấu hình Remote Origin tới: %REPO_URL%
git remote remove origin >nul 2>&1
git remote add origin %REPO_URL%

echo.
echo [*] Đang tiến hành Push toàn bộ mã nguồn lên GitHub...
echo (Lưu ý: Nếu GitHub yêu cầu đăng nhập, hãy nhập Personal Access Token làm mật khẩu)
echo.
git push -u origin main

if %ERRORLEVEL% EQU 0 (
    echo.
    echo ==============================================================================
    echo  [SUCCESS] ĐÃ PUSH MÃ NGUỒN LÊN GITHUB THÀNH CÔNG 100%!
    echo  Anh có thể gửi link Repository này cho Quản lý / Sếp Tiến kiểm tra.
    echo ==============================================================================
) else (
    echo.
    echo ==============================================================================
    echo  [!] Có thể chưa xác thực thành công Personal Access Token.
    echo  Vui lòng tạo token tại: https://github.com/settings/tokens (quyền 'repo')
    echo ==============================================================================
)

echo.
pause
