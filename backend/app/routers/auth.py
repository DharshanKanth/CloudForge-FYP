import os

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.deps import get_current_user
from app.core.rate_limit import enforce_rate_limit
from app.core.security import (
    get_password_hash,
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_token,
)
from app.database import get_db
from app.models.user import User
from app.schemas.user import UserCreate, UserLogin, UserResponse, TokenResponse

router = APIRouter()

# Cookies must outlive the short access token so the refresh cookie can renew
# the session; both are cleared server-side on logout.
_COOKIE_MAX_AGE_SECONDS = 60 * 60 * 24 * 30  # 30 days


def _is_production() -> bool:
    env = os.environ.get("CLOUDFORGE_ENV", os.environ.get("ENV", "development"))
    return env.lower() == "production"


def _auth_response(user: User) -> Response:
    """Build the token response and set the httpOnly session cookies."""
    token = create_access_token({"sub": user.id})
    refresh = create_refresh_token({"sub": user.id})
    body = TokenResponse(access_token=token, user=UserResponse.model_validate(user))
    response = Response(content=body.model_dump_json(), media_type="application/json")
    secure = _is_production()
    response.set_cookie(
        "cloudforge_access_token", token,
        max_age=_COOKIE_MAX_AGE_SECONDS, httponly=True, secure=secure, samesite="lax", path="/",
    )
    response.set_cookie(
        "cloudforge_refresh_token", refresh,
        max_age=_COOKIE_MAX_AGE_SECONDS, httponly=True, secure=secure, samesite="lax", path="/",
    )
    return response


@router.post("/register", response_model=TokenResponse)
async def register(user_data: UserCreate, request: Request, db: AsyncSession = Depends(get_db)):
    enforce_rate_limit(request, "register")

    result = await db.execute(select(User).where(User.email == user_data.email))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email already registered")

    result = await db.execute(select(User).where(User.username == user_data.username))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Username already taken")

    user = User(
        email=user_data.email,
        username=user_data.username,
        hashed_password=get_password_hash(user_data.password),
    )
    db.add(user)
    try:
        await db.commit()
    except IntegrityError:
        # Concurrent registration for the same email/username: the pre-checks
        # above can pass on both workers, so enforce uniqueness at commit time.
        await db.rollback()
        raise HTTPException(status_code=409, detail="Email or username already registered")
    await db.refresh(user)

    return _auth_response(user)


@router.post("/login", response_model=TokenResponse)
async def login(credentials: UserLogin, request: Request, db: AsyncSession = Depends(get_db)):
    enforce_rate_limit(request, "login")

    result = await db.execute(select(User).where(User.email == credentials.email))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )

    try:
        verified = verify_password(credentials.password, user.hashed_password)
    except Exception:
        verified = False

    if not verified:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )

    return _auth_response(user)


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    return current_user


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(request: Request, db: AsyncSession = Depends(get_db)):
    token = request.cookies.get("cloudforge_refresh_token")
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing refresh token")
    payload = decode_token(token, expected_type="refresh")
    if not payload:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

    user_id = payload.get("sub")
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    return _auth_response(user)


@router.post("/logout")
async def logout():
    response = Response(status_code=200)
    response.delete_cookie("cloudforge_refresh_token", path="/")
    response.delete_cookie("cloudforge_access_token", path="/")
    return response
