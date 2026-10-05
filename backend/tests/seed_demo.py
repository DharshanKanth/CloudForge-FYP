"""Seed a ready-made "3-Tier Demo App" architecture into a running CloudForge.

Usage: python seed_demo.py [base_url]

Creates/logs into the demo account (demo@cloudforge.io / demo1234), creates a
project with a full 3-tier AWS architecture (VPC, 2 subnets, IGW, route table,
NAT, ALB, 2x EC2, SG, RDS, S3, Lambda, DynamoDB, IAM role), saves it, runs
validation, and generates Terraform — so you can just open the builder.
"""
import json
import sys
import urllib.request
import urllib.error
import http.cookiejar

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"

jar = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))


def call(method: str, path: str, body: dict | None = None):
    req = urllib.request.Request(
        BASE + path,
        data=json.dumps(body).encode() if body is not None else None,
        headers={"Content-Type": "application/json"},
        method=method,
    )
    try:
        with opener.open(req, timeout=60) as resp:
            return resp.status, json.loads(resp.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        raw = e.read().decode() or "{}"
        try:
            return e.code, json.loads(raw)
        except json.JSONDecodeError:
            return e.code, {"detail": raw[:200]}


def fail(msg: str):
    print(f"FAIL  {msg}")
    sys.exit(1)


# ---------------------------------------------------------------- auth
status, data = call("POST", "/api/auth/register", {
    "email": "demo@cloudforge.io", "username": "demo", "password": "demo1234",
})
if status != 200:
    status, data = call("POST", "/api/auth/login", {
        "email": "demo@cloudforge.io", "password": "demo1234",
    })
if status != 200:
    fail(f"cannot auth as demo user (HTTP {status}): {data}")
print("PASS  auth as demo@cloudforge.io")

# ---------------------------------------------------------------- project
status, proj = call("POST", "/api/projects", {
    "name": "3-Tier Demo App",
    "description": "Production-style AWS web app: ALB + EC2 + RDS + serverless data tier",
    "provider": "aws",
})
if status != 200:
    fail(f"create project (HTTP {status}): {data}")
project_id = proj["id"]
print(f"PASS  project created: {project_id}")

# ---------------------------------------------------------------- architecture
def node(nid, rtype, label, props, x, y):
    return {
        "id": nid, "type": "resourceNode", "position": {"x": x, "y": y},
        "data": {"label": label, "resourceType": rtype, "provider": "aws",
                 "properties": props},
    }


nodes = [
    node("vpc", "vpc", "app-vpc",
         {"name": "app-vpc", "cidr": "10.0.0.0/16", "environment": "development"}, 480, 40),
    node("subnet-a", "subnet", "public-subnet-a",
         {"name": "public-subnet-a", "cidr": "10.0.1.0/24", "availabilityZone": "us-east-1a", "mapPublicIp": True}, 240, 220),
    node("subnet-b", "subnet", "public-subnet-b",
         {"name": "public-subnet-b", "cidr": "10.0.2.0/24", "availabilityZone": "us-east-1b", "mapPublicIp": True}, 720, 220),
    node("igw", "internet_gateway", "app-igw", {"name": "app-igw"}, 40, 120),
    node("rt", "route_table", "public-routes",
         {"name": "public-routes", "destinationCidr": "0.0.0.0/0"}, 920, 120),
    node("nat", "nat_gateway", "app-nat", {"name": "app-nat", "allocationId": ""}, 900, 320),
    node("lb", "load_balancer", "app-lb",
         {"name": "app-lb", "lbType": "application", "internal": False}, 480, 400),
    node("ec2-1", "ec2", "web-server-1",
         {"name": "web-server-1", "instanceType": "t3.micro", "associatePublicIp": True}, 240, 560),
    node("ec2-2", "ec2", "web-server-2",
         {"name": "web-server-2", "instanceType": "t3.micro", "associatePublicIp": True}, 720, 560),
    node("sg", "security_group", "web-sg",
         {"name": "web-sg", "description": "HTTP/HTTPS to app tier"}, 960, 500),
    node("rds", "rds", "app-db",
         {"identifier": "app-db", "engine": "mysql", "engineVersion": "8.0", "instanceClass": "db.t3.micro",
          "storage": 20, "dbName": "appdb", "username": "admin", "multiAz": False}, 120, 720),
    node("s3", "s3", "app-assets-bucket",
         {"bucketName": "app-assets-bucket", "versioning": False}, 960, 720),
    node("lambda", "lambda", "app-worker",
         {"functionName": "app-worker", "runtime": "python3.12", "handler": "app.handler",
          "filename": "lambda.zip", "memorySize": 128, "timeout": 30}, 600, 740),
    node("ddb", "dynamodb", "app-table",
         {"tableName": "app-table", "billingMode": "PAY_PER_REQUEST", "hashKey": "id", "hashKeyType": "S"}, 380, 740),
    node("role", "iam_role", "app-role",
         {"name": "app-role", "service": "lambda.amazonaws.com"}, 800, 740),
]

pairs = [
    ("vpc", "subnet-a"), ("vpc", "subnet-b"), ("vpc", "igw"), ("vpc", "rt"),
    ("subnet-a", "rt"), ("nat", "subnet-b"),
    ("lb", "subnet-a"), ("lb", "subnet-b"),
    ("ec2-1", "subnet-a"), ("ec2-2", "subnet-b"),
    ("lb", "ec2-1"), ("lb", "ec2-2"),
    ("sg", "ec2-1"), ("sg", "ec2-2"), ("sg", "lb"), ("sg", "rds"),
    ("rds", "subnet-a"),
    ("lambda", "role"), ("lambda", "ddb"), ("lambda", "subnet-b"),
]
edges = [
    {"id": f"e-{s}-{t}", "source": s, "target": t}
    for i, (s, t) in enumerate(pairs)
]

status, arch = call("PUT", f"/api/projects/{project_id}/architecture",
                    {"nodes": nodes, "edges": edges})
if status != 200:
    fail(f"save architecture (HTTP {status}): {arch}")
print(f"PASS  architecture saved (v{arch.get('version')}): {len(nodes)} nodes, {len(edges)} edges")

# ---------------------------------------------------------------- validate
status, result = call("POST", f"/api/projects/{project_id}/validate")
if status != 200:
    fail(f"validate (HTTP {status}): {result}")
errors = [i for i in result.get("issues", []) if i["level"] == "error"]
warnings = [i for i in result.get("issues", []) if i["level"] == "warning"]
print(f"{'PASS' if result['valid'] else 'FAIL'}  validation valid={result['valid']} "
      f"(errors={len(errors)}, warnings={len(warnings)})")
for issue in result.get("issues", []):
    print(f"      [{issue['level']}] {issue['message']}")
if not result["valid"]:
    sys.exit(1)

# ---------------------------------------------------------------- generate
status, gen = call("POST", f"/api/projects/{project_id}/terraform/generate")
if status != 200:
    fail(f"generate (HTTP {status}): {gen}")
print(f"PASS  terraform generated ({len(gen['files'])} files)")
for f in gen["files"]:
    lines = f["content"].count("\n") + 1
    print(f"      {f['filename']:<24} {lines:>4} lines")

print(
    "\nDemo seeded! Open http://localhost:3000 and log in with:\n"
    "    demo@cloudforge.io / demo1234\n"
    f"Then open the project  ->  Builder:\n"
    f"    http://localhost:3000/projects/{project_id}/builder\n"
    f"Terraform viewer:\n"
    f"    http://localhost:3000/projects/{project_id}/terraform\n"
)