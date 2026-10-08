"""Architecture-diagram import endpoints.

Structured formats (draw.io / Mermaid / JSON) are parsed **deterministically**.
Images are read by an **advisory** vision model. Both paths return a validated
canvas proposal only — nothing is persisted or deployed, and the user must
apply it explicitly.
"""
import base64
import binascii
import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.database import get_db
from app.models.user import User
from app.schemas.diagram import (
    DiagramImageImportRequest,
    DiagramImportRequest,
    DiagramImportResponse,
)
from app.services import ai_config_service, ai_service, diagram_import
from app.services.diagram_import import finalize_proposal
from app.services.validation_service import SUPPORTED_RESOURCE_TYPES

router = APIRouter()
logger = logging.getLogger("cloudforge.diagram")

_MAX_IMAGE_BYTES = 5_000_000


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


@router.post("/import-image", response_model=DiagramImportResponse)
async def import_diagram_image(
    req: DiagramImageImportRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Read an architecture image with a vision model into a canvas proposal."""
    try:
        raw = base64.b64decode(req.content, validate=True)
    except (binascii.Error, ValueError):
        raise HTTPException(status_code=400, detail="The image data is not valid base64.")
    if not raw:
        raise HTTPException(status_code=400, detail="The image is empty.")
    if len(raw) > _MAX_IMAGE_BYTES:
        raise HTTPException(status_code=413, detail="Image is too large (maximum 5 MB).")

    ai_service.set_config(await ai_config_service.resolve_config(db, current_user.id))
    if not ai_service.status()["configured"]:
        raise HTTPException(
            status_code=400,
            detail=(
                "Image import needs a vision-capable AI provider. Configure one in "
                "Settings → AI Assistant (e.g. gpt-4o, or a local model such as qwen2.5-vl)."
            ),
        )

    data_url = f"data:{req.media_type};base64,{req.content}"
    try:
        arch = await ai_service.analyze_diagram_image(data_url)
    except ai_service.AIUnavailable as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except ai_service.AIProviderError as exc:
        raise HTTPException(status_code=502, detail=f"The vision model could not read the image: {exc}")
    except ValueError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"The vision model returned an unusable response: {exc}",
        )

    nodes, edges = ai_service.to_canvas(arch)
    unrecognized = [
        (str(u.get("label", "?")), str(u.get("reason") or "Not a supported AWS resource type"))
        for u in arch.unrecognized
        if isinstance(u, dict) and u.get("label")
    ]
    # Nodes the model gave an unsupported type are dropped by to_canvas; report them.
    for node in arch.nodes:
        if node.resourceType not in SUPPORTED_RESOURCE_TYPES:
            unrecognized.append((node.id, f"Unsupported resource type '{node.resourceType}'"))

    warnings = [
        "Image import is best-effort — a vision model can miss or misread elements. "
        "Review the whole canvas before validating."
    ]
    model = ai_service.current_config().model
    if not ai_service.is_vision_capable(model):
        warnings.append(
            f"The configured model '{model}' is not a known vision model. If this failed, "
            "set a vision-capable model in Settings → AI Assistant."
        )

    return DiagramImportResponse(**finalize_proposal(
        "image", "architecture image", nodes, edges, unrecognized, warnings,
    ))
