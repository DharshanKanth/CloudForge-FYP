"""Deterministic security review of an architecture design.

Static checks over the node/edge graph — no AI, no cloud calls. Returns a list
of findings with a severity and a concrete recommendation, so the UI can show
the risky parts of a design before it is deployed.
"""
from typing import Dict, List

SEVERITY_ORDER = {"high": 0, "medium": 1, "low": 2, "info": 3}

OPEN_CIDRS = {"0.0.0.0/0", "::/0"}
SENSITIVE_PORTS = {"ssh": 22}


def _rtype(node: Dict) -> str:
    data = node.get("data", {}) if isinstance(node, dict) else {}
    if not isinstance(data, dict):
        data = {}
    return str(data.get("resourceType") or node.get("type", "unknown")).lower()


def _props(node: Dict) -> Dict:
    data = node.get("data", {}) if isinstance(node, dict) else {}
    props = data.get("properties", {}) if isinstance(data, dict) else {}
    return props if isinstance(props, dict) else {}


def _label(node: Dict) -> str:
    props = _props(node)
    return str(
        props.get("name") or props.get("bucketName") or props.get("identifier")
        or props.get("functionName") or props.get("tableName") or node.get("id", "?")
    )


def analyze(nodes: List[Dict], edges: List[Dict]) -> Dict:
    nodes = [n for n in (nodes or []) if isinstance(n, dict) and n.get("id")]
    edges = edges or []
    findings: List[Dict] = []

    def add(severity, title, recommendation, resource_id=None, resource_type=None):
        findings.append({
            "severity": severity,
            "title": title,
            "recommendation": recommendation,
            "resource_id": resource_id,
            "resource_type": resource_type,
        })

    types = {_rtype(n) for n in nodes}

    for node in nodes:
        rtype = _rtype(node)
        props = _props(node)
        nid = node.get("id")
        label = _label(node)

        if rtype == "security_group":
            if props.get("allowSsh") and str(props.get("sshCidr", "")) in OPEN_CIDRS:
                add("high", f"Security Group '{label}' exposes SSH (22) to the internet",
                    "Restrict the SSH CIDR to a bastion/VPN range or disable SSH.",
                    nid, rtype)
            web_cidr = str(props.get("webCidr", "0.0.0.0/0"))
            if (props.get("allowHttp", True) or props.get("allowHttps", True)) and web_cidr in OPEN_CIDRS:
                add("low", f"Security Group '{label}' allows web traffic from anywhere",
                    "Expected for a public site; scope the CIDR if the app is internal.",
                    nid, rtype)
            if props.get("allowAllOutbound", True):
                add("low", f"Security Group '{label}' allows all outbound traffic",
                    "Consider restricting egress to known endpoints.",
                    nid, rtype)

        elif rtype == "s3" and not props.get("versioning", False):
            add("medium", f"S3 bucket '{label}' has versioning disabled",
                "Enable versioning to protect against accidental deletes/overwrites.",
                nid, rtype)

        elif rtype == "rds" and not props.get("multiAz", False):
            add("info", f"RDS instance '{label}' is single-AZ",
                "Use Multi-AZ for production high availability (adds cost).",
                nid, rtype)

        elif rtype == "load_balancer" and not props.get("internal", False):
            add("info", f"Load balancer '{label}' is internet-facing",
                "Confirm it is intentionally public; make it internal if not.",
                nid, rtype)

        elif rtype == "subnet" and props.get("mapPublicIp", True):
            add("info", f"Subnet '{label}' auto-assigns public IPs",
                "Keep compute in private subnets behind the load balancer where possible.",
                nid, rtype)

        elif rtype == "ec2" and props.get("associatePublicIp", True):
            add("info", f"EC2 instance '{label}' gets a public IP",
                "Prefer private instances reached through the load balancer.",
                nid, rtype)

    # Encryption-at-rest: if sensitive resources exist but no KMS key is used.
    if types & {"s3", "rds", "ebs_volume", "lambda"} and "kms_key" not in types:
        add("low", "No customer-managed KMS key in the design",
            "Add a KMS key and connect it to data resources for control over encryption keys.")

    # Monitoring: compute/data resources without any CloudWatch alarm.
    if types & {"ec2", "rds", "load_balancer"} and "cloudwatch_alarm" not in types:
        add("info", "No CloudWatch alarms configured",
            "Add alarms (e.g. CPU, latency) so failures are noticed.")

    findings.sort(key=lambda f: SEVERITY_ORDER.get(f["severity"], 9))
    counts = {level: sum(1 for f in findings if f["severity"] == level)
              for level in ("high", "medium", "low", "info")}
    return {"findings": findings, "counts": counts}
