
import os
from celery import Celery
from dotenv import load_dotenv

load_dotenv()

celery_app = Celery(
    "ask_ai_email_pipeline",
    broker=os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0"),
    backend=os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/1"),
    include=["jobs.email_tasks"]
)

celery_app.conf.update(
    task_acks_late=True,          # don't ack until the task actually finishes
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,  # avoid one worker hoarding many slow OCR tasks
)
