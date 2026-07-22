# """
# TEMPORARY STUB for Step 4 development/testing.
# Replace with the real Celery task once Step 9 (job queue) lands.
# """

# class _StubTask:
#     def delay(self, **kwargs):
#         print(f"[STUB] would queue email processing task: {kwargs}")

# process_new_email_task = _StubTask()

# jobs/email_tasks.py — REPLACE THE ENTIRE STUB WITH THIS
"""
Real task: fetches the full Gmail message via the authenticated Gmail
client, then hands it to the shared extraction pipeline (Step 5).
Keeps the same .delay(**kwargs) call signature as the stub it replaces,
so gmail_webhook.py needs zero changes.
"""

from googleapiclient.discovery import build
from services.email_processor import process_email_message
from services.gmail_auth import get_valid_credentials


class _RealTask:
    def delay(self, user_id: str, message_id: str):
        try:
            creds = get_valid_credentials(user_id)
            gmail = build("gmail", "v1", credentials=creds)
            message = gmail.users().messages().get(userId="me", id=message_id, format="full").execute()

            result = process_email_message(message)
            print(f"Webhook-triggered processing complete: {result}")

        except Exception as exc:
            print(f"Failed to process webhook message {message_id}: {exc}")


process_new_email_task = _RealTask()
