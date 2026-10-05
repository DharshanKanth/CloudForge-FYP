"""Seed a SIMPLE free-tier demo into a running CloudForge.

Usage: python seed_demo_simple.py [base_url]

A fast-deploying, 100% free-tier architecture (no RDS/Lambda/NAT/ALB) so
plan/apply/destroy all complete quickly for a live demo.

Resources: VPC, 2 subnets, IGW, route table, 2x t3.micro EC2, SG, S3.
"""
import json, sys, urllib.request, urllib.error, http.cookiejar, random, string

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


def rand_suffix(n=6):
    return "".join(random.choices(string.ascii_lowercase + string.digits, k=n))


status, data = call("POST", "/api/auth/register",
                    {"email": "demo@cloudforge.io", "username": "demo", "password": "demo1234"})
if status != 200:
    status, data = call("POST", "/api/auth/login", {"email": "demo@cloudforge.io", "password": "demo1234"})
if status != 200:
    fail(f"auth failed (HTTP {status}): {data}")
print("PASS  auth as demo@cloudforge.io")

status, proj = call("POST", "/api/projects", {
    "name": "Simple Demo", "provider": "aws",
    "description": "Simple free-tier web server: VPC + EC2 + S3"})
if status != 200:
    fail(f"create project (HTTP {status}): {data}")
pid = proj["id"]
print(f"PASS  project created: {pid}")


def node(nid, rtype, label, props, x, y):
    return {"id": nid, "type": "resourceNode", "position": {"x": x, "y": y},
            "data": {"label": label, "resourceType": rtype, "provider": "aws", "properties": props}}


nodes = [
    node("vpc", "vpc", "app-vpc", {"name": "app-vpc", "cidr": "10.0.0.0/16", "environment": "development"}, 400, 40),
    node("subnet-a", "subnet", "public-subnet-a", {"name": "public-subnet-a", "cidr": "10.0.1.0/24", "availabilityZone": "us-east-1a", "mapPublicIp": True}, 200, 220),
    node("subnet-b", "subnet", "public-subnet-b", {"name": "public-subnet-b", "cidr": "10.0.2.0/24", "availabilityZone": "us-east-1b", "mapPublicIp": True}, 600, 220),
    node("igw", "internet_gateway", "app-igw", {"name": "app-igw"}, 40, 120),
    node("rt", "route_table", "public-routes", {"name": "public-routes", "destinationCidr": "0.0.0.0/0"}, 800, 120),
    node("ec2-1", "ec2", "web-server", {"name": "web-server", "instanceType": "t3.micro", "associatePublicIp": True}, 200, 420),
    node("sg", "security_group", "web-sg", {"name": "web-sg", "description": "HTTP/HTTPS to web server"}, 500, 420),
    node("s3", "s3", "app-bucket", {"bucketName": f"cloudforge-demo-{rand_suffix()}", "versioning": False}, 380, 580),
]
pairs = [
    ("vpc", "subnet-a"), ("vpc", "subnet-b"), ("vpc", "igw"), ("vpc", "rt"), ("subnet-a", "rt"),
    ("ec2-1", "subnet-a"), ("sg", "ec2-1"),
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

print(f"\nSimple demo seeded! Log in: demo@cloudforge.io / demo1234")
print(f"Builder:   http://localhost:3000/projects/{pid}/builder")
print(f"Terraform: http://localhost:3000/projects/{pid}/terraform")
print("\nSimple free-tier (us-east-1): VPC, 2 subnets, IGW, t3.micro EC2, S3")
print("-> Deploys in ~2 minutes (no RDS/Lambda)")
print("-> ALWAYS click Destroy after the demo")
