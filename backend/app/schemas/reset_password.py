from pydantic import BaseModel, EmailStr

class ForgotPasswordRequest(BaseModel):
    email: EmailStr

class ResetPasswordRequest(BaseModel):
    email: EmailStr
    code: str
    new_password: str

class SecurityQuestionRequest(BaseModel):
    email: EmailStr

class SecurityResetRequest(BaseModel):
    email: EmailStr
    answer: str
    new_password: str