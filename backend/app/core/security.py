import uuid
import bcrypt
from datetime import datetime, timedelta, timezone
from jose import jwt, JWTError
from app.core.config import settings

# ========== 密码 ==========
def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode('utf-8'), hashed.encode('utf-8'))

# ========== 安全回答 ==========
def hash_security_answer(answer: str) -> str:
    normalized = answer.strip().lower()
    return bcrypt.hashpw(normalized.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def verify_security_answer(plain: str, hashed: str) -> bool:
    normalized = plain.strip().lower()
    return bcrypt.checkpw(normalized.encode('utf-8'), hashed.encode('utf-8'))

# ========== JWT ==========
def _create_token(data: dict, expires_delta: timedelta, token_type: str) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + expires_delta
    to_encode.update({"exp": expire, "jti": str(uuid.uuid4()), "type": token_type})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

def create_access_token(data: dict) -> str:
    return _create_token(data, timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES), token_type="access")

def create_refresh_token(data: dict) -> str:
    return _create_token(data, timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS), token_type="refresh")

def decode_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except JWTError:
        return None

async def revoke_token(token: str) -> None:
    from app.core.redis import redis_client
    payload = decode_token(token)
    if not payload or not payload.get("jti"):
        return
    exp = payload.get("exp")
    if not exp:
        return
    remaining = int(exp - datetime.now(timezone.utc).timestamp())
    if remaining > 0:
        await redis_client.setex(f"token_blacklist:{payload['jti']}", remaining, "1")