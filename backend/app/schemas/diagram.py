from pydantic import BaseModel, Field
from typing import Any, Dict, List, Literal, Optional


class DiagramImportRequest(BaseModel):
    filename: str = Field(default="diagram", max_length=255)
    # The file is sent as text (draw.io XML, Mermaid, or JSON). Capped well below
    # any practical diagram size but large enough for big exports.
    content: str = Field(min_length=1, max_length=5_000_000)


class UnrecognizedElement(BaseModel):
    label: str
    reason: str = "Not a supported resource type"


class DiagramImportResponse(BaseModel):
    format: Literal["drawio", "mermaid", "json"]
    summary: str = ""
    nodes: List[Dict[str, Any]] = []
    edges: List[Dict[str, Any]] = []
    recognized: int = 0
    unrecognized: List[UnrecognizedElement] = []
    warnings: List[str] = []
    validation: Optional[Dict] = None
