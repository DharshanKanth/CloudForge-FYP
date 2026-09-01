from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models.project import Project
from app.models.architecture import Architecture
from app.models.user import User
from app.schemas.terraform import TerraformGenerateResponse, TerraformValidationResult
from app.core.deps import get_current_user
from app.services.terraform_service import generate_terraform_files
from app.services.validation_service import validate_architecture
from app.services.zip_service import create_terraform_zip
import json

router = APIRouter()


@router.post("/{project_id}/terraform/generate", response_model=TerraformGenerateResponse)
async def generate_terraform(
    project_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = await _get_project(project_id, current_user.id, db)
    arch = await _get_architecture(project_id, db)

    validation = validate_architecture(arch.nodes, arch.edges)

    files = generate_terraform_files(
        provider=project.provider,
        nodes=arch.nodes,
        edges=arch.edges,
        project_name=project.name,
    )

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

    files = generate_terraform_files(
        provider=project.provider,
        nodes=arch.nodes,
        edges=arch.edges,
        project_name=project.name,
    )

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

    files = generate_terraform_files(
        provider=project.provider,
        nodes=arch.nodes,
        edges=arch.edges,
        project_name=project.name,
    )

    zip_buffer = create_terraform_zip(files, project.name)

    safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in project.name)
    filename = f"cloudforge-{safe_name}.zip"

    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


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
