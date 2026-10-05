"""
Deterministic validation service for cloud architecture designs.
Validates resource configurations without AI — AI can be plugged in later
by adding a new validator class that implements the same interface.

Architecture
~~~~~~~~~~~~
The main ``validate_architecture`` entry-point delegates to:

1. **Required-field checks** — generic, driven by the ``REQUIRED_FIELDS`` table.
2. **Per-resource field validators** — looked up from ``RESOURCE_FIELD_VALIDATORS``
   (one function per resource type that knows the enum / range rules).
3. **Structural / topology checks** — ``_validate_structural_requirements``
   enforces connectivity rules (e.g. subnet ↔ VPC, Lambda ↔ IAM role).
4. **Cross-cutting checks** — CIDR overlap, cycle detection, name uniqueness.
"""
import ipaddress
import re
from collections import defaultdict
from typing import List, Dict, Any, Callable, Set, Tuple
from app.schemas.architecture import ValidationResult, ValidationIssue


# ── Constants ────────────────────────────────────────────────────────────────

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
    "internet_gateway": ["name"],
    "route_table": ["name"],
    "nat_gateway": ["name"],
    "lambda": ["functionName", "runtime", "handler"],
    "dynamodb": ["tableName", "hashKey"],
    "iam_role": ["name"],
    # ---- extended resource set (Review 2 showcase) ----
    "cloudfront": ["name"],
    "api_gateway": ["name", "protocol"],
    "route53_zone": ["domainName"],
    "route53_record": ["name", "recordType"],
    "elastic_ip": ["name"],
    "ebs_volume": ["name", "size"],
    "ecr_repository": ["name"],
    "ecs_cluster": ["name"],
    "efs": ["name"],
    "elasticache": ["name", "nodeType", "engine"],
    "aurora": ["identifier", "engine"],
    "redshift": ["clusterIdentifier", "nodeType"],
    "kinesis_stream": ["name", "shardCount"],
    "sqs": ["name"],
    "sns": ["name"],
    "step_function": ["name"],
    "secretsmanager": ["name"],
    "cloudwatch_alarm": ["name", "metric", "threshold"],
    "cloudwatch_log_group": ["name", "retentionDays"],
    "kms_key": ["name", "description"],
}

SUPPORTED_RESOURCE_TYPES = set(REQUIRED_FIELDS)

SUPPORTED_RELATIONSHIPS = {
    frozenset(("vpc", "subnet")), frozenset(("vpc", "internet_gateway")),
    frozenset(("vpc", "route_table")), frozenset(("subnet", "route_table")),
    frozenset(("subnet", "nat_gateway")), frozenset(("subnet", "lambda")),
    frozenset(("vpc", "lambda")),
    frozenset(("ec2", "subnet")), frozenset(("rds", "subnet")),
    frozenset(("security_group", "ec2")), frozenset(("security_group", "rds")),
    frozenset(("security_group", "lambda")), frozenset(("security_group", "load_balancer")),
    frozenset(("load_balancer", "ec2")), frozenset(("load_balancer", "subnet")),
    frozenset(("lambda", "iam_role")),
    frozenset(("lambda", "dynamodb")), frozenset(("dynamodb", "iam_role")),
    frozenset(("ec2", "iam_role")),
    # ---- extended relationships (Review 2 showcase) ----
    frozenset(("lambda", "sqs")), frozenset(("lambda", "sns")),
    frozenset(("sns", "sqs")),
    frozenset(("ec2", "elastic_ip")), frozenset(("ec2", "ebs_volume")),
    frozenset(("ecs_cluster", "ec2")), frozenset(("ecs_cluster", "ecr_repository")),
    frozenset(("api_gateway", "lambda")), frozenset(("api_gateway", "dynamodb")),
    frozenset(("route53_zone", "route53_record")),
    frozenset(("route53_record", "load_balancer")),
    frozenset(("s3", "cloudfront")),
    frozenset(("lambda", "cloudwatch_log_group")),
    frozenset(("kms_key", "s3")), frozenset(("kms_key", "rds")),
    frozenset(("kms_key", "lambda")),
    frozenset(("secretsmanager", "lambda")), frozenset(("secretsmanager", "ec2")),
    frozenset(("step_function", "lambda")),
    frozenset(("kinesis_stream", "lambda")), frozenset(("kinesis_stream", "s3")),
    frozenset(("aurora", "subnet")), frozenset(("redshift", "subnet")),
    frozenset(("elasticache", "subnet")), frozenset(("efs", "subnet")),
    frozenset(("cloudwatch_alarm", "ec2")), frozenset(("cloudwatch_alarm", "rds")),
    frozenset(("cloudwatch_alarm", "load_balancer")),
    frozenset(("vpc", "efs")), frozenset(("vpc", "ecs_cluster")),
}

# ── Enum / value allowlists ─────────────────────────────────────────────────

VALID_LAMBDA_RUNTIMES = {"python3.12", "nodejs22.x", "java21"}
VALID_DYNAMODB_KEY_TYPES = {"S", "N", "B"}
VALID_DYNAMODB_BILLING_MODES = {"PAY_PER_REQUEST", "PROVISIONED"}
VALID_API_GATEWAY_PROTOCOLS = {"REST", "HTTP", "WEBSOCKET"}
VALID_ROUTE53_RECORD_TYPES = {"A", "AAAA", "CNAME", "MX", "NS", "SOA", "SRV", "TXT", "PTR"}
VALID_ELASTICACHE_ENGINES = {"redis", "memcached"}
VALID_AURORA_ENGINES = {"aurora-mysql", "aurora-postgresql"}
VALID_REDSHIFT_NODE_TYPES = {
    "dc2.large", "dc2.8xlarge",
    "ra3.xlplus", "ra3.4xlargeplus", "ra3.16xlargeplus",
}
VALID_ELASTICACHE_NODE_TYPES = {
    "cache.t3.micro", "cache.t3.small", "cache.t3.medium",
    "cache.m5.large", "cache.m5.xlarge", "cache.r5.large",
}
VALID_EBS_VOLUME_TYPES = {"gp2", "gp3", "io1", "io2", "st1", "sc1"}
VALID_KINESIS_SHARD_MIN = 1
VALID_KINESIS_SHARD_MAX = 500
# AWS allows data retention between 24 hours and 8760 hours (365 days).
VALID_KINESIS_RETENTION_MIN = 24
VALID_KINESIS_RETENTION_MAX = 8760
VALID_EBS_SIZE_MIN = 1
VALID_EBS_SIZE_MAX = 16384
VALID_ALARM_METRICS = {
    "CPUUtilization", "MemoryUtilization", "NetworkIn", "NetworkOut",
    "DatabaseConnections", "Latency", "RequestCount",
}
VALID_RETENTION_DAYS = {
    "1", "3", "5", "7", "14", "30", "60", "90", "120", "150",
    "180", "365", "400", "545", "731", "1827", "3653",
}

# EC2 instance type pattern — matches standard AWS naming: {family}{gen}.{size}
EC2_INSTANCE_TYPE_RE = re.compile(
    r"^[a-z][a-z0-9]*\d+\.\w+$"
)


# ════════════════════════════════════════════════════════════════════════════
# Per-resource field validators
# ════════════════════════════════════════════════════════════════════════════
# EC2 instance type pattern — matches standard AWS naming: {family}{gen}.{size}
EC2_INSTANCE_TYPE_RE = re.compile(
    r"^[a-z][a-z0-9]*\d+\.\w+$"
)

# Free-Tier eligible sizes. t3.micro is the only EC2 size that is Free-Tier
# eligible in *every* commercial AWS region. t2.micro is Free-Tier eligible
# only in a subset of regions (e.g. us-east-1) and is rejected by AWS in
# others (e.g. ap-northeast-1) with:
#   InvalidParameterCombination: The specified instance type is not
#   eligible for Free Tier.
FREE_TIER_EC2_TYPES = {"t3.micro", "t2.micro"}
FREE_TIER_RDS_CLASSES = {"db.t3.micro", "db.t2.micro"}
# Free-Tier ECBS allowance per month (gp2/gp3 combined).
FREE_TIER_EBS_GB = 30
# Free-Tier RDS storage allowance (single-AZ db.t2/db.t3.micro).
FREE_TIER_RDS_STORAGE_GB = 20

# Each function has the signature:
#   fn(nid: str, label: str, props: Dict) -> List[ValidationIssue]


def _validate_ec2_fields(nid: str, label: str, props: Dict) -> List[ValidationIssue]:
    issues: List[ValidationIssue] = []
    inst_type = props.get("instanceType", "")
    if inst_type and not EC2_INSTANCE_TYPE_RE.match(inst_type):
        issues.append(ValidationIssue(
            level="warning", resource_id=nid, resource_type="ec2",
            message=(
                f"EC2 '{label}': instance type '{inst_type}' does not match "
                f"standard AWS naming (expected e.g. t3.micro, m5.large)."
            ),
            field="instanceType",
        ))
    # ── Free-Tier eligibility (non-blocking warnings) ────────────────
    elif inst_type and inst_type not in FREE_TIER_EC2_TYPES:
        issues.append(ValidationIssue(
            level="warning", resource_id=nid, resource_type="ec2",
            message=(
                f"EC2 '{label}': instance type '{inst_type}' is not Free-Tier "
                f"eligible. Use 't3.micro' — the only size that is Free-Tier "
                f"eligible in every AWS region."
            ),
            field="instanceType",
        ))
    elif inst_type == "t2.micro":
        issues.append(ValidationIssue(
            level="warning", resource_id=nid, resource_type="ec2",
            message=(
                f"EC2 '{label}': 't2.micro' is Free-Tier eligible only in some "
                f"regions (e.g. us-east-1); AWS rejects it in others (e.g. "
                f"ap-northeast-1) with InvalidParameterCombination. Prefer "
                f"'t3.micro' when deploying to any region."
            ),
            field="instanceType",
        ))
    volume_size = props.get("rootVolumeSize")
    if isinstance(volume_size, (int, float)) and volume_size > FREE_TIER_EBS_GB:
        issues.append(ValidationIssue(
            level="warning", resource_id=nid, resource_type="ec2",
            message=(
                f"EC2 '{label}': root volume size {int(volume_size)} GB exceeds "
                f"the Free-Tier EBS allowance of {FREE_TIER_EBS_GB} GB/month."
            ),
            field="rootVolumeSize",
        ))
    return issues


def _validate_rds_fields(nid: str, label: str, props: Dict) -> List[ValidationIssue]:
    issues: List[ValidationIssue] = []
    inst_class = props.get("instanceClass", "")
    if inst_class and inst_class not in FREE_TIER_RDS_CLASSES:
        issues.append(ValidationIssue(
            level="warning", resource_id=nid, resource_type="rds",
            message=(
                f"RDS '{label}': instance class '{inst_class}' is not Free-Tier "
                f"eligible. Use 'db.t3.micro' for Free-Tier deployment."
            ),
            field="instanceClass",
        ))
    if props.get("multiAz"):
        issues.append(ValidationIssue(
            level="warning", resource_id=nid, resource_type="rds",
            message=(
                f"RDS '{label}': Multi-AZ runs a paid standby instance and is "
                f"not covered by the Free Tier. Disable it for Free-Tier "
                f"deployment."
            ),
            field="multiAz",
        ))
    storage = props.get("storage")
    if isinstance(storage, (int, float)) and storage > FREE_TIER_RDS_STORAGE_GB:
        issues.append(ValidationIssue(
            level="warning", resource_id=nid, resource_type="rds",
            message=(
                f"RDS '{label}': storage {int(storage)} GB exceeds the Free-Tier "
                f"allowance of {FREE_TIER_RDS_STORAGE_GB} GB."
            ),
            field="storage",
        ))
    return issues


def _validate_lambda_fields(nid: str, label: str, props: Dict) -> List[ValidationIssue]:
    issues: List[ValidationIssue] = []
    runtime = props.get("runtime", "")
    if runtime and runtime not in VALID_LAMBDA_RUNTIMES:
        issues.append(ValidationIssue(
            level="error", resource_id=nid, resource_type="lambda",
            message=f"Lambda '{label}': runtime '{runtime}' is not supported.",
            field="runtime",
        ))
    handler = props.get("handler", "")
    if handler and not re.match(r"^[A-Za-z0-9_./-]+\.[A-Za-z0-9_-]+$", handler):
        issues.append(ValidationIssue(
            level="error", resource_id=nid, resource_type="lambda",
            message=f"Lambda '{label}': handler must look like 'module.function'.",
            field="handler",
        ))
    for fld, lo, hi in (("memorySize", 128, 10240), ("timeout", 1, 900)):
        value = props.get(fld)
        if value is not None and (not isinstance(value, (int, float)) or value < lo or value > hi):
            issues.append(ValidationIssue(
                level="error", resource_id=nid, resource_type="lambda",
                message=f"Lambda '{label}': {fld} must be between {lo} and {hi}.",
                field=fld,
            ))
    filename = str(props.get("filename", "") or "")
    if filename and (re.search(r"[\\/]", filename) or ".." in filename):
        issues.append(ValidationIssue(
            level="error", resource_id=nid, resource_type="lambda",
            message=f"Lambda '{label}': filename must be a plain file name.",
            field="filename",
        ))
    elif filename and not filename.lower().endswith(".zip"):
        issues.append(ValidationIssue(
            level="error", resource_id=nid, resource_type="lambda",
            message=f"Lambda '{label}': filename must point to a .zip deployment package.",
            field="filename",
        ))
    return issues


def _validate_dynamodb_fields(nid: str, label: str, props: Dict) -> List[ValidationIssue]:
    issues: List[ValidationIssue] = []
    billing_mode = props.get("billingMode", "PAY_PER_REQUEST")
    if billing_mode not in VALID_DYNAMODB_BILLING_MODES:
        issues.append(ValidationIssue(
            level="error", resource_id=nid, resource_type="dynamodb",
            message=f"DynamoDB '{label}': billing mode is invalid.",
            field="billingMode",
        ))
    key_type = props.get("hashKeyType", "S")
    if key_type not in VALID_DYNAMODB_KEY_TYPES:
        issues.append(ValidationIssue(
            level="error", resource_id=nid, resource_type="dynamodb",
            message=f"DynamoDB '{label}': key type must be S, N, or B.",
            field="hashKeyType",
        ))
    return issues


def _validate_iam_role_fields(nid: str, label: str, props: Dict) -> List[ValidationIssue]:
    issues: List[ValidationIssue] = []
    service = props.get("service", "")
    if service and not re.match(r"^[a-z0-9.-]+\.amazonaws\.com$", service):
        issues.append(ValidationIssue(
            level="error", resource_id=nid, resource_type="iam_role",
            message=f"IAM role '{label}': trusted service must be an AWS service domain.",
            field="service",
        ))
    return issues


def _validate_route_table_fields(nid: str, label: str, props: Dict) -> List[ValidationIssue]:
    issues: List[ValidationIssue] = []
    destination = props.get("destinationCidr", "")
    if destination and not _is_valid_cidr(destination):
        issues.append(ValidationIssue(
            level="error", resource_id=nid, resource_type="route_table",
            message=f"Route table '{label}': destination CIDR is not valid.",
            field="destinationCidr",
        ))
    return issues


def _validate_api_gateway_fields(nid: str, label: str, props: Dict) -> List[ValidationIssue]:
    issues: List[ValidationIssue] = []
    protocol = props.get("protocol", "HTTP")
    if protocol and protocol not in VALID_API_GATEWAY_PROTOCOLS:
        issues.append(ValidationIssue(
            level="error", resource_id=nid, resource_type="api_gateway",
            message=f"API Gateway '{label}': protocol must be one of {sorted(VALID_API_GATEWAY_PROTOCOLS)}.",
            field="protocol",
        ))
    return issues


def _validate_route53_record_fields(nid: str, label: str, props: Dict) -> List[ValidationIssue]:
    issues: List[ValidationIssue] = []
    record_type = props.get("recordType", "")
    if record_type and record_type not in VALID_ROUTE53_RECORD_TYPES:
        issues.append(ValidationIssue(
            level="error", resource_id=nid, resource_type="route53_record",
            message=f"Route 53 Record '{label}': record type '{record_type}' is not supported.",
            field="recordType",
        ))
    return issues


def _validate_ebs_volume_fields(nid: str, label: str, props: Dict) -> List[ValidationIssue]:
    issues: List[ValidationIssue] = []
    size = props.get("size")
    if size is not None and (
        not isinstance(size, (int, float))
        or size < VALID_EBS_SIZE_MIN
        or size > VALID_EBS_SIZE_MAX
    ):
        issues.append(ValidationIssue(
            level="error", resource_id=nid, resource_type="ebs_volume",
            message=f"EBS Volume '{label}': size must be between "
                    f"{VALID_EBS_SIZE_MIN} and {VALID_EBS_SIZE_MAX} GB.",
            field="size",
        ))
    volume_type = props.get("volumeType", "gp3")
    if volume_type and volume_type not in VALID_EBS_VOLUME_TYPES:
        issues.append(ValidationIssue(
            level="error", resource_id=nid, resource_type="ebs_volume",
            message=f"EBS Volume '{label}': volume type '{volume_type}' is not supported.",
            field="volumeType",
        ))
    return issues


def _validate_kinesis_stream_fields(nid: str, label: str, props: Dict) -> List[ValidationIssue]:
    issues: List[ValidationIssue] = []
    shards = props.get("shardCount")
    if shards is not None and (
        not isinstance(shards, (int, float))
        or shards < VALID_KINESIS_SHARD_MIN
        or shards > VALID_KINESIS_SHARD_MAX
    ):
        issues.append(ValidationIssue(
            level="error", resource_id=nid, resource_type="kinesis_stream",
            message=f"Kinesis Stream '{label}': shard count must be between "
                    f"{VALID_KINESIS_SHARD_MIN} and {VALID_KINESIS_SHARD_MAX}.",
            field="shardCount",
        ))
    retention = props.get("retentionHours")
    if retention is not None and (
        not isinstance(retention, (int, float))
        or retention < VALID_KINESIS_RETENTION_MIN
        or retention > VALID_KINESIS_RETENTION_MAX
    ):
        issues.append(ValidationIssue(
            level="error", resource_id=nid, resource_type="kinesis_stream",
            message=f"Kinesis Stream '{label}': retention must be between "
                    f"{VALID_KINESIS_RETENTION_MIN} and {VALID_KINESIS_RETENTION_MAX} hours.",
            field="retentionHours",
        ))
    return issues


def _validate_elasticache_fields(nid: str, label: str, props: Dict) -> List[ValidationIssue]:
    issues: List[ValidationIssue] = []
    engine = props.get("engine", "redis")
    if engine and engine not in VALID_ELASTICACHE_ENGINES:
        issues.append(ValidationIssue(
            level="error", resource_id=nid, resource_type="elasticache",
            message=f"ElastiCache '{label}': engine must be redis or memcached.",
            field="engine",
        ))
    node_type = props.get("nodeType", "")
    if node_type and node_type not in VALID_ELASTICACHE_NODE_TYPES:
        issues.append(ValidationIssue(
            level="error", resource_id=nid, resource_type="elasticache",
            message=f"ElastiCache '{label}': node type '{node_type}' is not supported.",
            field="nodeType",
        ))
    return issues


def _validate_aurora_fields(nid: str, label: str, props: Dict) -> List[ValidationIssue]:
    issues: List[ValidationIssue] = []
    engine = props.get("engine", "aurora-mysql")
    if engine and engine not in VALID_AURORA_ENGINES:
        issues.append(ValidationIssue(
            level="error", resource_id=nid, resource_type="aurora",
            message=f"Aurora '{label}': engine must be aurora-mysql or aurora-postgresql.",
            field="engine",
        ))
    return issues


def _validate_redshift_fields(nid: str, label: str, props: Dict) -> List[ValidationIssue]:
    issues: List[ValidationIssue] = []
    node_type = props.get("nodeType", "")
    if node_type and node_type not in VALID_REDSHIFT_NODE_TYPES:
        issues.append(ValidationIssue(
            level="error", resource_id=nid, resource_type="redshift",
            message=f"Redshift '{label}': node type '{node_type}' is not supported.",
            field="nodeType",
        ))
    return issues


def _validate_cloudwatch_log_group_fields(nid: str, label: str, props: Dict) -> List[ValidationIssue]:
    issues: List[ValidationIssue] = []
    retention = props.get("retentionDays")
    if retention is not None and retention != "":
        try:
            retention_ok = str(int(retention)) in VALID_RETENTION_DAYS
        except (TypeError, ValueError):
            retention_ok = False
        if not retention_ok:
            issues.append(ValidationIssue(
                level="error", resource_id=nid, resource_type="cloudwatch_log_group",
                message=(
                    f"CloudWatch Log Group '{label}': retention must be a valid "
                    f"CloudWatch value in days (e.g. 1, 7, 30, 365, 3653)."
                ),
                field="retentionDays",
            ))
    return issues


def _validate_cloudwatch_alarm_fields(nid: str, label: str, props: Dict) -> List[ValidationIssue]:
    issues: List[ValidationIssue] = []
    threshold = props.get("threshold")
    if threshold is not None and threshold != "" and not isinstance(threshold, (int, float)):
        issues.append(ValidationIssue(
            level="error", resource_id=nid, resource_type="cloudwatch_alarm",
            message=f"CloudWatch Alarm '{label}': threshold must be a number.",
            field="threshold",
        ))
    metric = props.get("metric", "")
    if metric and metric not in VALID_ALARM_METRICS:
        issues.append(ValidationIssue(
            level="warning", resource_id=nid, resource_type="cloudwatch_alarm",
            message=f"CloudWatch Alarm '{label}': metric '{metric}' is uncommon. "
                    f"Verify the namespace exposes it.",
            field="metric",
        ))
    return issues


# ── Validator registry ───────────────────────────────────────────────────────
# Maps resource type name → field-validator callable.
# Add new resource types here instead of growing if/elif chains.

RESOURCE_FIELD_VALIDATORS: Dict[str, Callable[[str, str, Dict], List[ValidationIssue]]] = {
    "ec2": _validate_ec2_fields,
    "rds": _validate_rds_fields,
    "lambda": _validate_lambda_fields,
    "dynamodb": _validate_dynamodb_fields,
    "iam_role": _validate_iam_role_fields,
    "route_table": _validate_route_table_fields,
    "api_gateway": _validate_api_gateway_fields,
    "route53_record": _validate_route53_record_fields,
    "ebs_volume": _validate_ebs_volume_fields,
    "kinesis_stream": _validate_kinesis_stream_fields,
    "elasticache": _validate_elasticache_fields,
    "aurora": _validate_aurora_fields,
    "redshift": _validate_redshift_fields,
    "cloudwatch_log_group": _validate_cloudwatch_log_group_fields,
    "cloudwatch_alarm": _validate_cloudwatch_alarm_fields,
}


# ════════════════════════════════════════════════════════════════════════════
# Structural / topology validators
# ════════════════════════════════════════════════════════════════════════════


def _validate_structural_requirements(
    nid: str,
    ntype: str,
    label: str,
    props: Dict,
    neighbor_types: Set[str],
    neighbor_ids: Set[str],
    subnet_ids: Set[str],
    vpc_ids: Set[str],
) -> List[ValidationIssue]:
    """Check topology constraints that must hold for valid Terraform output."""
    issues: List[ValidationIssue] = []

    # route_table / internet_gateway must connect to a VPC
    if ntype in ("route_table", "internet_gateway") and "vpc" not in neighbor_types:
        issues.append(ValidationIssue(
            level="error", resource_id=nid, resource_type=ntype,
            message=f"{ntype.replace('_', ' ').title()} '{label}' must be connected to a VPC.",
        ))

    # nat_gateway must connect to a subnet
    if ntype == "nat_gateway" and "subnet" not in neighbor_types:
        issues.append(ValidationIssue(
            level="error", resource_id=nid, resource_type=ntype,
            message=f"NAT Gateway '{label}' must be connected to a Subnet.",
        ))

    # lambda must connect to an iam_role
    if ntype == "lambda" and "iam_role" not in neighbor_types:
        issues.append(ValidationIssue(
            level="error", resource_id=nid, resource_type=ntype,
            message=f"Lambda '{label}' must be connected to an IAM role (execution role).",
        ))

    # route53_record must connect to a route53_zone
    if ntype == "route53_record" and "route53_zone" not in neighbor_types:
        issues.append(ValidationIssue(
            level="error", resource_id=nid, resource_type=ntype,
            message=f"Route 53 Record '{label}' must be connected to a Route 53 Hosted Zone.",
        ))

    # load_balancer needs minimum connected subnets
    if ntype == "load_balancer":
        connected_subnet_count = len(neighbor_ids & subnet_ids)
        min_subnets = 1 if props.get("lbType", "application") == "network" else 2
        if connected_subnet_count < min_subnets:
            issues.append(ValidationIssue(
                level="error", resource_id=nid, resource_type=ntype,
                message=(
                    f"Load Balancer '{label}' needs at least {min_subnets} connected "
                    f"Subnet(s) — found {connected_subnet_count}."
                ),
            ))

    # subnet must connect to a VPC
    if ntype == "subnet" and not (neighbor_ids & vpc_ids):
        issues.append(ValidationIssue(
            level="error", resource_id=nid, resource_type=ntype,
            message=f"Subnet '{label}' is not connected to any VPC.",
        ))

    # ec2 should connect to a subnet (warning)
    if ntype == "ec2" and not (neighbor_ids & subnet_ids):
        issues.append(ValidationIssue(
            level="warning", resource_id=nid, resource_type=ntype,
            message=f"EC2 '{label}' is not connected to any Subnet.",
        ))

    # rds should connect to a subnet (warning)
    if ntype == "rds" and not (neighbor_ids & subnet_ids):
        issues.append(ValidationIssue(
            level="warning", resource_id=nid, resource_type=ntype,
            message=f"RDS '{label}' is not connected to any Subnet.",
        ))

    # ecs_cluster should connect to an EC2 instance or ECR repository (warning)
    if ntype == "ecs_cluster" and not ({"ec2", "ecr_repository"} & neighbor_types):
        issues.append(ValidationIssue(
            level="warning", resource_id=nid, resource_type=ntype,
            message=(
                f"ECS Cluster '{label}' should be connected to an EC2 instance "
                f"or ECR Repository."
            ),
        ))

    return issues


# ════════════════════════════════════════════════════════════════════════════
# Cross-cutting graph analysis helpers
# ════════════════════════════════════════════════════════════════════════════


def _cidrs_overlap(cidr_a: str, cidr_b: str) -> bool:
    """Return True if two CIDR ranges overlap."""
    try:
        net_a = ipaddress.ip_network(cidr_a, strict=False)
        net_b = ipaddress.ip_network(cidr_b, strict=False)
        return net_a.overlaps(net_b)
    except ValueError:
        return False


def _check_cidr_overlap(nodes: List[Dict]) -> List[ValidationIssue]:
    """Detect overlapping CIDR blocks within the same resource class.

    VPC-vs-VPC and Subnet-vs-Subnet overlaps are flagged.
    Cross-type overlap (subnet inside VPC) is expected and not flagged.
    """
    issues: List[ValidationIssue] = []

    vpc_entries: List[Tuple[str, str]] = []
    subnet_entries: List[Tuple[str, str]] = []

    for node in nodes:
        if not isinstance(node, dict) or not node.get("id"):
            continue
        ntype = _get_resource_type(node)
        data = node.get("data", {})
        props = data.get("properties", {}) if isinstance(data, dict) else {}
        if not isinstance(props, dict):
            continue
        cidr = props.get("cidr", "")
        if not cidr:
            continue
        if ntype == "vpc":
            vpc_entries.append((node["id"], cidr))
        elif ntype == "subnet":
            subnet_entries.append((node["id"], cidr))

    def _check_pairs(entries: List[Tuple[str, str]], kind: str) -> None:
        seen_pairs: Set[Tuple[str, str]] = set()
        for i, (id_a, cidr_a) in enumerate(entries):
            for id_b, cidr_b in entries[i + 1:]:
                pair = (min(id_a, id_b), max(id_a, id_b))
                if pair in seen_pairs:
                    continue
                if _cidrs_overlap(cidr_a, cidr_b):
                    seen_pairs.add(pair)
                    issues.append(ValidationIssue(
                        level="warning",
                        resource_id=id_a,
                        message=(
                            f"CIDR '{cidr_a}' overlaps with {kind} '{id_b}' "
                            f"CIDR '{cidr_b}'."
                        ),
                    ))

    _check_pairs(vpc_entries, "VPC")
    _check_pairs(subnet_entries, "Subnet")
    return issues


def _detect_cycles(nodes: List[Dict], edges: List[Dict]) -> List[ValidationIssue]:
    """Detect cycles in the architecture dependency graph using DFS."""
    issues: List[ValidationIssue] = []

    adj: Dict[str, List[str]] = defaultdict(list)
    node_ids = {n["id"] for n in nodes if isinstance(n, dict) and n.get("id")}

    for edge in edges:
        if not isinstance(edge, dict):
            continue
        src, tgt = edge.get("source"), edge.get("target")
        if src in node_ids and tgt in node_ids:
            adj[src].append(tgt)

    WHITE, GRAY, BLACK = 0, 1, 2
    color: Dict[str, int] = {nid: WHITE for nid in node_ids}

    def _dfs(u: str, path: List[str]) -> bool:
        color[u] = GRAY
        path.append(u)
        for v in adj.get(u, []):
            if color[v] == GRAY:
                cycle_start = path.index(v)
                cycle = path[cycle_start:] + [v]
                issues.append(ValidationIssue(
                    level="warning",
                    message=f"Circular dependency detected: {' → '.join(cycle)}",
                ))
                return True
            if color[v] == WHITE and _dfs(v, path):
                return True
        path.pop()
        color[u] = BLACK
        return False

    for nid in node_ids:
        if color[nid] == WHITE:
            _dfs(nid, [])

    return issues


# ════════════════════════════════════════════════════════════════════════════
# Main entry point
# ════════════════════════════════════════════════════════════════════════════


def validate_architecture(nodes: List[Dict], edges: List[Dict]) -> ValidationResult:
    issues: List[ValidationIssue] = []

    if not nodes:
        issues.append(ValidationIssue(
            level="warning",
            message="Canvas is empty. Add resources to your architecture.",
        ))
        return ValidationResult(valid=True, issues=issues)

    # ── Build index structures ───────────────────────────────────────────
    node_ids: Set[str] = set()
    node_map: Dict[str, Dict] = {}
    for node in nodes:
        node_id = node.get("id") if isinstance(node, dict) else None
        if not node_id:
            issues.append(ValidationIssue(
                level="error", message="Every node must have an id.",
            ))
            continue
        if node_id in node_ids:
            issues.append(ValidationIssue(
                level="error", resource_id=node_id,
                message=f"Node id '{node_id}' is duplicated.",
            ))
        node_ids.add(node_id)
        node_map[node_id] = node

    # ── Validate edges ───────────────────────────────────────────────────
    edge_targets: Dict[str, List[str]] = {}
    edge_sources: Dict[str, List[str]] = {}
    seen_edges: Set[Tuple[str, str]] = set()
    for edge in edges:
        if not isinstance(edge, dict):
            issues.append(ValidationIssue(
                level="error", message="Every edge must be an object.",
            ))
            continue
        src = edge.get("source")
        tgt = edge.get("target")
        if not src or not tgt:
            issues.append(ValidationIssue(
                level="error",
                message="Every edge must have both source and target ids.",
            ))
            continue
        if src == tgt:
            issues.append(ValidationIssue(
                level="error",
                message=f"Edge '{src}' cannot connect a node to itself.",
            ))
            continue
        if src not in node_ids or tgt not in node_ids:
            issues.append(ValidationIssue(
                level="error",
                message=f"Edge references an unknown node: '{src}' -> '{tgt}'.",
            ))
            continue
        edge_key = (src, tgt)
        if edge_key in seen_edges or (tgt, src) in seen_edges:
            issues.append(ValidationIssue(
                level="error",
                message=f"Duplicate connection: '{src}' <-> '{tgt}'.",
            ))
            continue
        seen_edges.add(edge_key)
        src_type = _get_resource_type(node_map[src])
        tgt_type = _get_resource_type(node_map[tgt])
        if frozenset((src_type, tgt_type)) not in SUPPORTED_RELATIONSHIPS:
            issues.append(ValidationIssue(
                level="error",
                message=f"Relationship '{src_type}' -> '{tgt_type}' is not supported.",
            ))
            continue
        edge_targets.setdefault(src, []).append(tgt)
        edge_sources.setdefault(tgt, []).append(src)

    # ── Build VPC / subnet sets ──────────────────────────────────────────
    vpc_ids = {n["id"] for n in nodes if isinstance(n, dict) and n.get("id") and _get_resource_type(n) == "vpc"}
    subnet_ids = {n["id"] for n in nodes if isinstance(n, dict) and n.get("id") and _get_resource_type(n) == "subnet"}

    # Map each subnet to its VPC and count subnets per VPC. AWS RDS/Aurora DB
    # subnet groups must span at least two Availability Zones, which requires
    # at least two subnets in the database's VPC.
    subnet_vpc: Dict[str, str] = {}
    subnets_per_vpc: Dict[str, Set[str]] = defaultdict(set)
    for subnet_id in subnet_ids:
        for neighbor in edge_sources.get(subnet_id, []) + edge_targets.get(subnet_id, []):
            if neighbor in vpc_ids:
                subnet_vpc[subnet_id] = neighbor
                subnets_per_vpc[neighbor].add(subnet_id)

    # ── Per-node validation ──────────────────────────────────────────────
    resource_names: Dict[str, List[str]] = {}

    for node in nodes:
        if not isinstance(node, dict) or not node.get("id"):
            continue
        nid = node["id"]
        ntype = _get_resource_type(node)
        data = node.get("data", {})
        props = data.get("properties", {}) if isinstance(data, dict) else {}
        if not isinstance(props, dict):
            issues.append(ValidationIssue(
                level="error", resource_id=nid, resource_type=ntype,
                message=f"{ntype.upper()} '{nid}': properties must be an object.",
            ))
            props = {}
        if ntype not in SUPPORTED_RESOURCE_TYPES:
            issues.append(ValidationIssue(
                level="error", resource_id=nid, resource_type=ntype,
                message=f"Resource type '{ntype}' is not supported.",
            ))

        label = _get_label(node)

        # ── Required fields (generic) ────────────────────────────────
        required = REQUIRED_FIELDS.get(ntype, [])
        for field in required:
            value = props.get(field, "")
            if not value or str(value).strip() == "":
                issues.append(ValidationIssue(
                    level="error",
                    resource_id=nid,
                    resource_type=ntype,
                    message=f"{ntype.upper()} '{label}': field '{field}' is required.",
                    field=field,
                ))

        # ── CIDR validation ──────────────────────────────────────────
        cidr_field = props.get("cidr", "")
        if ntype in ("vpc", "subnet") and cidr_field:
            if not _is_valid_cidr(cidr_field):
                issues.append(ValidationIssue(
                    level="error",
                    resource_id=nid,
                    resource_type=ntype,
                    message=f"{ntype.upper()} '{label}': CIDR '{cidr_field}' is not valid.",
                    field="cidr",
                ))

        # ── Per-resource-type field validation (registry lookup) ─────
        validator = RESOURCE_FIELD_VALIDATORS.get(ntype)
        if validator:
            issues.extend(validator(nid, label, props))

        # ── Structural / topology checks ─────────────────────────────
        raw_neighbors = edge_sources.get(nid, []) + edge_targets.get(nid, [])
        neighbor_types = {_get_resource_type(node_map[x]) for x in raw_neighbors if x in node_map}
        neighbor_id_set = set(raw_neighbors)

        issues.extend(_validate_structural_requirements(
            nid, ntype, label, props,
            neighbor_types, neighbor_id_set,
            subnet_ids, vpc_ids,
        ))

        # ── DB subnet-group coverage (RDS / Aurora) ──────────────────
        # Their subnet group is generated from every subnet in the database's
        # VPC, and AWS requires it to span two AZs. With a single subnet in
        # that VPC the generated HCL would be rejected at apply time.
        if ntype in ("rds", "aurora"):
            db_subnets = neighbor_id_set & subnet_ids
            db_vpcs = {subnet_vpc[s] for s in db_subnets if s in subnet_vpc}
            if db_vpcs and all(len(subnets_per_vpc[v]) < 2 for v in db_vpcs):
                issues.append(ValidationIssue(
                    level="error", resource_id=nid, resource_type=ntype,
                    message=(
                        f"{ntype.upper()} '{label}': its VPC needs at least 2 "
                        f"subnets so the DB subnet group can span two "
                        f"Availability Zones."
                    ),
                ))

        # ── Track name uniqueness ────────────────────────────────────
        name = (
            props.get("name")
            or props.get("bucketName")
            or props.get("identifier")
            or props.get("functionName")
            or props.get("tableName")
            or ""
        )
        if name:
            resource_names.setdefault(name.strip(), []).append(nid)

    # ── Cross-cutting checks ─────────────────────────────────────────────

    # Duplicate name check — error because duplicate names break Terraform
    for name, ids in resource_names.items():
        if len(ids) > 1:
            issues.append(ValidationIssue(
                level="error",
                message=(
                    f"Resource name '{name}' is used by {len(ids)} resources. "
                    f"Names must be unique."
                ),
            ))

    # CIDR overlap detection (same resource class only)
    issues.extend(_check_cidr_overlap(nodes))

    # Circular dependency detection
    issues.extend(_detect_cycles(nodes, edges))

    has_errors = any(i.level == "error" for i in issues)
    return ValidationResult(valid=not has_errors, issues=issues)


# ════════════════════════════════════════════════════════════════════════════
# Private helpers
# ════════════════════════════════════════════════════════════════════════════


def _get_resource_type(node: Dict) -> str:
    data = node.get("data", {}) if isinstance(node, dict) else {}
    resource_type = data.get("resourceType") if isinstance(data, dict) else None
    return str(resource_type or node.get("type", "unknown")).lower()


def _get_label(node: Dict) -> str:
    data = node.get("data", {}) if isinstance(node, dict) else {}
    props = data.get("properties", {}) if isinstance(data, dict) else {}
    if not isinstance(props, dict):
        props = {}
    label = data.get("label") if isinstance(data, dict) else None
    return (
        props.get("name")
        or props.get("bucketName")
        or props.get("identifier")
        or label
        or node.get("id", "unknown")
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
