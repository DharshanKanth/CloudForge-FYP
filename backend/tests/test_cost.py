from app.services.cost_service import estimate


def _node(nid, rtype, props):
    return {"id": nid, "type": rtype, "data": {"resourceType": rtype, "properties": props}}


def test_free_tier_architecture_is_zero():
    nodes = [
        _node("vpc", "vpc", {"name": "v"}),
        _node("ec2", "ec2", {"name": "web", "instanceType": "t3.micro"}),
        _node("s3", "s3", {"bucketName": "b"}),
    ]
    result = estimate(nodes)
    assert result["monthly_total"] == 0.0
    assert result["currency"] == "USD"


def test_ebs_is_priced_per_gb():
    result = estimate([_node("vol", "ebs_volume", {"name": "d", "size": 100, "volumeType": "gp3"})])
    assert result["items"][0]["monthly_cost"] == 8.0  # 100 GB * $0.08


def test_big_drivers_are_ranked_first():
    nodes = [
        _node("nat", "nat_gateway", {"name": "nat"}),
        _node("lb", "load_balancer", {"name": "lb"}),
        _node("db", "rds", {"identifier": "db", "engine": "mysql", "instanceClass": "db.t3.medium", "storage": 20}),
        _node("ec2", "ec2", {"name": "web", "instanceType": "t3.micro"}),
    ]
    result = estimate(nodes)
    assert result["monthly_total"] > 50
    assert result["items"][0]["monthly_cost"] >= result["items"][-1]["monthly_cost"]
    assert result["items"][0]["resource_type"] in {"nat_gateway", "load_balancer", "rds"}
