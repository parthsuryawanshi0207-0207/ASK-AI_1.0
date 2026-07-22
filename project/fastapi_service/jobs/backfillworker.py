# jobs/backfillworker.py
from googleapiclient.discovery import build
from jobs.email_tasks import process_backfill_batch_task
from services.gmail_auth import get_valid_credentials
from services.rate_limiter import acquire_token

BATCH_SIZE = 100


def start_backfill(user_id: str) -> int:
    """
    Kicks off a full historical backfill for a user. Returns the number
    of batches queued so a caller/UI can show progress if desired.
    """
    creds = get_valid_credentials(user_id)
    gmail = build("gmail", "v1", credentials=creds)

    batches_queued = 0
    page_token = None

    while True:
        acquire_token(bucket="gmail_api")
        response = (
            gmail.users()
            .messages()
            .list(
                userId="me",
                maxResults=BATCH_SIZE,
                pageToken=page_token,
            )
            .execute()
        )

        message_ids = [m["id"] for m in response.get("messages", [])]
        if message_ids:
            process_backfill_batch_task.delay(user_id=user_id, message_ids=message_ids)
            batches_queued += 1

        page_token = response.get("nextPageToken")
        if not page_token:
            break

    return batches_queued
