"""Deterministic repair of common validation errors.

Used as a reliable first pass for the AI "fix" endpoint. It:
  * removes edges whose relationship is invalid (or is a self-loop),
  * de-duplicates connections (including reciprocal pairs),
  * fills required fields that are missing with sensible defaults,
  * adds unambiguous missing connections (when exactly one candidate exists).

It never removes or invents *resources*, so it cannot make a design worse.
"""
from copy import deepcopy
from typing import Dict, List, Tuple

from app.services.validation_service import REQUIRED_FIELDS, SUPPORTED_RELATIONSHIPS

# Resource types that must be attached to a VPC.
_VPC_CHILDREN = ("subnet", "route_table", "internet_gateway")

# Required fields that are "names" — default to the node id (always unique).
_NAME_FIELDS = {
    "name", "bucketName", "identifier", "clusterIdentifier",
    "functionName", "tableName",
}

# Defaults for other required fields (Free-Tier friendly where relevant).
_FIELD_DEFAULTS: Dict[str, object] = {
    "cidr": "10.0.0.0/16",
    "instanceType": "t3.micro",
    "amiId": "",
    "engine": "mysql",
    "engineVersion": "8.0",
    "instanceClass": "db.t3.micro",
    "runtime": "python3.12",
    "handler": "lambda_function.lambda_handler",
    "hashKey": "id",
    "hashKeyType": "S",
    "billingMode": "PAY_PER_REQUEST",
    "domainName": "example.com",
    "recordType": "A",
    "protocol": "HTTP",
    "size": 8,
    "volumeType": "gp3",
    "nodeType": "cache.t3.micro",
    "numberOfNodes": 2,
    "shardCount": 1,
    "retentionDays": 30,
    "service": "lambda.amazonaws.com",
    "metric": "CPUUtilization",
    "threshold": 80,
    "description": "Managed by CloudForge",
}


def _rtype(node: Dict) -> str:
    data = node.get("data", {}) if isinstance(node, dict) else {}
    if not isinstance(data, dict):
        data = {}
    return str(data.get("resourceType") or node.get("type") or "").lower()


def _props(node: Dict) -> Dict:
    data = node.get("data", {}) if isinstance(node, dict) else {}
    props = data.get("properties", {}) if isinstance(data, dict) else {}
    return props if isinstance(props, dict) else {}


def _fill_required(nid: str, rtype: str, props: Dict) -> Tuple[Dict, bool]:
    changed = False
    for field in REQUIRED_FIELDS.get(rtype, []):
        if props.get(field) not in (None, "", []):
            continue
        if field in _NAME_FIELDS:
            props[field] = nid
        elif rtype == "subnet" and field == "cidr":
            props[field] = "10.0.1.0/24"
        elif field in _FIELD_DEFAULTS:
            props[field] = _FIELD_DEFAULTS[field]
        else:
            props[field] = nid  # last resort: satisfy "non-empty"
        changed = True
    return props, changed


def _clean_edges(type_of: Dict[str, str], edges: List[Dict]) -> List[Dict]:
    """Drop invalid/self/duplicate edges, keeping one per unordered pair."""
    seen = set()
    out: List[Dict] = []
    for e in edges:
        if not isinstance(e, dict):
            continue
        s, t = e.get("source"), e.get("target")
        if s not in type_of or t not in type_of or s == t:
            continue
        if frozenset((type_of[s], type_of[t])) not in SUPPORTED_RELATIONSHIPS:
            continue
        key = (s, t) if s < t else (t, s)
        if key in seen:
            continue
        seen.add(key)
        out.append({"id": e.get("id") or f"edge-{len(out)}", "source": s, "target": t})
    return out


def auto_fix(nodes: List[Dict], edges: List[Dict]) -> Tuple[List[Dict], List[Dict]]:
    """Return (nodes, edges) with common validation errors repaired."""
    type_of: Dict[str, str] = {}
    by_type: Dict[str, List[str]] = {}
    nodes_out: List[Dict] = []

    for n in nodes:
        if not isinstance(n, dict) or not n.get("id"):
            nodes_out.append(n)
            continue
        nid = n["id"]
        rtype = _rtype(n)
        type_of[nid] = rtype
        by_type.setdefault(rtype, []).append(nid)
        props = dict(_props(n))
        props, _ = _fill_required(nid, rtype, props)
        clone = deepcopy(n)
        clone.setdefault("data", {})
        clone["data"]["properties"] = props
        nodes_out.append(clone)

    cleaned = _clean_edges(type_of, edges)

    neighbors: Dict[str, set] = {i: set() for i in type_of}
    existing: set = set()
    for e in cleaned:
        s, t = e["source"], e["target"]
        neighbors[s].add(t)
        neighbors[t].add(s)
        existing.add((min(s, t), max(s, t)))

    added: List[Tuple[str, str]] = []

    def connect(a: str, b: str) -> None:
        if a == b or a not in type_of or b not in type_of:
            return
        if frozenset((type_of[a], type_of[b])) not in SUPPORTED_RELATIONSHIPS:
            return
        key = (min(a, b), max(a, b))
        if key in existing:
            return
        existing.add(key)
        neighbors[a].add(b)
        neighbors[b].add(a)
        added.append((a, b))

    def neighbor_types(nid: str) -> set:
        return {type_of[x] for x in neighbors.get(nid, set())}

    vpcs = by_type.get("vpc", [])
    subnets = by_type.get("subnet", [])
    roles = by_type.get("iam_role", [])
    zones = by_type.get("route53_zone", [])

    for nid in type_of:
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

    for lb_id in by_type.get("load_balancer", []):
        lb_props = _props(next((n for n in nodes_out if n.get("id") == lb_id), {}))
        minimum = 1 if str(lb_props.get("lbType", "application")) == "network" else 2
        connected = [s for s in neighbors.get(lb_id, set()) if s in subnets]
        if len(connected) >= minimum:
            continue
        for s in subnets:
            if s not in connected:
                connect(lb_id, s)
                connected.append(s)
                if len(connected) >= minimum:
                    break

    if added:
        cleaned = cleaned + [
            {"id": f"autofix-{i}", "source": s, "target": t} for i, (s, t) in enumerate(added)
        ]

    return nodes_out, cleaned
