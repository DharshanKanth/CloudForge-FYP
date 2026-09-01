from pydantic import BaseModel
from typing import Dict, List, Optional


class TerraformFile(BaseModel):
    filename: str
    content: str


class TerraformGenerateResponse(BaseModel):
    project_id: str
    provider: str
    files: List[TerraformFile]
    validation: Optional[Dict] = None


class TerraformValidationResult(BaseModel):
    fmt_success: bool
    validate_success: bool
    fmt_output: str
    validate_output: str
    terraform_available: bool
