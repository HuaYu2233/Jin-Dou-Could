from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.base import get_db
from app.models.user import User
from app.schemas.user import UserCreate, UserLogin, UserResponse
from app.schemas.token import TokenResponse
from app.schemas.reset_password import (
    ForgotPasswordRequest,
    ResetPasswordRequest,
    SecurityQuestionRequest,
    SecurityResetRequest,
)
from app.services.user_service import create_user
from app.services import reset_password_service
from app.core.security import verify_password, create_access_token, create_refresh_token

router = APIRouter()

@router.post("/register", response_model=UserResponse)
async def register(data: UserCreate, db: AsyncSession = Depends(get_db)):
    try:
        user = await create_user(db, data)
        return user
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/login", response_model=TokenResponse)
async def login(
    response: Response,
    data: UserLogin,  
    db: AsyncSession = Depends(get_db),
):
    # 查用户
    result = await db.execute(select(User).where(User.email == data.email))
    user = result.scalar_one_or_none()
    
    if not user or not verify_password(data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    
    # 生成 Token
    access_token = create_access_token({"sub": str(user.id)})
    refresh_token = create_refresh_token({"sub": str(user.id)})
    
    # Refresh Token 放 HttpOnly Cookie
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        max_age=7 * 24 * 3600,  # 7 天
        samesite="lax",
    )
    
    return TokenResponse(access_token=access_token)


@router.post("/forgot-password")
async def forgot_password(
    data: ForgotPasswordRequest,
    db: AsyncSession = Depends(get_db),
):
    try:
        await reset_password_service.send_code(db, data.email)
    except ValueError as e:
        raise HTTPException(status_code=429, detail=str(e))
    return {"detail": "验证码已发送"}


@router.post("/reset-password")
async def reset_password(
    data: ResetPasswordRequest,
    db: AsyncSession = Depends(get_db),
):
    try:
        await reset_password_service.reset_password(db, data.email, data.code, data.new_password)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"detail": "密码重置成功"}


@router.post("/security-question")
async def get_security_question(
    data: SecurityQuestionRequest,
    db: AsyncSession = Depends(get_db),
):
    question = await reset_password_service.get_security_question(db, data.email)
    if not question:
        raise HTTPException(status_code=404, detail="未找到用户或未设置密保问题")
    return {"question": question}


@router.post("/reset-password-by-security")
async def reset_password_by_security(
    data: SecurityResetRequest,
    db: AsyncSession = Depends(get_db),
):
    try:
        await reset_password_service.reset_password_by_security(
            db, data.email, data.answer, data.new_password
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"detail": "密码重置成功"}