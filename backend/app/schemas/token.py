from pydantic import BaseModel

class LoginResponse(BaseModel):
    detail: str = "登录成功"