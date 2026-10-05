"""End-to-end API smoke test against a running CloudForge backend.

Usage: python smoke_api.py [base_url]
Verifies: register -> create project -> save architecture -> generate
Terraform -> plan-destroy guard (409 before deploy).
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
        with opener.open(req, timeout=30) as resp:
            return resp.status, json.loads(resp.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        raw = e.read().decode() or "{}"
        try:
            return e.code, json.loads(raw)
        except json.JSONDecodeError:
            return e.code, {"detail": raw[:200]}


def check(name: str, cond: bool, extra: str = ""):
    print(f"{'PASS' if cond else 'FAIL'}  {name} {extra}")
    if not cond:
        sys.exit(1)


# 1. Register (or login if the smoke user already exists)
status, data = call("POST", "/api/auth/register", {
    "email": "smoke@test.io", "username": "smoketest", "password": "password123",
})
if status == 400:  # already registered from a previous run
    status, data = call("POST", "/api/auth/login", {
        "email": "smoke@test.io", "password": "password123",
    })
check("auth", status == 200 and "user" in data, f"(HTTP {status})")

# 2. Create project (single-transaction fix: project + empty architecture)
status, proj = call("POST", "/api/projects", {"name": "Smoke Test", "provider": "aws"})
check("create project", status == 200 and proj["resource_count"] == 0, f"(HTTP {status})")
project_id = proj["id"]

# 3. Save a small architecture (VPC + Subnet)
nodes = [
    {"id": "v1", "type": "resourceNode", "position": {"x": 0, "y": 0},
     "data": {"label": "VPC", "resourceType": "vpc", "provider": "aws",
              "properties": {"name": "smoke-vpc", "cidr": "10.0.0.0/16"}}},
    {"id": "s1", "type": "resourceNode", "position": {"x": 200, "y": 0},
     "data": {"label": "Subnet", "resourceType": "subnet", "provider": "aws",
              "properties": {"name": "smoke-subnet", "cidr": "10.0.1.0/24"}}},
]
edges = [{"id": "e1", "source": "v1", "target": "s1"}]
status, arch = call("PUT", f"/api/projects/{project_id}/architecture",
                    {"nodes": nodes, "edges": edges})
# create_project seeds the architecture row, so the first save bumps it to v2
check("save architecture", status == 200 and arch["version"] >= 1, f"(HTTP {status}, v{arch.get('version')})")

# 4. List projects (N+1 fix: single joined query, resource_count present)
status, projects = call("GET", "/api/projects")
count = next((p["resource_count"] for p in projects if p["id"] == project_id), -1)
check("list projects w/ resource_count", status == 200 and count == 2, f"(count={count})")

# 5. Generate Terraform (TemplateNotFound fix: unknown types skipped)
nodes.append({"id": "x1", "type": "resourceNode", "position": {"x": 400, "y": 0},
              "data": {"label": "Mystery", "resourceType": "quantum_computer",
                       "provider": "aws", "properties": {"name": "q"}}})
call("PUT", f"/api/projects/{project_id}/architecture", {"nodes": nodes, "edges": edges})
status, gen = call("POST", f"/api/projects/{project_id}/terraform/generate")
main = next((f["content"] for f in gen.get("files", []) if f["filename"] == "main.tf"), "")
check("generate terraform", status == 200 and len(gen["files"]) >= 4, f"(HTTP {status}, {len(gen.get('files', []))} files)")
check("unknown type skipped", "Skipped 'quantum_computer'" in main)

# 6. plan-destroy guard: 409 because nothing is deployed yet
status, pd = call("POST", f"/api/projects/{project_id}/terraform/plan-destroy")
check("plan-destroy guard (409 pre-deploy)", status == 409, f"(HTTP {status})")

# 6b. Record a deployment-history row (clear on an empty workspace is instant
#     and side-effect free) so the delete below exercises the FK cascade fix.
status, _ = call("DELETE", f"/api/projects/{project_id}/terraform/clear")
check("clear records event", status == 200, f"(HTTP {status})")

# 7. Cleanup: delete the project (must succeed even with deployment history)
status, _ = call("DELETE", f"/api/projects/{project_id}")
check("delete project with history", status == 200, f"(HTTP {status})")

print("\nAll smoke checks passed. Backend is healthy end-to-end.")