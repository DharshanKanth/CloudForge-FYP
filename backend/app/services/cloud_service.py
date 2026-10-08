"""Connected cloud accounts and how their credentials reach Terraform."""
from typing import Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.crypto import decrypt_credentials, encrypt_credentials
from app.models.cloud_account import CloudAccount


def build_aws_env(credentials: Dict) -> Dict[str, str]:
    """Map stored AWS credentials to the environment variables Terraform reads."""
    env: Dict[str, str] = {}
    if credentials.get("access_key_id"):
        env["AWS_ACCESS_KEY_ID"] = str(credentials["access_key_id"])
    if credentials.get("secret_access_key"):
        env["AWS_SECRET_ACCESS_KEY"] = str(credentials["secret_access_key"])
    if credentials.get("session_token"):
        env["AWS_SESSION_TOKEN"] = str(credentials["session_token"])
    if credentials.get("region"):
        env["AWS_DEFAULT_REGION"] = str(credentials["region"])
    return env


def _sts_client(credentials: Dict, region: str):
    import boto3  # imported lazily so startup/tests don't require AWS

    return boto3.client(
        "sts",
        region_name=region or credentials.get("region") or "us-east-1",
        aws_access_key_id=credentials.get("access_key_id"),
        aws_secret_access_key=credentials.get("secret_access_key"),
        aws_session_token=credentials.get("session_token"),
    )


def verify_aws(credentials: Dict, region: str = "") -> Dict:
    """Validate AWS credentials with an STS GetCallerIdentity call.

    Returns ``{"valid": True, "account"/"arn"/"user_id"}`` on success, or
    ``{"valid": False, "error": ...}`` with the real provider error. Never raises
    and never fabricates a result.
    """
    try:
        identity = _sts_client(credentials, region).get_caller_identity()
        return {
            "valid": True,
            "account": identity.get("Account"),
            "arn": identity.get("Arn"),
            "user_id": identity.get("UserId"),
        }
    except Exception as exc:  # noqa: BLE001 - surface the provider error verbatim
        return {"valid": False, "error": str(exc)}


async def create_account(db: AsyncSession, user_id: str, data) -> CloudAccount:
    account = CloudAccount(
        user_id=user_id,
        provider=data.provider,
        name=data.name,
        region=data.region,
        encrypted_credentials=encrypt_credentials({
            "access_key_id": data.access_key_id,
            "secret_access_key": data.secret_access_key,
            "session_token": data.session_token,
            "region": data.region,
        }),
    )
    db.add(account)
    await db.commit()
    await db.refresh(account)
    return account


async def list_accounts(db: AsyncSession, user_id: str) -> List[CloudAccount]:
    result = await db.execute(
        select(CloudAccount)
        .where(CloudAccount.user_id == user_id)
        .order_by(CloudAccount.created_at.desc())
    )
    return list(result.scalars().all())


async def get_account(db: AsyncSession, user_id: str, account_id: str) -> Optional[CloudAccount]:
    result = await db.execute(
        select(CloudAccount).where(
            CloudAccount.id == account_id, CloudAccount.user_id == user_id
        )
    )
    return result.scalar_one_or_none()


async def delete_account(db: AsyncSession, user_id: str, account_id: str) -> bool:
    account = await get_account(db, user_id, account_id)
    if not account:
        return False
    await db.delete(account)
    await db.commit()
    return True


async def aws_env_for_user(db: AsyncSession, user_id: str) -> Dict[str, str]:
    """AWS environment for the user's default connected account.

    Returns an empty dict when the user has not connected an account, so the
    deployment runner falls back to the process environment (dev convenience).
    """
    result = await db.execute(
        select(CloudAccount)
        .where(CloudAccount.user_id == user_id, CloudAccount.provider == "aws")
        .order_by(CloudAccount.created_at.asc())
    )
    account = result.scalars().first()
    if not account:
        return {}
    try:
        return build_aws_env(decrypt_credentials(account.encrypted_credentials))
    except ValueError:
        # Undecryptable (e.g. SECRET_KEY rotated): fall back rather than crash.
        return {}
