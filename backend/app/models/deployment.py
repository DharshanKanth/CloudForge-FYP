"""Deployment jobs executed by the isolated Terraform worker.

The API only ever *enqueues* a deployment (status ``queued``); a separate worker
process claims and runs it, streaming output into ``deployment_logs``. This
keeps Terraform execution out of the web API process.
"""
import uuid

from sqlalchemy import Column, String, Text, Integer, DateTime, ForeignKey, Index, func
from sqlalchemy.orm import relationship

from app.database import Base


class Deployment(Base):
    __tablename__ = "deployments"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(String, ForeignKey("projects.id"), nullable=False, index=True)
    operation = Column(String, nullable=False)   # plan | apply | plan_destroy | destroy
    status = Column(String, nullable=False, default="queued")  # queued | running | succeeded | failed
    step = Column(String, nullable=True)
    output_tail = Column(Text, nullable=False, default="")
    resource_count = Column(Integer, nullable=True)
    error = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    started_at = Column(DateTime(timezone=True), nullable=True)
    finished_at = Column(DateTime(timezone=True), nullable=True)

    logs = relationship(
        "DeploymentLog",
        back_populates="deployment",
        cascade="all, delete-orphan",
        order_by="DeploymentLog.seq",
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "project_id": self.project_id,
            "operation": self.operation,
            "status": self.status,
            "step": self.step,
            "resource_count": self.resource_count,
            "error": self.error,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
        }


class DeploymentLog(Base):
    __tablename__ = "deployment_logs"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    deployment_id = Column(String, ForeignKey("deployments.id"), nullable=False, index=True)
    seq = Column(Integer, nullable=False)
    message = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    deployment = relationship("Deployment", back_populates="logs")

    __table_args__ = (
        Index("ix_deployment_logs_deployment_seq", "deployment_id", "seq"),
    )
