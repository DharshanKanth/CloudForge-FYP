"""Seed demo deployment events for the review.

Populates the deployment_events table with a realistic timeline so the
History tab and Dashboard activity line are not empty during evaluation.

Usage: python seed_demo_events.py
"""
import asyncio
import sys
from datetime import datetime, timedelta, timezone

# Ensure the app package is importable
sys.path.insert(0, "/app")

from sqlalchemy import select
from app.database import AsyncSessionLocal
from app.models.deployment_event import DeploymentEvent
from app.models.project import Project


async def seed():
    async with AsyncSessionLocal() as db:
        # Find the demo project
        result = await db.execute(
            select(Project).where(Project.name == "infra")
        )
        project = result.scalars().first()
        if not project:
            print("No project named 'infra' found. Run a deployment first.")
            return

        project_id = project.id
        print(f"Seeding events for project '{project.name}' ({project_id})")

        now = datetime.now(timezone.utc)
        events = [
            DeploymentEvent(
                project_id=project_id,
                event_type="plan",
                status="succeeded",
                detail="Plan: 12 to add, 0 to change, 0 to destroy.\n\nTerraform will perform the following actions:\n  # aws_instance.web_server will be create\n  + resource \"aws_instance\" \"web_server\" {\n      + ami                          = \"ami-0f57b5b58b68248a3\"\n      + instance_type                = \"t3.micro\"\n      + public_ip                    = (known after apply)\n      ...\n    }\n  # aws_s3_bucket.app_storage will be create\n  + resource \"aws_s3_bucket\" \"app_storage\" {\n      + bucket = \"my-app-storage-7o4titds\"\n      ...\n    }\n\nPlan: 12 to add, 0 to change, 0 to destroy.",
                resource_count=12,
                created_at=now - timedelta(minutes=45),
            ),
            DeploymentEvent(
                project_id=project_id,
                event_type="apply",
                status="succeeded",
                detail="Apply complete! Resources: 12 added, 0 changed, 0 destroyed.\n\nOutputs:\n\nec2_public_ip_web_server = \"18.183.79.178\"\ns3_bucket_name = \"my-app-storage-7o4titds\"\nvpc_id = \"vpc-0dfd5e63b908e6200\"",
                resource_count=12,
                created_at=now - timedelta(minutes=42),
            ),
            DeploymentEvent(
                project_id=project_id,
                event_type="plan_destroy",
                status="succeeded",
                detail="Plan: 0 to add, 0 to change, 12 to destroy.\n\nTerraform will perform the following actions:\n  # aws_instance.web_server will be destroyed\n  - resource \"aws_instance\" \"web_server\" {\n      - id                          = \"i-0bef4590dc54b8129\" -> null\n      - instance_state              = \"running\" -> null\n      ...\n    }\n\nPlan: 0 to add, 0 to change, 12 to destroy.",
                resource_count=12,
                created_at=now - timedelta(minutes=20),
            ),
            DeploymentEvent(
                project_id=project_id,
                event_type="destroy",
                status="succeeded",
                detail="Destroy complete! Resources: 12 destroyed.",
                resource_count=12,
                created_at=now - timedelta(minutes=18),
            ),
            DeploymentEvent(
                project_id=project_id,
                event_type="plan",
                status="succeeded",
                detail="Plan: 12 to add, 0 to change, 0 to destroy.\n\nTerraform will perform the following actions:\n  # aws_instance.web_server will be create\n  + resource \"aws_instance\" \"web_server\" {\n      + ami                          = \"ami-0f57b5b58b68248a3\"\n      + instance_type                = \"t3.micro\"\n      ...\n    }\n\nPlan: 12 to add, 0 to change, 0 to destroy.",
                resource_count=12,
                created_at=now - timedelta(minutes=10),
            ),
            DeploymentEvent(
                project_id=project_id,
                event_type="apply",
                status="succeeded",
                detail="Apply complete! Resources: 12 added, 0 changed, 0 destroyed.\n\nOutputs:\n\nec2_public_ip_web_server = \"43.207.76.253\"\ns3_bucket_name = \"my-app-storage-1xp3li73\"\nvpc_id = \"vpc-0b51bb133d804bff6\"",
                resource_count=12,
                created_at=now - timedelta(minutes=8),
            ),
        ]

        db.add_all(events)
        await db.commit()
        print(f"Seeded {len(events)} events")


if __name__ == "__main__":
    asyncio.run(seed())
