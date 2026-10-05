"""Audit-log style history of every deployment action for a project."""
from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, String, Text, func
from app.database import Base
import uuid


class DeploymentEvent(Base):
    """One entry per plan/apply/plan-destroy/destroy/clear action.

    Populated by the Terraform router after each operation completes so the
    UI can show a per-project deployment timeline (what was deployed, when,
    whether it succeeded, and how many resources were affected).
    """
    __tablename__ = "deployment_events"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(String, ForeignKey("projects.id"), nullable=False)
    event_type = Column(String, nullable=False)   # plan | apply | plan_destroy | destroy | clear
    status = Column(String, nullable=False)        # succeeded | failed | blocked
    detail = Column(Text, nullable=False, default="")
    resource_count = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("ix_deployment_events_project_time", "project_id", "created_at"),
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "project_id": self.project_id,
            "event_type": self.event_type,
            "status": self.status,
            "detail": self.detail,
            "resource_count": self.resource_count,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }