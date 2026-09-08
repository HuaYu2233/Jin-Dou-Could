from pydantic import BaseModel, EmailStr, field_validator
from app.schemas.user import _validate_password_complexity

class ForgotPasswordRequest(BaseModel):
    email: EmailStr

class ResetPasswordRequest(BaseModel):
    email: EmailStr
    code: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def _validate_password(cls, v: str) -> str:
        return _validate_password_complexity(v)

class SecurityQuestionRequest(BaseModel):
    email: EmailStr

class SecurityResetRequest(BaseModel):
    email: EmailStr
    answer: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def _validate_password(cls, v: str) -> str:
        return _validate_password_complexity(v)