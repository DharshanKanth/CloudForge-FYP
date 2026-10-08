from app.services.autofix_service import auto_fix
from app.services.validation_service import validate_architecture


def _n(i, t, p=None):
    return {"id": i, "type": "resourceNode", "data": {"resourceType": t, "properties": p or {}}}


def test_autofix_connects_orphan_subnet_to_single_vpc():
    nodes = [
        _n("vpc", "vpc", {"name": "v", "cidr": "10.0.0.0/16"}),
        _n("sub", "subnet", {"name": "s", "cidr": "10.0.1.0/24"}),
    ]
    fixed_nodes, fixed_edges = auto_fix(nodes, [])
    assert validate_architecture(fixed_nodes, fixed_edges).valid is True


def test_autofix_connects_igw_and_route_table():
    nodes = [
        _n("vpc", "vpc", {"name": "v", "cidr": "10.0.0.0/16"}),
        _n("igw", "internet_gateway", {"name": "igw"}),
        _n("rt", "route_table", {"name": "rt"}),
    ]
    fixed_nodes, fixed_edges = auto_fix(nodes, [])
    res = validate_architecture(fixed_nodes, fixed_edges)
    assert not [i for i in res.issues if i.level == "error"]


def test_autofix_is_conservative_when_ambiguous():
    nodes = [_n("vpc1", "vpc"), _n("vpc2", "vpc"), _n("sub", "subnet")]
    _, edges = auto_fix(nodes, [])
    assert edges == []  # two VPCs — don't guess


def test_autofix_connects_lambda_to_single_role():
    nodes = [
        _n("role", "iam_role", {"name": "r", "service": "lambda.amazonaws.com"}),
        _n("fn", "lambda", {"functionName": "f", "runtime": "python3.12", "handler": "app.handler"}),
    ]
    fixed_nodes, fixed_edges = auto_fix(nodes, [])
    assert validate_architecture(fixed_nodes, fixed_edges).valid is True


def test_autofix_gives_load_balancer_two_subnets():
    nodes = [
        _n("vpc", "vpc"),
        _n("s1", "subnet"),
        _n("s2", "subnet"),
        _n("lb", "load_balancer", {"name": "lb", "lbType": "application"}),
    ]
    _, edges = auto_fix(nodes, [])
    lb_edges = [e for e in edges if "lb" in (e["source"], e["target"])]
    assert len(lb_edges) == 2
