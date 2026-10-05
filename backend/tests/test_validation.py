import pytest
from app.services.validation_service import (
    validate_architecture,
    _check_cidr_overlap,
    _detect_cycles,
    _cidrs_overlap,
    _get_resource_type,
    _get_label,
    _is_valid_cidr,
    RESOURCE_FIELD_VALIDATORS,
    REQUIRED_FIELDS,
)


# ════════════════════════════════════════════════════════════════════════════
# Existing tests (backward-compatible)
# ════════════════════════════════════════════════════════════════════════════


def test_empty_canvas_warns():
    res = validate_architecture([], [])
    assert res.valid is True
    assert any(i.level == "warning" and "Canvas is empty" in i.message for i in res.issues)


def test_missing_required_field_reports_error():
    nodes = [
        {"id": "vpc1", "type": "vpc", "data": {"resourceType": "vpc", "properties": {"name": ""}}}
    ]
    res = validate_architecture(nodes, [])
    assert res.valid is False
    assert any(i.level == "error" and "field 'cidr' is required" in i.message for i in res.issues)


def test_cidr_validation():
    nodes = [
        {"id": "vpc1", "type": "vpc", "data": {"resourceType": "vpc", "properties": {"name": "VPC", "cidr": "10.0.0.0/33"}}}
    ]
    res = validate_architecture(nodes, [])
    assert res.valid is False
    assert any(i.field == "cidr" for i in res.issues)


def test_new_resource_fields_are_validated():
    nodes = [
        {"id": "fn", "type": "lambda", "data": {"resourceType": "lambda", "properties": {
            "functionName": "worker", "runtime": "ruby3.3", "handler": "invalid"
        }}},
        {"id": "table", "type": "dynamodb", "data": {"resourceType": "dynamodb", "properties": {
            "tableName": "items", "hashKey": "id", "billingMode": "WRONG", "hashKeyType": "X"
        }}},
    ]
    res = validate_architecture(nodes, [])
    assert res.valid is False
    assert {issue.field for issue in res.issues} >= {"runtime", "handler", "billingMode", "hashKeyType"}


def test_unsupported_edges_are_reported():
    nodes = [
        {"id": "bucket", "type": "s3", "data": {"resourceType": "s3", "properties": {"bucketName": "files"}}},
        {"id": "fn", "type": "lambda", "data": {"resourceType": "lambda", "properties": {
            "functionName": "worker", "runtime": "python3.12", "handler": "app.handler"
        }}},
    ]
    res = validate_architecture(nodes, [{"source": "bucket", "target": "fn"}])
    assert res.valid is False
    assert any("not supported" in issue.message for issue in res.issues)


def test_new_resources_require_their_configuration_fields():
    nodes = [
        {"id": "igw", "type": "internet_gateway", "data": {"resourceType": "internet_gateway", "properties": {}}},
        {"id": "fn", "type": "lambda", "data": {"resourceType": "lambda", "properties": {}}},
        {"id": "table", "type": "dynamodb", "data": {"resourceType": "dynamodb", "properties": {}}},
    ]
    res = validate_architecture(nodes, [])
    assert not res.valid
    assert {issue.field for issue in res.issues if issue.field} >= {"name", "functionName", "runtime", "handler", "tableName", "hashKey"}


def test_malformed_and_unsupported_edges_are_reported_without_raising():
    nodes = [
        {"id": "vpc", "type": "vpc", "data": {"resourceType": "vpc", "properties": {"name": "v", "cidr": "10.0.0.0/16"}}},
        {"id": "bucket", "type": "s3", "data": {"resourceType": "s3", "properties": {"bucketName": "b"}}},
    ]
    res = validate_architecture(nodes, [{"source": "vpc"}, {"source": "vpc", "target": "missing"}, {"source": "vpc", "target": "bucket"}])
    assert not res.valid
    assert any("both source and target" in issue.message for issue in res.issues)
    assert any("unknown node" in issue.message for issue in res.issues)
    assert any("not supported" in issue.message for issue in res.issues)


# ════════════════════════════════════════════════════════════════════════════
# Edge validation
# ════════════════════════════════════════════════════════════════════════════


def test_self_loop_detected():
    nodes = [
        {"id": "vpc", "type": "vpc", "data": {"resourceType": "vpc", "properties": {"name": "v", "cidr": "10.0.0.0/16"}}},
    ]
    res = validate_architecture(nodes, [{"source": "vpc", "target": "vpc"}])
    assert not res.valid
    assert any("cannot connect a node to itself" in i.message for i in res.issues)


def test_duplicate_edge_detected():
    nodes = [
        {"id": "a", "type": "vpc", "data": {"resourceType": "vpc", "properties": {"name": "a", "cidr": "10.0.0.0/16"}}},
        {"id": "b", "type": "subnet", "data": {"resourceType": "subnet", "properties": {"name": "b", "cidr": "10.0.1.0/24"}}},
    ]
    edges = [
        {"source": "a", "target": "b"},
        {"source": "a", "target": "b"},
    ]
    res = validate_architecture(nodes, edges)
    assert not res.valid
    assert any("Duplicate connection" in i.message for i in res.issues)


def test_reverse_duplicate_edge_detected():
    nodes = [
        {"id": "a", "type": "vpc", "data": {"resourceType": "vpc", "properties": {"name": "a", "cidr": "10.0.0.0/16"}}},
        {"id": "b", "type": "subnet", "data": {"resourceType": "subnet", "properties": {"name": "b", "cidr": "10.0.1.0/24"}}},
    ]
    edges = [
        {"source": "a", "target": "b"},
        {"source": "b", "target": "a"},
    ]
    res = validate_architecture(nodes, edges)
    assert not res.valid
    assert any("Duplicate connection" in i.message for i in res.issues)


def test_node_without_id_flagged():
    nodes = [
        {"type": "vpc", "data": {"resourceType": "vpc", "properties": {"name": "v", "cidr": "10.0.0.0/16"}}},
    ]
    res = validate_architecture(nodes, [])
    assert not res.valid
    assert any("must have an id" in i.message for i in res.issues)


def test_duplicate_node_id_flagged():
    nodes = [
        {"id": "dup", "type": "vpc", "data": {"resourceType": "vpc", "properties": {"name": "a", "cidr": "10.0.0.0/16"}}},
        {"id": "dup", "type": "subnet", "data": {"resourceType": "subnet", "properties": {"name": "b", "cidr": "10.0.1.0/24"}}},
    ]
    res = validate_architecture(nodes, [])
    assert any("duplicated" in i.message for i in res.issues)


# ════════════════════════════════════════════════════════════════════════════
# Name uniqueness (now error)
# ════════════════════════════════════════════════════════════════════════════


def test_duplicate_name_is_error():
    nodes = [
        {"id": "a", "type": "vpc", "data": {"resourceType": "vpc", "properties": {"name": "my-vpc", "cidr": "10.0.0.0/16"}}},
        {"id": "b", "type": "subnet", "data": {"resourceType": "subnet", "properties": {"name": "my-vpc", "cidr": "10.0.1.0/24"}}},
    ]
    res = validate_architecture(nodes, [])
    name_issues = [i for i in res.issues if "my-vpc" in i.message and "unique" in i.message.lower()]
    assert name_issues, "Expected a name-uniqueness error"
    assert name_issues[0].level == "error"


def test_unique_names_pass():
    nodes = [
        {"id": "a", "type": "vpc", "data": {"resourceType": "vpc", "properties": {"name": "vpc-a", "cidr": "10.0.0.0/16"}}},
        {"id": "b", "type": "subnet", "data": {"resourceType": "subnet", "properties": {"name": "sub-b", "cidr": "10.0.1.0/24"}}},
    ]
    res = validate_architecture(nodes, [])
    name_issues = [i for i in res.issues if "unique" in i.message.lower()]
    assert not name_issues


# ════════════════════════════════════════════════════════════════════════════
# CIDR overlap detection
# ════════════════════════════════════════════════════════════════════════════


def test_cidr_overlap_detected_vpcs():
    nodes = [
        {"id": "v1", "type": "vpc", "data": {"resourceType": "vpc", "properties": {"name": "v1", "cidr": "10.0.0.0/16"}}},
        {"id": "v2", "type": "vpc", "data": {"resourceType": "vpc", "properties": {"name": "v2", "cidr": "10.0.0.0/24"}}},
    ]
    issues = _check_cidr_overlap(nodes)
    assert any("overlaps" in i.message for i in issues)


def test_cidr_overlap_detected_subnets():
    nodes = [
        {"id": "s1", "type": "subnet", "data": {"resourceType": "subnet", "properties": {"name": "s1", "cidr": "10.0.1.0/24"}}},
        {"id": "s2", "type": "subnet", "data": {"resourceType": "subnet", "properties": {"name": "s2", "cidr": "10.0.1.128/25"}}},
    ]
    issues = _check_cidr_overlap(nodes)
    assert any("overlaps" in i.message for i in issues)


def test_subnet_inside_vpc_not_flagged():
    """A subnet CIDR that falls within a VPC CIDR is expected."""
    nodes = [
        {"id": "v1", "type": "vpc", "data": {"resourceType": "vpc", "properties": {"name": "v1", "cidr": "10.0.0.0/16"}}},
        {"id": "s1", "type": "subnet", "data": {"resourceType": "subnet", "properties": {"name": "s1", "cidr": "10.0.1.0/24"}}},
    ]
    issues = _check_cidr_overlap(nodes)
    assert not issues


def test_non_overlapping_cidrs_clean():
    nodes = [
        {"id": "s1", "type": "subnet", "data": {"resourceType": "subnet", "properties": {"name": "s1", "cidr": "10.0.1.0/24"}}},
        {"id": "s2", "type": "subnet", "data": {"resourceType": "subnet", "properties": {"name": "s2", "cidr": "10.0.2.0/24"}}},
    ]
    issues = _check_cidr_overlap(nodes)
    assert not issues


def test_cidrs_overlap_helper():
    assert _cidrs_overlap("10.0.0.0/16", "10.0.1.0/24") is True
    assert _cidrs_overlap("10.0.0.0/16", "10.1.0.0/16") is False
    assert _cidrs_overlap("10.0.0.0/24", "10.0.0.0/24") is True  # identical


# ════════════════════════════════════════════════════════════════════════════
# Circular dependency detection
# ════════════════════════════════════════════════════════════════════════════


def test_cycle_detected():
    nodes = [
        {"id": "a", "type": "vpc", "data": {"resourceType": "vpc", "properties": {"name": "a", "cidr": "10.0.0.0/16"}}},
        {"id": "b", "type": "subnet", "data": {"resourceType": "subnet", "properties": {"name": "b", "cidr": "10.0.1.0/24"}}},
        {"id": "c", "type": "route_table", "data": {"resourceType": "route_table", "properties": {"name": "c"}}},
    ]
    edges = [
        {"source": "a", "target": "b"},
        {"source": "b", "target": "c"},
        {"source": "c", "target": "a"},
    ]
    issues = _detect_cycles(nodes, edges)
    assert any("Circular dependency" in i.message for i in issues)


def test_no_cycle_in_dag():
    nodes = [
        {"id": "a", "type": "vpc", "data": {"resourceType": "vpc", "properties": {"name": "a", "cidr": "10.0.0.0/16"}}},
        {"id": "b", "type": "subnet", "data": {"resourceType": "subnet", "properties": {"name": "b", "cidr": "10.0.1.0/24"}}},
    ]
    edges = [{"source": "a", "target": "b"}]
    issues = _detect_cycles(nodes, edges)
    assert not issues


# ════════════════════════════════════════════════════════════════════════════
# Structural / topology checks
# ════════════════════════════════════════════════════════════════════════════


def test_route_table_without_vpc_is_error():
    nodes = [
        {"id": "rt", "type": "route_table", "data": {"resourceType": "route_table", "properties": {"name": "rt"}}},
    ]
    res = validate_architecture(nodes, [])
    assert not res.valid
    assert any("must be connected to a VPC" in i.message for i in res.issues)


def test_internet_gateway_without_vpc_is_error():
    nodes = [
        {"id": "igw", "type": "internet_gateway", "data": {"resourceType": "internet_gateway", "properties": {"name": "igw"}}},
    ]
    res = validate_architecture(nodes, [])
    assert not res.valid
    assert any("must be connected to a VPC" in i.message for i in res.issues)


def test_nat_gateway_without_subnet_is_error():
    nodes = [
        {"id": "ngw", "type": "nat_gateway", "data": {"resourceType": "nat_gateway", "properties": {"name": "ngw"}}},
    ]
    res = validate_architecture(nodes, [])
    assert not res.valid
    assert any("must be connected to a Subnet" in i.message for i in res.issues)


def test_lambda_without_iam_role_is_error():
    nodes = [
        {"id": "fn", "type": "lambda", "data": {"resourceType": "lambda", "properties": {
            "functionName": "f", "runtime": "python3.12", "handler": "app.handler",
        }}},
    ]
    res = validate_architecture(nodes, [])
    assert not res.valid
    assert any("must be connected to an IAM role" in i.message for i in res.issues)


def test_route53_record_without_zone_is_error():
    nodes = [
        {"id": "rec", "type": "route53_record", "data": {"resourceType": "route53_record", "properties": {
            "name": "rec", "recordType": "A",
        }}},
    ]
    res = validate_architecture(nodes, [])
    assert not res.valid
    assert any("must be connected to a Route 53 Hosted Zone" in i.message for i in res.issues)


def test_subnet_without_vpc_is_error():
    nodes = [
        {"id": "sub", "type": "subnet", "data": {"resourceType": "subnet", "properties": {"name": "sub", "cidr": "10.0.1.0/24"}}},
    ]
    res = validate_architecture(nodes, [])
    assert not res.valid
    assert any("not connected to any VPC" in i.message for i in res.issues)


def test_load_balancer_needs_two_subnets():
    nodes = [
        {"id": "lb", "type": "load_balancer", "data": {"resourceType": "load_balancer", "properties": {"name": "lb"}}},
        {"id": "sub1", "type": "subnet", "data": {"resourceType": "subnet", "properties": {"name": "sub1", "cidr": "10.0.1.0/24"}}},
    ]
    edges = [{"source": "lb", "target": "sub1"}]
    res = validate_architecture(nodes, edges)
    assert not res.valid
    assert any("needs at least 2" in i.message for i in res.issues)


def test_load_balancer_nlb_needs_one_subnet():
    nodes = [
        {"id": "lb", "type": "load_balancer", "data": {"resourceType": "load_balancer", "properties": {"name": "lb", "lbType": "network"}}},
        {"id": "sub1", "type": "subnet", "data": {"resourceType": "subnet", "properties": {"name": "sub1", "cidr": "10.0.1.0/24"}}},
    ]
    edges = [{"source": "lb", "target": "sub1"}]
    res = validate_architecture(nodes, edges)
    lb_errors = [i for i in res.issues if "Load Balancer" in (i.message or "") and "Subnet" in (i.message or "")]
    assert not lb_errors  # NLB with 1 subnet is fine


def test_ecs_cluster_without_ec2_or_ecr_is_warning():
    nodes = [
        {"id": "ecs", "type": "ecs_cluster", "data": {"resourceType": "ecs_cluster", "properties": {"name": "ecs"}}},
    ]
    res = validate_architecture(nodes, [])
    assert any("should be connected" in i.message and "ECS" in i.message for i in res.issues)


def test_ec2_without_subnet_is_warning():
    nodes = [
        {"id": "i", "type": "ec2", "data": {"resourceType": "ec2", "properties": {"name": "i", "instanceType": "t3.micro"}}},
    ]
    res = validate_architecture(nodes, [])
    assert any("not connected to any Subnet" in i.message for i in res.issues)


def test_rds_with_single_subnet_vpc_is_error():
    """RDS/Aurora DB subnet groups must span two AZs, so a VPC with only one
    subnet would generate HCL that AWS rejects at apply time."""
    nodes = [
        {"id": "vpc", "type": "vpc", "data": {"resourceType": "vpc", "properties": {"name": "v", "cidr": "10.0.0.0/16"}}},
        {"id": "sub", "type": "subnet", "data": {"resourceType": "subnet", "properties": {"name": "s", "cidr": "10.0.1.0/24"}}},
        {"id": "db", "type": "rds", "data": {"resourceType": "rds", "properties": {
            "identifier": "db", "engine": "mysql", "instanceClass": "db.t3.micro",
        }}},
    ]
    edges = [{"source": "vpc", "target": "sub"}, {"source": "sub", "target": "db"}]
    res = validate_architecture(nodes, edges)
    assert not res.valid
    assert any(
        i.level == "error" and "Availability Zones" in i.message for i in res.issues
    )


def test_rds_with_two_subnets_is_valid():
    nodes = [
        {"id": "vpc", "type": "vpc", "data": {"resourceType": "vpc", "properties": {"name": "v", "cidr": "10.0.0.0/16"}}},
        {"id": "s1", "type": "subnet", "data": {"resourceType": "subnet", "properties": {"name": "s1", "cidr": "10.0.1.0/24"}}},
        {"id": "s2", "type": "subnet", "data": {"resourceType": "subnet", "properties": {"name": "s2", "cidr": "10.0.2.0/24"}}},
        {"id": "db", "type": "rds", "data": {"resourceType": "rds", "properties": {
            "identifier": "db", "engine": "mysql", "instanceClass": "db.t3.micro",
        }}},
    ]
    edges = [
        {"source": "vpc", "target": "s1"},
        {"source": "vpc", "target": "s2"},
        {"source": "s1", "target": "db"},
    ]
    res = validate_architecture(nodes, edges)
    assert res.valid is True, [i.message for i in res.issues if i.level == "error"]


def test_security_group_without_attachment_warns_default_vpc():
    """An unattached SG can't infer a VPC and lands in the default VPC."""
    nodes = [
        {"id": "sg", "type": "security_group", "data": {"resourceType": "security_group", "properties": {"name": "web-sg"}}},
    ]
    res = validate_architecture(nodes, [])
    assert any(
        i.level == "warning" and "default VPC" in i.message for i in res.issues
    )


def test_security_group_attached_to_vpc_resource_has_no_default_vpc_warning():
    nodes = [
        {"id": "vpc", "type": "vpc", "data": {"resourceType": "vpc", "properties": {"name": "v", "cidr": "10.0.0.0/16"}}},
        {"id": "sub", "type": "subnet", "data": {"resourceType": "subnet", "properties": {"name": "s", "cidr": "10.0.1.0/24"}}},
        {"id": "ec2", "type": "ec2", "data": {"resourceType": "ec2", "properties": {"name": "web", "instanceType": "t3.micro"}}},
        {"id": "sg", "type": "security_group", "data": {"resourceType": "security_group", "properties": {"name": "web-sg"}}},
    ]
    edges = [
        {"source": "vpc", "target": "sub"},
        {"source": "sub", "target": "ec2"},
        {"source": "sg", "target": "ec2"},
    ]
    res = validate_architecture(nodes, edges)
    assert not any("default VPC" in i.message for i in res.issues)


def test_rds_without_subnet_is_warning():
    nodes = [
        {"id": "db", "type": "rds", "data": {"resourceType": "rds", "properties": {
            "identifier": "db", "engine": "mysql", "instanceClass": "db.t3.micro",
        }}},
    ]
    res = validate_architecture(nodes, [])
    assert any("not connected to any Subnet" in i.message for i in res.issues)


# ════════════════════════════════════════════════════════════════════════════
# Per-resource field validators (extended coverage)
# ════════════════════════════════════════════════════════════════════════════


def test_ec2_invalid_instance_type_warning():
    nodes = [
        {"id": "i", "type": "ec2", "data": {"resourceType": "ec2", "properties": {"name": "i", "instanceType": "invalid-type"}}},
    ]
    res = validate_architecture(nodes, [])
    assert any(i.field == "instanceType" and i.level == "warning" for i in res.issues)


def test_lambda_memory_out_of_range():
    nodes = [
        {"id": "fn", "type": "lambda", "data": {"resourceType": "lambda", "properties": {
            "functionName": "f", "runtime": "python3.12", "handler": "app.handler",
            "memorySize": 50,  # below 128
        }}},
    ]
    res = validate_architecture(nodes, [])
    assert any(i.field == "memorySize" for i in res.issues)


def test_lambda_timeout_out_of_range():
    nodes = [
        {"id": "fn", "type": "lambda", "data": {"resourceType": "lambda", "properties": {
            "functionName": "f", "runtime": "python3.12", "handler": "app.handler",
            "timeout": 999,  # above 900
        }}},
    ]
    res = validate_architecture(nodes, [])
    assert any(i.field == "timeout" for i in res.issues)


# ════════════════════════════════════════════════════════════════════════════
# Free-Tier eligibility checks
# ════════════════════════════════════════════════════════════════════════════


def test_ec2_non_free_tier_instance_type_warning():
    nodes = [
        {"id": "i", "type": "ec2", "data": {"resourceType": "ec2", "properties": {
            "name": "i", "instanceType": "t3.medium",
        }}},
    ]
    res = validate_architecture(nodes, [])
    warnings = [i for i in res.issues if i.field == "instanceType"]
    assert any("not Free-Tier eligible" in i.message for i in warnings)
    assert all(i.level == "warning" for i in warnings)
    assert res.valid is True  # advisory only, never blocks the design


def test_ec2_t2_micro_region_restriction_warning():
    nodes = [
        {"id": "i", "type": "ec2", "data": {"resourceType": "ec2", "properties": {
            "name": "i", "instanceType": "t2.micro",
        }}},
    ]
    res = validate_architecture(nodes, [])
    warnings = [i for i in res.issues if i.field == "instanceType"]
    assert any("t3.micro" in i.message and "regions" in i.message for i in warnings)


def test_ec2_free_tier_type_has_no_instance_type_warning():
    nodes = [
        {"id": "i", "type": "ec2", "data": {"resourceType": "ec2", "properties": {
            "name": "i", "instanceType": "t3.micro",
        }}},
    ]
    res = validate_architecture(nodes, [])
    assert not [i for i in res.issues if i.field == "instanceType"]


def test_ec2_oversized_root_volume_warning():
    nodes = [
        {"id": "i", "type": "ec2", "data": {"resourceType": "ec2", "properties": {
            "name": "i", "instanceType": "t3.micro", "rootVolumeSize": 60,
        }}},
    ]
    res = validate_architecture(nodes, [])
    assert any(
        i.field == "rootVolumeSize" and i.level == "warning" for i in res.issues
    )


def test_rds_non_free_tier_instance_class_warning():
    nodes = [
        {"id": "db", "type": "rds", "data": {"resourceType": "rds", "properties": {
            "identifier": "db", "engine": "mysql", "instanceClass": "db.t3.medium",
        }}},
    ]
    res = validate_architecture(nodes, [])
    warnings = [i for i in res.issues if i.field == "instanceClass"]
    assert any("not Free-Tier eligible" in i.message for i in warnings)


def test_rds_multiaz_and_oversized_storage_warnings():
    nodes = [
        {"id": "db", "type": "rds", "data": {"resourceType": "rds", "properties": {
            "identifier": "db", "engine": "mysql", "instanceClass": "db.t3.micro",
            "multiAz": True, "storage": 50,
        }}},
    ]
    res = validate_architecture(nodes, [])
    fields = {i.field for i in res.issues}
    assert "multiAz" in fields and "storage" in fields
    assert res.valid is True  # warnings only


def test_rds_free_tier_config_is_clean():
    nodes = [
        {"id": "db", "type": "rds", "data": {"resourceType": "rds", "properties": {
            "identifier": "db", "engine": "mysql", "instanceClass": "db.t3.micro",
            "multiAz": False, "storage": 20,
        }}},
    ]
    res = validate_architecture(nodes, [])
    flagged = {i.field for i in res.issues if i.field in ("instanceClass", "multiAz", "storage")}
    assert not flagged


def test_lambda_bad_filename():
    nodes = [
        {"id": "fn", "type": "lambda", "data": {"resourceType": "lambda", "properties": {
            "functionName": "f", "runtime": "python3.12", "handler": "app.handler",
            "filename": "../etc/passwd",
        }}},
    ]
    res = validate_architecture(nodes, [])
    assert any(i.field == "filename" for i in res.issues)


def test_lambda_non_zip_filename():
    nodes = [
        {"id": "fn", "type": "lambda", "data": {"resourceType": "lambda", "properties": {
            "functionName": "f", "runtime": "python3.12", "handler": "app.handler",
            "filename": "code.tar.gz",
        }}},
    ]
    res = validate_architecture(nodes, [])
    assert any(i.field == "filename" for i in res.issues)


def test_api_gateway_invalid_protocol():
    nodes = [
        {"id": "gw", "type": "api_gateway", "data": {"resourceType": "api_gateway", "properties": {
            "name": "gw", "protocol": "GRPC",
        }}},
    ]
    res = validate_architecture(nodes, [])
    assert any(i.field == "protocol" for i in res.issues)


def test_route53_record_invalid_type():
    nodes = [
        {"id": "rec", "type": "route53_record", "data": {"resourceType": "route53_record", "properties": {
            "name": "rec", "recordType": "INVALID",
        }}},
    ]
    res = validate_architecture(nodes, [])
    assert any(i.field == "recordType" for i in res.issues)


def test_ebs_volume_size_out_of_range():
    nodes = [
        {"id": "vol", "type": "ebs_volume", "data": {"resourceType": "ebs_volume", "properties": {
            "name": "vol", "size": 99999,
        }}},
    ]
    res = validate_architecture(nodes, [])
    assert any(i.field == "size" for i in res.issues)


def test_ebs_volume_bad_type():
    nodes = [
        {"id": "vol", "type": "ebs_volume", "data": {"resourceType": "ebs_volume", "properties": {
            "name": "vol", "size": 100, "volumeType": "ssd-ultra",
        }}},
    ]
    res = validate_architecture(nodes, [])
    assert any(i.field == "volumeType" for i in res.issues)


def test_kinesis_shard_out_of_range():
    nodes = [
        {"id": "ks", "type": "kinesis_stream", "data": {"resourceType": "kinesis_stream", "properties": {
            "name": "ks", "shardCount": 0,
        }}},
    ]
    res = validate_architecture(nodes, [])
    assert any(i.field == "shardCount" for i in res.issues)


def test_kinesis_retention_out_of_range():
    nodes = [
        {"id": "ks", "type": "kinesis_stream", "data": {"resourceType": "kinesis_stream", "properties": {
            "name": "ks", "retentionHours": 10,
        }}},
        {"id": "ks2", "type": "kinesis_stream", "data": {"resourceType": "kinesis_stream", "properties": {
            "name": "ks2", "retentionHours": "soon",
        }}},
    ]
    res = validate_architecture(nodes, [])
    fields = {i.field for i in res.issues if i.resource_id in {"ks", "ks2"}}
    assert "retentionHours" in fields
    assert res.valid is False


def test_elasticache_bad_engine():
    nodes = [
        {"id": "ec", "type": "elasticache", "data": {"resourceType": "elasticache", "properties": {
            "name": "ec", "nodeType": "cache.t3.micro", "engine": "memsql",
        }}},
    ]
    res = validate_architecture(nodes, [])
    assert any(i.field == "engine" for i in res.issues)


def test_elasticache_bad_node_type():
    nodes = [
        {"id": "ec", "type": "elasticache", "data": {"resourceType": "elasticache", "properties": {
            "name": "ec", "nodeType": "cache.nano", "engine": "redis",
        }}},
    ]
    res = validate_architecture(nodes, [])
    assert any(i.field == "nodeType" for i in res.issues)


def test_aurora_bad_engine():
    nodes = [
        {"id": "aur", "type": "aurora", "data": {"resourceType": "aurora", "properties": {
            "identifier": "aur", "engine": "aurora-sqlserver",
        }}},
    ]
    res = validate_architecture(nodes, [])
    assert any(i.field == "engine" for i in res.issues)


def test_redshift_bad_node_type():
    nodes = [
        {"id": "rs", "type": "redshift", "data": {"resourceType": "redshift", "properties": {
            "clusterIdentifier": "rs", "nodeType": "dc2.nano",
        }}},
    ]
    res = validate_architecture(nodes, [])
    assert any(i.field == "nodeType" for i in res.issues)


def test_cloudwatch_log_group_bad_retention():
    nodes = [
        {"id": "lg", "type": "cloudwatch_log_group", "data": {"resourceType": "cloudwatch_log_group", "properties": {
            "name": "lg", "retentionDays": 99,
        }}},
    ]
    res = validate_architecture(nodes, [])
    assert any(i.field == "retentionDays" for i in res.issues)


def test_cloudwatch_alarm_bad_threshold():
    nodes = [
        {"id": "al", "type": "cloudwatch_alarm", "data": {"resourceType": "cloudwatch_alarm", "properties": {
            "name": "al", "metric": "CPUUtilization", "threshold": "high",
        }}},
    ]
    res = validate_architecture(nodes, [])
    assert any(i.field == "threshold" for i in res.issues)


def test_cloudwatch_alarm_unknown_metric_warning():
    nodes = [
        {"id": "al", "type": "cloudwatch_alarm", "data": {"resourceType": "cloudwatch_alarm", "properties": {
            "name": "al", "metric": "DiskUsage", "threshold": 80,
        }}},
    ]
    res = validate_architecture(nodes, [])
    assert any(i.field == "metric" and i.level == "warning" for i in res.issues)


def test_iam_role_bad_service():
    nodes = [
        {"id": "role", "type": "iam_role", "data": {"resourceType": "iam_role", "properties": {
            "name": "role", "service": "example.com",
        }}},
    ]
    res = validate_architecture(nodes, [])
    assert any(i.field == "service" for i in res.issues)


def test_route_table_bad_destination_cidr():
    nodes = [
        {"id": "rt", "type": "route_table", "data": {"resourceType": "route_table", "properties": {
            "name": "rt", "destinationCidr": "999.0.0.0/8",
        }}},
    ]
    res = validate_architecture(nodes, [])
    assert any(i.field == "destinationCidr" for i in res.issues)


# ════════════════════════════════════════════════════════════════════════════
# Helpers
# ════════════════════════════════════════════════════════════════════════════


def test_get_resource_type_uses_data_over_type():
    node = {"id": "x", "type": "old_type", "data": {"resourceType": "lambda"}}
    assert _get_resource_type(node) == "lambda"


def test_get_resource_type_falls_back_to_type():
    node = {"id": "x", "type": "s3", "data": {}}
    assert _get_resource_type(node) == "s3"


def test_get_label_prefers_name():
    node = {"id": "x", "data": {"label": "Label", "properties": {"name": "Actual"}}}
    assert _get_label(node) == "Actual"


def test_get_label_falls_back_to_id():
    node = {"id": "x", "data": {}}
    assert _get_label(node) == "x"


def test_is_valid_cidr_valid():
    assert _is_valid_cidr("10.0.0.0/16") is True
    assert _is_valid_cidr("192.168.1.0/24") is True
    assert _is_valid_cidr("0.0.0.0/0") is True


def test_is_valid_cidr_invalid():
    assert _is_valid_cidr("10.0.0.0/33") is False
    assert _is_valid_cidr("999.0.0.0/8") is False
    assert _is_valid_cidr("not-a-cidr") is False
    assert _is_valid_cidr("10.0.0.0") is False


def test_all_resource_types_have_validators_or_are_simple():
    """Every type in REQUIRED_FIELDS is either in the registry or has no
    special field checks (just required-field validation)."""
    for rtype in REQUIRED_FIELDS:
        # Should not raise — either it's in the registry or it's not
        if rtype in RESOURCE_FIELD_VALIDATORS:
            assert callable(RESOURCE_FIELD_VALIDATORS[rtype])


# ════════════════════════════════════════════════════════════════════════════
# Valid architecture happy-path
# ════════════════════════════════════════════════════════════════════════════


def test_valid_minimal_architecture():
    """A small but complete VPC → Subnet → EC2 architecture should validate."""
    nodes = [
        {"id": "vpc", "type": "vpc", "data": {"resourceType": "vpc", "properties": {"name": "main", "cidr": "10.0.0.0/16"}}},
        {"id": "sub", "type": "subnet", "data": {"resourceType": "subnet", "properties": {"name": "pub", "cidr": "10.0.1.0/24"}}},
        {"id": "igw", "type": "internet_gateway", "data": {"resourceType": "internet_gateway", "properties": {"name": "igw"}}},
        {"id": "i", "type": "ec2", "data": {"resourceType": "ec2", "properties": {"name": "web", "instanceType": "t3.micro"}}},
        {"id": "sg", "type": "security_group", "data": {"resourceType": "security_group", "properties": {"name": "web-sg"}}},
    ]
    edges = [
        {"source": "vpc", "target": "sub"},
        {"source": "vpc", "target": "igw"},
        {"source": "i", "target": "sub"},
        {"source": "sg", "target": "i"},
    ]
    res = validate_architecture(nodes, edges)
    errors = [i for i in res.issues if i.level == "error"]
    assert res.valid is True, f"Expected valid, got errors: {[i.message for i in errors]}"


def test_valid_lambda_architecture():
    """Lambda + IAM + DynamoDB should validate cleanly."""
    nodes = [
        {"id": "role", "type": "iam_role", "data": {"resourceType": "iam_role", "properties": {"name": "exec-role", "service": "lambda.amazonaws.com"}}},
        {"id": "fn", "type": "lambda", "data": {"resourceType": "lambda", "properties": {
            "functionName": "processor", "runtime": "python3.12", "handler": "app.handler",
        }}},
        {"id": "tbl", "type": "dynamodb", "data": {"resourceType": "dynamodb", "properties": {
            "tableName": "items", "hashKey": "id",
        }}},
    ]
    edges = [
        {"source": "fn", "target": "role"},
        {"source": "fn", "target": "tbl"},
    ]
    res = validate_architecture(nodes, edges)
    errors = [i for i in res.issues if i.level == "error"]
    assert res.valid is True, f"Expected valid, got errors: {[i.message for i in errors]}"
