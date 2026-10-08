"""Canonical CloudForge JSON importer.

Accepts either a saved architecture (``{nodes, edges}`` in canvas form) or the
compact AI-style shape (``nodes`` with ``resourceType``/``properties`` plus
``edges``). Unknown/unsupported resource types are reported, never guessed.
"""
import json
from typing import Any, Dict, List, Set

from app.services.diagram_import.mapping import classify_label
from app.services.diagram_import.model import DiagramParseError, ParsedDiagram, ParsedEdge, ParsedNode
from app.services.validation_service import SUPPORTED_RESOURCE_TYPES


def _unique(value: str, seen: Set[str]) -> str:
    if value not in seen:
        seen.add(value)
        return value
    i = 2
    while f"{value}-{i}" in seen:
        i += 1
    seen.add(f"{value}-{i}")
    return f"{value}-{i}"


def parse_canonical(content: str) -> ParsedDiagram:
    try:
        data: Any = json.loads(content)
    except json.JSONDecodeError as exc:
        raise DiagramParseError(f"Could not parse JSON: {exc}") from exc

    if isinstance(data, list):
        raw_nodes, raw_edges = data, []
    elif isinstance(data, dict):
        raw_nodes = data.get("nodes") or []
        raw_edges = data.get("edges") or []
    else:
        raise DiagramParseError("JSON must be an object with 'nodes'/'edges' or a list of nodes.")
    if not isinstance(raw_nodes, list):
        raise DiagramParseError("'nodes' must be a list.")

    nodes: List[ParsedNode] = []
    unrecognized: List = []
    seen: Set[str] = set()
    id_map: Dict[str, str] = {}

    for index, raw in enumerate(raw_nodes):
        if not isinstance(raw, dict):
            continue
        data_obj = raw.get("data") if isinstance(raw.get("data"), dict) else {}
        rtype = str(
            data_obj.get("resourceType") or raw.get("resourceType") or raw.get("type") or ""
        )
        if rtype in ("resourceNode", "groupNode"):
            rtype = ""
        raw_id = str(raw.get("id") or f"node-{index}")
        label = str(data_obj.get("label") or raw.get("label") or raw_id)
        props = data_obj.get("properties") or raw.get("properties") or {}
        if not isinstance(props, dict):
            props = {}
        if rtype not in SUPPORTED_RESOURCE_TYPES:
            # Fall back to classifying the label.
            rtype = classify_label(label) or ""
        if rtype in SUPPORTED_RESOURCE_TYPES:
            nid = _unique(raw_id, seen)
            id_map[raw_id] = nid
            position = raw.get("position") if isinstance(raw.get("position"), dict) else None
            nodes.append(ParsedNode(
                id=nid, resource_type=rtype, label=label,
                properties=dict(props), position=position,
            ))
        else:
            reason = "Unsupported or unknown resource type"
            unrecognized.append((label, reason))

    edges: List[ParsedEdge] = []
    for raw in raw_edges:
        if not isinstance(raw, dict):
            continue
        source, target = raw.get("source"), raw.get("target")
        source = id_map.get(str(source))
        target = id_map.get(str(target))
        if source and target and source != target:
            edges.append(ParsedEdge(source=source, target=target))

    warnings = []
    if not nodes:
        warnings.append("No supported resources found in the JSON file.")
    return ParsedDiagram(nodes=nodes, edges=edges, unrecognized=unrecognized, warnings=warnings)
