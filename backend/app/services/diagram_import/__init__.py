"""Deterministic architecture-diagram import.

Converts an uploaded diagram into the builder canvas shape
(``{nodes, edges}``), then runs it through the *same* deterministic autofix and
validator the rest of CloudForge uses. There is no AI here: elements are matched
against an ordered mapping table, unknown elements are reported, and the result
is only ever a proposal the user reviews before saving/deploying.

Supported formats:
  * draw.io / diagrams.net (``.drawio``/``.xml``) — icon + hierarchy driven
  * Mermaid flowcharts (``.mmd``/``.mermaid``/text)
  * CloudForge / AI canonical JSON (``.json``)
"""
import json
import re
from typing import Dict, List, Set, Tuple

from app.services.autofix_service import auto_fix
from app.services.diagram_import.canonical import parse_canonical
from app.services.diagram_import.drawio import parse_drawio
from app.services.diagram_import.mapping import build_properties
from app.services.diagram_import.mermaid import parse_mermaid
from app.services.diagram_import.model import DiagramParseError, ParsedDiagram
from app.services.validation_service import validate_architecture

__all__ = ["DiagramParseError", "detect_format", "import_diagram", "finalize_proposal"]

_PARSERS = {"drawio": parse_drawio, "mermaid": parse_mermaid, "json": parse_canonical}


def detect_format(filename: str, content: str) -> str:
    name = (filename or "").lower()
    stripped = content.lstrip()
    if name.endswith(".json") or stripped.startswith("{") or stripped.startswith("["):
        try:
            json.loads(content)
            return "json"
        except json.JSONDecodeError:
            if name.endswith(".json"):
                raise DiagramParseError("The uploaded .json file is not valid JSON.")
    if "<mxfile" in content or "<mxGraphModel" in content or name.endswith(".drawio"):
        return "drawio"
    if re.search(r"^\s*(flowchart|graph)\b", content, re.M) or name.endswith((".mmd", ".mermaid")):
        return "mermaid"
    if "-->" in content or "---" in content or "-.->" in content:
        return "mermaid"
    raise DiagramParseError(
        "Unrecognized diagram format. Upload a draw.io file (.drawio/.xml), a "
        "Mermaid flowchart (.mmd), or CloudForge JSON (.json)."
    )


def _slug(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")
    return (slug[:48] or "resource").strip("-")


def _unique(value: str, used: Set[str]) -> str:
    if value not in used:
        used.add(value)
        return value
    i = 2
    while f"{value}-{i}" in used:
        i += 1
    used.add(f"{value}-{i}")
    return f"{value}-{i}"


def _to_canvas(parsed: ParsedDiagram) -> Tuple[List[Dict], List[Dict]]:
    used_ids: Set[str] = set()
    used_names: Set[str] = set()
    id_map: Dict[str, str] = {}
    subnet_i = 0
    vpc_i = 0
    nodes: List[Dict] = []

    for i, pn in enumerate(parsed.nodes):
        nid = _unique(pn.id or f"node-{i}", used_ids)
        id_map[pn.id] = nid
        label = pn.label or pn.resource_type
        name = _unique(_slug(label), used_names)
        props = build_properties(pn.resource_type, name)
        if pn.resource_type == "vpc" and "cidr" not in pn.properties:
            props["cidr"] = f"10.{vpc_i}.0.0/16"
            vpc_i += 1
        if pn.resource_type == "subnet" and "cidr" not in pn.properties:
            props["cidr"] = f"10.0.{subnet_i + 1}.0/24"
            subnet_i += 1
        if pn.properties:
            props.update(pn.properties)
        pos = pn.position or {"x": 260 * (i % 4), "y": 210 * (i // 4)}
        nodes.append({
            "id": nid,
            "type": "resourceNode",
            "position": {"x": float(pos.get("x", 0)), "y": float(pos.get("y", 0))},
            "data": {
                "label": label,
                "resourceType": pn.resource_type,
                "provider": "aws",
                "properties": props,
            },
        })

    edges: List[Dict] = []
    seen: Set[Tuple[str, str]] = set()
    for e in parsed.edges:
        source, target = id_map.get(e.source), id_map.get(e.target)
        if not source or not target or source == target:
            continue
        key = (source, target) if source < target else (target, source)
        if key in seen:
            continue
        seen.add(key)
        edges.append({"id": f"imp-e{len(edges)}", "source": source, "target": target})

    return nodes, edges


def finalize_proposal(
    fmt: str,
    source_label: str,
    nodes: List[Dict],
    edges: List[Dict],
    unrecognized: List[Tuple[str, str]],
    warnings: List[str],
) -> Dict:
    """Repair + validate a canvas proposal and shape the API response.

    Shared by every import path so a proposal is treated identically regardless
    of whether it came from a draw.io file or a vision model.
    """
    nodes, edges = auto_fix(nodes, edges)
    validation = validate_architecture(nodes, edges)

    warnings = list(warnings)
    if nodes:
        warnings.append(
            "Resource properties are filled with Free-Tier defaults where the "
            "diagram did not specify them — review them in the config panel."
        )

    summary = f"Imported {source_label}: {len(nodes)} resource(s), {len(edges)} connection(s)."
    if unrecognized:
        summary += f" {len(unrecognized)} element(s) were not recognised."

    return {
        "format": fmt,
        "summary": summary,
        "nodes": nodes,
        "edges": edges,
        "recognized": len(nodes),
        "unrecognized": [{"label": label, "reason": reason} for label, reason in unrecognized],
        "warnings": warnings,
        "validation": validation.model_dump(),
    }


def import_diagram(filename: str, content: str) -> Dict:
    """Parse a structured diagram and return a validated, canvas-ready proposal."""
    fmt = detect_format(filename, content)
    parsed = _PARSERS[fmt](content)
    nodes, edges = _to_canvas(parsed)
    source_label = {"drawio": "draw.io diagram", "mermaid": "Mermaid diagram", "json": "JSON file"}[fmt]
    return finalize_proposal(fmt, source_label, nodes, edges, parsed.unrecognized, parsed.warnings)
