from pydantic import BaseModel
from typing import Optional, Literal
from datetime import datetime


class ProjectCreate(BaseModel):
    name: str
    description: Optional[str] = None
    provider: Literal["aws", "azure", "gcp"] = "aws"


class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None


class ProjectResponse(BaseModel):
    id: str
    user_id: str
    name: str
    description: Optional[str]
    provider: str
    status: str
    created_at: datetime
    updated_at: datetime
    resource_count: int = 0

    model_config = {"from_attributes": True}
