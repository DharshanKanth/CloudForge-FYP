from app.services.validation_service import validate_architecture


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
