FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    unzip \
    && rm -rf /var/lib/apt/lists/*

# Optional: Install Terraform CLI for validation
RUN curl -fsSL https://releases.hashicorp.com/terraform/1.7.5/terraform_1.7.5_linux_amd64.zip -o terraform.zip \
    && unzip terraform.zip \
    && mv terraform /usr/local/bin/terraform \
    && rm terraform.zip \
    && terraform --version

# Install Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Run as a non-root user. The app only writes to its Terraform workspace
# (CLOUDFORGE_DEPLOYMENT_ROOT, default /tmp/cloudforge-deployments) and to ./app
# caches; both are made writable here. In docker-compose the source is bind
# mounted read-only-ish, which is fine — the app never writes to /app.
RUN useradd --create-home --uid 1000 app \
    && mkdir -p /tmp/cloudforge-deployments \
    && chown -R app:app /app /tmp/cloudforge-deployments

USER app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=5 \
    CMD curl -fsS http://localhost:8000/api/health || exit 1

# Production start (no reload). docker-compose overrides this with --reload
# for live local development.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
