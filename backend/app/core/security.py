import os
from datetime import datetime, timedelta, timezone
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext

_DEFAULT_SECRET = "cloudforge-secret-key-change-in-production"
# Use an explicit env var for environment selection so CI/dev can set it.
_ENV = os.getenv("CLOUDFORGE_ENV", os.getenv("ENV", "development")).lower()
SECRET_KEY = os.getenv("SECRET_KEY", _DEFAULT_SECRET)

# Fail fast in production if SECRET_KEY wasn't explicitly provided.
if _ENV == "production" and SECRET_KEY == _DEFAULT_SECRET:
    raise RuntimeError("SECRET_KEY must be set in production environment")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60  # short-lived; clients refresh via POST /api/auth/refresh

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    to_encode.update({"type": "access"})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


REFRESH_TOKEN_EXPIRE_DAYS = 30


def create_refresh_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS))
    to_encode.update({"exp": expire, "type": "refresh"})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str, expected_type: str = "access") -> Optional[dict]:
    """Decode and verify a JWT, rejecting tokens whose type doesn't match.

    Access tokens must never be accepted where refresh tokens are expected and
    vice versa; get_current_user relies on the default expected_type="access"
    so long-lived refresh tokens cannot be replayed as session credentials.
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        return None
    if payload.get("type") != expected_type:
        return None
    return payload
