from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models.project import Project
from app.models.architecture import Architecture
from app.models.user import User
from app.models.deployment_event import DeploymentEvent
from app.schemas.terraform import TerraformGenerateResponse, TerraformValidationResult
from app.core.deps import get_current_user
from app.services.terraform_service import generate_terraform_files
from app.services.validation_service import validate_architecture
from app.services.zip_service import create_terraform_zip
from app.services import deployment_service, cloud_service, deployment_state, cloud_ops_service
import json
import subprocess
import asyncio

router = APIRouter()


async def _create_event(
    db: AsyncSession,
    project_id: str,
    event_type: str,
    status: str,
    detail: str = "",
    resource_count=None,
):
    """Record one entry in the project's deployment history (audit log)."""
    db.add(DeploymentEvent(
        project_id=project_id,
        event_type=event_type,
        status=status,
        detail=(detail or "")[:500],
        resource_count=resource_count,
    ))
    await db.commit()


@router.post("/{project_id}/terraform/generate", response_model=TerraformGenerateResponse)
async def generate_terraform(
    project_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = await _get_project(project_id, current_user.id, db)
    arch = await _get_architecture(project_id, db)

    validation = validate_architecture(arch.nodes, arch.edges)

    files = _generate_or_400(project, arch)

    if project.status in {
        deployment_state.DRAFT, deployment_state.VALIDATED,
        deployment_state.GENERATED, deployment_state.FAILED, deployment_state.DESTROYED,
    }:
        project.status = deployment_state.GENERATED
        await db.commit()

    return TerraformGenerateResponse(
        project_id=project_id,
        provider=project.provider,
        files=files,
        validation={"valid": validation.valid, "issues": [i.model_dump() for i in validation.issues]},
    )


@router.get("/{project_id}/terraform")
async def get_terraform(
    project_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = await _get_project(project_id, current_user.id, db)
    arch = await _get_architecture(project_id, db)

    files = _generate_or_400(project, arch)

    return {
        "project_id": project_id,
        "provider": project.provider,
        "files": [{"filename": f.filename, "content": f.content} for f in files],
    }


@router.get("/{project_id}/terraform/download")
async def download_terraform_zip(
    project_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = await _get_project(project_id, current_user.id, db)
    arch = await _get_architecture(project_id, db)

    files = _generate_or_400(project, arch)

    zip_buffer = create_terraform_zip(files, project.name)

    safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in project.name)
    filename = f"cloudforge-{safe_name}.zip"

    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/{project_id}/terraform/plan")
async def plan_terraform(
    project_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = await _get_project(project_id, current_user.id, db)
    arch = await _get_architecture(project_id, db)
    validation = validate_architecture(arch.nodes, arch.edges)
    if not validation.valid:
        raise HTTPException(status_code=422, detail={
            "message": "Fix validation errors before creating a deployment plan.",
            "issues": [issue.model_dump() for issue in validation.issues],
        })
    files = _generate_or_400(project, arch)
    env_extra = await cloud_service.aws_env_for_user(db, project.user_id)
    result = await _run_deployment(deployment_service.plan, project_id, files, env_extra)
    if result["status"] == "planned":
        project.status = deployment_state.READY
    else:
        project.status = deployment_state.FAILED
    await db.commit()
    await _create_event(
        db, project_id, "plan",
        "succeeded" if result["status"] == "planned" else "failed",
        result.get("output", ""),
        deployment_service.parse_resource_count(result.get("output", ""), "plan_add"),
    )
    return result


@router.post("/{project_id}/terraform/apply")
async def apply_terraform(
    project_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = await _get_project(project_id, current_user.id, db)
    env_extra = await cloud_service.aws_env_for_user(db, project.user_id)
    if project.status == deployment_state.READY:
        project.status = deployment_state.DEPLOYING
        await db.commit()
    result = await _run_deployment(deployment_service.apply, project_id, env_extra)
    project.status = (
        deployment_state.DEPLOYED if result["status"] == "deployed" else deployment_state.FAILED
    )
    await db.commit()
    await _create_event(
        db, project_id, "apply",
        "succeeded" if result["status"] == "deployed" else "failed",
        result.get("output", ""),
        deployment_service.parse_resource_count(result.get("output", ""), "apply_added"),
    )
    return result


@router.get("/{project_id}/terraform/infrastructure")
async def get_infrastructure(
    project_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List the live infrastructure this project has deployed.

    Reads the Terraform state file — the source of truth for the last
    successful apply — so the UI can show exactly what is running (instance
    IDs, public IPs, bucket names) without any cloud API calls.
    """
    project = await _get_project(project_id, current_user.id, db)
    return deployment_service.infrastructure(project.id)


@router.post("/{project_id}/terraform/resources/{address}/{action}")
async def resource_power(
    project_id: str,
    address: str,
    action: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Start or stop a compute resource in place (provider API, not destroy)."""
    if action not in ("start", "stop"):
        raise HTTPException(status_code=400, detail="action must be 'start' or 'stop'")
    project = await _get_project(project_id, current_user.id, db)
    live = deployment_service.infrastructure(project.id)
    target = next((r for r in live.get("resources", []) if r["address"] == address), None)
    if not target:
        raise HTTPException(status_code=404, detail="Resource not found in the deployed state")
    if not target.get("controllable"):
        raise HTTPException(status_code=400, detail=f"{target['type']} does not support start/stop")

    env_extra = await cloud_service.aws_env_for_user(db, project.user_id)
    result = await asyncio.to_thread(
        cloud_ops_service.power, [target["id"]], action, env_extra, live.get("region", "")
    )
    await _create_event(
        db, project_id, action,
        "succeeded" if result.get("state") in ("started", "stopped") else "failed",
        result.get("message") or f"{action} {target['id']}",
        None,
    )
    return result


@router.delete("/{project_id}/terraform/clear")
async def clear_workspace(
    project_id: str,
    force: bool = False,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete the local Terraform workspace (state, plans) for a project.

    Blocked with 409 while the state file tracks live resources — clearing
    then would orphan real cloud infrastructure. Pass ``?force=true`` to
    override deliberately (e.g. you already destroyed the resources).
    """
    project = await _get_project(project_id, current_user.id, db)
    result = deployment_service.clear(project.id, force=force)
    if result.get("status") == "blocked":
        raise HTTPException(status_code=409, detail=result)
    project.status = deployment_state.DRAFT
    await db.commit()
    await _create_event(
        db, project_id, "clear",
        "succeeded",
        result.get("message", "Workspace cleared"),
        result.get("live_resources"),
    )
    return result


@router.post("/{project_id}/terraform/plan-destroy")
async def plan_destroy_terraform(
    project_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Trust the Terraform state file (the source of truth for what is actually
    # deployed) over the DB `status` column, which can drift out of sync —
    # e.g. after a Dashboard-driven redeploy or a partial teardown. Without
    # this, a live stack behind a stale "saved" status is impossible to destroy.
    live = deployment_service.infrastructure(project_id)
    if live.get("status") != "deployed":
        raise HTTPException(status_code=409, detail="Nothing is deployed for this project yet.")
    env_extra = await cloud_service.aws_env_for_user(db, current_user.id)
    result = await _run_deployment(deployment_service.plan_destroy, project_id, env_extra)
    await _create_event(
        db, project_id, "plan_destroy",
        "succeeded" if result["status"] == "destroy_planned" else "failed",
        result.get("output", ""),
        deployment_service.parse_resource_count(result.get("output", ""), "plan_destroy"),
    )
    return result


@router.post("/{project_id}/terraform/destroy")
async def destroy_terraform(
    project_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = await _get_project(project_id, current_user.id, db)
    env_extra = await cloud_service.aws_env_for_user(db, project.user_id)
    project.status = deployment_state.DESTROYING
    await db.commit()
    result = await _run_deployment(deployment_service.destroy, project_id, env_extra)
    project.status = (
        deployment_state.DESTROYED if result["status"] == "destroyed" else deployment_state.FAILED
    )
    await db.commit()
    await _create_event(
        db, project_id, "destroy",
        "succeeded" if result["status"] == "destroyed" else "failed",
        result.get("output", ""),
        deployment_service.parse_resource_count(result.get("output", ""), "destroy_destroyed"),
    )
    return result


@router.get("/{project_id}/deployment-events")
async def get_deployment_events(
    project_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return the deployment history (audit log) for a project, newest first.

    Every plan/apply/plan-destroy/destroy/clear action is recorded so the UI
    can render a timeline of what was deployed, when, and whether it succeeded.
    """
    await _get_project(project_id, current_user.id, db)
    result = await db.execute(
        select(DeploymentEvent)
        .where(DeploymentEvent.project_id == project_id)
        .order_by(DeploymentEvent.created_at.desc())
        .limit(100)
    )
    return [event.to_dict() for event in result.scalars().all()]


def _generate_or_400(project: Project, arch: Architecture):
    """Generate Terraform, mapping configuration errors to 400 instead of 500."""
    try:
        return generate_terraform_files(
            provider=project.provider,
            nodes=arch.nodes,
            edges=arch.edges,
            project_name=project.name,
            aws_region=arch.aws_region,
        )
    except (ValueError, NotImplementedError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))


async def _run_deployment(operation, project_id: str, *args):
    import asyncio
    try:
        return await asyncio.to_thread(operation, project_id, *args)
    except FileNotFoundError:
        return {"status": "failed", "step": "terraform", "output": "Terraform CLI is not available."}
    except subprocess.TimeoutExpired:
        return {"status": "failed", "step": "terraform", "output": "Terraform command timed out."}


async def _get_project(project_id: str, user_id: str, db: AsyncSession) -> Project:
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.user_id == user_id)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


async def _get_architecture(project_id: str, db: AsyncSession) -> Architecture:
    result = await db.execute(
        select(Architecture).where(Architecture.project_id == project_id)
    )
    arch = result.scalar_one_or_none()
    if not arch:
        raise HTTPException(status_code=404, detail="Architecture not found. Save your design first.")
    return arch
