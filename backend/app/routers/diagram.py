"""Deterministic architecture-diagram import endpoint.

Parsing is pure CPU work — no AI, no persistence, no deployment. The endpoint
returns a validated canvas proposal that the user reviews before saving.
"""
import logging

from fastapi import APIRouter, Depends, HTTPException

from app.core.deps import get_current_user
from app.models.user import User
from app.schemas.diagram import DiagramImportRequest, DiagramImportResponse
from app.services import diagram_import

router = APIRouter()
logger = logging.getLogger("cloudforge.diagram")


@router.post("/import", response_model=DiagramImportResponse)
async def import_diagram(
    req: DiagramImportRequest,
    current_user: User = Depends(get_current_user),
):
    """Read a draw.io / Mermaid / JSON diagram into a validated canvas proposal."""
    try:
        result = diagram_import.import_diagram(req.filename, req.content)
    except diagram_import.DiagramParseError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:  # noqa: BLE001 - normalize to a clear client error
        logger.exception("Diagram import failed")
        raise HTTPException(status_code=422, detail=f"Could not read the diagram: {exc}")
    return DiagramImportResponse(**result)
