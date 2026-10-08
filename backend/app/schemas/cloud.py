from pydantic import BaseModel, Field
from typing import Literal
from datetime import datetime


class CloudAccountCreate(BaseModel):
    """Credentials are accepted here but never echoed back in a response."""

    provider: Literal["aws"] = "aws"
    name: str = Field(min_length=1, max_length=100)
    region: str = Field(default="us-east-1", min_length=2, max_length=32)
    access_key_id: str = Field(min_length=8, max_length=256)
    secret_access_key: str = Field(min_length=8, max_length=512)
    session_token: str | None = Field(default=None, max_length=4096)


class CloudAccountResponse(BaseModel):
    id: str
    provider: str
    name: str
    region: str
    created_at: datetime

    model_config = {"from_attributes": True}
