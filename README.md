# ☁ CloudForge — Visual Multi-Cloud Infrastructure Automation Platform

**Final Year Project** | Visual AWS Infrastructure Builder → Terraform Generator

---

## Features (Review 2)

| Feature | Status |
|---|---|
| 🎨 **Visual Infrastructure Builder** | ✅ Drag & drop React Flow canvas |
| ⚙ **Resource Configuration** | ✅ Per-type property panels |
| ✅ **Architecture Validation** | ✅ Deterministic rule-based checks |
| ⚡ **Terraform Generation** | ✅ Jinja2 templates → valid HCL |
| 💾 **Save/Load Architecture** | ✅ PostgreSQL via SQLAlchemy |
| 📦 **ZIP Download** | ✅ In-memory ZIP of all .tf files |
| 🔐 **Auth** | ✅ JWT login/register |

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

## Demo Workflow

1. **Register** or use demo credentials: `demo@cloudforge.io` / `demo1234`
2. Click **New Project** → Name it, select AWS
3. You land in the **Visual Builder**:
   - Drag a **VPC** from the sidebar
   - Drag a **Subnet**, connect it to the VPC
   - Drag an **EC2 Instance**, connect it to the Subnet
   - Click resources to configure properties in the right panel
4. Click **Validate** to check the architecture
5. Click **Generate Terraform** → view syntax-highlighted HCL in Monaco Editor
6. Click **Download ZIP** to get a deployable Terraform project

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
- The auth rate limiter is **in-process** (per uvicorn worker). It is fine for a
  single worker; with multiple workers or horizontally scaled replicas, put a
  shared limiter in front (e.g. nginx `limit_req`) instead of relying on it.

---

## Future Roadmap

- 🔵 Azure & GCP providers
- 🤖 AI assistant for architecture suggestions
- 💰 Cost estimation per resource
- 🔒 Security analysis (open ports, IAM issues)
- 🚀 Direct Terraform plan/apply via backend
- 📊 Resource monitoring dashboard
