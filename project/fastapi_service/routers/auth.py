# routers/auth.py
import os
from fastapi import APIRouter, HTTPException, Query
from googleapiclient.discovery import build
from services.gmail_auth import build_auth_url, exchange_code_for_tokens, get_valid_credentials

router = APIRouter(prefix="/auth", tags=["Google OAuth & Gmail Watch"])

DEFAULT_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:8000/auth/google/callback")
GCP_TOPIC_NAME = os.getenv("GCP_PUBSUB_TOPIC", "projects/ask-ai-502904/topics/gmail-notifications")


@router.get("/google/login", summary="Generate Google OAuth Login Link")
def google_login(
    user_email: str = Query(..., description="The user's email address (e.g. user@gmail.com)"),
    redirect_uri: str = Query(DEFAULT_REDIRECT_URI, description="OAuth Redirect URI registered in Google Console")
):
    """
    Step 1: Generate the Google Login URL.
    Open the returned auth_url in your browser to sign in and grant Gmail permissions.
    """
    try:
        auth_url = build_auth_url(user_id=user_email, redirect_uri=redirect_uri)
        return {
            "status": "success",
            "user_email": user_email,
            "auth_url": auth_url,
            "instructions": "Copy and open the auth_url in your browser to authorize Gmail access."
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to generate login URL: {str(exc)}")


@router.get("/google/callback", summary="Google OAuth Callback Handler")
def google_callback(
    code: str = Query(..., description="Authorization code returned by Google"),
    state: str = Query(..., description="The user email passed as state"),
    redirect_uri: str = Query(DEFAULT_REDIRECT_URI, description="Matching OAuth Redirect URI")
):
    """
    Step 2: Handles the redirect back from Google after user signs in.
    1. Exchanges authorization code for long-lived credentials.
    2. Saves credentials to tokens/{user_email}.json.
    3. Automatically registers the Gmail Pub/Sub watch subscription.
    """
    user_email = state
    try:
        # 1. Exchange code for token and save credentials
        creds = exchange_code_for_tokens(code=code, redirect_uri=redirect_uri, user_id=user_email)

        # 2. Register watch subscription automatically if GCP topic is configured
        watch_result = None
        watch_error = None
        if GCP_TOPIC_NAME:
            try:
                gmail = build("gmail", "v1", credentials=creds)
                request_body = {
                    "topicName": GCP_TOPIC_NAME,
                    "labelIds": ["INBOX"]
                }
                watch_result = gmail.users().watch(userId="me", body=request_body).execute()
            except Exception as w_err:
                watch_error = str(w_err)

        return {
            "message": f"Successfully authenticated {user_email}!",
            "user_email": user_email,
            "credentials_saved": True,
            "watch_registered": watch_result is not None,
            "watch_details": watch_result,
            "watch_error": watch_error
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to exchange token or register watch: {str(exc)}")


@router.post("/gmail/watch", summary="Register or Renew Gmail Watch Subscription")
def register_watch(
    user_email: str = Query(..., description="The authenticated user's email address"),
    topic_name: str = Query(GCP_TOPIC_NAME, description="Format: projects/PROJECT_ID/topics/TOPIC_NAME")
):
    """
    Manually register or renew a 7-day Gmail Pub/Sub watch subscription for a registered user.
    """
    if not topic_name.startswith("projects/") or "/topics/" not in topic_name:
        raise HTTPException(status_code=400, detail="Invalid topic format. Must be: projects/PROJECT_ID/topics/TOPIC_NAME")

    try:
        creds = get_valid_credentials(user_id=user_email)
        gmail = build("gmail", "v1", credentials=creds)

        request_body = {
            "topicName": topic_name,
            "labelIds": ["INBOX"]
        }

        response = gmail.users().watch(userId="me", body=request_body).execute()
        return {
            "status": "success",
            "user_email": user_email,
            "topic_name": topic_name,
            "history_id": response.get("historyId"),
            "expiration_ms": response.get("expiration"),
            "note": "Gmail watch subscriptions expire every 7 days and must be renewed."
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to register watch: {str(exc)}")


@router.post("/gmail/stop", summary="Stop Gmail Watch Subscription")
def stop_watch(
    user_email: str = Query(..., description="The authenticated user's email address to stop watching"),
    remove_token: bool = Query(True, description="Whether to also delete stored credentials from disk")
):
    """
    Stops real-time push notifications for the specified Gmail inbox and optionally removes stored credentials.
    """
    try:
        creds = get_valid_credentials(user_id=user_email)
        gmail = build("gmail", "v1", credentials=creds)

        # Call Gmail API users().stop() to cancel the active watch subscription
        gmail.users().stop(userId="me").execute()

        token_removed = False
        if remove_token:
            token_path = os.path.join("tokens", f"{user_email}.json")
            if os.path.exists(token_path):
                os.remove(token_path)
                token_removed = True

        return {
            "status": "success",
            "message": f"Successfully stopped watching Gmail inbox for {user_email}.",
            "user_email": user_email,
            "watch_stopped": True,
            "token_removed": token_removed
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to stop watch: {str(exc)}")


@router.post("/gmail/backfill", summary="Trigger Full Historical Email Backfill")
def trigger_backfill(
    user_email: str = Query(..., description="The authenticated user's email address")
):
    """
    Triggers a full historical mailbox scan for the specified user.
    Lists all past emails and dispatches them in batches of 100 to Celery workers for embedding & indexing into Pinecone.
    """
    try:
        from jobs.backfillworker import start_backfill

        batches_queued = start_backfill(user_id=user_email)
        return {
            "status": "success",
            "message": f"Historical backfill initiated for {user_email}.",
            "user_email": user_email,
            "batches_queued": batches_queued,
            "total_emails_queued_approx": batches_queued * 100,
            "note": "Celery workers are processing these batches in the background."
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to start backfill: {str(exc)}")
