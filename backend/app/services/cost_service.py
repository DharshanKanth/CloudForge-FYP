"""Rough monthly cost estimation for AWS architectures.

Static, region-agnostic USD estimates — an order-of-magnitude guide that
highlights the big cost drivers (NAT, ALB, RDS, EC2, Redshift, …), not a
billing API. Values assume on-demand pricing in a US region and call out
Free-Tier-eligible resources separately.
"""
from typing import Dict, List

HOURS_PER_MONTH = 730

# Flat monthly USD by resource type (0 = Free Tier / negligible at demo scale).
FLAT_MONTHLY: Dict[str, float] = {
    "vpc": 0.0,
    "subnet": 0.0,
    "internet_gateway": 0.0,
    "route_table": 0.0,
    "security_group": 0.0,
    "iam_role": 0.0,
    "lambda": 0.0,
    "s3": 0.0,
    "dynamodb": 0.0,
    "api_gateway": 0.0,
    "cloudfront": 0.0,
    "route53_zone": 0.50,
    "route53_record": 0.0,
    "sqs": 0.0,
    "sns": 0.0,
    "step_function": 0.0,
    "ecr_repository": 0.0,
    "ecs_cluster": 0.0,
    "cloudwatch_log_group": 0.50,
    "cloudwatch_alarm": 0.10,
    "ebs_volume": 0.0,  # priced per GB below
    "efs": 0.0,         # priced per GB below
    "elastic_ip": 0.0,  # free while attached
}

EC2_HOURLY: Dict[str, float] = {
    "t3.micro": 0.0, "t2.micro": 0.0,  # Free Tier
    "t3.small": 0.0208, "t2.small": 0.023, "t3.medium": 0.0416, "t2.medium": 0.0464,
    "t2.large": 0.0928, "t3.large": 0.0832, "m5.large": 0.096, "c5.large": 0.085,
}
RDS_MONTHLY: Dict[str, float] = {
    "db.t3.micro": 0.0, "db.t2.micro": 0.0,  # Free Tier (single-AZ)
    "db.t3.small": 26.0, "db.t3.medium": 52.0, "db.r5.large": 175.0,
}
ELASTICACHE_MONTHLY: Dict[str, float] = {
    "cache.t3.micro": 12.0, "cache.t3.small": 24.0, "cache.t3.medium": 48.0,
    "cache.m5.large": 110.0, "cache.m5.xlarge": 220.0, "cache.r5.large": 150.0,
}
REDSHIFT_MONTHLY: Dict[str, float] = {
    "dc2.large": 180.0, "dc2.8xlarge": 2880.0,
    "ra3.xlplus": 1030.0, "ra3.4xlargeplus": 4100.0, "ra3.16xlargeplus": 16400.0,
}
EBS_GB_RATE: Dict[str, float] = {
    "gp3": 0.08, "gp2": 0.10, "io1": 0.125, "io2": 0.125, "st1": 0.045, "sc1": 0.015,
}
NAT_GATEWAY_MONTHLY = 32.40
ALB_MONTHLY = 16.20
KINESIS_SHARD_MONTHLY = 10.95
KMS_KEY_MONTHLY = 1.00
SECRETS_MANAGER_MONTHLY = 0.40
EFS_GB_MONTHLY = 0.30
EFS_ASSUMED_GB = 5.0


def _num(value, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _estimate_one(rtype: str, props: Dict) -> (float, str):
    if rtype == "ec2":
        itype = str(props.get("instanceType", "t3.micro"))
        cost = EC2_HOURLY.get(itype, 0.05) * HOURS_PER_MONTH
        note = "Free Tier" if cost == 0 else f"{itype} on-demand"
        return cost, note
    if rtype == "rds":
        iclass = str(props.get("instanceClass", "db.t3.micro"))
        base = RDS_MONTHLY.get(iclass, 50.0)
        storage = _num(props.get("storage"), 20.0) * EBS_GB_RATE.get("gp2", 0.10)
        cost = base + storage + (base if props.get("multiAz") else 0.0)
        note = "Free Tier (single-AZ)" if base == 0 and not props.get("multiAz") else f"{iclass}, {int(storage)}GB"
        return cost, note
    if rtype == "aurora":
        return 0.0, "cluster only — add an instance to serve traffic"
    if rtype == "redshift":
        nodes = max(1, int(_num(props.get("numberOfNodes"), 2)))
        ntype = str(props.get("nodeType", "dc2.large"))
        return REDSHIFT_MONTHLY.get(ntype, 180.0) * nodes, f"{ntype} x{nodes}"
    if rtype == "elasticache":
        ntype = str(props.get("nodeType", "cache.t3.micro"))
        nodes = max(1, int(_num(props.get("numCacheNodes"), 1)))
        return ELASTICACHE_MONTHLY.get(ntype, 12.0) * nodes, f"{ntype} x{nodes}"
    if rtype == "load_balancer":
        return ALB_MONTHLY, "ALB (fixed hourly)"
    if rtype == "nat_gateway":
        return NAT_GATEWAY_MONTHLY, "fixed hourly"
    if rtype == "ebs_volume":
        size = _num(props.get("size"), 8.0)
        vtype = str(props.get("volumeType", "gp3"))
        return size * EBS_GB_RATE.get(vtype, 0.08), f"{int(size)}GB {vtype}"
    if rtype == "efs":
        return EFS_ASSUMED_GB * EFS_GB_MONTHLY, f"~{int(EFS_ASSUMED_GB)}GB provisioned"
    if rtype == "kinesis_stream":
        shards = max(1, int(_num(props.get("shardCount"), 1)))
        return KINESIS_SHARD_MONTHLY * shards, f"{shards} shard(s)"
    if rtype == "kms_key":
        return KMS_KEY_MONTHLY, "per key"
    if rtype == "secretsmanager":
        return SECRETS_MANAGER_MONTHLY, "per secret"
    return FLAT_MONTHLY.get(rtype, 0.0), ""


def estimate(nodes: List[Dict]) -> Dict:
    items: List[Dict] = []
    total = 0.0
    for node in nodes or []:
        if not isinstance(node, dict):
            continue
        data = node.get("data", {}) if isinstance(node.get("data"), dict) else {}
        rtype = str(data.get("resourceType") or node.get("type", "unknown")).lower()
        props = data.get("properties", {}) if isinstance(data.get("properties"), dict) else {}
        cost, note = _estimate_one(rtype, props)
        total += cost
        items.append({
            "resource_id": node.get("id"),
            "resource_type": rtype,
            "label": props.get("name") or props.get("identifier") or props.get("bucketName") or props.get("functionName") or node.get("id"),
            "monthly_cost": round(cost, 2),
            "note": note,
        })
    items.sort(key=lambda i: i["monthly_cost"], reverse=True)
    return {
        "currency": "USD",
        "monthly_total": round(total, 2),
        "items": items,
        "disclaimer": (
            "Rough on-demand estimates in a US region; Free-Tier resources are $0 "
            "within their limits. Not a billing quote."
        ),
    }
