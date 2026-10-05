"""Seed a FREE-TIER-ONLY demo into a running CloudForge.

Usage: python seed_demo_free.py [base_url]
Logs into demo@cloudforge.io / demo1234 and seeds a 100% AWS Free Tier
architecture (no NAT Gateway, no ALB). Uses t3.micro (free-tier eligible
in all regions incl. ap-south-1 Mumbai).
"""
import json, sys, urllib.request, urllib.error, http.cookiejar, random, string


def rand_suffix(length=6):
    return "".join(random.choices(string.ascii_lowercase + string.digits, k=length))

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"
jar = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))


def call(method, path, body=None):
    req = urllib.request.Request(
        BASE + path,
        data=json.dumps(body).encode() if body else None,
        headers={"Content-Type": "application/json"}, method=method)
    try:
        with opener.open(req, timeout=60) as resp:
            return resp.status, json.loads(resp.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        raw = e.read().decode() or "{}"
        try:
            return e.code, json.loads(raw)
        except json.JSONDecodeError:
            return e.code, {"detail": raw[:500]}


def fail(msg):
    print(f"FAIL  {msg}"); sys.exit(1)


status, data = call("POST", "/api/auth/register",
                    {"email": "demo@cloudforge.io", "username": "demo", "password": "demo1234"})
if status != 200:
    status, data = call("POST", "/api/auth/login", {"email": "demo@cloudforge.io", "password": "demo1234"})
if status != 200:
    fail(f"auth failed (HTTP {status}): {data}")
print("PASS  auth as demo@cloudforge.io")

status, proj = call("POST", "/api/projects", {
    "name": "Free-Tier Demo", "provider": "aws",
    "description": "100% AWS Free Tier web app: EC2 t3.micro + RDS + serverless"})
if status != 200:
    fail(f"create project (HTTP {status}): {data}")
pid = proj["id"]
print(f"PASS  project created: {pid}")


def node(nid, rtype, label, props, x, y):
    return {"id": nid, "type": "resourceNode", "position": {"x": x, "y": y},
            "data": {"label": label, "resourceType": rtype, "provider": "aws", "properties": props}}


nodes = [
    node("vpc", "vpc", "app-vpc", {"name": "app-vpc", "cidr": "10.0.0.0/16", "environment": "development"}, 480, 40),
    node("subnet-a", "subnet", "public-subnet-a", {"name": "public-subnet-a", "cidr": "10.0.1.0/24", "availabilityZone": "us-east-1a", "mapPublicIp": True}, 240, 220),
    node("subnet-b", "subnet", "public-subnet-b", {"name": "public-subnet-b", "cidr": "10.0.2.0/24", "availabilityZone": "us-east-1b", "mapPublicIp": True}, 720, 220),
    node("igw", "internet_gateway", "app-igw", {"name": "app-igw"}, 40, 120),
    node("rt", "route_table", "public-routes", {"name": "public-routes", "destinationCidr": "0.0.0.0/0"}, 920, 120),
    node("ec2-1", "ec2", "web-server-1", {"name": "web-server-1", "instanceType": "t3.micro", "associatePublicIp": True}, 180, 460),
    node("ec2-2", "ec2", "web-server-2", {"name": "web-server-2", "instanceType": "t3.micro", "associatePublicIp": True}, 520, 460),
    node("sg", "security_group", "web-sg", {"name": "web-sg", "description": "HTTP/HTTPS/SSH to web tier"}, 340, 620),
    node("rds", "rds", "app-db", {"identifier": "app-db", "engine": "mysql", "engineVersion": "8.0", "instanceClass": "db.t3.micro", "storage": 20, "dbName": "appdb", "username": "admin", "multiAz": False}, 760, 460),
    node("s3", "s3", "app-assets-bucket", {"bucketName": f"app-assets-bucket-{rand_suffix()}", "versioning": False}, 960, 460),
    node("lambda", "lambda", "app-worker", {"functionName": "app-worker", "runtime": "python3.12", "handler": "app.handler", "filename": "lambda.zip", "memorySize": 128, "timeout": 30}, 600, 640),
    node("ddb", "dynamodb", "app-table", {"tableName": "app-table", "billingMode": "PAY_PER_REQUEST", "hashKey": "id", "hashKeyType": "S"}, 380, 640),
    node("role", "iam_role", "app-role", {"name": "app-role", "service": "lambda.amazonaws.com"}, 800, 640),
]


pairs = [
    ("vpc", "subnet-a"), ("vpc", "subnet-b"), ("vpc", "igw"), ("vpc", "rt"), ("subnet-a", "rt"),
    ("ec2-1", "subnet-a"), ("ec2-2", "subnet-b"),
    ("sg", "ec2-1"), ("sg", "ec2-2"), ("sg", "rds"), ("rds", "subnet-b"),
    ("lambda", "role"), ("lambda", "ddb"), ("lambda", "subnet-b"),
]
edges = [{"id": f"e-{s}-{t}", "source": s, "target": t} for (s, t) in pairs]

status, arch = call("PUT", f"/api/projects/{pid}/architecture", {"nodes": nodes, "edges": edges})
if status != 200:
    fail(f"save architecture (HTTP {status}): {arch}")
print(f"PASS  architecture saved (v{arch.get('version')}): {len(nodes)} nodes, {len(edges)} edges")

status, result = call("POST", f"/api/projects/{pid}/validate")
if status != 200:
    fail(f"validate (HTTP {status}): {result}")
errors = [i for i in result.get("issues", []) if i["level"] == "error"]
warnings = [i for i in result.get("issues", []) if i["level"] == "warning"]
print(f"{'PASS' if result['valid'] else 'FAIL'}  validation valid={result['valid']} (errors={len(errors)}, warnings={len(warnings)})")
for issue in result.get("issues", []):
    print(f"      [{issue['level']}] {issue['message']}")
if not result["valid"]:
    sys.exit(1)

status, gen = call("POST", f"/api/projects/{pid}/terraform/generate")
if status != 200:
    fail(f"generate (HTTP {status}): {gen}")
print(f"PASS  terraform generated ({len(gen['files'])} files)")
for f in gen["files"]:
    print(f"      {f['filename']:<24} {f['content'].count(chr(10))+1:>4} lines")

print(f"\nFree-tier demo seeded! Log in: demo@cloudforge.io / demo1234")
print(f"Builder:   http://localhost:3000/projects/{pid}/builder")
print(f"Terraform: http://localhost:3000/projects/{pid}/terraform")
print("\n100% AWS Free Tier (us-east-1): 2x t3.micro EC2, db.t3.micro RDS, S3, Lambda, DynamoDB")
print("-> terraform apply creates real resources at ZERO cost")
print("-> ALWAYS run terraform destroy after the demo to stay clean")
