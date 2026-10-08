"""Integration test for the isolated deployment worker.

Runs only when ``CLOUDFORGE_TEST_DB=1`` (CI sets it with a migrated Postgres).
It creates a project + architecture + a queued deployment, stubs Terraform,
drives ``claim_next`` + ``run_job``, and asserts the job succeeds, streams log
rows and advances the project's lifecycle. It cleans up after itself.
"""
import asyncio
import os
import uuid

import pytest
from sqlalchemy import delete, select

from app.database import AsyncSessionLocal
from app.models.architecture import Architecture
from app.models.deployment import Deployment, DeploymentLog
from app.models.deployment_event import DeploymentEvent
from app.models.project import Project
from app.models.user import User
from app.services import deployment_runner, deployment_service

pytestmark = pytest.mark.skipif(
    not os.getenv("CLOUDFORGE_TEST_DB"),
    reason="set CLOUDFORGE_TEST_DB=1 with a migrated database (CI does this)",
)


def _node(i, t, p):
    return {
        "id": i,
        "type": "resourceNode",
        "position": {"x": 0, "y": 0},
        "data": {"label": i, "resourceType": t, "provider": "aws", "properties": p},
    }


def test_worker_claims_runs_and_streams():
    async def scenario():
        ids = {}
        async with AsyncSessionLocal() as db:
            tag = uuid.uuid4().hex[:8]
            user = User(email=f"worker-{tag}@test.io", username=f"worker{tag}", hashed_password="x")
            db.add(user)
            await db.flush()
            project = Project(user_id=user.id, name="Worker IT", provider="aws", status="draft")
            db.add(project)
            await db.flush()
            nodes = [
                _node("vpc", "vpc", {"name": "v", "cidr": "10.0.0.0/16"}),
                _node("sub", "subnet", {"name": "s", "cidr": "10.0.1.0/24"}),
                _node("ec2", "ec2", {"name": "w", "instanceType": "t3.micro"}),
            ]
            edges = [
                {"id": "e1", "source": "vpc", "target": "sub"},
                {"id": "e2", "source": "sub", "target": "ec2"},
            ]
            db.add(Architecture(project_id=project.id, nodes=nodes, edges=edges, aws_region="us-east-1"))
            job = Deployment(project_id=project.id, operation="plan", status="queued")
            db.add(job)
            await db.commit()
            ids = {"user": user.id, "project": project.id, "job": job.id}

        # Claim it exactly once.
        async with AsyncSessionLocal() as db:
            assert await deployment_runner.claim_next(db) == ids["job"]

        # Stub Terraform (sync, like the real plan) and run the job.
        original = deployment_service.plan

        def fake_plan(project_id, files, env_extra=None, on_line=None):
            if on_line:
                on_line("Initializing provider plugins...")
                on_line("Plan: 3 to add, 0 to change, 0 to destroy.")
            return {
                "status": "planned",
                "step": "plan",
                "output": "Plan: 3 to add, 0 to change, 0 to destroy.",
            }

        deployment_service.plan = fake_plan
        try:
            await deployment_runner.run_job(ids["job"])
        finally:
            deployment_service.plan = original

        async with AsyncSessionLocal() as db:
            job = (await db.execute(select(Deployment).where(Deployment.id == ids["job"]))).scalar_one()
            logs = (await db.execute(
                select(DeploymentLog).where(DeploymentLog.deployment_id == ids["job"])
            )).scalars().all()
            project = (await db.execute(select(Project).where(Project.id == ids["project"]))).scalar_one()
            result = {
                "job_status": job.status,
                "resource_count": job.resource_count,
                "log_count": len(logs),
                "project_status": project.status,
            }

        async with AsyncSessionLocal() as db:
            await db.execute(delete(DeploymentLog).where(DeploymentLog.deployment_id == ids["job"]))
            await db.execute(delete(Deployment).where(Deployment.id == ids["job"]))
            await db.execute(delete(DeploymentEvent).where(DeploymentEvent.project_id == ids["project"]))
            await db.execute(delete(Architecture).where(Architecture.project_id == ids["project"]))
            await db.execute(delete(Project).where(Project.id == ids["project"]))
            await db.execute(delete(User).where(User.id == ids["user"]))
            await db.commit()

        return result

    result = asyncio.run(scenario())
    assert result["job_status"] == "succeeded"
    assert result["log_count"] >= 2
    assert result["resource_count"] == 3
    assert result["project_status"] == "ready"
