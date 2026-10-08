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
    AIFixResponse,
    AIProjectRequest,
    AIStatusResponse,
    AITextResponse,
    AITroubleshootRequest,
)
from app.services import ai_service
from app.services.autofix_service import auto_fix
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


async def _get_arch(db: AsyncSession, project_id: str) -> Architecture:
    arch = (await db.execute(
        select(Architecture).where(Architecture.project_id == project_id)
    )).scalar_one_or_none()
    if not arch:
        raise HTTPException(status_code=404, detail="Architecture not found. Save your design first.")
    return arch


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
    except ai_service.AIProviderError as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    except (ValueError, ValidationError) as exc:
        raise HTTPException(status_code=502, detail=f"AI returned an unusable response: {exc}")

    nodes, edges = ai_service.to_canvas(arch)
    # Deterministically clean up the model's draft (missing required fields,
    # orphan resources, invalid/duplicate edges) before showing it, so the
    # suggestion is valid or as close as possible.
    nodes, edges = auto_fix(nodes, edges)
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
    except ai_service.AIProviderError as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    db.add(AIRecommendation(
        user_id=current_user.id, project_id=project.id, kind="explain",
        prompt=project.name, response=text[:8000], provider=ai_service.status()["provider"],
    ))
    await db.commit()
    return AITextResponse(configured=True, text=text)


@router.post("/fix", response_model=AIFixResponse)
async def fix_architecture_endpoint(
    req: AIProjectRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Ask the AI to correct the current design's validation problems.

    Advisory: the corrected design is re-checked by the deterministic validator
    and the user must apply it.
    """
    if not ai_service.status()["configured"]:
        return AIFixResponse(configured=False, message=_NOT_CONFIGURED)
    project = await _get_project(req.project_id, current_user.id, db)
    arch = await _get_arch(db, project.id)
    before = validate_architecture(arch.nodes, arch.edges)
    if not before.issues:
        return AIFixResponse(
            configured=True, source="none",
            message="No validation issues to fix.", before=before.model_dump()
        )

    def _err(v):
        return sum(1 for i in v.issues if i.level == "error")

    # 1) Deterministic structural repair first (reliable, never worse).
    fixed_nodes, fixed_edges = auto_fix(arch.nodes, arch.edges)
    engine_validation = validate_architecture(fixed_nodes, fixed_edges)
    best_nodes, best_edges, after, source = fixed_nodes, fixed_edges, engine_validation, "engine"

    # 2) If the engine didn't resolve everything, let the AI try on the repaired design.
    if _err(engine_validation) > 0:
        try:
            suggestion = await ai_service.fix_architecture(
                fixed_nodes, fixed_edges, [i.model_dump() for i in engine_validation.issues]
            )
            ai_nodes, ai_edges = ai_service.to_canvas(suggestion)
            ai_validation = validate_architecture(ai_nodes, ai_edges)
            if _err(ai_validation) < _err(engine_validation):
                best_nodes, best_edges, after, source = ai_nodes, ai_edges, ai_validation, "ai"
        except (ai_service.AIProviderError, ValueError, ValidationError):
            pass

    improved = _err(after) < _err(before)
    changed = len(best_edges) != len(arch.edges)
    configured = ai_service.status()["configured"]

    if not improved and not changed:
        return AIFixResponse(
            configured=configured, source="none",
            message="No automatic fix found for these issues.",
            before=before.model_dump(), after=after.model_dump(),
        )

    db.add(AIRecommendation(
        user_id=current_user.id, project_id=project.id, kind="fix",
        prompt=f"{len(before.issues)} validation issues",
        response=json.dumps({"source": source, "before_errors": _err(before), "after_errors": _err(after)})[:4000],
        provider="engine" if source == "engine" else ai_service.status()["provider"],
    ))
    await db.commit()

    return AIFixResponse(
        configured=configured,
        source=source,
        nodes=best_nodes,
        edges=best_edges,
        before=before.model_dump(),
        after=after.model_dump(),
    )


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
    except ai_service.AIProviderError as exc:
        raise HTTPException(status_code=502, detail=str(exc))
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
