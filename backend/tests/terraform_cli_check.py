"""Cross-check the Terraform generator against the real Terraform CLI.

Builds several representative (and validation-clean) architectures, renders
them to HCL with the generator, then runs `terraform init -backend=false`,
`terraform validate` and `terraform fmt -check` on each one. This catches HCL
that is syntactically fine but semantically invalid for the AWS provider —
something the unit tests cannot see.

Requires the `terraform` binary on PATH (it ships in the backend Docker image).
The filename deliberately does not start with `test_`, so pytest does not
collect it.

Usage:
    python tests/terraform_cli_check.py
"""
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.validation_service import validate_architecture  # noqa: E402
from app.terraform.generator import AWSTerraformGenerator  # noqa: E402


def node(nid, rtype, props):
    return {"id": nid, "type": "resourceNode", "data": {"resourceType": rtype, "properties": props}}


def edges(*pairs):
    return [{"id": f"{s}-{t}", "source": s, "target": t} for s, t in pairs]


def three_tier():
    nodes = [
        node("vpc", "vpc", {"name": "app-vpc", "cidr": "10.0.0.0/16"}),
        node("subnet-a", "subnet", {"name": "public-subnet-a", "cidr": "10.0.1.0/24"}),
        node("subnet-b", "subnet", {"name": "public-subnet-b", "cidr": "10.0.2.0/24"}),
        node("igw", "internet_gateway", {"name": "app-igw"}),
        node("rt", "route_table", {"name": "public-routes", "destinationCidr": "0.0.0.0/0"}),
        node("nat", "nat_gateway", {"name": "app-nat"}),
        node("lb", "load_balancer", {"name": "app-lb", "lbType": "application"}),
        node("ec2-1", "ec2", {"name": "web-server-1", "instanceType": "t3.micro"}),
        node("ec2-2", "ec2", {"name": "web-server-2", "instanceType": "t3.micro"}),
        node("sg", "security_group", {"name": "web-sg"}),
        node("rds", "rds", {"identifier": "app-db", "engine": "mysql", "instanceClass": "db.t3.micro"}),
        node("s3", "s3", {"bucketName": "app-assets"}),
        node("alarm", "cloudwatch_alarm", {"name": "cpu-alarm", "metric": "CPUUtilization", "threshold": 80}),
        node("lambda", "lambda", {"functionName": "app-worker", "runtime": "python3.12", "handler": "app.handler"}),
        node("ddb", "dynamodb", {"tableName": "app-table", "hashKey": "id"}),
        node("role", "iam_role", {"name": "app-role", "service": "lambda.amazonaws.com"}),
    ]
    edge_list = edges(
        ("vpc", "subnet-a"), ("vpc", "subnet-b"), ("vpc", "igw"), ("vpc", "rt"),
        ("subnet-a", "rt"), ("nat", "subnet-b"),
        ("lb", "subnet-a"), ("lb", "subnet-b"),
        ("ec2-1", "subnet-a"), ("ec2-2", "subnet-b"),
        ("lb", "ec2-1"), ("lb", "ec2-2"),
        ("sg", "ec2-1"), ("sg", "ec2-2"), ("sg", "lb"), ("sg", "rds"),
        ("rds", "subnet-a"),
        ("alarm", "ec2-1"),
        ("lambda", "role"), ("lambda", "ddb"), ("lambda", "subnet-b"),
    )
    return nodes, edge_list


def serverless():
    nodes = [
        node("role", "iam_role", {"name": "exec-role", "service": "lambda.amazonaws.com"}),
        node("fn", "lambda", {"functionName": "processor", "runtime": "python3.12", "handler": "app.handler"}),
        node("ddb", "dynamodb", {"tableName": "items", "hashKey": "id"}),
        node("sqs", "sqs", {"name": "tasks-queue"}),
        node("sns", "sns", {"name": "notifications"}),
        node("api", "api_gateway", {"name": "app-api", "protocol": "HTTP"}),
        node("log", "cloudwatch_log_group", {"name": "app-logs", "retentionDays": "30"}),
        node("kinesis", "kinesis_stream", {"name": "events-stream", "shardCount": 1, "retentionHours": 24}),
        node("s3", "s3", {"bucketName": "events-assets"}),
        node("cf", "cloudfront", {"name": "cdn"}),
        node("zone", "route53_zone", {"name": "zone", "domainName": "example.com"}),
        node("record", "route53_record", {"name": "www", "recordType": "A", "recordValue": "example.com"}),
        node("sfn", "step_function", {"name": "workflow"}),
        node("kms", "kms_key", {"name": "app-key", "description": "app key"}),
        node("secret", "secretsmanager", {"name": "app-secrets", "description": "secrets"}),
    ]
    edge_list = edges(
        ("fn", "role"), ("fn", "ddb"), ("fn", "sqs"), ("fn", "sns"),
        ("sns", "sqs"), ("api", "fn"), ("api", "ddb"), ("fn", "log"),
        ("kinesis", "fn"), ("kinesis", "s3"), ("s3", "cf"),
        ("zone", "record"), ("sfn", "fn"), ("secret", "fn"),
        ("kms", "s3"), ("kms", "fn"),
    )
    return nodes, edge_list


def data_tier():
    nodes = [
        node("vpc", "vpc", {"name": "data-vpc", "cidr": "10.1.0.0/16"}),
        node("subnet-a", "subnet", {"name": "data-subnet-a", "cidr": "10.1.1.0/24"}),
        node("subnet-b", "subnet", {"name": "data-subnet-b", "cidr": "10.1.2.0/24"}),
        node("rds", "rds", {"identifier": "app-db", "engine": "mysql", "instanceClass": "db.t3.micro"}),
        node("aurora", "aurora", {"identifier": "app-cluster", "engine": "aurora-mysql"}),
        node("redshift", "redshift", {"clusterIdentifier": "analytics", "nodeType": "dc2.large"}),
        node("redis", "elasticache", {"name": "app-cache", "nodeType": "cache.t3.micro", "engine": "redis"}),
        node("efs", "efs", {"name": "shared-files"}),
    ]
    edge_list = edges(
        ("vpc", "subnet-a"), ("vpc", "subnet-b"),
        ("rds", "subnet-a"), ("aurora", "subnet-a"),
        ("redshift", "subnet-a"), ("redis", "subnet-a"), ("efs", "subnet-a"),
    )
    return nodes, edge_list


def containers():
    nodes = [
        node("vpc", "vpc", {"name": "app-vpc", "cidr": "10.2.0.0/16"}),
        node("subnet", "subnet", {"name": "app-subnet", "cidr": "10.2.1.0/24"}),
        node("ec2", "ec2", {"name": "app-node", "instanceType": "t3.micro"}),
        node("ebs", "ebs_volume", {"name": "data-volume", "size": 8}),
        node("eip", "elastic_ip", {"name": "static-ip"}),
        node("ecr", "ecr_repository", {"name": "app-images"}),
        node("ecs", "ecs_cluster", {"name": "app-cluster"}),
    ]
    edge_list = edges(
        ("vpc", "subnet"), ("subnet", "ec2"),
        ("ec2", "ebs"), ("ec2", "eip"),
        ("ecs", "ec2"), ("ecs", "ecr"),
    )
    return nodes, edge_list


FIXTURES = {
    "three_tier": three_tier,
    "serverless": serverless,
    "data_tier": data_tier,
    "containers": containers,
}


def _run(cmd, cwd):
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=420)


def main():
    terraform = shutil.which("terraform")
    if not terraform:
        print("SKIP  terraform binary not found on PATH")
        return 2

    os.environ.setdefault("TF_PLUGIN_CACHE_DIR", str(Path(tempfile.gettempdir()) / "tf-plugin-cache"))
    generator = AWSTerraformGenerator()
    failures = 0

    for name, build in FIXTURES.items():
        nodes, edge_list = build()
        result = validate_architecture(nodes, edge_list)
        errors = [i for i in result.issues if i.level == "error"]
        if errors:
            failures += 1
            print(f"FAIL  {name}: architecture did not pass validation")
            for e in errors:
                print(f"        [error] {e.message}")
            continue

        files = generator.generate(nodes, edge_list, project_name=name)
        workdir = Path(tempfile.mkdtemp(prefix=f"tf-{name}-"))
        for f in files:
            (workdir / f.filename).write_text(f.content, encoding="utf-8")

        init = _run(["terraform", "init", "-backend=false", "-input=false", "-no-color"], workdir)
        if init.returncode != 0:
            failures += 1
            print(f"FAIL  {name}: terraform init failed")
            print((init.stdout + init.stderr).strip()[-1500:])
            continue

        validate = _run(["terraform", "validate", "-no-color"], workdir)
        fmt = _run(["terraform", "fmt", "-check", "-no-color"], workdir)

        if validate.returncode != 0:
            failures += 1
            print(f"FAIL  {name}: terraform validate failed")
            print((validate.stdout + validate.stderr).strip()[-2500:])
        elif fmt.returncode != 0:
            print(f"WARN  {name}: validate OK but terraform fmt found formatting drift")
            print("        " + fmt.stdout.strip().replace("\n", "\n        "))
        else:
            print(f"PASS  {name}: init + validate + fmt clean ({len(files)} files)")

    if failures:
        print(f"\n{failures} fixture(s) FAILED")
        return 1
    print("\nAll fixtures passed terraform validate")
    return 0


if __name__ == "__main__":
    sys.exit(main())
