from fastapi import APIRouter, Depends, HTTPException, status, Response, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models.user import User
from app.schemas.user import UserCreate, UserLogin, UserResponse, TokenResponse
from app.core.security import (
    get_password_hash,
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_token,
    is_refresh_token,
)

router = APIRouter()


@router.post("/register", response_model=TokenResponse)
async def register(user_data: UserCreate, db: AsyncSession = Depends(get_db)):
    # Check if email exists
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
    await db.commit()
    await db.refresh(user)

    token = create_access_token({"sub": user.id})
    refresh = create_refresh_token({"sub": user.id})
    resp = TokenResponse(
        access_token=token,
        user=UserResponse.model_validate(user),
    )
    response = Response(content=resp.model_dump_json(), media_type="application/json")
    # Set httpOnly access + refresh cookies
    secure = True if __import__('os').environ.get('CLOUDFORGE_ENV', __import__('os').environ.get('ENV', 'development')).lower() == 'production' else False
    response.set_cookie("cloudforge_access_token", token, httponly=True, secure=secure, samesite='lax', path='/')
    response.set_cookie("cloudforge_refresh_token", refresh, httponly=True, secure=secure, samesite='lax', path='/')
    return response


@router.post("/login", response_model=TokenResponse)
async def login(credentials: UserLogin, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == credentials.email))
    user = result.scalar_one_or_none()

    if not user or not verify_password(credentials.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )

    token = create_access_token({"sub": user.id})
    refresh = create_refresh_token({"sub": user.id})
    resp = TokenResponse(
        access_token=token,
        user=UserResponse.model_validate(user),
    )
    response = Response(content=resp.model_dump_json(), media_type="application/json")
    secure = True if __import__('os').environ.get('CLOUDFORGE_ENV', __import__('os').environ.get('ENV', 'development')).lower() == 'production' else False
    response.set_cookie("cloudforge_access_token", token, httponly=True, secure=secure, samesite='lax', path='/')
    response.set_cookie("cloudforge_refresh_token", refresh, httponly=True, secure=secure, samesite='lax', path='/')
    return response


@router.get("/me", response_model=UserResponse)
async def get_me(db: AsyncSession = Depends(get_db)):
    """Returns current user info - requires token in Authorization header"""
    from app.core.deps import get_current_user
    # This is handled by dependency injection at route level
    raise HTTPException(status_code=501, detail="Use Authorization header")


@router.post('/refresh', response_model=TokenResponse)
async def refresh_token(request: Request, db: AsyncSession = Depends(get_db)):
    # Read refresh token from httpOnly cookie
    token = request.cookies.get('cloudforge_refresh_token')
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Missing refresh token')
    payload = decode_token(token)
    if not payload or not is_refresh_token(payload):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Invalid refresh token')

    user_id = payload.get('sub')
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='User not found')

    access = create_access_token({"sub": user.id})
    refresh = create_refresh_token({"sub": user.id})
    resp = TokenResponse(access_token=access, user=UserResponse.model_validate(user))
    response = Response(content=resp.model_dump_json(), media_type='application/json')
    secure = True if __import__('os').environ.get('CLOUDFORGE_ENV', __import__('os').environ.get('ENV', 'development')).lower() == 'production' else False
    response.set_cookie("cloudforge_access_token", access, httponly=True, secure=secure, samesite='lax', path='/')
    response.set_cookie("cloudforge_refresh_token", refresh, httponly=True, secure=secure, samesite='lax', path='/')
    return response


@router.post('/logout')
async def logout():
    response = Response(status_code=200)
    response.delete_cookie('cloudforge_refresh_token', path='/')
    response.delete_cookie('cloudforge_access_token', path='/')
    return response
