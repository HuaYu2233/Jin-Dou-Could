from fastapi import APIRouter, Depends, HTTPException, Response, Request
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.base import get_db
from app.schemas.user import UserCreate, UserLogin, UserResponse
from app.schemas.token import LoginResponse
from app.schemas.reset_password import (
    ForgotPasswordRequest,
    ResetPasswordRequest,
    SecurityQuestionRequest,
    SecurityResetRequest,
)
from app.services.user_service import create_user
from app.services import auth_service, reset_password_service

router = APIRouter()


@router.post("/register", response_model=UserResponse)
async def register(data: UserCreate, db: AsyncSession = Depends(get_db)):
    try:
        user = await create_user(db, data)
        return user
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/login", response_model=LoginResponse)
async def login(
    request: Request,
    response: Response,
    data: UserLogin,
    db: AsyncSession = Depends(get_db),
):
    client_ip = auth_service.get_client_ip(request)

    try:
        await auth_service.check_login_rate_limit(client_ip, data.email)
    except ValueError as e:
        raise HTTPException(status_code=429, detail=str(e))

    user = await auth_service.authenticate_user(db, data.email, data.password)
    if not user:
        await auth_service.record_login_failure(client_ip, data.email)
        raise HTTPException(status_code=401, detail="Invalid email or password")

    await auth_service.clear_login_rate_limit(client_ip, data.email)
    auth_service.set_auth_cookies(response, user)
    return LoginResponse()


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


@router.post("/logout")
async def logout(request: Request, response: Response):
    await auth_service.logout(request, response)
    return {"detail": "已退出登录"}


@router.post("/refresh")
async def refresh_token(request: Request, response: Response):
    try:
        await auth_service.refresh_access_token(request, response)
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))
    return {"detail": "Token 已刷新"}