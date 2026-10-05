"""Tests for the live-infrastructure tracker and the clear guard.

The tracker parses terraform.tfstate directly (no terraform binary and no
cloud API involved), so these tests run against small state fixtures.
"""
import json

import pytest

from app.services import deployment_service as ds

PROJECT_ID = "11111111-2222-3333-4444-555555555555"


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    """Point DEPLOYMENT_ROOT at a temp dir with a project workspace inside."""
    monkeypatch.setattr(ds, "DEPLOYMENT_ROOT", tmp_path)
    ws = tmp_path / PROJECT_ID
    ws.mkdir(parents=True)
    return ws


def write_state(ws, resources, outputs=None):
    state = {
        "version": 4,
        "terraform_version": "1.7.5",
        "outputs": outputs or {},
        "resources": resources,
    }
    (ws / "terraform.tfstate").write_text(json.dumps(state), encoding="utf-8")


INSTANCE = {
    "mode": "managed",
    "type": "aws_instance",
    "name": "web_server",
    "instances": [{
        "attributes": {
            "id": "i-123",
            "instance_state": "running",
            "public_ip": "1.2.3.4",
            "instance_type": "t3.micro",
            "availability_zone": "ap-northeast-1a",
            "tags": {"Name": "web-server", "ManagedBy": "CloudForge"},
            "password_data": "SUPER-SECRET",  # must never leak
        },
    }],
}

VPC = {
    "mode": "managed",
    "type": "aws_vpc",
    "name": "main_vpc",
    "instances": [{
        "attributes": {
            "id": "vpc-1",
            "cidr_block": "10.0.0.0/16",
            "tags": {"Name": "main-vpc"},
        },
    }],
}

DATA_SOURCE = {
    "mode": "data",
    "type": "aws_ami",
    "name": "amazon_linux",
    "instances": [{"attributes": {"id": "ami-xyz"}}],
}


def test_infrastructure_not_deployed_when_workspace_is_empty(workspace):
    result = ds.infrastructure(PROJECT_ID)
    assert result["status"] == "not_deployed"
    assert result["resources"] == []
    assert result["outputs"] == {}
    assert result["state_updated_at"] is None


def test_infrastructure_lists_resources_hides_secrets_and_data_sources(workspace):
    write_state(workspace, [INSTANCE, VPC, DATA_SOURCE])
    result = ds.infrastructure(PROJECT_ID)
    assert result["status"] == "deployed"
    # data source excluded, 2 managed resources listed
    assert len(result["resources"]) == 2
    by_type = {r["type"]: r for r in result["resources"]}
    inst = by_type["aws_instance"]
    assert inst["label"] == "web-server"          # from tags.Name
    assert inst["id"] == "i-123"
    assert inst["category"] == "compute"
    assert inst["attributes"]["public_ip"] == "1.2.3.4"
    assert inst["attributes"]["instance_state"] == "running"
    assert "password_data" not in inst["attributes"]  # whitelisted only
    assert by_type["aws_vpc"]["attributes"]["cidr_block"] == "10.0.0.0/16"


def test_infrastructure_includes_outputs_and_region(workspace):
    (workspace / "variables.tf").write_text(
        'variable "aws_region" {\n  default     = "ap-northeast-1"\n}\n',
        encoding="utf-8",
    )
    write_state(workspace, [INSTANCE], outputs={
        "ec2_public_ip_web_server": {"value": "1.2.3.4", "type": "string"},
    })
    result = ds.infrastructure(PROJECT_ID)
    assert result["outputs"] == {"ec2_public_ip_web_server": "1.2.3.4"}
    assert result["region"] == "ap-northeast-1"
    assert result["state_updated_at"] is not None


def test_clear_blocked_while_resources_are_live(workspace):
    write_state(workspace, [INSTANCE, VPC])
    result = ds.clear(PROJECT_ID)
    assert result["status"] == "blocked"
    assert result["live_resources"] == 2
    assert "aws_instance.web_server" in result["addresses"]
    assert (workspace / "terraform.tfstate").exists()  # untouched


def test_clear_force_removes_workspace_even_when_deployed(workspace):
    write_state(workspace, [INSTANCE])
    result = ds.clear(PROJECT_ID, force=True)
    assert result["status"] == "cleared"
    assert not workspace.exists()


def test_clear_succeeds_when_nothing_is_deployed(workspace):
    result = ds.clear(PROJECT_ID)
    assert result["status"] == "cleared"


def test_infrastructure_reports_not_deployed_after_destroy(workspace):
    """A destroyed deployment leaves an empty resources list in the state."""
    write_state(workspace, [])  # terraform leaves resources: [] after destroy
    result = ds.infrastructure(PROJECT_ID)
    assert result["status"] == "not_deployed"
    assert result["resources"] == []


# ════════════════════════════════════════════════════════════════════════════
# Dashboard bulk summary
# ════════════════════════════════════════════════════════════════════════════


def test_summary_returns_only_deployed_projects_with_counts(tmp_path, monkeypatch):
    monkeypatch.setattr(ds, "DEPLOYMENT_ROOT", tmp_path)
    live_id = "aaaaaaaa-0000-0000-0000-000000000001"
    empty_id = "aaaaaaaa-0000-0000-0000-000000000002"
    for pid in (live_id, empty_id):
        (tmp_path / pid).mkdir(parents=True)
    write_state(tmp_path / live_id, [INSTANCE, VPC, DATA_SOURCE])
    write_state(tmp_path / empty_id, [])  # destroyed previously

    result = ds.infrastructure_summary([live_id, empty_id, "missing-project"])

    assert len(result) == 1  # only the deployed one
    entry = result[0]
    assert entry["status"] == "deployed"
    assert entry["resource_count"] == 2          # data source excluded
    assert entry["categories"] == {"compute": 1, "network": 1, "data": 0}
    assert entry["resources"][0]["type"] == "aws_instance"


def test_summary_preserves_caller_order(tmp_path, monkeypatch):
    monkeypatch.setattr(ds, "DEPLOYMENT_ROOT", tmp_path)
    id_a = "aaaaaaaa-0000-0000-0000-00000000000a"
    id_b = "aaaaaaaa-0000-0000-0000-00000000000b"
    for pid in (id_a, id_b):
        (tmp_path / pid).mkdir(parents=True)
    write_state(tmp_path / id_a, [INSTANCE])
    write_state(tmp_path / id_b, [VPC])  # distinguishable content

    result = ds.infrastructure_summary([id_b, id_a])

    assert [e["resources"][0]["type"] for e in result] == ["aws_vpc", "aws_instance"]
    assert len(result) == 2


# ════════════════════════════════════════════════════════════════════════════
# Deployment-history helpers
# ════════════════════════════════════════════════════════════════════════════


def test_parse_resource_count_matches_terraform_summaries():
    assert ds.parse_resource_count(
        "Plan: 12 to add, 0 to change, 0 to destroy.", "plan_add"
    ) == 12
    assert ds.parse_resource_count(
        "Apply complete! Resources: 12 added, 0 changed, 0 destroyed.",
        "apply_added",
    ) == 12
    assert ds.parse_resource_count("Plan: 12 to destroy.", "plan_destroy") == 12
    assert ds.parse_resource_count(
        "Apply complete! Resources: 0 added, 0 changed, 12 destroyed.",
        "destroy_destroyed",
    ) == 12


def test_parse_resource_count_handles_garbage():
    assert ds.parse_resource_count("no summary line here", "plan_add") is None
    assert ds.parse_resource_count(None, "plan_add") is None
    assert ds.parse_resource_count("Plan: 12 to add", "unknown_kind") is None
    assert ds.parse_resource_count("", "apply_added") is None