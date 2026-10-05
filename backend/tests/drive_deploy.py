"""Drive the CloudForge API end-to-end for the demo project.

Usage (inside the backend container):
    python /tmp/drive_deploy.py generate
    python /tmp/drive_deploy.py plan
    python /tmp/drive_deploy.py apply
    python /tmp/drive_deploy.py outputs
Logs in as demo@cloudforge.io (project owner) and calls the same
endpoints the UI uses, so the DB status stays consistent.
"""
import json
import sys
import time
import urllib.error
import urllib.request
import http.cookiejar

PID = "888a92f6-2c06-451d-a3bc-bf96e5b1515d"
BASE = "http://localhost:8000"
jar = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))


def call(method, path, body=None, timeout=60):
    req = urllib.request.Request(
        BASE + path,
        data=json.dumps(body).encode() if body is not None else None,
        headers={"Content-Type": "application/json"},
        method=method,
    )
    try:
        with opener.open(req, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        raw = e.read().decode() or "{}"
        try:
            return e.code, json.loads(raw)
        except json.JSONDecodeError:
            return e.code, {"detail": raw[:800]}


def fail(msg):
    print(f"FAIL  {msg}")
    sys.exit(1)


stage = sys.argv[1] if len(sys.argv) > 1 else "all"

# Every invocation is a fresh process, so always log in first.
status, data = call("POST", "/api/auth/login",
                    {"email": "demo@cloudforge.io", "password": "demo1234"})
if status != 200:
    fail(f"login (HTTP {status}): {data}")
print("PASS  login as demo@cloudforge.io")

if stage in ("all", "generate"):
    status, gen = call("POST", f"/api/projects/{PID}/terraform/generate")
    if status != 200:
        fail(f"generate (HTTP {status}): {gen}")
    issues = gen.get("validation", {}).get("issues", [])
    print(f"PASS  generated {len(gen['files'])} files; validation valid="
          f"{gen.get('validation', {}).get('valid')} ({len(issues)} issues)")
    for i in issues:
        print(f"      [{i['level']}] {i['message'][:160]}")

if stage in ("all", "plan"):
    t0 = time.time()
    status, res = call("POST", f"/api/projects/{PID}/terraform/plan", timeout=1500)
    out = res.get("output", json.dumps(res)[:1500])
    print(f"PLAN  HTTP {status} in {time.time()-t0:.0f}s, status={res.get('status')}")
    print("\n".join("      " + l for l in out.splitlines()[-40:]))

if stage in ("all", "clearguard"):
    status, res = call("DELETE", f"/api/projects/{PID}/terraform/clear")
    print(f"CLEAR-GUARD HTTP {status}: {json.dumps(res)[:400]}")

if stage in ("all", "summary"):
    status, res = call("GET", "/api/infrastructure")
    if status != 200:
        fail(f"infrastructure summary (HTTP {status}): {res}")
    print(f"SUMMARY HTTP {status}: {len(res)} live stack(s)")
    for s in res:
        print(f"      {s.get('name')} [{s.get('provider')}] {s.get('region')} "
              f"resources={s.get('resource_count')} categories={s.get('categories')} "
              f"outputs={list(s.get('outputs', {}).keys())[:3]}")

if stage in ("all", "infra"):
    status, res = call("GET", f"/api/projects/{PID}/terraform/infrastructure")
    if status != 200:
        fail(f"infrastructure (HTTP {status}): {res}")
    print(f"INFRA status={res.get('status')} region={res.get('region')} "
          f"resources={len(res.get('resources', []))}")
    for r in res.get("resources", []):
        print(f"      {r['address']:<45} id={r['id']}  {json.dumps(r['attributes'])[:120]}")
    print(f"      outputs: {json.dumps(res.get('outputs'))[:300]}")

if stage in ("all", "apply"):
    t0 = time.time()
    status, res = call("POST", f"/api/projects/{PID}/terraform/apply", timeout=1700)
    out = res.get("output", json.dumps(res)[:1500])
    print(f"APPLY HTTP {status} in {time.time()-t0:.0f}s, status={res.get('status')}")
    print("\n".join("      " + l for l in out.splitlines()[-40:]))
