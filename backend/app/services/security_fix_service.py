"""Deterministic security hardening for common findings.

Property-only changes for the unambiguous, high/medium findings the security
review raises — it never removes resources or edges, so it can't make a design
unsafe. Anything it can't fix is left for the user (or the AI reviewer).
"""
from copy import deepcopy
from typing import Dict, List, Tuple

OPEN_CIDRS = {"0.0.0.0/0", "::/0"}
_PRIVATE_SSH_CIDR = "10.0.0.0/8"


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
    """Return (nodes, edges) with safe security hardening applied."""
    out: List[Dict] = []
    for n in nodes:
        if not isinstance(n, dict) or not n.get("id"):
            out.append(n)
            continue
        rtype = _rtype(n)
        props = dict(_props(n))
        changed = False

        if rtype == "security_group":
            # SSH open to the internet -> restrict to a private range.
            if props.get("allowSsh") and str(props.get("sshCidr", "")) in OPEN_CIDRS:
                props["sshCidr"] = _PRIVATE_SSH_CIDR
                changed = True
        elif rtype == "s3":
            # Versioning off -> on (protects against accidental deletes).
            if not props.get("versioning", False):
                props["versioning"] = True
                changed = True

        if changed:
            clone = deepcopy(n)
            clone.setdefault("data", {})
            clone["data"]["properties"] = props
            out.append(clone)
        else:
            out.append(n)

    # Edges are untouched by property hardening.
    return out, edges
