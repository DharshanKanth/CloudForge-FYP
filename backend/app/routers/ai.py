"""Advisory AI endpoints.

AI never executes infrastructure and never persists an architecture — it
returns a structured suggestion that the deterministic validator scores and
the user must apply through the normal save/validate flow. When no provider is
configured, endpoints return ``configured: false`` (never fabricated output).
"""
import json
import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.database import get_db
from app.models.ai_recommendation import AIRecommendation
from app.models.architecture import Architecture
from app.models.project import Project
from app.models.user import User
from app.schemas.ai import (
    AIArchitectRequest,
    AIArchitectResponse,
    AIProjectRequest,
    AIStatusResponse,
    AITextResponse,
    AITroubleshootRequest,
)
from app.services import ai_service
from app.services.terraform_service import generate_terraform_files
from app.services.validation_service import validate_architecture

router = APIRouter()
logger = logging.getLogger("cloudforge.ai")

_NOT_CONFIGURED = "AI is not configured on the backend. Set AI_PROVIDER and AI_API_KEY (or AI_BASE_URL for a local model)."


async def _get_project(project_id: str, user_id: str, db: AsyncSession) -> Project:
    project = (await db.execute(
        select(Project).where(Project.id == project_id, Project.user_id == user_id)
    )).scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


async def _files_for(db: AsyncSession, project: Project):
    arch = (await db.execute(
        select(Architecture).where(Architecture.project_id == project.id)
    )).scalar_one_or_none()
    if not arch:
        raise HTTPException(status_code=404, detail="Architecture not found. Save your design first.")
    try:
        return generate_terraform_files(
            provider=project.provider, nodes=arch.nodes, edges=arch.edges,
            project_name=project.name, aws_region=arch.aws_region,
        )
    except (ValueError, NotImplementedError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/status", response_model=AIStatusResponse)
async def ai_status(current_user: User = Depends(get_current_user)):
    """Whether the AI layer is configured, and with which provider/model."""
    return ai_service.status()


@router.post("/architect", response_model=AIArchitectResponse)
async def architect(
    req: AIArchitectRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Turn a description into a structured architecture suggestion (advisory)."""
    if not ai_service.status()["configured"]:
        return AIArchitectResponse(configured=False, message=_NOT_CONFIGURED)
    if req.project_id:
        await _get_project(req.project_id, current_user.id, db)

    try:
        arch = await ai_service.recommend_architecture(req.prompt)
    except ai_service.AIUnavailable as exc:
        return AIArchitectResponse(configured=False, message=str(exc))
    except (ValueError, ValidationError) as exc:
        raise HTTPException(status_code=502, detail=f"AI returned an unusable response: {exc}")

    nodes, edges = ai_service.to_canvas(arch)
    validation = validate_architecture(nodes, edges)

    db.add(AIRecommendation(
        user_id=current_user.id, project_id=req.project_id, kind="architecture",
        prompt=req.prompt[:2000],
        response=json.dumps({"rationale": arch.rationale, "node_count": len(nodes)})[:4000],
        provider=ai_service.status()["provider"],
    ))
    await db.commit()

    return AIArchitectResponse(
        configured=True, rationale=arch.rationale, nodes=nodes, edges=edges,
        validation=validation.model_dump(),
    )


@router.post("/explain", response_model=AITextResponse)
async def explain(
    req: AIProjectRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Explain a project's generated Terraform in plain language."""
    if not ai_service.status()["configured"]:
        return AITextResponse(configured=False, message=_NOT_CONFIGURED)
    project = await _get_project(req.project_id, current_user.id, db)
    files = await _files_for(db, project)
    try:
        text = await ai_service.explain_terraform(files)
    except ai_service.AIUnavailable as exc:
        return AITextResponse(configured=False, message=str(exc))
    db.add(AIRecommendation(
        user_id=current_user.id, project_id=project.id, kind="explain",
        prompt=project.name, response=text[:8000], provider=ai_service.status()["provider"],
    ))
    await db.commit()
    return AITextResponse(configured=True, text=text)


@router.post("/troubleshoot", response_model=AITextResponse)
async def troubleshoot(
    req: AITroubleshootRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Explain a Terraform error and suggest a fix (advisory only)."""
    if not ai_service.status()["configured"]:
        return AITextResponse(configured=False, message=_NOT_CONFIGURED)
    project = await _get_project(req.project_id, current_user.id, db)
    files = await _files_for(db, project)
    try:
        text = await ai_service.troubleshoot(req.error, files)
    except ai_service.AIUnavailable as exc:
        return AITextResponse(configured=False, message=str(exc))
    db.add(AIRecommendation(
        user_id=current_user.id, project_id=project.id, kind="troubleshoot",
        prompt=req.error[:2000], response=text[:8000], provider=ai_service.status()["provider"],
    ))
    await db.commit()
    return AITextResponse(configured=True, text=text)


@router.get("/recommendations")
async def list_recommendations(
    project_id: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    stmt = select(AIRecommendation).where(AIRecommendation.user_id == current_user.id)
    if project_id:
        stmt = stmt.where(AIRecommendation.project_id == project_id)
    stmt = stmt.order_by(AIRecommendation.created_at.desc()).limit(50)
    return [r.to_dict() for r in (await db.execute(stmt)).scalars().all()]
