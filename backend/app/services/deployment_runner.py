"""Executes queued deployment jobs in the worker process.

The API enqueues a ``Deployment`` row; the worker claims it (``FOR UPDATE SKIP
LOCKED``), runs Terraform, and streams every output line into
``deployment_logs`` so the UI can follow along live.
"""
import asyncio
import logging
from datetime import datetime, timezone
from queue import Empty, Queue
from typing import Dict, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal
from app.models.architecture import Architecture
from app.models.deployment import Deployment, DeploymentLog
from app.models.deployment_event import DeploymentEvent
from app.models.project import Project
from app.services import cloud_service, deployment_service, deployment_state
from app.services.terraform_service import generate_terraform_files

logger = logging.getLogger("cloudforge.worker")

SUCCESS_STATES = {"planned", "deployed", "destroy_planned", "destroyed"}
RESOURCE_COUNT_KEY = {
    "plan": "plan_add",
    "apply": "apply_added",
    "plan_destroy": "plan_destroy",
    "destroy": "destroy_destroyed",
}


async def claim_next(db: AsyncSession) -> Optional[str]:
    """Atomically claim the oldest queued deployment, or None."""
    stmt = (
        select(Deployment)
        .where(Deployment.status == "queued")
        .order_by(Deployment.created_at)
        .with_for_update(skip_locked=True)
        .limit(1)
    )
    job = (await db.execute(stmt)).scalar_one_or_none()
    if job is None:
        return None
    job.status = "running"
    job.started_at = datetime.now(timezone.utc)
    await db.commit()
    return job.id


def _run_callable(operation: str, project_id: str, files, env_extra: Dict[str, str]):
    """Return (callable, base positional args) for the operation.

    The streaming callback is appended by the caller as the final argument.
    """
    if operation == "plan":
        return deployment_service.plan, (project_id, files, env_extra)
    if operation == "apply":
        return deployment_service.apply, (project_id, env_extra)
    if operation == "plan_destroy":
        return deployment_service.plan_destroy, (project_id, env_extra)
    if operation == "destroy":
        return deployment_service.destroy, (project_id, env_extra)
    raise ValueError(f"Unknown operation: {operation}")


def _project_state_for(operation: str, ok: bool) -> str:
    if not ok:
        return deployment_state.FAILED
    if operation == "plan":
        return deployment_state.READY
    if operation == "apply":
        return deployment_state.DEPLOYED
    if operation == "destroy":
        return deployment_state.DESTROYED
    return deployment_state.DEPLOYED  # plan_destroy keeps it deployed


async def run_job(deployment_id: str) -> None:
    async with AsyncSessionLocal() as db:
        job = (await db.execute(select(Deployment).where(Deployment.id == deployment_id))).scalar_one_or_none()
        if job is None:
            return
        project = (await db.execute(select(Project).where(Project.id == job.project_id))).scalar_one_or_none()
        arch = (await db.execute(select(Architecture).where(Architecture.project_id == job.project_id))).scalar_one_or_none()
        if project is None or arch is None:
            await _finish(db, job, "failed", None, "Project or architecture not found")
            return

        # Reflect "in progress" on the project for the dashboard.
        if job.operation in ("apply", "destroy") and deployment_state.is_design_editable(project.status):
            project.status = (
                deployment_state.DEPLOYING if job.operation == "apply" else deployment_state.DESTROYING
            )
            await db.commit()

        try:
            files = generate_terraform_files(
                provider=project.provider, nodes=arch.nodes, edges=arch.edges,
                project_name=project.name, aws_region=arch.aws_region,
            )
        except Exception as exc:  # generation/validation errors are job failures
            await _finish(db, job, "failed", None, f"Terraform generation failed: {exc}")
            await _update_project_and_event(db, job, project, ok=False, output="")
            return

        env_extra = await cloud_service.aws_env_for_user(db, project.user_id)

        try:
            func, base_args = _run_callable(job.operation, job.project_id, files, env_extra)
        except ValueError as exc:
            await _finish(db, job, "failed", None, str(exc))
            return

        line_q: "Queue[str]" = Queue()

        def on_line(line: str) -> None:
            line_q.put(line)

        task = asyncio.ensure_future(asyncio.to_thread(func, *base_args, on_line))

        seq = 0
        while not task.done() or not line_q.empty():
            try:
                line = line_q.get_nowait()
                db.add(DeploymentLog(deployment_id=job.id, seq=seq, message=line[:4000]))
                seq += 1
                await db.commit()
            except Empty:
                await asyncio.sleep(0.15)

        try:
            result = await task
        except FileNotFoundError:
            result = {"status": "failed", "step": "terraform", "output": "Terraform CLI is not available."}
        except Exception as exc:  # noqa: BLE001
            result = {"status": "failed", "step": job.operation, "output": str(exc)}

        ok = result.get("status") in SUCCESS_STATES
        await _finish(db, job, "succeeded" if ok else "failed", result, None if ok else result.get("output", ""))
        await _update_project_and_event(db, job, project, ok=ok, output=result.get("output", ""))


async def mark_failed(deployment_id: str, error: str) -> None:
    """Mark a queued/running job as failed after an unexpected crash."""
    async with AsyncSessionLocal() as db:
        job = (await db.execute(select(Deployment).where(Deployment.id == deployment_id))).scalar_one_or_none()
        if job is not None and job.status in ("queued", "running"):
            job.status = "failed"
            job.error = str(error)[:2000]
            job.finished_at = datetime.now(timezone.utc)
            await db.commit()


async def _finish(db: AsyncSession, job: Deployment, status: str, result, error) -> None:
    job.status = status
    job.finished_at = datetime.now(timezone.utc)
    if result:
        job.step = result.get("step")
        job.output_tail = (result.get("output") or "")[-20000:]
        job.resource_count = deployment_service.parse_resource_count(
            result.get("output", ""), RESOURCE_COUNT_KEY.get(job.operation, "")
        )
    if error:
        job.error = str(error)[:2000]
    await db.commit()


async def _update_project_and_event(db: AsyncSession, job: Deployment, project: Project, ok: bool, output: str) -> None:
    project.status = _project_state_for(job.operation, ok)
    event_ok = ok
    db.add(DeploymentEvent(
        project_id=job.project_id,
        event_type=job.operation,
        status="succeeded" if event_ok else "failed",
        detail=(output or "")[:500],
        resource_count=job.resource_count,
    ))
    await db.commit()
