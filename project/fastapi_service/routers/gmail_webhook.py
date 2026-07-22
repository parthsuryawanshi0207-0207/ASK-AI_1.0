"""
Real-time ingestion entry point. Google Cloud Pub/Sub pushes a
notification here whenever a new email arrives. HMAC verification is
the very first thing that runs -- reject before fetching the message,
before dedup, before OCR, before anything else is trusted.

The actual heavy work (fetch full message, extract, chunk, embed, upsert)
is handed off to the job queue rather than done inline, so the webhook
responds to Google quickly and doesn't block on OCR or LLM-adjacent work.
"""

from fastapi import APIRouter, HTTPException, Request
from jobs.email_tasks import process_new_email_task
from services.webhook_security import verify_webhook_signature

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.post("/gmail")
async def gmail_webhook(request: Request):
    raw_body = await request.body()
    signature = request.headers.get("X-Goog-Signature", "")

    if not verify_webhook_signature(raw_body, signature):
        # Reject silently-fast: no processing, no queueing, no DB writes.
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

    payload = await request.json()
    message_id = payload["message"]["data"]  # base64-encoded Pub/Sub data
    user_id = payload["message"].get("attributes", {}).get("emailAddress")

    # Hand off to the queue. Retries and failure handling for a specific
    # message are the queue's job, not this endpoint's.
    process_new_email_task.delay(user_id=user_id, message_id=message_id)

    return {"status": "queued"}
