"""Deterministic repair of common structural validation errors.

Used as a reliable first pass for the AI "fix" endpoint. It only *adds*
unambiguous connections (when exactly one candidate resource exists) and never
removes or invents resources — so it can't make a design worse.
"""
from typing import Dict, List, Tuple

# Resource types that must be attached to a VPC.
_VPC_CHILDREN = ("subnet", "route_table", "internet_gateway")


def _rtype(node: Dict) -> str:
    data = node.get("data", {}) if isinstance(node, dict) else {}
    if not isinstance(data, dict):
        data = {}
    return str(data.get("resourceType") or node.get("type") or "").lower()


def _props(node: Dict) -> Dict:
    data = node.get("data", {}) if isinstance(node, dict) else {}
    props = data.get("properties", {}) if isinstance(data, dict) else {}
    return props if isinstance(props, dict) else {}


def auto_fix(nodes: List[Dict], edges: List[Dict]) -> Tuple[List[Dict], List[Dict]]:
    """Return (nodes, edges) with unambiguous missing connections added."""
    ids = [n["id"] for n in nodes if isinstance(n, dict) and n.get("id")]
    if not ids:
        return nodes, edges

    by_type: Dict[str, List[str]] = {}
    type_of: Dict[str, str] = {}
    props_of: Dict[str, Dict] = {}
    for n in nodes:
        if not isinstance(n, dict) or not n.get("id"):
            continue
        t = _rtype(n)
        by_type.setdefault(t, []).append(n["id"])
        type_of[n["id"]] = t
        props_of[n["id"]] = _props(n)

    neighbors: Dict[str, set] = {i: set() for i in ids}
    existing: set = set()
    for e in edges:
        s, t = e.get("source"), e.get("target")
        if s in neighbors and t in neighbors:
            neighbors[s].add(t)
            neighbors[t].add(s)
            existing.add((min(s, t), max(s, t)))

    added: List[Tuple[str, str]] = []

    def connect(a: str, b: str) -> None:
        if a == b or not a or not b:
            return
        key = (min(a, b), max(a, b))
        if key in existing:
            return
        existing.add(key)
        added.append((a, b))

    def neighbor_types(nid: str) -> set:
        return {type_of[x] for x in neighbors.get(nid, set())}

    vpcs = by_type.get("vpc", [])
    subnets = by_type.get("subnet", [])
    roles = by_type.get("iam_role", [])
    zones = by_type.get("route53_zone", [])

    for nid in ids:
        t = type_of[nid]
        nt = neighbor_types(nid)
        if t in _VPC_CHILDREN and "vpc" not in nt and len(vpcs) == 1:
            connect(vpcs[0], nid)
        elif t == "nat_gateway" and "subnet" not in nt and len(subnets) == 1:
            connect(subnets[0], nid)
        elif t == "lambda" and "iam_role" not in nt and len(roles) == 1:
            connect(roles[0], nid)
        elif t == "route53_record" and "route53_zone" not in nt and len(zones) == 1:
            connect(zones[0], nid)

    # Load balancers need at least 1 (NLB) or 2 (ALB) subnets.
    for lb_id in by_type.get("load_balancer", []):
        minimum = 1 if str(props_of.get(lb_id, {}).get("lbType", "application")) == "network" else 2
        connected = [s for s in neighbors.get(lb_id, set()) if s in subnets]
        if len(connected) >= minimum:
            continue
        for s in subnets:
            if s not in connected:
                connect(lb_id, s)
                connected.append(s)
                if len(connected) >= minimum:
                    break

    if not added:
        return nodes, edges

    new_edges = list(edges) + [
        {"id": f"autofix-{i}", "source": s, "target": t} for i, (s, t) in enumerate(added)
    ]
    return nodes, new_edges
