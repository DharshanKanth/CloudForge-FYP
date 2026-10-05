"""Bulk live-infrastructure endpoint for the Dashboard.

One request returns the running stacks of every project owned by the current
user — reading Terraform state files, never the cloud APIs.
"""
import asyncio

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.database import get_db
from app.models.project import Project
from app.models.user import User
from app.models.deployment_event import DeploymentEvent
from app.services import deployment_service

router = APIRouter()


@router.get("")
async def list_running_infrastructure(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Summarise live infrastructure across all of the user's projects.

    One entry per project that currently has resources deployed, most
    recently updated first. Scoped to the current user. Each entry also
    carries the latest deployment events for a compact activity line.
    """
    result = await db.execute(
        select(Project)
        .where(Project.user_id == current_user.id)
        .order_by(Project.updated_at.desc())
    )
    projects = result.scalars().all()
    summaries = await asyncio.to_thread(
        deployment_service.infrastructure_summary, [p.id for p in projects]
    )
    if not summaries:
        return []

    # Bulk-load the most recent events for these projects (one query total).
    events_result = await db.execute(
        select(DeploymentEvent)
        .where(DeploymentEvent.project_id.in_([s["project_id"] for s in summaries]))
        .order_by(DeploymentEvent.created_at.desc())
    )
    events_by_project: dict = {}
    for event in events_result.scalars().all():
        events_by_project.setdefault(event.project_id, []).append(event.to_dict())

    meta = {p.id: p for p in projects}
    return [
        {
            **summary,
            "name": meta[summary["project_id"]].name,
            "provider": meta[summary["project_id"]].provider,
            "recent_events": events_by_project.get(summary["project_id"], [])[:4],
        }
        for summary in summaries
    ]