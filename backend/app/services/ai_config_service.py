"""Resolve and persist a user's AI provider settings.

The API key is encrypted at rest (like cloud credentials) and never returned.
When a user has no saved setting the process-environment config is used.
"""
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.crypto import decrypt_credentials, encrypt_credentials
from app.models.ai_setting import AISetting
from app.services.ai_service import AIConfig, DEFAULT_BASE, DEFAULT_MODEL, config_from_env


async def get_setting(db: AsyncSession, user_id: str) -> Optional[AISetting]:
    return (await db.execute(
        select(AISetting).where(AISetting.user_id == user_id)
    )).scalar_one_or_none()


async def save_setting(db: AsyncSession, user_id: str, data) -> AISetting:
    setting = await get_setting(db, user_id)
    if setting is None:
        setting = AISetting(user_id=user_id)
        db.add(setting)
    setting.provider = data.provider
    setting.base_url = data.base_url
    setting.model = data.model or DEFAULT_MODEL.get(data.provider, "")
    if data.api_key:
        # Only overwrite when a new key is supplied, so re-saving other fields
        # doesn't wipe an existing key.
        setting.encrypted_api_key = encrypt_credentials({"api_key": data.api_key})
    await db.commit()
    await db.refresh(setting)
    return setting


async def delete_setting(db: AsyncSession, user_id: str) -> bool:
    setting = await get_setting(db, user_id)
    if setting is None:
        return False
    await db.delete(setting)
    await db.commit()
    return True


def config_from_input(provider: str, base_url: Optional[str], model: str, api_key: Optional[str]) -> AIConfig:
    base = (base_url or "").rstrip("/") or DEFAULT_BASE.get(provider)
    return AIConfig(
        provider=provider,
        base_url=base,
        model=model or DEFAULT_MODEL.get(provider, ""),
        api_key=api_key or None,
    )


async def resolve_config(db: AsyncSession, user_id: str) -> AIConfig:
    """The user's saved config if present, else the server environment default."""
    setting = await get_setting(db, user_id)
    if setting is None:
        return config_from_env()
    api_key = None
    if setting.encrypted_api_key:
        try:
            api_key = decrypt_credentials(setting.encrypted_api_key).get("api_key")
        except ValueError:
            api_key = None
    return config_from_input(setting.provider, setting.base_url, setting.model, api_key)
