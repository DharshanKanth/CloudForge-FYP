"""Per-user connected cloud accounts.

Credentials are stored encrypted (see app.core.crypto) and are never returned
by the API — responses expose only metadata (provider, name, region).
"""
import uuid

from sqlalchemy import Column, String, Text, DateTime, ForeignKey, UniqueConstraint, func

from app.database import Base


class CloudAccount(Base):
    __tablename__ = "cloud_accounts"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    provider = Column(String, nullable=False, default="aws")  # aws (azure/gcp later)
    name = Column(String, nullable=False)
    region = Column(String, nullable=False, default="us-east-1")
    encrypted_credentials = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("user_id", "name", name="uq_cloud_accounts_user_name"),
    )
