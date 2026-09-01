"""
Terraform Generator — Provider strategy pattern.

Base class: TerraformGenerator
AWS implementation: AWSTerraformGenerator

To add Azure/GCP support:
    class AzureTerraformGenerator(TerraformGenerator):
        ...
    
    Register in get_generator().
"""
import os
from pathlib import Path
import re
from abc import ABC, abstractmethod
from typing import List, Dict, Any
from jinja2 import Environment, FileSystemLoader, select_autoescape
from app.schemas.terraform import TerraformFile


# Resolve templates directory relative to the repository `backend/templates/terraform`
# generator.py lives at: backend/app/terraform/generator.py
# parents[2] -> backend/
TEMPLATES_DIR = Path(__file__).resolve().parents[2] / "templates" / "terraform"


def _slug(name: str) -> str:
    """Convert a name to a valid Terraform resource identifier."""
    s = re.sub(r"[^a-zA-Z0-9_]", "_", name.strip())
    s = re.sub(r"_+", "_", s)
    return s.lower().strip("_") or "resource"


class TerraformGenerator(ABC):
    """Abstract base class for provider-specific Terraform generators."""

    @abstractmethod
    def generate(
        self,
        nodes: List[Dict],
        edges: List[Dict],
        project_name: str,
    ) -> List[TerraformFile]:
        ...


class AWSTerraformGenerator(TerraformGenerator):
    """
    Generates Terraform HCL for AWS resources from a node/edge graph.
    Uses Jinja2 templates from backend/templates/terraform/aws/.
    """

    def __init__(self):
        aws_templates_path = TEMPLATES_DIR / "aws"
        self.env = Environment(
            loader=FileSystemLoader(str(aws_templates_path)),
            autoescape=select_autoescape([]),
            trim_blocks=True,
            lstrip_blocks=True,
        )
        self.env.globals["slug"] = _slug

    def generate(
        self,
        nodes: List[Dict],
        edges: List[Dict],
        project_name: str,
    ) -> List[TerraformFile]:
        if not nodes:
            return self._empty_project(project_name)

        context = self._build_context(nodes, edges, project_name)
        files = []

        # providers.tf
        providers_content = self._render("providers.tf.j2", context)
        files.append(TerraformFile(filename="providers.tf", content=providers_content))

        # variables.tf
        variables_content = self._render("variables.tf.j2", context)
        files.append(TerraformFile(filename="variables.tf", content=variables_content))

        # main.tf — aggregate all resources
        main_blocks = []
        for resource_type, resource_list in context["resources"].items():
            for resource in resource_list:
                try:
                    block = self._render(f"{resource_type}/main.tf.j2", {**context, "resource": resource})
                    main_blocks.append(block)
                except Exception as e:
                    main_blocks.append(f"# Error rendering {resource_type}: {e}\n")

        main_content = "\n".join(main_blocks)
        files.append(TerraformFile(filename="main.tf", content=main_content))

        # outputs.tf
        outputs_content = self._render("outputs.tf.j2", context)
        files.append(TerraformFile(filename="outputs.tf", content=outputs_content))

        return files

    def _build_context(self, nodes: List[Dict], edges: List[Dict], project_name: str) -> Dict:
        """Parse nodes and edges into a rich context for templates."""
        resources: Dict[str, List[Dict]] = {}
        node_map: Dict[str, Dict] = {}

        for node in nodes:
            ntype = self._get_type(node)
            props = node.get("data", {}).get("properties", {})
            node_id = node["id"]

            resource = {
                "node_id": node_id,
                "type": ntype,
                "props": props,
                "slug": _slug(
                    props.get("name")
                    or props.get("bucketName")
                    or props.get("identifier")
                    or node_id
                ),
            }
            resources.setdefault(ntype, []).append(resource)
            node_map[node_id] = resource

        # Resolve edge relationships
        for edge in edges:
            src_id = edge.get("source")
            tgt_id = edge.get("target")
            if not src_id or not tgt_id:
                continue

            src = node_map.get(src_id)
            tgt = node_map.get(tgt_id)
            if not src or not tgt:
                continue

            # subnet -> vpc
            if src["type"] == "vpc" and tgt["type"] == "subnet":
                tgt["vpc_ref"] = src["slug"]
            elif src["type"] == "subnet" and tgt["type"] == "vpc":
                src["vpc_ref"] = tgt["slug"]

            # ec2 -> subnet
            if src["type"] == "subnet" and tgt["type"] == "ec2":
                tgt["subnet_ref"] = src["slug"]
            elif src["type"] == "ec2" and tgt["type"] == "subnet":
                src["subnet_ref"] = tgt["slug"]

            # rds -> subnet
            if src["type"] == "subnet" and tgt["type"] == "rds":
                tgt["subnet_ref"] = src["slug"]
            elif src["type"] == "rds" and tgt["type"] == "subnet":
                src["subnet_ref"] = tgt["slug"]

            # ec2/rds -> security_group
            if src["type"] == "security_group" and tgt["type"] in ("ec2", "rds"):
                tgt.setdefault("sg_refs", []).append(src["slug"])
            elif tgt["type"] == "security_group" and src["type"] in ("ec2", "rds"):
                src.setdefault("sg_refs", []).append(tgt["slug"])

            # ec2 -> load_balancer
            if src["type"] == "load_balancer" and tgt["type"] == "ec2":
                src.setdefault("target_ec2_refs", []).append(tgt["slug"])
            elif src["type"] == "ec2" and tgt["type"] == "load_balancer":
                tgt.setdefault("target_ec2_refs", []).append(src["slug"])

        # Build list of VPCs for subnet variables
        vpcs = resources.get("vpc", [])
        subnets = resources.get("subnet", [])

        return {
            "project_name": project_name,
            "project_slug": _slug(project_name),
            "provider": "aws",
            "resources": resources,
            "vpcs": vpcs,
            "subnets": subnets,
            "has_vpc": bool(vpcs),
            "has_subnet": bool(subnets),
            "has_ec2": bool(resources.get("ec2")),
            "has_s3": bool(resources.get("s3")),
            "has_rds": bool(resources.get("rds")),
            "has_sg": bool(resources.get("security_group")),
            "has_lb": bool(resources.get("load_balancer")),
        }

    def _render(self, template_path: str, context: Dict) -> str:
        tmpl = self.env.get_template(template_path)
        return tmpl.render(**context)

    def _get_type(self, node: Dict) -> str:
        return node.get("data", {}).get("resourceType", node.get("type", "unknown")).lower()

    def _empty_project(self, project_name: str) -> List[TerraformFile]:
        content = f'# CloudForge — {project_name}\n# No resources defined yet.\n'
        return [
            TerraformFile(filename="main.tf", content=content),
            TerraformFile(filename="providers.tf", content='provider "aws" {\n  region = var.aws_region\n}\n'),
            TerraformFile(filename="variables.tf", content='variable "aws_region" {\n  default = "us-east-1"\n}\n'),
            TerraformFile(filename="outputs.tf", content="# No outputs defined\n"),
        ]


def get_generator(provider: str) -> TerraformGenerator:
    """Factory function — returns the correct generator for the cloud provider."""
    generators = {
        "aws": AWSTerraformGenerator,
        # Future: "azure": AzureTerraformGenerator,
        # Future: "gcp": GCPTerraformGenerator,
    }
    cls = generators.get(provider.lower())
    if not cls:
        raise ValueError(f"Unsupported provider: {provider}. Supported: {list(generators.keys())}")
    return cls()
