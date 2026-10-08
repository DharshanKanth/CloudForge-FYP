from app.services.security_service import analyze


def _n(nid, rtype, props):
    return {"id": nid, "type": rtype, "data": {"resourceType": rtype, "properties": props}}


def test_ssh_open_to_world_is_high():
    res = analyze([_n("sg", "security_group", {"name": "sg", "allowSsh": True, "sshCidr": "0.0.0.0/0"})], [])
    assert any(f["severity"] == "high" and "SSH" in f["title"] for f in res["findings"])
    assert res["counts"]["high"] >= 1


def test_restricted_ssh_is_not_high():
    res = analyze([_n("sg", "security_group", {"name": "sg", "allowSsh": True, "sshCidr": "10.0.0.0/8"})], [])
    assert not any(f["severity"] == "high" for f in res["findings"])


def test_s3_without_versioning_is_medium():
    res = analyze([_n("s3", "s3", {"bucketName": "b", "versioning": False})], [])
    assert any("versioning" in f["title"].lower() and f["severity"] == "medium" for f in res["findings"])


def test_missing_kms_and_alarms_are_reported():
    res = analyze(
        [
            _n("ec2", "ec2", {"name": "web", "instanceType": "t3.micro"}),
            _n("s3", "s3", {"bucketName": "b", "versioning": True}),
        ],
        [],
    )
    titles = " ".join(f["title"] for f in res["findings"])
    assert "KMS" in titles
    assert "alarm" in titles.lower()


def test_clean_design_reports_no_high_findings():
    nodes = [
        _n("vpc", "vpc", {"name": "v"}),
        _n("sub", "subnet", {"name": "s", "mapPublicIp": False}),
        _n("ec2", "ec2", {"name": "web", "associatePublicIp": False}),
        _n("sg", "security_group", {"name": "sg", "allowSsh": False, "webCidr": "10.0.0.0/16", "allowAllOutbound": False}),
        _n("kms", "kms_key", {"name": "k", "description": "key"}),
        _n("alarm", "cloudwatch_alarm", {"name": "a", "metric": "CPUUtilization", "threshold": 80}),
        _n("s3", "s3", {"bucketName": "b", "versioning": True}),
    ]
    res = analyze(nodes, [])
    assert res["counts"]["high"] == 0


def test_security_fix_restricts_open_ssh():
    from app.services.security_fix_service import auto_fix as security_auto_fix

    nodes = [_n("sg", "security_group", {"name": "sg", "allowSsh": True, "sshCidr": "0.0.0.0/0"})]
    fixed, _ = security_auto_fix(nodes, [])
    sg = next(n for n in fixed if n["id"] == "sg")
    assert sg["data"]["properties"]["sshCidr"] != "0.0.0.0/0"
    assert not any(f["severity"] == "high" for f in analyze(fixed, [])["findings"])


def test_security_fix_enables_s3_versioning():
    from app.services.security_fix_service import auto_fix as security_auto_fix

    nodes = [_n("s3", "s3", {"bucketName": "b", "versioning": False})]
    fixed, _ = security_auto_fix(nodes, [])
    assert next(n for n in fixed if n["id"] == "s3")["data"]["properties"]["versioning"] is True


def test_security_fix_does_not_mutate_input():
    from app.services.security_fix_service import auto_fix as security_auto_fix

    nodes = [_n("s3", "s3", {"bucketName": "b", "versioning": False})]
    security_auto_fix(nodes, [])
    assert nodes[0]["data"]["properties"]["versioning"] is False
