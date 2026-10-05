"""Trigger a terraform plan via the API and print its output.

Usage: python run_plan.py [base_url]
Logs in as demo@cloudforge.io, finds the most recent project, and runs Plan.
Prints the raw terraform output so HCL errors are visible.
"""
import json
import sys
import urllib.request
import urllib.error
import http.cookiejar

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"

jar = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))


def call(method, path, body=None):
    req = urllib.request.Request(
        BASE + path,
        data=json.dumps(body).encode() if body else None,
        headers={"Content-Type": "application/json"},
        method=method,
    )
    try:
        with opener.open(req, timeout=400) as resp:
            return resp.status, json.loads(resp.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        raw = e.read().decode() or "{}"
        try:
            return e.code, json.loads(raw)
        except json.JSONDecodeError:
            return e.code, {"detail": raw[:500]}


# login
status, data = call("POST", "/api/auth/login",
                    {"email": "demo@cloudforge.io", "password": "demo1234"})
if status != 200:
    print(f"login failed HTTP {status}: {data}")
    sys.exit(1)

# find a project
status, projects = call("GET", "/api/projects")
if status != 200 or not projects:
    print(f"no projects (HTTP {status})")
    sys.exit(1)
project_id = projects[0]["id"]
print(f"project: {project_id} ({projects[0]['name']})")

# plan
print("--- running terraform plan (this runs init + validate + plan) ---")
status, result = call("POST", f"/api/projects/{project_id}/terraform/plan")
print(f"HTTP {status}  step={result.get('step')}  status={result.get('status')}")
output = result.get("output", "")
print(output[-3000:] if len(output) > 3000 else output)