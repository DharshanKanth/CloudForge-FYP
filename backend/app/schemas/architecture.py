from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from datetime import datetime


class NodeData(BaseModel):
    label: Optional[str] = None
    resourceType: str
    provider: str = "aws"
    properties: Dict[str, Any] = {}


class Node(BaseModel):
    id: str
    type: str
    position: Dict[str, float]
    data: Dict[str, Any]


class Edge(BaseModel):
    id: str
    source: str
    target: str
    sourceHandle: Optional[str] = None
    targetHandle: Optional[str] = None
    type: Optional[str] = None


class ArchitectureSave(BaseModel):
    aws_region: str = "us-east-1"
    nodes: List[Dict[str, Any]]
    edges: List[Dict[str, Any]]


class ArchitectureResponse(BaseModel):
    id: str
    project_id: str
    aws_region: str = "us-east-1"
    nodes: List[Dict[str, Any]]
    edges: List[Dict[str, Any]]
    version: int
    updated_at: datetime

    model_config = {"from_attributes": True}


class ValidationIssue(BaseModel):
    level: str
    resource_id: Optional[str] = None
    resource_type: Optional[str] = None
    message: str
    field: Optional[str] = None


class ValidationResult(BaseModel):
    valid: bool
    issues: List[ValidationIssue]
