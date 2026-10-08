"""Per-user AI provider settings (API key or local LLM endpoint)."""
import uuid

from sqlalchemy import Column, String, Text, DateTime, ForeignKey, func
from app.database import Base


class AISetting(Base):
    __tablename__ = "ai_settings"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=False, unique=True)
    provider = Column(String, nullable=False, default="openai")  # openai | ollama
    base_url = Column(String, nullable=True)
    model = Column(String, nullable=False, default="")
    encrypted_api_key = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now())
