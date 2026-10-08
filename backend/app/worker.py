"""Standalone Terraform worker.

Runs as its own process/container so Terraform never executes inside the web
API process. It polls the ``deployments`` table for queued jobs, runs them, and
streams output into ``deployment_logs``.

Run with:  python -m app.worker
"""
import asyncio
import logging

from app.database import AsyncSessionLocal, run_migrations
from app.services import deployment_runner

POLL_SECONDS = 2.0

logger = logging.getLogger("cloudforge.worker")


async def main() -> None:
    # Idempotent: makes the worker safe to start before/with the API.
    run_migrations()
    # Configure logging AFTER migrations: Alembic's fileConfig resets the root
    # logger, which would otherwise silence the worker's own logs.
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        force=True,
    )
    logger.info("Terraform worker started (polling every %.0fs)", POLL_SECONDS)
    while True:
        job_id = None
        async with AsyncSessionLocal() as db:
            job_id = await deployment_runner.claim_next(db)
        if job_id:
            logger.info("running deployment %s", job_id)
            try:
                await deployment_runner.run_job(job_id)
            except Exception as exc:  # noqa: BLE001 - keep the worker alive
                logger.exception("deployment %s crashed", job_id)
                await deployment_runner.mark_failed(job_id, str(exc))
        else:
            await asyncio.sleep(POLL_SECONDS)


if __name__ == "__main__":
    asyncio.run(main())
