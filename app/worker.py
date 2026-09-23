import httpx
from celery import Celery

from app.core.config import settings
from app.db.session import SessionLocal
from app.services.test_runner import REQUEST_TIMEOUT_SECONDS, execute_test_run

celery_app = Celery("specpulse", broker=settings.redis_url)
celery_app.conf.update(task_ignore_result=True, worker_prefetch_multiplier=1)


@celery_app.task(name="specpulse.execute_test_run")
def execute_test_run_task(run_id: int) -> None:
    with SessionLocal() as db:
        with httpx.Client(
            timeout=REQUEST_TIMEOUT_SECONDS, follow_redirects=False, trust_env=False
        ) as client:
            execute_test_run(db, run_id, client)
