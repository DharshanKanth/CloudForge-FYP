from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List
from app.database import get_db
from app.models.project import Project
from app.models.architecture import Architecture
from app.models.user import User
from app.schemas.project import ProjectCreate, ProjectUpdate, ProjectResponse
from app.core.deps import get_current_user

router = APIRouter()


@router.post("", response_model=ProjectResponse)
async def create_project(
    project_data: ProjectCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = Project(
        user_id=current_user.id,
        name=project_data.name,
        description=project_data.description,
        provider=project_data.provider,
    )
    db.add(project)
    # flush() populates project.id (Python-side uuid default) without ending
    # the transaction, so the project and its empty architecture are created
    # atomically — a failure can no longer leave a project with no architecture.
    await db.flush()

    arch = Architecture(project_id=project.id, nodes=[], edges=[])
    db.add(arch)
    await db.commit()
    await db.refresh(project)

    return _project_to_response(project, 0)


@router.get("", response_model=List[ProjectResponse])
async def list_projects(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Single query: join each project with its (unique) architecture to obtain
    # resource counts, instead of issuing one query per project (N+1).
    result = await db.execute(
        select(Project, Architecture)
        .outerjoin(Architecture, Architecture.project_id == Project.id)
        .where(Project.user_id == current_user.id)
        .order_by(Project.updated_at.desc())
    )
    rows = result.all()

    return [
        _project_to_response(
            project,
            len(arch.nodes) if arch and arch.nodes else 0,
        )
        for project, arch in rows
    ]


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = await _get_project_or_404(project_id, current_user.id, db)
    arch_result = await db.execute(
        select(Architecture).where(Architecture.project_id == project.id)
    )
    arch = arch_result.scalar_one_or_none()
    count = len(arch.nodes) if arch and arch.nodes else 0
    return _project_to_response(project, count)


@router.put("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: str,
    project_data: ProjectUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = await _get_project_or_404(project_id, current_user.id, db)

    if project_data.name is not None:
        project.name = project_data.name
    if project_data.description is not None:
        project.description = project_data.description
    if project_data.status is not None:
        project.status = project_data.status

    await db.commit()
    await db.refresh(project)

    arch_result = await db.execute(
        select(Architecture).where(Architecture.project_id == project.id)
    )
    arch = arch_result.scalar_one_or_none()
    count = len(arch.nodes) if arch and arch.nodes else 0
    return _project_to_response(project, count)


@router.delete("/{project_id}")
async def delete_project(
    project_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = await _get_project_or_404(project_id, current_user.id, db)
    await db.delete(project)
    await db.commit()
    return {"message": "Project deleted"}


async def _get_project_or_404(project_id: str, user_id: str, db: AsyncSession) -> Project:
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.user_id == user_id)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


def _project_to_response(project: Project, resource_count: int) -> ProjectResponse:
    return ProjectResponse(
        id=project.id,
        user_id=project.user_id,
        name=project.name,
        description=project.description,
        provider=project.provider,
        status=project.status,
        created_at=project.created_at,
        updated_at=project.updated_at,
        resource_count=resource_count,
    )
