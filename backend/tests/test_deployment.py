"""Tests for the deployment workspace / plan-hash binding logic.

Terraform itself is stubbed via monkeypatching `_run`, so these run with no
AWS credentials and no terraform binary.
"""
import json
import subprocess

from app.services import deployment_service as ds
from app.schemas.terraform import TerraformFile

PROJECT_ID = "11111111-2222-3333-4444-555555555555"


def _fake_run(returncode=0, out="ok"):
    def runner(cmd, cwd, env_extra=None, on_line=None):
        return subprocess.CompletedProcess(cmd, returncode, out, "")
    return runner


def test_plan_invokes_fmt_and_binds_hash(tmp_path, monkeypatch):
    monkeypatch.setattr(ds, "DEPLOYMENT_ROOT", tmp_path)
    calls = []

    def runner(cmd, cwd, env_extra=None, on_line=None):
        calls.append(cmd[1])
        return subprocess.CompletedProcess(cmd, 0, "ok", "")

    monkeypatch.setattr(ds, "_run", runner)

    result = ds.plan(PROJECT_ID, [TerraformFile(filename="main.tf", content='resource "aws_vpc" "v" {}\n')])

    assert result["status"] == "planned"
    assert "fmt" in calls  # generated files are canonicalized before planning
    meta = json.loads((ds._workspace(PROJECT_ID) / ds.PLAN_META_FILENAME).read_text())
    assert meta["files_sha256"] == ds._files_hash(ds._workspace(PROJECT_ID))


def test_apply_refuses_after_files_change(tmp_path, monkeypatch):
    monkeypatch.setattr(ds, "DEPLOYMENT_ROOT", tmp_path)
    monkeypatch.setattr(ds, "_run", _fake_run(0, "Apply complete! Resources: 1 added"))

    ws = ds._write_files(PROJECT_ID, [TerraformFile(filename="main.tf", content='resource "aws_vpc" "v" {}\n')])
    (ws / "tfplan").write_text("plan", encoding="utf-8")
    (ws / ds.PLAN_META_FILENAME).write_text(
        json.dumps({"files_sha256": ds._files_hash(ws)}), encoding="utf-8"
    )

    # Unchanged files: the apply proceeds.
    assert ds.apply(PROJECT_ID)["status"] == "deployed"

    # Re-plan, then change the design: the bound hash no longer matches.
    (ws / "tfplan").write_text("plan", encoding="utf-8")
    (ws / ds.PLAN_META_FILENAME).write_text(
        json.dumps({"files_sha256": ds._files_hash(ws)}), encoding="utf-8"
    )
    (ws / "main.tf").write_text('resource "aws_vpc" "v" { cidr_block = "10.0.0.0/16" }\n', encoding="utf-8")

    result = ds.apply(PROJECT_ID)
    assert result["status"] == "failed"
    assert "changed" in result["output"].lower()


def test_apply_requires_a_plan(tmp_path, monkeypatch):
    monkeypatch.setattr(ds, "DEPLOYMENT_ROOT", tmp_path)
    result = ds.apply(PROJECT_ID)  # no workspace / no tfplan
    assert result["status"] == "failed"
    assert "plan" in result["output"].lower()


def test_run_streams_output_lines(tmp_path):
    """`_run` must invoke the callback per line (used for live logs)."""
    import sys

    lines: list[str] = []
    result = ds._run(
        [sys.executable, "-c", "print('alpha'); print('beta')"],
        tmp_path,
        None,
        lines.append,
    )
    assert result.returncode == 0
    assert "alpha" in lines and "beta" in lines
    assert "alpha" in result.stdout
