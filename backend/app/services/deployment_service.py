"""Controlled Terraform deployment runner for CloudForge projects."""
from pathlib import Path
import hashlib
import json
import os
import re
import shutil
import subprocess
import threading
from typing import Dict, List

from app.schemas.terraform import TerraformFile


DEPLOYMENT_ROOT = Path(os.getenv("CLOUDFORGE_DEPLOYMENT_ROOT", "/tmp/cloudforge-deployments"))
COMMAND_TIMEOUT_SECONDS = int(os.getenv("CLOUDFORGE_TERRAFORM_TIMEOUT", "300"))
PLAN_META_FILENAME = ".cloudforge-plan.meta"
DESTROY_META_FILENAME = ".cloudforge-destroy.meta"
TERRAFORM_SUFFIXES = (".tf", ".tfvars")

# One lock per project id so plan/apply/destroy can never interleave their
# workspace staging with a running terraform process. In-process only.
_locks_guard = threading.Lock()
_locks: Dict[str, threading.Lock] = {}


def _project_lock(project_id: str) -> threading.Lock:
    with _locks_guard:
        lock = _locks.get(project_id)
        if lock is None:
            lock = threading.Lock()
            _locks[project_id] = lock
        return lock


def _workspace(project_id: str) -> Path:
    if not project_id or Path(project_id).name != project_id or project_id in {".", ".."}:
        raise ValueError("Invalid project id")
    path = DEPLOYMENT_ROOT / project_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def _write_files(project_id: str, files: List[TerraformFile]) -> Path:
    workspace = _workspace(project_id)
    for pattern in ("*.tf", "*.tfvars"):
        for existing in workspace.glob(pattern):
            existing.unlink()
    has_lambda = False
    for terraform_file in files:
        name = Path(terraform_file.filename).name
        if Path(terraform_file.filename).suffix not in TERRAFORM_SUFFIXES or name != terraform_file.filename:
            raise ValueError("Invalid Terraform filename")
        (workspace / name).write_text(terraform_file.content, encoding="utf-8")
        if "aws_lambda_function" in terraform_file.content:
            has_lambda = True
    # Lambda's filename/source_code_hash reference a .zip that the generator
    # doesn't ship; drop in a minimal valid zip so plan/apply don't choke.
    if has_lambda and not (workspace / "lambda.zip").exists():
        (workspace / "lambda.zip").write_bytes(_minimal_zip())
    return workspace


def _minimal_zip() -> bytes:
    """Return a tiny valid ZIP containing a placeholder lambda handler.

    Real packages are the user's responsibility; this stub only lets
    terraform plan/apply validate the resource without a 404 on the filename.
    """
    import io, zipfile
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("lambda_function.py", "def lambda_handler(event, context):\n    return event\n")
    return buf.getvalue()


def _terraform_files(workspace: Path) -> List[Path]:
    return sorted(p for p in workspace.iterdir() if p.is_file() and p.suffix in TERRAFORM_SUFFIXES)


def _files_hash(workspace: Path) -> str:
    digest = hashlib.sha256()
    for path in _terraform_files(workspace):
        digest.update(path.name.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def _run(command: List[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=COMMAND_TIMEOUT_SECONDS,
        env=os.environ.copy(),
    )


def plan(project_id: str, files: List[TerraformFile]) -> Dict:
    with _project_lock(project_id):
        workspace = _write_files(project_id, files)
        init = _run(["terraform", "init", "-input=false", "-no-color"], workspace)
        if init.returncode != 0:
            return {"status": "failed", "step": "init", "output": _output(init)}
        validate = _run(["terraform", "validate", "-no-color"], workspace)
        if validate.returncode != 0:
            return {"status": "failed", "step": "validate", "output": _output(validate)}
        planned = _run(["terraform", "plan", "-input=false", "-no-color", "-out=tfplan"], workspace)
        if planned.returncode == 0:
            # Bind the plan to the exact files it was computed from so a stale
            # plan can't be applied after the design changed.
            meta = {"files_sha256": _files_hash(workspace)}
            (workspace / PLAN_META_FILENAME).write_text(json.dumps(meta), encoding="utf-8")
        return {
            "status": "planned" if planned.returncode == 0 else "failed",
            "step": "plan",
            "output": _output(planned),
        }


def apply(project_id: str) -> Dict:
    with _project_lock(project_id):
        workspace = _workspace(project_id)
        if not (workspace / "tfplan").exists():
            return {"status": "failed", "step": "apply", "output": "Run a successful plan before applying."}
        meta_path = workspace / PLAN_META_FILENAME
        if not meta_path.exists():
            return {"status": "failed", "step": "apply", "output": "Plan metadata is missing — run Plan again before applying."}
        try:
            expected_hash = json.loads(meta_path.read_text(encoding="utf-8"))["files_sha256"]
        except (ValueError, KeyError):
            return {"status": "failed", "step": "apply", "output": "Plan metadata is unreadable — run Plan again before applying."}
        if _files_hash(workspace) != expected_hash:
            return {"status": "failed", "step": "apply", "output": "The design changed since the plan was created — run Plan again before applying."}
        result = _run(["terraform", "apply", "-input=false", "-no-color", "tfplan"], workspace)
        if result.returncode == 0:
            meta_path.unlink(missing_ok=True)
        return {"status": "deployed" if result.returncode == 0 else "failed", "step": "apply", "output": _output(result)}


def plan_destroy(project_id: str) -> Dict:
    """Create a reviewable destroy plan bound to the current workspace files.

    Destroying what was *deployed* means using the workspace files from the
    last plan/apply — not regenerating from the (possibly changed) canvas.
    """
    with _project_lock(project_id):
        workspace = _workspace(project_id)
        if not any(workspace.glob("*.tf")):
            return {"status": "failed", "step": "plan-destroy", "output": "No Terraform workspace found — run a Plan first."}
        init = _run(["terraform", "init", "-input=false", "-no-color"], workspace)
        if init.returncode != 0:
            return {"status": "failed", "step": "init", "output": _output(init)}
        planned = _run(["terraform", "plan", "-destroy", "-input=false", "-no-color", "-out=tfdestroy"], workspace)
        if planned.returncode == 0:
            meta = {"files_sha256": _files_hash(workspace)}
            (workspace / DESTROY_META_FILENAME).write_text(json.dumps(meta), encoding="utf-8")
        return {
            "status": "destroy_planned" if planned.returncode == 0 else "failed",
            "step": "plan-destroy",
            "output": _output(planned),
        }


def destroy(project_id: str) -> Dict:
    """Apply the previously created destroy plan (two-step, reviewed destroy)."""
    with _project_lock(project_id):
        workspace = _workspace(project_id)
        if not (workspace / "tfdestroy").exists():
            return {"status": "failed", "step": "destroy", "output": "Run a destroy plan before destroying infrastructure."}
        meta_path = workspace / DESTROY_META_FILENAME
        if not meta_path.exists():
            return {"status": "failed", "step": "destroy", "output": "Destroy plan metadata is missing — run the destroy plan again."}
        try:
            expected_hash = json.loads(meta_path.read_text(encoding="utf-8"))["files_sha256"]
        except (ValueError, KeyError):
            return {"status": "failed", "step": "destroy", "output": "Destroy plan metadata is unreadable — run the destroy plan again."}
        if _files_hash(workspace) != expected_hash:
            return {"status": "failed", "step": "destroy", "output": "The workspace changed since the destroy plan was created — run the destroy plan again."}
        # Applying the saved destroy plan executes exactly what was reviewed.
        result = _run(["terraform", "apply", "-input=false", "-no-color", "tfdestroy"], workspace)
        if result.returncode == 0:
            meta_path.unlink(missing_ok=True)
        return {"status": "destroyed" if result.returncode == 0 else "failed", "step": "destroy", "output": _output(result)}


def clear(project_id: str, force: bool = False) -> Dict:
    """Remove the local workspace (state, plans, cached providers).

    Refuses to run while the state file still tracks live resources — deleting
    the state would orphan real cloud infrastructure (it keeps running with
    nothing left to manage it). Pass ``force=True`` to override deliberately.
    """
    with _project_lock(project_id):
        state = _read_state(project_id)
        resources = _parse_state_resources(state)
        if resources and not force:
            return {
                "status": "blocked",
                "live_resources": len(resources),
                "addresses": [f"{r['type']}.{r['name']}" for r in resources][:50],
                "message": (
                    f"{len(resources)} live resources are deployed. Destroy "
                    f"them first (Plan Destroy → Destroy) or force-clear to "
                    f"orphan them in your cloud account."
                ),
            }
        shutil.rmtree(DEPLOYMENT_ROOT / project_id, ignore_errors=True)
        return {"status": "cleared"}


def _output(result: subprocess.CompletedProcess[str]) -> str:
    return (result.stdout + "\n" + result.stderr).strip()[-20000:]


# ════════════════════════════════════════════════════════════════════════════
# Live infrastructure tracking
# ════════════════════════════════════════════════════════════════════════════
# Terraform's state file is the source of truth for what CloudForge deployed.
# Reading it directly is provider-agnostic, needs no cloud API calls and no
# provider schemas, and stays in sync with plan/apply/destroy automatically.

# Whitelisted state attributes per resource type. Never expose raw state —
# it can contain sensitive values (e.g. password_data, secrets).
_ATTR_WHITELIST: Dict[str, tuple] = {
    "aws_instance": ("id", "instance_state", "public_ip", "private_ip",
                     "instance_type", "availability_zone", "public_dns"),
    "aws_vpc": ("id", "cidr_block"),
    "aws_subnet": ("id", "cidr_block", "availability_zone",
                   "map_public_ip_on_launch"),
    "aws_security_group": ("id", "name", "description"),
    "aws_s3_bucket": ("id", "bucket", "region"),
    "aws_s3_object": ("id", "bucket", "key"),
    "aws_internet_gateway": ("id",),
    "aws_route_table": ("id",),
    "aws_route_table_association": ("id", "subnet_id", "gateway_id"),
    "aws_db_instance": ("id", "address", "port", "db_name", "engine",
                        "engine_version", "instance_class", "multi_az"),
    "aws_lambda_function": ("id", "function_name", "runtime", "handler",
                            "qualified_arn"),
    "aws_dynamodb_table": ("id", "name", "arn"),
    "aws_iam_role": ("id", "name", "arn"),
    "aws_elasticache_cluster": ("id", "cache_nodes", "node_type"),
    "aws_ecs_cluster": ("id", "name", "arn"),
}

_RESOURCE_CATEGORY: Dict[str, str] = {
    "aws_instance": "compute", "aws_lambda_function": "compute",
    "aws_db_instance": "data", "aws_dynamodb_table": "data",
    "aws_elasticache_cluster": "data", "aws_s3_bucket": "data",
    "aws_s3_object": "data",
    # everything else defaults to "network" (vpc/subnet/igw/rt/sg/…)
}


def _read_state(project_id: str) -> Dict:
    """Return the parsed terraform.tfstate for a project, or {} when absent."""
    if not project_id or Path(project_id).name != project_id or project_id in {".", ".."}:
        raise ValueError("Invalid project id")
    state_path = DEPLOYMENT_ROOT / project_id / "terraform.tfstate"
    if not state_path.is_file():
        return {}
    try:
        return json.loads(state_path.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return {}


def _state_friendly_name(attrs: Dict) -> str:
    tags = attrs.get("tags")
    if isinstance(tags, dict):
        return tags.get("Name") or ""
    return ""


def _parse_state_resources(state: Dict) -> List[Dict]:
    """Extract a UI-friendly list of *managed* resources from a tfstate dict."""
    resources: List[Dict] = []
    for res in state.get("resources", []):
        if res.get("mode") != "managed":
            continue  # data sources are lookups, not live infrastructure
        rtype = res.get("type", "unknown")
        rname = res.get("name", "")
        allow = set(_ATTR_WHITELIST.get(rtype, ("id", "arn")))
        for inst in res.get("instances", []):
            attrs = inst.get("attributes")
            if not isinstance(attrs, dict):
                continue
            index_key = inst.get("index_key")
            address = f"{rtype}.{rname}"
            if index_key is not None:
                address += f"[{index_key}]"
            resources.append({
                "address": address,
                "type": rtype,
                "name": rname,
                "label": _state_friendly_name(attrs) or rname,
                "id": attrs.get("id") or attrs.get("bucket") or attrs.get("name") or "",
                "category": _RESOURCE_CATEGORY.get(rtype, "network"),
                "attributes": {
                    k: attrs.get(k)
                    for k in sorted(allow)
                    if attrs.get(k) not in (None, "")
                },
            })
    return resources


def _workspace_region(workspace: Path) -> str:
    """Best-effort deployment region (parsed from the generated variables.tf)."""
    try:
        for tf in workspace.glob("*.tf"):
            match = re.search(
                r'variable\s+"aws_region"\s*\{[^}]*?default\s*=\s*"([^"]+)"',
                tf.read_text(encoding="utf-8", errors="ignore"),
                re.S,
            )
            if match:
                return match.group(1)
    except OSError:
        pass
    return os.getenv("AWS_DEFAULT_REGION", "us-east-1")


def infrastructure(project_id: str) -> Dict:
    """Summarise the live infrastructure a project has deployed.

    Reads the Terraform state file directly — no cloud API calls — so the
    response reflects exactly what the last successful apply created, and it
    stays correct after plan-destroy/destroy as well.
    """
    with _project_lock(project_id):
        workspace = DEPLOYMENT_ROOT / project_id
        state = _read_state(project_id)
        resources = _parse_state_resources(state)
        region = _workspace_region(workspace)
        state_path = workspace / "terraform.tfstate"
        if not resources:
            return {
                "status": "not_deployed",
                "resources": [],
                "outputs": {},
                "region": region,
                "state_updated_at": None,
            }
        outputs = {
            key: value.get("value")
            for key, value in (state.get("outputs") or {}).items()
            if isinstance(value, dict) and "value" in value
        }
        return {
            "status": "deployed",
            "resources": resources,
            "outputs": outputs,
            "region": region,
            "state_updated_at": (
                state_path.stat().st_mtime if state_path.is_file() else None
            ),
        }


def infrastructure_summary(project_ids: List[str]) -> List[Dict]:
    """Bulk variant of ``infrastructure`` for dashboards.

    Returns one entry per project id that currently has live resources (in the
    order given), each enriched with ``resource_count`` and per-category
    ``categories`` counts so the UI can render compact stack cards. Projects
    without live infrastructure are omitted.
    """
    summaries: List[Dict] = []
    for project_id in project_ids:
        data = infrastructure(project_id)
        if data.get("status") != "deployed":
            continue
        categories: Dict[str, int] = {"compute": 0, "network": 0, "data": 0}
        for resource in data["resources"]:
            cat = resource["category"]
            categories[cat] = categories.get(cat, 0) + 1
        data["project_id"] = project_id
        data["resource_count"] = len(data["resources"])
        data["categories"] = categories
        summaries.append(data)
    return summaries


def parse_resource_count(output: str, kind: str):
    """Parse the resource count from terraform text output.

    ``kind`` selects which summary line to look for:
      - "plan_add"          -> "Plan: 12 to add"
      - "apply_added"       -> "Resources: 12 added"
      - "plan_destroy"      -> "Plan: 12 to destroy"
      - "destroy_destroyed" -> "Resources: 12 destroyed"
    Returns None when the line is absent/unparseable.
    """
    patterns = {
        "plan_add": r"Plan:\s+(\d+)\s+to add",
        "apply_added": r"(\d+)\s+added",
        "plan_destroy": r"Plan:\s+(\d+)\s+to destroy",
        "destroy_destroyed": r"(\d+)\s+destroyed",
    }
    pattern = patterns.get(kind)
    if not pattern:
        return None
    match = re.search(pattern, output or "")
    return int(match.group(1)) if match else None
