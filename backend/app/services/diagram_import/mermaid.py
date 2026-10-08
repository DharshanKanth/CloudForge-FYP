"""Deterministic Mermaid flowchart importer.

Handles the common ``flowchart``/``graph`` forms: labelled nodes
(``A[Web Server]``, ``B[(Database)]`, ``C((Cache))``), edges
(``A --> B``, ``A -.-> B``, ``A ==> B & C``) and ``subgraph`` blocks (mapped to
VPC/subnet containers when their title names one). No AI is involved.
"""
import re
from typing import Dict, List, Optional, Tuple

from app.services.diagram_import.mapping import CONTAINER_TYPES, classify_label
from app.services.diagram_import.model import ParsedDiagram, ParsedEdge, ParsedNode

_LABEL = r"\(\(.*?\)\)|\[\[.*?\]\]|\[\(.*?\)\]|\[/.*?/\]|\[[^\]]*\]|\([^)]*\)|\{[^}]*\}"
_TOKEN_RE = re.compile(rf"^\s*([A-Za-z_][\w-]*)\s*({_LABEL})?")
_EDGE_OP = re.compile(
    r"\s*(?:<-->|-.->|-->|==>|--x|--o|===|---|--|\.\.)\s*(?:\|[^|]*\|\s*)?"
)
_SKIP_LINE = re.compile(
    r"^(flowchart|graph|classDef|class|click|linkStyle|style|direction)\b", re.I
)


def _strip_brackets(text: str) -> str:
    s = (text or "").strip()
    s = s.strip("\"'")
    s = re.sub(r"^[\[\{\(]+", "", s)
    s = re.sub(r"[\]\}\)]+$", "", s)
    s = re.sub(r"<br\s*/?>", " ", s, flags=re.I)
    return s.strip().strip("\"'")


def _parse_subgraph(expr: str) -> Tuple[str, str]:
    expr = expr.strip()
    match = re.match(r"^([A-Za-z_][\w-]*)\s*(.*)$", expr)
    if match and match.group(2).strip():
        sid, rest = match.group(1), match.group(2).strip()
        title = _strip_brackets(rest)
    elif match and not expr.startswith(('"', "'")):
        sid = match.group(1)
        title = sid
    else:
        title = _strip_brackets(expr)
        sid = "sub_" + re.sub(r"\W+", "_", title.lower()).strip("_")
    return sid or "sub", title or sid


def parse_mermaid(content: str) -> ParsedDiagram:
    labels: Dict[str, str] = {}
    order: List[str] = []
    edges_raw: List[Tuple[str, str]] = []
    membership: Dict[str, str] = {}
    stack: List[Optional[str]] = []

    def note(nid: str, label: str) -> None:
        if nid not in labels:
            order.append(nid)
            labels[nid] = ""
        if label:
            labels[nid] = label
        for container in reversed(stack):
            if container:
                membership[nid] = container
                break

    for raw_line in re.split(r"[\n;]+", content):
        line = raw_line.strip()
        if not line or line.startswith("%%"):
            continue
        if line.startswith("subgraph"):
            sid, title = _parse_subgraph(line[len("subgraph"):])
            if classify_label(title) in CONTAINER_TYPES:
                note(sid, title)
                stack.append(sid)
            else:
                stack.append(None)
            continue
        if line == "end":
            if stack:
                stack.pop()
            continue
        if _SKIP_LINE.match(line):
            continue

        groups: List[List[str]] = []
        for part in _EDGE_OP.split(line):
            if not part.strip():
                continue
            ids: List[str] = []
            for segment in part.split("&"):
                match = _TOKEN_RE.match(segment)
                if not match:
                    continue
                nid = match.group(1)
                label = _strip_brackets(match.group(2)) if match.group(2) else ""
                note(nid, label)
                ids.append(nid)
            if ids:
                groups.append(ids)

        for i in range(len(groups) - 1):
            for source in groups[i]:
                for target in groups[i + 1]:
                    if source != target:
                        edges_raw.append((source, target))

    nodes: List[ParsedNode] = []
    unrecognized: List[Tuple[str, str]] = []
    for nid in order:
        label = labels[nid]
        rtype = classify_label(label) if label else None
        if rtype:
            nodes.append(ParsedNode(id=nid, resource_type=rtype, label=label or rtype))
        elif label:
            unrecognized.append((label, "Not a supported AWS resource type"))

    node_ids = {n.id for n in nodes}
    edges: List[ParsedEdge] = []
    for nid, container in membership.items():
        if nid in node_ids and container in node_ids and nid != container:
            edges.append(ParsedEdge(source=container, target=nid))
    for s, t in edges_raw:
        if s in node_ids and t in node_ids and s != t:
            edges.append(ParsedEdge(source=s, target=t))

    warnings: List[str] = []
    if unrecognized:
        warnings.append(
            f"{len(unrecognized)} element(s) were not recognised and were skipped."
        )
    if not nodes:
        warnings.append("No supported AWS resources were found in the Mermaid diagram.")

    return ParsedDiagram(nodes=nodes, edges=edges, unrecognized=unrecognized, warnings=warnings)
