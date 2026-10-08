import asyncio

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.core.deps import get_current_user
from app.core.crypto import decrypt_credentials
from app.schemas.cloud import CloudAccountCreate, CloudAccountResponse
from app.services import cloud_service

router = APIRouter()


@router.get("/accounts", response_model=list[CloudAccountResponse])
async def list_accounts(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List the current user's connected cloud accounts (metadata only)."""
    return await cloud_service.list_accounts(db, current_user.id)


@router.post("/accounts", response_model=CloudAccountResponse, status_code=201)
async def create_account(
    data: CloudAccountCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Connect a cloud account. Credentials are encrypted and never returned."""
    try:
        return await cloud_service.create_account(db, current_user.id, data)
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail="A cloud account with that name already exists")


@router.delete("/accounts/{account_id}")
async def delete_account(
    account_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    deleted = await cloud_service.delete_account(db, current_user.id, account_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Cloud account not found")
    return {"message": "Cloud account deleted"}


@router.post("/verify")
async def verify_credentials(
    data: CloudAccountCreate,
    current_user: User = Depends(get_current_user),
):
    """Validate credentials before saving, via an STS GetCallerIdentity call."""
    creds = {
        "access_key_id": data.access_key_id,
        "secret_access_key": data.secret_access_key,
        "session_token": data.session_token,
        "region": data.region,
    }
    return await asyncio.to_thread(cloud_service.verify_aws, creds, data.region)


@router.post("/accounts/{account_id}/verify")
async def verify_account(
    account_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Validate a saved account's stored credentials."""
    account = await cloud_service.get_account(db, current_user.id, account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Cloud account not found")
    try:
        creds = decrypt_credentials(account.encrypted_credentials)
    except ValueError:
        return {"valid": False, "error": "Stored credentials could not be decrypted"}
    return await asyncio.to_thread(cloud_service.verify_aws, creds, account.region)
