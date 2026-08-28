"""
Authentication & User Management Router
Handles login, registration (sign up with Pending Approval), logout, user profile, and Admin RBAC user management.
"""
import uuid
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Request, Response, HTTPException, status, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.config import settings
from app.database.models import (
    User, UserRole, UserStatus, UserInDB,
    UserLoginRequest, UserRegisterRequest,
    UserUpdateStatusRequest, UserUpdateRoleRequest,
    TokenResponse
)
from app.database.db import db
from app.services.auth import (
    hash_password,
    verify_password,
    create_access_token,
    get_current_user_optional,
    get_current_user,
    require_manager_or_admin,
    require_admin
)

router = APIRouter(tags=["Authentication & Users"])
templates = Jinja2Templates(directory="app/templates")


@router.get("/login", response_class=HTMLResponse)
async def login_page(
    request: Request,
    current_user: Optional[User] = Depends(get_current_user_optional)
):
    """Serve the Vertex brand login page. If already authenticated, redirect to /"""
    if current_user:
        return RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)

    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={"settings": settings, "error": None}
    )


@router.get("/register", response_class=HTMLResponse)
async def register_page(
    request: Request,
    current_user: Optional[User] = Depends(get_current_user_optional)
):
    """Serve the Vertex PCCC registration page"""
    if current_user:
        return RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)

    return templates.TemplateResponse(
        request=request,
        name="register.html",
        context={"settings": settings, "error": None}
    )


@router.post("/api/auth/register")
async def api_register(
    payload: UserRegisterRequest
):
    """
    API endpoint for new user registration (Staff, Dealers, Contractors).
    All newly registered accounts are set to PENDING_APPROVAL status and must be approved by Admin (Sếp Tiến)
    before they can log in and access any price or BOQ data.
    """
    username = payload.username.strip().lower()
    if not username or len(username) < 3:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tên đăng nhập phải có ít nhất 3 ký tự!"
        )

    if not payload.password or len(payload.password) < 6:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Mật khẩu phải có ít nhất 6 ký tự!"
        )

    # Check if username already exists
    existing = db.get_user_by_username(username)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tên đăng nhập này đã tồn tại trong hệ thống. Vui lòng chọn tên khác!"
        )

    # Determine requested role based on account_type
    account_type = (payload.account_type or "STAFF").upper()
    if account_type == "DEALER":
        user_role = UserRole.DEALER
    elif account_type == "PARTNER":
        user_role = UserRole.PARTNER
    else:
        user_role = UserRole.STAFF

    user_id = str(uuid.uuid4())
    hashed_pwd = hash_password(payload.password)
    
    from app.services.sanitizer import clean_string

    clean_full_name = clean_string(payload.full_name, escape_html_entities=False) or username
    clean_email = clean_string(payload.email, escape_html_entities=False)
    clean_phone = clean_string(payload.phone, escape_html_entities=False)
    clean_company = clean_string(payload.company_name, escape_html_entities=False) or "Khách hàng / Đối tác PCCC"

    # Strictly set newly registered user to PENDING_APPROVAL and is_active=False
    user_status = UserStatus.PENDING_APPROVAL

    user_in_db = UserInDB(
        id=user_id,
        username=username,
        full_name=clean_full_name,
        email=clean_email,
        phone=clean_phone,
        company_name=clean_company,
        role=user_role,
        status=user_status,
        hashed_password=hashed_pwd,
        is_active=False
    )

    db.create_user(user_in_db)

    user = User(
        id=user_in_db.id,
        username=user_in_db.username,
        full_name=user_in_db.full_name,
        email=user_in_db.email,
        phone=user_in_db.phone,
        company_name=user_in_db.company_name,
        role=user_in_db.role,
        status=user_in_db.status,
        is_active=user_in_db.is_active,
        created_at=user_in_db.created_at
    )

    # Notice: Do NOT issue JWT token or set session cookie!
    return {
        "status": "pending",
        "message": f"Đăng ký tài khoản '{username}' thành công! Tài khoản của bạn đang ở trạng thái CHỜ DUYỆT (Pending). Vui lòng liên hệ Admin (Sếp Tiến) để phê duyệt kích hoạt trước khi đăng nhập.",
        "user": user
    }


@router.post("/api/auth/login", response_model=TokenResponse)
async def api_login(
    response: Response,
    payload: UserLoginRequest
):
    """
    API endpoint to authenticate with username & password.
    Rejects users who are PENDING_APPROVAL or DISABLED.
    """
    user_db = db.get_user_by_username(payload.username)
    if not user_db or not verify_password(payload.password, user_db.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Tên đăng nhập hoặc mật khẩu không chính xác!"
        )

    # Check approval status
    if user_db.status in [UserStatus.PENDING_APPROVAL, "PENDING", "pending"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tài khoản của bạn đang ở trạng thái CHỜ DUYỆT (Pending). Vui lòng liên hệ Admin (Sếp Tiến) để kích hoạt tài khoản trước khi đăng nhập."
        )

    if not user_db.is_active or user_db.status in [UserStatus.DISABLED, "DISABLED"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tài khoản này đã bị khóa hoặc vô hiệu hóa. Vui lòng liên hệ Ban Giám Đốc."
        )

    user = User(
        id=user_db.id,
        username=user_db.username,
        full_name=user_db.full_name,
        email=user_db.email,
        phone=user_db.phone,
        company_name=user_db.company_name,
        role=user_db.role,
        status=user_db.status,
        is_active=user_db.is_active,
        created_at=user_db.created_at
    )

    access_token = create_access_token(user)

    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        max_age=86400,
        samesite="lax"
    )

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        user=user
    )


@router.get("/logout")
async def logout(response: Response):
    """Logs out user by clearing the access_token session cookie and redirects to /login"""
    redirect = RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
    redirect.delete_cookie(key="access_token")
    return redirect


@router.get("/api/auth/me", response_model=User)
async def get_my_profile(current_user: User = Depends(get_current_user)):
    """Returns the authenticated user profile"""
    return current_user


# Admin User Management Endpoints
@router.get("/api/users", response_model=List[User])
async def list_users(current_user: User = Depends(require_manager_or_admin)):
    """List all registered users (Admin / Manager only)"""
    return db.list_all_users()


@router.put("/api/users/{user_id}/status")
async def update_user_status(
    user_id: str,
    payload: UserUpdateStatusRequest,
    current_user: User = Depends(require_manager_or_admin)
):
    """Admin updates user status (ACTIVE, PENDING_APPROVAL, DISABLED)"""
    success = db.update_user_status(user_id, payload.status)
    if not success:
        raise HTTPException(status_code=404, detail="Không tìm thấy người dùng này!")
    return {"status": "success", "message": f"Đã cập nhật trạng thái người dùng thành '{payload.status.value}'"}



@router.put("/api/users/{user_id}/role")
async def update_user_role(
    user_id: str,
    payload: UserUpdateRoleRequest,
    current_user: User = Depends(require_manager_or_admin)
):
    """Admin updates user role (ADMIN, MANAGER, STAFF, DEALER, PARTNER)"""
    success = db.update_user_role(user_id, payload.role)
    if not success:
        raise HTTPException(status_code=404, detail="Không tìm thấy người dùng này!")
    return {"status": "success", "message": f"Đã cập nhật phân quyền người dùng thành '{payload.role.value}'"}
