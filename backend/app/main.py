from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import os

from app.database import engine, Base
from app.routers import auth, projects, architecture, terraform, infrastructure


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create tables on startup
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield


app = FastAPI(
    title="CloudForge API",
    description="Visual Multi-Cloud Infrastructure Automation Platform",
    version="1.0.0",
    lifespan=lifespan,
)

# Configure CORS. In production, require ALLOWED_ORIGINS env var (comma-separated).
_ENV = os.environ.get('CLOUDFORGE_ENV', os.environ.get('ENV', 'development')).lower()
if _ENV == 'production':
    allowed = os.environ.get('ALLOWED_ORIGINS')
    if not allowed:
        raise RuntimeError('ALLOWED_ORIGINS must be set in production (comma-separated origins)')
    allow_origins = [o.strip() for o in allowed.split(',') if o.strip()]
else:
    # Auth is cookie-based, so wildcard origins are not an option even in dev:
    # a reflected Origin would let any site make credentialed requests.
    # ALLOWED_ORIGINS can override this list in dev if needed.
    allowed = os.environ.get('ALLOWED_ORIGINS')
    if allowed:
        allow_origins = [o.strip() for o in allowed.split(',') if o.strip()]
    else:
        allow_origins = [
            'http://localhost:5173',
            'http://127.0.0.1:5173',
            'http://localhost:3000',
            'http://127.0.0.1:3000',
        ]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api/auth", tags=["Authentication"])
app.include_router(projects.router, prefix="/api/projects", tags=["Projects"])
app.include_router(architecture.router, prefix="/api/projects", tags=["Architecture"])
app.include_router(terraform.router, prefix="/api/projects", tags=["Terraform"])
app.include_router(infrastructure.router, prefix="/api/infrastructure", tags=["Infrastructure"])


@app.get("/api/health")
async def health():
    return {"status": "ok", "service": "CloudForge API"}
