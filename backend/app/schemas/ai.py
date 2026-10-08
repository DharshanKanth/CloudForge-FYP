from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional


class AIRecNode(BaseModel):
    id: str
    resourceType: str
    properties: Dict[str, Any] = {}

    model_config = {"extra": "allow"}


class AIRecEdge(BaseModel):
    source: str
    target: str


class AIArchitecture(BaseModel):
    """Structured architecture an AI may propose (validated by the engine)."""

    nodes: List[AIRecNode] = []
    edges: List[AIRecEdge] = []
    rationale: str = ""


class AIArchitectRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=2000)
    project_id: Optional[str] = None


class AIProjectRequest(BaseModel):
    project_id: str


class AITroubleshootRequest(BaseModel):
    project_id: str
    error: str = Field(min_length=1, max_length=8000)


class AIStatusResponse(BaseModel):
    configured: bool
    provider: str
    model: str
    base_url: Optional[str] = None


class AIArchitectResponse(BaseModel):
    configured: bool
    message: Optional[str] = None
    rationale: Optional[str] = None
    nodes: List[Dict[str, Any]] = []
    edges: List[Dict[str, Any]] = []
    validation: Optional[Dict] = None


class AITextResponse(BaseModel):
    configured: bool
    message: Optional[str] = None
    text: Optional[str] = None


class AIFixResponse(BaseModel):
    configured: bool
    source: Optional[str] = None  # engine | ai | none
    message: Optional[str] = None
    rationale: Optional[str] = None
    nodes: List[Dict[str, Any]] = []
    edges: List[Dict[str, Any]] = []
    before: Optional[Dict] = None
    after: Optional[Dict] = None
