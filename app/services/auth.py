"""
Authentication & RBAC Service Module
Handles password hashing (PBKDF2-HMAC-SHA256), JWT token issuance/verification, and FastAPI security dependencies.
Enforces strict checks that only ACTIVE accounts can obtain tokens or access protected endpoints.
"""
import os
import hashlib
import jwt
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any
from fastapi import Request, HTTPException, status, Depends, Cookie
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.config import settings
from app.database.models import User, UserRole, UserStatus, UserInDB
from app.database.db import db

security_bearer = HTTPBearer(auto_error=False)

JWT_ALGORITHM = "HS256"
JWT_EXPIRE_HOURS = 24


def hash_password(password: str, salt: Optional[str] = None) -> str:
    """Hashes password using PBKDF2 HMAC SHA-256 with salt"""
    if not salt:
        salt = os.urandom(16).hex()
    key = hashlib.pbkdf2_hmac(
        'sha256',
        password.encode('utf-8'),
        salt.encode('utf-8'),
        100000
    )
    return f"{salt}${key.hex()}"


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifies plain password against hashed salt$hex string"""
    try:
        salt, expected_hex = hashed_password.split("$")
        key = hashlib.pbkdf2_hmac(
            'sha256',
            plain_password.encode('utf-8'),
            salt.encode('utf-8'),
            100000
        )
        return key.hex() == expected_hex
    except Exception:
        return False


def create_access_token(user: User, expires_delta: Optional[timedelta] = None) -> str:
    """Creates signed JWT token with user payload"""
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(hours=JWT_EXPIRE_HOURS))
    payload = {
        "sub": user.id,
        "username": user.username,
        "full_name": user.full_name,
        "role": user.role.value,
        "exp": expire,
        "iat": datetime.now(timezone.utc)
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> Optional[Dict[str, Any]]:
    """Decodes and validates JWT token"""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[JWT_ALGORITHM])
        return payload
    except Exception:
        return None


def generate_approval_token(quote_id: str, action: str, secret_key: str, expire_minutes: int = 60) -> str:
    """
    Generates a secure, timestamped HMAC-SHA256 token for quick approval/rejection links.
    Format: {expire_ts}.{signature}
    """
    import hmac
    import time
    expire_ts = int(time.time()) + (expire_minutes * 60)
    data = f"{quote_id}:{action.lower()}:{expire_ts}"
    signature = hmac.new(
        secret_key.encode("utf-8"),
        data.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()
    return f"{expire_ts}.{signature}"


def verify_approval_token(quote_id: str, action: str, token: str, secret_key: str) -> bool:
    """
    Verifies that the approval token is valid, untampered, and not expired.
    """
    import hmac
    import time
    if not token or "." not in token:
        return False
    try:
        expire_ts_str, signature = token.split(".", 1)
        expire_ts = int(expire_ts_str)
        if time.time() > expire_ts:
            return False  # Token expired
        data = f"{quote_id}:{action.lower()}:{expire_ts}"
        expected_sig = hmac.new(
            secret_key.encode("utf-8"),
            data.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(expected_sig, signature)
    except Exception:
        return False



async def get_current_user_optional(
    request: Request,
    auth_header: Optional[HTTPAuthorizationCredentials] = Depends(security_bearer),
    access_token_cookie: Optional[str] = Cookie(None, alias="access_token")
) -> Optional[User]:
    """
    Retrieves user from Authorization Bearer header or access_token cookie if available.
    Ensures that only ACTIVE users are recognized.
    """
    token = None
    if auth_header and auth_header.credentials:
        token = auth_header.credentials
    elif access_token_cookie:
        token = access_token_cookie

    if not token:
        return None

    payload = decode_access_token(token)
    if not payload or "sub" not in payload:
        return None

    user_id = payload["sub"]
    user_db = db.get_user_by_id(user_id)
    if not user_db or not user_db.is_active or user_db.status != UserStatus.ACTIVE:
        return None

    return User(
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


async def get_current_user(
    request: Request,
    user: Optional[User] = Depends(get_current_user_optional)
) -> User:
    """
    Mandatory authentication dependency - raises 401 if unauthenticated or pending/disabled.
    """
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Yêu cầu đăng nhập tài khoản hợp lệ (Token JWT) để truy cập tài nguyên này",
            headers={"WWW-Authenticate": "Bearer"}
        )
    return user


async def require_manager_or_admin(
    current_user: User = Depends(get_current_user)
) -> User:
    """RBAC dependency: Requires MANAGER or ADMIN role"""
    if current_user.role not in [UserRole.ADMIN, UserRole.MANAGER]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bạn không có quyền thực hiện thao tác này (Chỉ Quản lý / Giám đốc mới có quyền duyệt)"
        )
    return current_user


async def require_admin(
    current_user: User = Depends(get_current_user)
) -> User:
    """RBAC dependency: Requires ADMIN role (Sếp Tiến)"""
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Yêu cầu quyền Quản Trị Viên (Admin) để thực hiện thao tác này."
        )
    return current_user
