"""
Terraform Generator — Provider strategy pattern.

Base class: TerraformGenerator
AWS implementation: AWSTerraformGenerator

To add Azure/GCP support:
    class AzureTerraformGenerator(TerraformGenerator):
        ...

    Register in get_generator().
"""
import secrets
from pathlib import Path
import re
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Set
from jinja2 import Environment, FileSystemLoader
from app.schemas.terraform import TerraformFile


# Resolve templates directory relative to the repository `backend/templates/terraform`
# generator.py lives at: backend/app/terraform/generator.py
# parents[2] -> backend/
TEMPLATES_DIR = Path(__file__).resolve().parents[2] / "templates" / "terraform"


def _slug(name: str) -> str:
    """Convert a name to a valid Terraform resource identifier."""
    s = re.sub(r"[^a-zA-Z0-9_]", "_", str(name).strip())
    s = re.sub(r"_+", "_", s)
    s = s.lower().strip("_") or "resource"
    if s[0].isdigit():
        # HCL identifiers may not start with a digit.
        s = f"r_{s}"
    return s


def hcl_escape(value: Any) -> str:
    """Escape a Python string for safe interpolation inside a double-quoted HCL string.

    User-typed properties are interpolated raw into templates with autoescaping
    disabled (HCL is not HTML), so anything quoted must pass through here or a
    value containing `"` / `${` can break out and inject arbitrary Terraform.
    """
    s = str(value)
    s = s.replace("\\", "\\\\")
    s = s.replace('"', '\\"')
    s = s.replace("${", "$${")
    s = s.replace("%{", "%%{")
    s = s.replace("\r", "").replace("\n", "\\n").replace("\t", "\\t")
    return s


def random_suffix(length: int = 8) -> str:
    """Generate a random alphanumeric suffix for global uniqueness."""
    import random
    import string
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=length))


def hcl_int(value: Any, default: int = 0) -> int:
    """Coerce a user-supplied numeric property to int for unquoted HCL slots."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _escape_props(props: Any) -> Dict[str, Any]:
    """Escape all string values of a property dict once, at context build time."""
    if not isinstance(props, dict):
        return {}
    return {k: hcl_escape(v) if isinstance(v, str) else v for k, v in props.items()}


def _sanitize_comment(text: Any) -> str:
    """Make a value safe for a single-line HCL comment."""
    return str(text).replace("\r", " ").replace("\n", " ")


def aws_name(value: Any, max_len: int = 32) -> str:
    """Sanitize a string into a valid AWS resource name.

    AWS name attributes (LB, target group, S3 bucket, RDS identifier, ...)
    reject characters like the underscores that CloudForge slugs contain.
    Lowercases, replaces invalid chars with '-', collapses repeats, trims
    leading/trailing '-', and truncates to max_len (default 32, the LB/TG limit).
    """
    s = re.sub(r"[^a-zA-Z0-9-]", "-", str(value).strip().lower())
    s = re.sub(r"-+", "-", s).strip("-")
    if not s:
        s = "resource"
    return s[:max_len]


class TerraformGenerator(ABC):
    """Abstract base class for provider-specific Terraform generators."""

    @abstractmethod
    def generate(
        self,
        nodes: List[Dict],
        edges: List[Dict],
        project_name: str,
        aws_region: str = "us-east-1",
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
            autoescape=False,  # HCL is not HTML; injection is handled by hcl_escape
            trim_blocks=True,
            lstrip_blocks=True,
        )
        self.env.globals["slug"] = _slug
        self.env.globals["aws_name"] = aws_name
        self.env.filters["hcl_int"] = hcl_int
        self.env.globals["random_suffix"] = random_suffix

    def generate(
        self,
        nodes: List[Dict],
        edges: List[Dict],
        project_name: str,
        aws_region: str = "us-east-1",
    ) -> List[TerraformFile]:
        if not nodes:
            return self._empty_project(project_name)

        context = self._build_context(nodes, edges, project_name, aws_region)
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
                template_path = f"{resource_type}/main.tf.j2"
                if not self._template_exists(template_path):
                    # A saved architecture can contain a resource type with no
                    # template (e.g. saved by a newer client). Skip it with a
                    # comment instead of failing the whole generation with 500.
                    main_blocks.append(
                        f"# Skipped '{resource_type}' — no Terraform template for this resource type.\n"
                    )
                    continue
                main_blocks.append(self._render(template_path, {**context, "resource": resource}))

        main_content = "\n".join(main_blocks)
        files.append(TerraformFile(filename="main.tf", content=main_content))

        # outputs.tf
        outputs_content = self._render("outputs.tf.j2", context)
        files.append(TerraformFile(filename="outputs.tf", content=outputs_content))

        # RDS master passwords: no weak default in variables.tf — generate one
        # random password per instance and ship it in terraform.auto.tfvars
        # (auto-loaded by terraform plan/apply, kept out of source control by
        # convention since the ZIP is the user's to store).
        rds_resources = context["resources"].get("rds", [])
        if rds_resources:
            lines = [
                "# Auto-generated by CloudForge. Contains generated secrets — do not commit.",
                "# Rotate these values before real deployments.",
                "",
            ]
            for rds in rds_resources:
                lines.append(f'rds_password_{rds["slug"]} = "{secrets.token_urlsafe(18)}"')
            files.append(TerraformFile(filename="terraform.auto.tfvars", content="\n".join(lines) + "\n"))

        return files

    def _build_context(self, nodes: List[Dict], edges: List[Dict], project_name: str, aws_region: str = "us-east-1") -> Dict:
        """Parse nodes and edges into a rich context for templates."""
        resources: Dict[str, List[Dict]] = {}
        node_map: Dict[str, Dict] = {}
        used_slugs: Set[str] = set()

        def register_slug(raw: Any) -> str:
            base = _slug(raw)
            candidate = base
            counter = 2
            while candidate in used_slugs:
                candidate = f"{base}_{counter}"
                counter += 1
            used_slugs.add(candidate)
            return candidate

        for node in nodes:
            ntype = self._get_type(node)
            props = _escape_props(node.get("data", {}).get("properties", {}))
            node_id = node["id"]

            resource = {
                "node_id": node_id,
                "type": ntype,
                "props": props,
                "slug": register_slug(
                    props.get("name")
                    or props.get("bucketName")
                    or props.get("identifier")
                    or props.get("functionName")
                    or props.get("tableName")
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

            if src["type"] == "security_group" and tgt["type"] in ("lambda", "load_balancer"):
                tgt.setdefault("sg_refs", []).append(src["slug"])
            elif tgt["type"] == "security_group" and src["type"] in ("lambda", "load_balancer"):
                src.setdefault("sg_refs", []).append(tgt["slug"])

            # ec2 -> load_balancer
            if src["type"] == "load_balancer" and tgt["type"] == "ec2":
                src.setdefault("target_ec2_refs", []).append(tgt["slug"])
            elif src["type"] == "ec2" and tgt["type"] == "load_balancer":
                tgt.setdefault("target_ec2_refs", []).append(src["slug"])

            # subnet -> load_balancer (aws_lb requires at least two subnets)
            if src["type"] == "subnet" and tgt["type"] == "load_balancer":
                tgt.setdefault("subnet_refs", []).append(src["slug"])
            elif src["type"] == "load_balancer" and tgt["type"] == "subnet":
                src.setdefault("subnet_refs", []).append(tgt["slug"])

            # VPC networking resources
            if src["type"] == "vpc" and tgt["type"] in ("internet_gateway", "route_table"):
                tgt["vpc_ref"] = src["slug"]
            elif tgt["type"] == "vpc" and src["type"] in ("internet_gateway", "route_table"):
                src["vpc_ref"] = tgt["slug"]

            if src["type"] == "vpc" and tgt["type"] == "lambda":
                tgt["vpc_ref"] = src["slug"]
            elif tgt["type"] == "vpc" and src["type"] == "lambda":
                src["vpc_ref"] = tgt["slug"]

            if src["type"] == "subnet" and tgt["type"] in ("route_table", "nat_gateway", "lambda", "elasticache", "aurora", "redshift", "efs"):
                tgt["subnet_ref"] = src["slug"]
            elif tgt["type"] == "subnet" and src["type"] in ("route_table", "nat_gateway", "lambda", "elasticache", "aurora", "redshift", "efs"):
                src["subnet_ref"] = tgt["slug"]

            # s3 -> cloudfront (origin bucket)
            if src["type"] == "s3" and tgt["type"] == "cloudfront":
                tgt["s3_ref"] = src["slug"]
            elif src["type"] == "cloudfront" and tgt["type"] == "s3":
                src["s3_ref"] = tgt["slug"]

            # elastic_ip -> ec2 (static address association)
            if src["type"] == "elastic_ip" and tgt["type"] == "ec2":
                src["instance_ref"] = tgt["slug"]
            elif src["type"] == "ec2" and tgt["type"] == "elastic_ip":
                tgt["instance_ref"] = src["slug"]

            # ebs_volume -> ec2 (the volume must be created in the instance's AZ)
            if src["type"] == "ec2" and tgt["type"] == "ebs_volume":
                tgt["instance_ref"] = src["slug"]
            elif src["type"] == "ebs_volume" and tgt["type"] == "ec2":
                src["instance_ref"] = tgt["slug"]

            # route53_zone -> route53_record
            if src["type"] == "route53_zone" and tgt["type"] == "route53_record":
                tgt["zone_ref"] = src["slug"]
            elif src["type"] == "route53_record" and tgt["type"] == "route53_zone":
                src["zone_ref"] = tgt["slug"]

            # IAM execution role relationships
            if src["type"] == "iam_role" and tgt["type"] in ("lambda", "dynamodb"):
                tgt["role_ref"] = src["slug"]
            elif tgt["type"] == "iam_role" and src["type"] in ("lambda", "dynamodb"):
                src["role_ref"] = tgt["slug"]

        # Index subnets by slug (reused by the subnet-group and VPC inference
        # steps below).
        subnet_by_slug = {r["slug"]: r for r in resources.get("subnet", [])}

        # ── Availability-zone assignment ─────────────────────────────
        # AWS DB/cluster subnet groups require their subnets to span at least
        # two Availability Zones. Spread each VPC's subnets across the region's
        # AZ letters instead of pinning every subnet to "<region>a", which made
        # RDS/Aurora creation fail with an AZ-coverage error.
        az_letters = "abcd"
        az_counters: Dict[str, int] = {}
        for subnet in resources.get("subnet", []):
            group_key = subnet.get("vpc_ref") or "_"
            index = az_counters.get(group_key, 0)
            az_counters[group_key] = index + 1
            subnet["az"] = f"{aws_region}{az_letters[index % len(az_letters)]}"

        # EBS volumes must live in the same AZ as the instance they attach to,
        # otherwise AWS rejects the attachment. Pull the AZ from the instance's
        # subnet when the two are connected.
        ec2_by_slug = {r["slug"]: r for r in resources.get("ec2", [])}
        for ebs in resources.get("ebs_volume", []):
            instance = ec2_by_slug.get(ebs.get("instance_ref"))
            if instance and instance.get("subnet_ref"):
                instance_az = subnet_by_slug.get(instance["subnet_ref"], {}).get("az")
                if instance_az:
                    ebs["az"] = instance_az

        # ── Database / cache subnet groups ───────────────────────────
        # A subnet group must reference only subnets from its own VPC, and
        # should include every subnet in that VPC so it can satisfy the
        # multi-AZ coverage requirement.
        subnets_by_vpc: Dict[str, List[str]] = {}
        for subnet in resources.get("subnet", []):
            subnets_by_vpc.setdefault(subnet.get("vpc_ref") or "_", []).append(subnet["slug"])
        for resource_type in ("rds", "aurora", "redshift", "elasticache"):
            for db in resources.get(resource_type, []):
                subnet_ref = db.get("subnet_ref")
                if not subnet_ref:
                    continue
                vpc_ref = db.get("vpc_ref") or subnet_by_slug.get(subnet_ref, {}).get("vpc_ref")
                if vpc_ref:
                    db["vpc_ref"] = vpc_ref
                    refs = list(subnets_by_vpc.get(vpc_ref, []))
                else:
                    refs = []
                if subnet_ref not in refs:
                    refs.insert(0, subnet_ref)
                db["subnet_group_refs"] = refs

        # Infer the load balancer's VPC from its subnets so the target group
        # pins to the right VPC instead of blindly using the first one.
        for lb in resources.get("load_balancer", []):
            if lb.get("vpc_ref"):
                continue
            for subnet_slug in lb.get("subnet_refs", []):
                vpc_slug = subnet_by_slug.get(subnet_slug, {}).get("vpc_ref")
                if vpc_slug:
                    lb["vpc_ref"] = vpc_slug
                    break

        # Route tables can emit a default route (destinationCidr) through the
        # internet gateway of their VPC. There is no direct IGW<->route-table
        # edge in the supported relationship set, so infer the gateway from
        # the shared VPC and expose it to templates as "igw_ref".
        igw_by_vpc: Dict[str, str] = {}
        for igw in resources.get("internet_gateway", []):
            igw_vpc = igw.get("vpc_ref")
            if igw_vpc and igw_vpc not in igw_by_vpc:
                igw_by_vpc[igw_vpc] = igw["slug"]
        for rt in resources.get("route_table", []):
            igw_slug = igw_by_vpc.get(rt.get("vpc_ref"))
            if igw_slug:
                rt["igw_ref"] = igw_slug

        # Security groups have no direct vpc edge in the supported relationship
        # set, so infer their VPC from the resources they protect (EC2/RDS/
        # Lambda/LB). The SG -> VPC map is built by scanning protected
        # resources: each EC2/RDS/Lambda/LB lists its security groups in
        # "sg_refs" and carries a subnet ("subnet_ref"/"subnet_refs"), so the
        # SG's VPC = the VPC of the subnets of the resources that attach it.
        sg_to_vpc: Dict[str, Set[str]] = {}
        for group in resources.values():
            for candidate in group:
                if candidate["type"] not in ("ec2", "rds", "lambda", "load_balancer"):
                    continue
                subnet_slugs = (
                    [candidate["subnet_ref"]]
                    if candidate.get("subnet_ref")
                    else candidate.get("subnet_refs", [])
                )
                sg_slugs = candidate.get("sg_refs", [])
                if not subnet_slugs or not sg_slugs:
                    continue
                vpc_slugs = {subnet_by_slug[s].get("vpc_ref") for s in subnet_slugs if s in subnet_by_slug}
                vpc_slugs.discard(None)
                if not vpc_slugs:
                    continue
                for sg_slug in sg_slugs:
                    sg_to_vpc.setdefault(sg_slug, set()).update(vpc_slugs)
        # A SG on resources spanning multiple VPCs is ambiguous; only pin when
        # all its protected resources resolve to one VPC.
        for sg in resources.get("security_group", []):
            if sg.get("vpc_ref"):
                continue
            candidates = sg_to_vpc.get(sg["slug"], set())
            if len(candidates) == 1:
                sg["vpc_ref"] = next(iter(candidates))

        # Build list of VPCs for subnet variables
        vpcs = resources.get("vpc", [])
        subnets = resources.get("subnet", [])

        return {
            "project_name": _sanitize_comment(project_name),
            "project_slug": _slug(project_name),
            "provider": "aws",
            "aws_region": aws_region,
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
            "has_internet_gateway": bool(resources.get("internet_gateway")),
            "has_route_table": bool(resources.get("route_table")),
            "has_nat_gateway": bool(resources.get("nat_gateway")),
            "has_lambda": bool(resources.get("lambda")),
            "has_dynamodb": bool(resources.get("dynamodb")),
            "has_iam_role": bool(resources.get("iam_role")),
        }

    def _template_exists(self, template_path: str) -> bool:
        return (TEMPLATES_DIR / "aws" / template_path).is_file()

    def _render(self, template_path: str, context: Dict) -> str:
        tmpl = self.env.get_template(template_path)
        return tmpl.render(**context)

    def _get_type(self, node: Dict) -> str:
        return node.get("data", {}).get("resourceType", node.get("type", "unknown")).lower()

    def _empty_project(self, project_name: str) -> List[TerraformFile]:
        content = f'# CloudForge — {_sanitize_comment(project_name)}\n# No resources defined yet.\n'
        return [
            TerraformFile(filename="main.tf", content=content),
            TerraformFile(filename="providers.tf", content='provider "aws" {\n  region = var.aws_region\n}\n'),
            TerraformFile(filename="variables.tf", content='variable "aws_region" {\n  default = "us-east-1"\n}\n'),
            TerraformFile(filename="outputs.tf", content="# No outputs defined\n"),
        ]


class _UnimplementedGenerator(TerraformGenerator):
    """Placeholder for providers that are not implemented yet.

    Registered in the factory so an unsupported provider yields a clear,
    user-facing message instead of a generic "unsupported provider" error.
    """

    provider_name = "unknown"

    def generate(self, nodes, edges, project_name, aws_region="us-east-1"):
        raise NotImplementedError(
            f"{self.provider_name} support is not implemented yet. "
            f"CloudForge currently generates Terraform for AWS only."
        )


class AzureTerraformGenerator(_UnimplementedGenerator):
    provider_name = "Azure"


class GCPTerraformGenerator(_UnimplementedGenerator):
    provider_name = "GCP"


def get_generator(provider: str) -> TerraformGenerator:
    """Factory function — returns the correct generator for the cloud provider."""
    generators = {
        "aws": AWSTerraformGenerator,
        "azure": AzureTerraformGenerator,
        "gcp": GCPTerraformGenerator,
    }
    cls = generators.get((provider or "").lower())
    if not cls:
        raise ValueError(f"Unsupported provider: {provider}. Supported: {list(generators.keys())}")
    return cls()
