"""
Deterministic validation service for cloud architecture designs.
Validates resource configurations without AI — AI can be plugged in later
by adding a new validator class that implements the same interface.
"""
import re
from typing import List, Dict, Any
from app.schemas.architecture import ValidationResult, ValidationIssue


CIDR_PATTERN = re.compile(
    r"^(\d{1,3}\.){3}\d{1,3}/\d{1,2}$"
)

REQUIRED_FIELDS: Dict[str, List[str]] = {
    "vpc": ["name", "cidr"],
    "subnet": ["name", "cidr"],
    "ec2": ["name", "instanceType"],
    "s3": ["bucketName"],
    "rds": ["identifier", "engine", "instanceClass"],
    "security_group": ["name"],
    "load_balancer": ["name"],
}

VALID_EC2_TYPES = [
    "t2.micro", "t2.small", "t2.medium", "t2.large",
    "t3.micro", "t3.small", "t3.medium", "t3.large",
    "m5.large", "m5.xlarge", "c5.large", "r5.large",
]


def validate_architecture(nodes: List[Dict], edges: List[Dict]) -> ValidationResult:
    issues: List[ValidationIssue] = []

    if not nodes:
        issues.append(ValidationIssue(
            level="warning",
            message="Canvas is empty. Add resources to your architecture.",
        ))
        return ValidationResult(valid=True, issues=issues)

    node_ids = {n["id"] for n in nodes}
    node_map = {n["id"]: n for n in nodes}

    # Build adjacency: what each node connects to
    edge_targets: Dict[str, List[str]] = {}
    edge_sources: Dict[str, List[str]] = {}
    for edge in edges:
        src = edge.get("source")
        tgt = edge.get("target")
        if src and tgt:
            edge_targets.setdefault(src, []).append(tgt)
            edge_sources.setdefault(tgt, []).append(src)

    # Build VPC and Subnet sets
    vpc_ids = {n["id"] for n in nodes if _get_resource_type(n) == "vpc"}
    subnet_ids = {n["id"] for n in nodes if _get_resource_type(n) == "subnet"}

    # Track names for uniqueness check
    resource_names: Dict[str, List[str]] = {}

    for node in nodes:
        nid = node["id"]
        ntype = _get_resource_type(node)
        props = node.get("data", {}).get("properties", {})

        # Required fields
        required = REQUIRED_FIELDS.get(ntype, [])
        for field in required:
            value = props.get(field, "")
            if not value or str(value).strip() == "":
                issues.append(ValidationIssue(
                    level="error",
                    resource_id=nid,
                    resource_type=ntype,
                    message=f"{ntype.upper()} '{_get_label(node)}': field '{field}' is required.",
                    field=field,
                ))

        # CIDR validation
        cidr_field = props.get("cidr", "")
        if ntype in ("vpc", "subnet") and cidr_field:
            if not _is_valid_cidr(cidr_field):
                issues.append(ValidationIssue(
                    level="error",
                    resource_id=nid,
                    resource_type=ntype,
                    message=f"{ntype.upper()} '{_get_label(node)}': CIDR '{cidr_field}' is not valid.",
                    field="cidr",
                ))

        # EC2 instance type
        if ntype == "ec2":
            inst_type = props.get("instanceType", "")
            if inst_type and inst_type not in VALID_EC2_TYPES:
                issues.append(ValidationIssue(
                    level="warning",
                    resource_id=nid,
                    resource_type=ntype,
                    message=f"EC2 '{_get_label(node)}': instance type '{inst_type}' is uncommon. Verify it's valid.",
                    field="instanceType",
                ))

        # Subnet should connect to a VPC
        if ntype == "subnet":
            connected_vpcs = [s for s in edge_sources.get(nid, []) + edge_targets.get(nid, [])
                              if s in vpc_ids]
            if not connected_vpcs:
                issues.append(ValidationIssue(
                    level="warning",
                    resource_id=nid,
                    resource_type=ntype,
                    message=f"Subnet '{_get_label(node)}' is not connected to any VPC.",
                ))

        # EC2 should connect to a Subnet
        if ntype == "ec2":
            connected_subnets = [s for s in edge_sources.get(nid, []) + edge_targets.get(nid, [])
                                 if s in subnet_ids]
            if not connected_subnets:
                issues.append(ValidationIssue(
                    level="warning",
                    resource_id=nid,
                    resource_type=ntype,
                    message=f"EC2 '{_get_label(node)}' is not connected to any Subnet.",
                ))

        # RDS should connect to a Subnet
        if ntype == "rds":
            connected_subnets = [s for s in edge_sources.get(nid, []) + edge_targets.get(nid, [])
                                 if s in subnet_ids]
            if not connected_subnets:
                issues.append(ValidationIssue(
                    level="warning",
                    resource_id=nid,
                    resource_type=ntype,
                    message=f"RDS '{_get_label(node)}' is not connected to any Subnet.",
                ))

        # Track name uniqueness
        name = props.get("name") or props.get("bucketName") or props.get("identifier") or ""
        if name:
            resource_names.setdefault(name.strip(), []).append(nid)

    # Duplicate name check
    for name, ids in resource_names.items():
        if len(ids) > 1:
            issues.append(ValidationIssue(
                level="warning",
                message=f"Resource name '{name}' is used by {len(ids)} resources. Names should be unique.",
            ))

    has_errors = any(i.level == "error" for i in issues)
    return ValidationResult(valid=not has_errors, issues=issues)


def _get_resource_type(node: Dict) -> str:
    return node.get("data", {}).get("resourceType", node.get("type", "unknown")).lower()


def _get_label(node: Dict) -> str:
    props = node.get("data", {}).get("properties", {})
    return (
        props.get("name")
        or props.get("bucketName")
        or props.get("identifier")
        or node.get("data", {}).get("label", node["id"])
    )


def _is_valid_cidr(cidr: str) -> bool:
    if not CIDR_PATTERN.match(cidr):
        return False
    parts = cidr.split("/")
    prefix = int(parts[1])
    if prefix < 0 or prefix > 32:
        return False
    octets = parts[0].split(".")
    return all(0 <= int(o) <= 255 for o in octets)
