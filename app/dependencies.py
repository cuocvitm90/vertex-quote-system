"""
Common FastAPI Dependencies for Vertex Construction & PCCC
Enforces object-level authorization (IDOR protection) and resource access control.
"""
from typing import Optional
from fastapi import Depends, HTTPException, Path, status
from app.database.db import db
from app.database.models import Quote, User, UserRole
from app.services.auth import get_current_user


async def can_access_quote(
    quote_id: str = Path(..., description="ID hoặc Mã số báo giá"),
    current_user: User = Depends(get_current_user)
) -> Quote:
    """
    Object-Level Authorization Dependency (IDOR Protection).
    - Admins and Managers have full read/write access across all quotes.
    - Staff, Dealers, Partners can only access quotes they created or quotes belonging to their profile/company.
    """
    quote = db.get_quote(quote_id)
    if not quote:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy báo giá với mã hoặc ID '{quote_id}'!"
        )

    # Internal company roles (Admin, Manager, QS Staff) have company-wide visibility
    if current_user.role in [UserRole.ADMIN, UserRole.MANAGER, UserRole.STAFF]:
        return quote

    # Check ownership / identity match for external users (Dealer, Partner)
    is_owner = False
    
    # Direct match with user id / full name
    if hasattr(quote, "created_by_user_id") and getattr(quote, "created_by_user_id", None) == current_user.id:
        is_owner = True
    elif hasattr(quote, "created_by") and getattr(quote, "created_by", None) == current_user.full_name:
        is_owner = True
    elif quote.customer_email and current_user.email and quote.customer_email.lower().strip() == current_user.email.lower().strip():
        is_owner = True
    elif quote.customer_phone and current_user.phone and quote.customer_phone.strip() == current_user.phone.strip():
        is_owner = True
    elif current_user.company_name and quote.customer_name and current_user.company_name.lower() in quote.customer_name.lower():
        is_owner = True

    # Check in logs for creator record
    if not is_owner and quote.logs:
        for log_entry in quote.logs:
            if current_user.full_name in log_entry or current_user.username in log_entry:
                is_owner = True
                break

    if not is_owner:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bạn không có quyền truy cập hoặc thao tác trên báo giá này (IDOR Protection)!"
        )

    return quote
