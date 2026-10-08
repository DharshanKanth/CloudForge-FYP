# ☁ CloudForge — Visual Multi-Cloud Infrastructure Automation Platform

[![CI](https://github.com/DharshanKanth/CloudForge-FYP/actions/workflows/ci.yml/badge.svg)](https://github.com/DharshanKanth/CloudForge-FYP/actions/workflows/ci.yml)

**Final Year Project** | Visual AWS Infrastructure Builder → Terraform Generator → Deploy → Manage → Destroy

---

## Features

| Feature | Status |
|---|---|
| 🎨 **Visual builder** — drag & drop, grouping, focus/breadcrumb, search, auto-layout | ✅ React Flow |
| 🧩 **Canonical architecture model** (single source of truth for validation + generation) | ✅ JSON nodes/edges |
| ✅ **Validation engine** — required fields, topology, CIDR overlap, cycles, severities | ✅ Deterministic |
| ⚡ **Terraform generation** — 40+ AWS resource templates | ✅ Jinja2 → valid HCL |
| 👁 **Terraform preview + ZIP export** | ✅ Monaco / in-memory ZIP |
| 🔐 **Auth** — cookie JWT, refresh, rate limiting, per-user projects | ✅ |
| ☁ **Cloud accounts** — per user, credentials **encrypted at rest**, backend-only | ✅ Fernet |
| 🚀 **Deployment** — isolated worker, **streamed logs**, plan → approve → apply | ✅ Separate container |
| 🧭 **Lifecycle state machine** — draft → validated → generated → ready → deploying → deployed → destroying → destroyed/failed | ✅ |
| ⏯ **EC2 stop / start** via the provider API (not destroy) | ✅ boto3 |
| 💰 **Cost estimation** + 🔒 **security analysis** | ✅ Deterministic |
| 🤖 **AI assistant** (advisory; local Ollama or hosted, per-user keys) | ✅ Never executes infra |
| 📥 **Diagram import** — draw.io / Mermaid / JSON → canvas proposal | ✅ Deterministic |
| 🧪 **Tests + CI** — pytest, vitest, Alembic drift check | ✅ GitHub Actions |

---

## Tech Stack

**Frontend**: React 19, TypeScript, Vite, React Flow (xyflow), Tailwind CSS v4, Monaco Editor, Axios  
**Backend**: Python 3.11, FastAPI, SQLAlchemy (async), PostgreSQL, Pydantic v2, Jinja2  
**Infrastructure**: Docker, docker-compose, Nginx

---

## Quick Start — Docker (Recommended)

```bash
docker-compose up --build
```

- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- API Docs: http://localhost:8000/docs

> On first start the backend seeds a demo account (**demo@cloudforge.io / demo1234**) and a ready-made demo project. Set `CLOUDFORGE_SEED_DEMO=false` for a clean database.

---

## Quick Start — Local Development

### Prerequisites
- Node 18+, Python 3.11+, PostgreSQL running locally

### Backend

```bash
cd backend
python -m venv venv
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

pip install -r requirements.txt

# Set env vars (or create .env file)
set DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/cloudforge
set SECRET_KEY=dev-secret-key

uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

App opens at: **http://localhost:5173**

---

## End-to-End Demo Runbook

> **Prerequisite for the deploy steps:** a working AWS account connected in
> **Settings → Cloud Accounts** (Access Key ID + Secret + region), or set
> `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` in `.env`. Steps 1–6 work
> without AWS credentials.

**Login:** `demo@cloudforge.io` / `demo1234` (created automatically by the seed).

### Part A — Design → Validate → Generate (no AWS needed)
1. **Dashboard → New Project** (e.g. "Three-Tier Web App", provider AWS).
2. In the **Builder**, drag resources onto the canvas:
   `VPC → 2 Subnets → Internet Gateway → Route Table → Load Balancer → 2× EC2 → Security Group → S3`.
3. **Connect** them: subnet→VPC, EC2→subnet, LB→subnets, SG→EC2s. Related
   resources are auto-nested into their container; click a group to expand it.
4. Configure a resource by clicking it (right-hand panel).
5. **Validate** — errors block; warnings are advisory.
6. **Generate Terraform** — inspect `main.tf` / `variables.tf` / `outputs.tf` /
   `providers.tf` in Monaco, then **Download ZIP**.

### Part A2 — Import an existing diagram (draw.io / Mermaid / JSON)
Builder toolbar → **Import** → drop a **draw.io** (`.drawio`/`.xml`) file, a
**Mermaid** flowchart (`.mmd`), or CloudForge **JSON**. CloudForge maps AWS
icons/labels to resources **deterministically** (no AI), fills Free-Tier
defaults, reports anything it could not recognise, runs the validator, and shows
a preview — click **Apply to canvas**, then **Validate** as usual. VPC/subnet
containment is derived from draw.io nesting and Mermaid `subgraph` blocks.

### Part B — Plan → Deploy → Logs (needs AWS)
7. **Plan** — enqueues a job; the **isolated worker** runs `terraform init/validate/plan`
   and streams output live. The project moves to **ready**.
8. **Deploy** — applies the reviewed plan; logs stream in real time and the
   project moves to **deployed**.
9. Open the **Infra** tab — live resources read from Terraform state (IDs,
   public IPs, states).
10. Open the **Runs** tab — browse every past plan/apply/destroy with its full logs.
11. For an EC2 resource, use **Start / Stop** (a real provider API call, not a destroy).

### Part C — AI assistant (works offline via bundled Ollama)
12. Builder → **AI** → describe an architecture → **Generate suggestion** →
    review the validation summary → **Apply to canvas**.
13. On the Terraform page: **Explain** (code view) and **Troubleshoot with AI**
    on a failed deployment. The AI is advisory and never runs Terraform.
    To use your **own key or local LLM**, open **Settings → AI Assistant**,
    pick a provider, (optionally) paste a key, **Test connection**, then **Save**.

### Part D — Cost & security
14. The Builder toolbar shows an estimated **~/mo** cost and a **high-risk** count
    (deterministic — no LLM involved).

### Part E — Destroy
15. Terraform page → **Plan Destroy** → review → **Destroy**. Status moves to
    **destroyed** and the Infra tab empties. Deleting a project also removes its
    local workspace.

---

## Project Structure

```
cloudforge/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI app entry point
│   │   ├── database.py          # SQLAlchemy async engine
│   │   ├── core/                # Auth, JWT, dependencies
│   │   ├── models/              # SQLAlchemy ORM models
│   │   ├── schemas/             # Pydantic request/response schemas
│   │   ├── routers/             # API route handlers
│   │   ├── services/            # Business logic (validation, terraform, zip)
│   │   └── terraform/           # Generator engine (strategy pattern)
│   └── templates/terraform/aws/ # Jinja2 HCL templates
├── frontend/
│   └── src/
│       ├── pages/               # Login, Dashboard, Builder, TerraformViewer
│       ├── features/builder/    # React Flow canvas components
│       ├── components/          # Layout, ProtectedRoute, LoadingButton
│       ├── hooks/               # useAuth
│       ├── services/            # Axios API client
│       └── types/               # TypeScript interfaces
├── docker-compose.yml
└── README.md
```

---

## Production Notes

- The container runs as a non-root user and its default command starts uvicorn
  **without** `--reload` (docker-compose adds `--reload` for local dev).
- Set `CLOUDFORGE_ENV=production`. The app then **requires** `SECRET_KEY` and
  `ALLOWED_ORIGINS` (comma-separated) and refuses to start without them, and it
  stops seeding demo data.
- Schema is owned by Alembic and applied automatically on startup
  (`app/database.run_migrations`). Pre-existing databases are adopted safely.
- Both images define a `HEALTHCHECK` (backend `/api/health`, frontend `/`).
- Deployments run in a **separate `worker` container**, not the API process:
  the API enqueues jobs (`deployments`) and the worker runs Terraform, streaming
  output into `deployment_logs`. The UI polls
  `/api/projects/{id}/deployments/{job}/logs` for live logs.
- The **AI assistant is advisory and disabled by default**. Enable it with
  `AI_PROVIDER` + `AI_API_KEY` (hosted) or `AI_PROVIDER=ollama` +
  `AI_BASE_URL` (local). It never runs Terraform and its suggestions are gated
  by the deterministic validator; unconfigured endpoints return
  `configured: false` rather than fabricated output.
  - **docker-compose ships a local Ollama** (`ollama` service, model
    `qwen2.5:3b`) and points the backend at it, so the assistant works with no
    API key. Pull the model once: `docker compose exec ollama ollama pull qwen2.5:3b`.
    Local CPU models are slower and less reliable than a hosted key; override
    `AI_MODEL` to use a larger model.
  - **Users can bring their own provider** in **Settings → AI Assistant**:
    choose *OpenAI-compatible (hosted)* and paste an API key, or *Ollama (local)*
    and point the Base URL at their own server (e.g.
    `http://host.docker.internal:11434/v1` when the app runs in Docker). The key
    is encrypted at rest and never returned; **Test connection** verifies it
    before saving, and **Clear** falls back to the server default. Per-user
    settings always win over the environment config for that user.
- The auth rate limiter is **in-process** (per uvicorn worker). It is fine for a
  single worker; with multiple workers or horizontally scaled replicas, put a
  shared limiter in front (e.g. nginx `limit_req`) instead of relying on it.

---

## CI & Maintenance

- GitHub Actions (`.github/workflows/ci.yml`) runs on every push/PR to `main`:
  - **backend**: starts a Postgres service, runs `alembic upgrade head` +
    `alembic check` (migration-drift guard), then `pytest`.
  - **frontend**: `npm ci`, `tsc` + `vite build`, then `vitest`.
- **Dependabot** (`.github/dependabot.yml`) opens weekly PRs for pip, npm,
  Docker and GitHub Actions updates.
- Recommended: enable **branch protection** on `main` (require the CI checks to
  pass before merge).

---

## Future Roadmap

- 🔵 Azure & GCP providers (provider abstraction + stubs are in place)
- 📊 Resource monitoring dashboard (metrics/logs beyond Terraform state)
- 🧩 More AWS resource types and richer cross-resource validation
- 🤝 Team/multi-user projects and sharing
- 🧱 Move deployments to a hosted job queue (Redis/Celery) for horizontal scale
