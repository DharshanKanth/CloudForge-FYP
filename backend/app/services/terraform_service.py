"""
Terraform generation service.
Orchestrates Jinja2 template rendering to produce valid Terraform files.
Provider-agnostic interface: add AzureTerraformGenerator, GCPTerraformGenerator later.
"""
from typing import List, Dict, Any
from app.terraform.generator import get_generator
from app.schemas.terraform import TerraformFile


def generate_terraform_files(
    provider: str,
    nodes: List[Dict],
    edges: List[Dict],
    project_name: str,
) -> List[TerraformFile]:
    """
    Main entry point for Terraform generation.
    Returns a list of TerraformFile objects ready to display or zip.
    """
    generator = get_generator(provider)
    return generator.generate(nodes=nodes, edges=edges, project_name=project_name)
