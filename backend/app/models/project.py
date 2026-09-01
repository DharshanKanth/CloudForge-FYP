from sqlalchemy import Column, String, DateTime, Text, ForeignKey, func, Integer
from sqlalchemy.orm import relationship
from app.database import Base
import uuid


class Project(Base):
    __tablename__ = "projects"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    provider = Column(String, nullable=False, default="aws")  # aws, azure, gcp
    status = Column(String, nullable=False, default="draft")  # draft, saved, deployed
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now())

    user = relationship("User", back_populates="projects")
    architectures = relationship("Architecture", back_populates="project", cascade="all, delete-orphan")

    # Future tables (commented out placeholders for clean extension)
    # deployments = relationship("Deployment", back_populates="project")
    # cost_estimates = relationship("CostEstimate", back_populates="project")
