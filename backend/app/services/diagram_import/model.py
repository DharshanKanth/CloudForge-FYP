"""Internal representation shared by the diagram parsers."""
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


class DiagramParseError(ValueError):
    """Raised when an uploaded diagram cannot be read."""


@dataclass
class ParsedNode:
    id: str
    resource_type: str
    label: str
    properties: Dict = field(default_factory=dict)
    position: Optional[Dict[str, float]] = None


@dataclass
class ParsedEdge:
    source: str
    target: str


@dataclass
class ParsedDiagram:
    nodes: List[ParsedNode] = field(default_factory=list)
    edges: List[ParsedEdge] = field(default_factory=list)
    # (label, reason) for elements we could not map to a supported resource.
    unrecognized: List[Tuple[str, str]] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
