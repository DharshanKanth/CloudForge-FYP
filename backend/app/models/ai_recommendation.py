"""Stored AI recommendations (audit of what the advisory layer produced)."""
import uuid

from sqlalchemy import Column, String, Text, DateTime, ForeignKey, func
from app.database import Base


class AIRecommendation(Base):
    __tablename__ = "ai_recommendations"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    project_id = Column(String, ForeignKey("projects.id"), nullable=True)
    kind = Column(String, nullable=False)  # architecture | explain | troubleshoot
    prompt = Column(Text, nullable=False, default="")
    response = Column(Text, nullable=False, default="")
    provider = Column(String, nullable=False, default="")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "project_id": self.project_id,
            "kind": self.kind,
            "prompt": self.prompt,
            "response": self.response,
            "provider": self.provider,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
