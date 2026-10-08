"""Deterministic draw.io / diagrams.net (.drawio, .xml) importer.

Reads both uncompressed ``<mxGraphModel>`` pages and the compressed pages that
draw.io emits by default (URL-encoded base64 of a raw-deflate stream). Cells are
classified from their AWS icon style or label; draw.io parent/child hierarchy is
converted into the containment edges the builder canvas understands.
"""
import base64
import html
import re
import urllib.parse
import xml.etree.ElementTree as ET
import zlib
from typing import Dict, List, Optional, Tuple

from app.services.diagram_import.mapping import (
    CONTAINER_TYPES,
    classify_cell,
    is_ignorable_group,
)
from app.services.diagram_import.model import DiagramParseError, ParsedDiagram, ParsedEdge, ParsedNode


def _inner_diagram(content: str) -> str:
    match = re.search(r"<diagram[^>]*>(.*?)</diagram>", content, re.DOTALL)
    return match.group(1).strip() if match else content.strip()


def decode_drawio(content: str) -> str:
    """Return the (uncompressed) ``<mxGraphModel>`` XML for a draw.io file."""
    inner = _inner_diagram(content)
    if inner.startswith("<"):
        return inner
    raw = urllib.parse.unquote(inner)
    try:
        data = base64.b64decode(raw)
    except Exception as exc:  # noqa: BLE001 - normalize to a clear parse error
        raise DiagramParseError("Could not decode the draw.io diagram (invalid base64).") from exc
    for wbits in (-15, 15, 47):  # raw deflate, zlib, gzip
        try:
            return zlib.decompress(data, wbits).decode("utf-8")
        except zlib.error:
            continue
    raise DiagramParseError(
        "Could not decode the draw.io diagram. Re-export it as XML "
        "(Extras → Edit Diagram) and try again."
    )


def _clean_label(value: Optional[str]) -> str:
    text = html.unescape(re.sub(r"<[^>]+>", " ", value or ""))
    return re.sub(r"\s+", " ", text).strip()


def _num(value: Optional[str]) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def parse_drawio(content: str) -> ParsedDiagram:
    xml = decode_drawio(content)
    try:
        root = ET.fromstring(xml)
    except ET.ParseError as exc:
        raise DiagramParseError(f"Could not parse draw.io XML: {exc}") from exc

    cells: Dict[str, ET.Element] = {
        cell.get("id"): cell
        for cell in root.iter("mxCell")
        if cell.get("id")
    }
    geom: Dict[str, Dict[str, float]] = {}
    for cid, cell in cells.items():
        g = cell.find("mxGeometry")
        if g is None:
            g = next(iter(cell.iter("mxGeometry")), None)
        if g is not None:
            geom[cid] = {
                "x": _num(g.get("x")), "y": _num(g.get("y")),
                "width": _num(g.get("width")), "height": _num(g.get("height")),
            }

    resources: Dict[str, str] = {}
    unrecognized: List[Tuple[str, str]] = []
    for cid, cell in cells.items():
        if cell.get("vertex") != "1":
            continue
        style = cell.get("style") or ""
        label = _clean_label(cell.get("value"))
        if is_ignorable_group(style):
            continue
        rtype = classify_cell(style, label)
        if rtype:
            resources[cid] = rtype
        elif label and _is_reportable_shape(style, geom.get(cid, {})):
            unrecognized.append((label, "Not a supported AWS resource type"))

    memo: Dict[str, Tuple[float, float]] = {}

    def absolute(cid: str) -> Tuple[float, float]:
        if cid in memo:
            return memo[cid]
        g = geom.get(cid, {"x": 0.0, "y": 0.0})
        x, y = g.get("x", 0.0), g.get("y", 0.0)
        parent = cells[cid].get("parent")
        if parent and parent in cells and parent not in ("0", "1"):
            px, py = absolute(parent)
            x += px
            y += py
        memo[cid] = (x, y)
        return memo[cid]

    nodes: List[ParsedNode] = []
    for cid, rtype in resources.items():
        label = _clean_label(cells[cid].get("value")) or rtype
        x, y = absolute(cid)
        nodes.append(ParsedNode(
            id=cid, resource_type=rtype, label=label,
            position={"x": x, "y": y},
        ))

    edges: List[ParsedEdge] = []
    # Containment from draw.io hierarchy: nearest resource ancestor that is a
    # container (VPC/subnet) becomes the parent edge.
    for cid in resources:
        parent = cells[cid].get("parent")
        while parent and parent in cells and parent not in ("0", "1"):
            ptype = resources.get(parent)
            if ptype:
                if ptype in CONTAINER_TYPES:
                    edges.append(ParsedEdge(source=parent, target=cid))
                break
            parent = cells[parent].get("parent")

    # Explicit drawn connectors.
    for cell in cells.values():
        if cell.get("edge") != "1":
            continue
        s, t = cell.get("source"), cell.get("target")
        if s in resources and t in resources and s != t:
            edges.append(ParsedEdge(source=s, target=t))

    warnings: List[str] = []
    if len(re.findall(r"<diagram[^>]*>", content)) > 1:
        warnings.append("The draw.io file has multiple pages; only the first was imported.")
    if unrecognized:
        warnings.append(
            f"{len(unrecognized)} element(s) were not recognised and were skipped."
        )

    return ParsedDiagram(nodes=nodes, edges=edges, unrecognized=unrecognized, warnings=warnings)


def _is_reportable_shape(style: str, geometry: Dict[str, float]) -> bool:
    s = (style or "").lower()
    if any(token in s for token in ("text", "group", "image", "label")):
        return False
    return geometry.get("width", 0) > 0 and geometry.get("height", 0) > 0
