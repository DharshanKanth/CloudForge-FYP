"""Deterministic mapping from diagram elements to CloudForge resource types.

Nothing here is AI-driven: a label/icon is matched against an ordered table of
aliases and, if recognised, given sensible default properties so the imported
design validates as cleanly as possible. Unknown elements are reported to the
user rather than guessed.
"""
import re
from typing import Dict, List, Optional, Tuple

# Resource types that act as containers on the canvas (nest their children).
CONTAINER_TYPES = {"vpc", "subnet"}

# The required "name-like" field for each resource type (filled from the label).
NAME_FIELDS: Dict[str, str] = {
    "vpc": "name", "subnet": "name", "ec2": "name", "s3": "bucketName",
    "rds": "identifier", "security_group": "name", "load_balancer": "name",
    "internet_gateway": "name", "route_table": "name", "nat_gateway": "name",
    "lambda": "functionName", "dynamodb": "tableName", "iam_role": "name",
    "cloudfront": "name", "api_gateway": "name", "route53_zone": "domainName",
    "route53_record": "name", "elastic_ip": "name", "ebs_volume": "name",
    "ecr_repository": "name", "ecs_cluster": "name", "efs": "name",
    "elasticache": "name", "aurora": "identifier", "redshift": "clusterIdentifier",
    "kinesis_stream": "name", "sqs": "name", "sns": "name",
    "step_function": "name", "secretsmanager": "name", "cloudwatch_alarm": "name",
    "cloudwatch_log_group": "name", "kms_key": "name",
}

# Free-Tier-friendly (and validator-valid) defaults per resource type. Anything
# still missing is filled deterministically by autofix_service afterwards.
DEFAULT_PROPS: Dict[str, Dict] = {
    "vpc": {"cidr": "10.0.0.0/16"},
    "ec2": {"instanceType": "t3.micro", "associatePublicIp": False},
    "rds": {"engine": "mysql", "engineVersion": "8.0", "instanceClass": "db.t3.micro",
            "storage": 20, "multiAz": False},
    "security_group": {"description": "Managed by CloudForge"},
    "load_balancer": {"lbType": "application", "internal": False},
    "lambda": {"runtime": "python3.12", "handler": "lambda_function.lambda_handler"},
    "dynamodb": {"hashKey": "id", "hashKeyType": "S", "billingMode": "PAY_PER_REQUEST"},
    "api_gateway": {"protocol": "HTTP"},
    "route53_record": {"recordType": "A"},
    "ebs_volume": {"size": 8, "volumeType": "gp3"},
    "elasticache": {"nodeType": "cache.t3.micro", "engine": "redis", "numberOfNodes": 2},
    "aurora": {"engine": "aurora-mysql", "instanceClass": "db.t3.micro"},
    "redshift": {"nodeType": "dc2.large", "numberOfNodes": 1},
    "kinesis_stream": {"shardCount": 1},
    "cloudwatch_alarm": {"metric": "CPUUtilization", "threshold": 80},
    "cloudwatch_log_group": {"retentionDays": 30},
    "kms_key": {"description": "Managed by CloudForge"},
}

# Ordered alias table (most specific first). Matched on a normalised label with
# word boundaries so short tokens ("s3", "vm", "db") don't match inside words.
_ALIASES: List[Tuple[str, str]] = [
    ("aurora", "aurora"),
    ("elasticache", "elasticache"),
    ("redis", "elasticache"),
    ("memcached", "elasticache"),
    ("redshift", "redshift"),
    ("dynamodb", "dynamodb"),
    ("dynamo db", "dynamodb"),
    ("api gateway", "api_gateway"),
    ("apigateway", "api_gateway"),
    ("api gw", "api_gateway"),
    ("cloudfront", "cloudfront"),
    ("cdn", "cloudfront"),
    ("step function", "step_function"),
    ("stepfunctions", "step_function"),
    ("state machine", "step_function"),
    ("kinesis", "kinesis_stream"),
    ("kinesis stream", "kinesis_stream"),
    ("container registry", "ecr_repository"),
    ("ecr", "ecr_repository"),
    ("fargate", "ecs_cluster"),
    ("ecs", "ecs_cluster"),
    ("container cluster", "ecs_cluster"),
    ("elastic file", "efs"),
    ("efs", "efs"),
    ("file system", "efs"),
    ("elastic block", "ebs_volume"),
    ("ebs", "ebs_volume"),
    ("volume", "ebs_volume"),
    ("elastic ip", "elastic_ip"),
    ("eip", "elastic_ip"),
    ("static ip", "elastic_ip"),
    ("database", "rds"),
    ("rds", "rds"),
    ("relational database", "rds"),
    ("mysql", "rds"),
    ("postgres", "rds"),
    ("postgresql", "rds"),
    ("dns record", "route53_record"),
    ("route 53 record", "route53_record"),
    ("record set", "route53_record"),
    ("route 53", "route53_zone"),
    ("route53", "route53_zone"),
    ("hosted zone", "route53_zone"),
    ("dns zone", "route53_zone"),
    ("dns", "route53_zone"),
    ("s3", "s3"),
    ("bucket", "s3"),
    ("object storage", "s3"),
    ("lambda", "lambda"),
    ("serverless", "lambda"),
    ("function", "lambda"),
    ("elastic load", "load_balancer"),
    ("load balancer", "load_balancer"),
    ("alb", "load_balancer"),
    ("nlb", "load_balancer"),
    ("elb", "load_balancer"),
    ("security group", "security_group"),
    ("firewall", "security_group"),
    ("internet gateway", "internet_gateway"),
    ("igw", "internet_gateway"),
    ("nat gateway", "nat_gateway"),
    ("nat", "nat_gateway"),
    ("route table", "route_table"),
    ("secrets manager", "secretsmanager"),
    ("secret", "secretsmanager"),
    ("kms", "kms_key"),
    ("key management", "kms_key"),
    ("cloudwatch log", "cloudwatch_log_group"),
    ("log group", "cloudwatch_log_group"),
    ("cloudwatch alarm", "cloudwatch_alarm"),
    ("alarm", "cloudwatch_alarm"),
    ("cloudwatch", "cloudwatch_alarm"),
    ("iam role", "iam_role"),
    ("iam", "iam_role"),
    ("role", "iam_role"),
    ("sqs", "sqs"),
    ("queue", "sqs"),
    ("sns", "sns"),
    ("topic", "sns"),
    ("notification", "sns"),
    ("vpc", "vpc"),
    ("virtual private cloud", "vpc"),
    ("subnet", "subnet"),
    ("ec2", "ec2"),
    ("instance", "ec2"),
    ("virtual machine", "ec2"),
    ("vm", "ec2"),
    ("compute", "ec2"),
    ("server", "ec2"),
]

# draw.io AWS4 icon tokens -> resource type.
_DRAWIO_ICONS: Dict[str, str] = {
    "ec2": "ec2",
    "lambda": "lambda",
    "s3": "s3",
    "rds": "rds",
    "dynamodb": "dynamodb",
    "api_gateway": "api_gateway",
    "cloudfront": "cloudfront",
    "elastic_load_balancing": "load_balancer",
    "nat_gateway": "nat_gateway",
    "internet_gateway": "internet_gateway",
    "route_table": "route_table",
    "security_group": "security_group",
    "vpc": "vpc",
    "subnet": "subnet",
    "ecr": "ecr_repository",
    "ecs": "ecs_cluster",
    "efs": "efs",
    "elasticache": "elasticache",
    "aurora": "aurora",
    "redshift": "redshift",
    "kinesis": "kinesis_stream",
    "sqs": "sqs",
    "sns": "sns",
    "step_functions": "step_function",
    "secrets_manager": "secretsmanager",
    "kms": "kms_key",
    "cloudwatch": "cloudwatch_alarm",
    "elastic_ip": "elastic_ip",
    "ebs": "ebs_volume",
    "route_53": "route53_zone",
    "iam": "iam_role",
}

# AWS "group" shapes that are just visual grouping (Cloud/Region/AZ/account…),
# not resources — parse their children but don't create a node for them.
_IGNORABLE_GROUPS = (
    "group_aws_cloud", "group_region", "group_availability_zone",
    "group_security_group", "group_account", "group_auto_scaling_group",
    "group_elastic_beanstalk", "group_spot_fleet", "group_ec2_instance",
    "group_database", "group_iot", "group_vpc_subnet",
)


def normalize(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (text or "").lower()).strip()


def _matches(norm: str, alias: str) -> bool:
    return re.search(
        r"(?<![a-z0-9])" + re.escape(alias) + r"(?![a-z0-9])", norm
    ) is not None


def classify_label(label: str) -> Optional[str]:
    """Map a human label to a resource type, or None if unrecognised."""
    norm = normalize(label)
    if not norm:
        return None
    for alias, rtype in _ALIASES:
        if _matches(norm, alias):
            return rtype
    return None


def classify_style(style: str) -> Optional[str]:
    """Map a draw.io style string to a resource type, or None."""
    s = (style or "").lower()
    if not s:
        return None
    # Group containers first (VPC / subnet).
    if "group_vpc" in s:
        return "vpc"
    if "group_subnet" in s:
        return "subnet"
    # Icon tokens: check longest tokens first for specificity.
    for token in sorted(_DRAWIO_ICONS, key=len, reverse=True):
        if f"aws4.{token}" in s or f"resicon=mxgraph.aws4.{token}" in s:
            return _DRAWIO_ICONS[token]
    return None


def is_ignorable_group(style: str) -> bool:
    s = (style or "").lower()
    return any(g in s for g in _IGNORABLE_GROUPS)


def classify_cell(style: str, label: str) -> Optional[str]:
    """Best-effort deterministic classification of a diagram cell."""
    return classify_style(style) or classify_label(label)


def build_properties(resource_type: str, name: str) -> Dict:
    props: Dict = {}
    name_field = NAME_FIELDS.get(resource_type)
    if name_field:
        props[name_field] = name
    props.update(DEFAULT_PROPS.get(resource_type, {}))
    return props
