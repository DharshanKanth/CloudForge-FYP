from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models.project import Project
from app.models.architecture import Architecture
from app.models.user import User
from app.schemas.architecture import ArchitectureSave, ArchitectureResponse, ValidationResult
from app.core.deps import get_current_user
from app.services.validation_service import validate_architecture

router = APIRouter()


@router.get("/{project_id}/architecture", response_model=ArchitectureResponse)
async def get_architecture(
    project_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _ensure_project_access(project_id, current_user.id, db)

    result = await db.execute(
        select(Architecture).where(Architecture.project_id == project_id)
    )
    arch = result.scalar_one_or_none()
    if not arch:
        raise HTTPException(status_code=404, detail="Architecture not found")
    return arch


@router.put("/{project_id}/architecture", response_model=ArchitectureResponse)
async def save_architecture(
    project_id: str,
    arch_data: ArchitectureSave,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _ensure_project_access(project_id, current_user.id, db)

    result = await db.execute(
        select(Architecture).where(Architecture.project_id == project_id)
    )
    arch = result.scalar_one_or_none()

    if arch:
        arch.nodes = arch_data.nodes
        arch.edges = arch_data.edges
        arch.aws_region = arch_data.aws_region
        arch.version = arch.version + 1
    else:
        arch = Architecture(
            project_id=project_id,
            nodes=arch_data.nodes,
            edges=arch_data.edges,
            aws_region=arch_data.aws_region,
        )
        db.add(arch)

    # Update project's updated_at
    proj_result = await db.execute(select(Project).where(Project.id == project_id))
    project = proj_result.scalar_one_or_none()
    if project:
        project.status = "saved"

    try:
        await db.commit()
    except IntegrityError:
        # Two concurrent first saves can both take the insert path on the
        # unique project_id; fall back to updating the winner's row.
        await db.rollback()
        result = await db.execute(
            select(Architecture).where(Architecture.project_id == project_id)
        )
        arch = result.scalar_one_or_none()
        if not arch:
            raise
        arch.nodes = arch_data.nodes
        arch.edges = arch_data.edges
        arch.version = arch.version + 1
        await db.commit()
    await db.refresh(arch)
    return arch


@router.post("/{project_id}/validate", response_model=ValidationResult)
async def validate_project_architecture(
    project_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _ensure_project_access(project_id, current_user.id, db)

    result = await db.execute(
        select(Architecture).where(Architecture.project_id == project_id)
    )
    arch = result.scalar_one_or_none()
    if not arch:
        raise HTTPException(status_code=404, detail="Architecture not found")

    return validate_architecture(arch.nodes, arch.edges)


async def _ensure_project_access(project_id: str, user_id: str, db: AsyncSession):
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.user_id == user_id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Project not found")
