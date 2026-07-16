# services/gmail_auth.py
import os
import json
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from google.auth.transport.requests import Request

# Define the minimum required permission scope to read emails
SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

# Read your environment configurations
CLIENT_SECRETS_FILE = os.getenv("GMAIL_CLIENT_SECRETS_FILE", "client_secret.json")
TOKEN_STORE_PATH = os.getenv("GMAIL_TOKEN_STORE", "tokens/{user_id}.json")


def build_auth_url(user_id: str, redirect_uri: str) -> str:
    """
    Sub-Step A: Generate the Google Consent Screen URL.
    This creates the link that your React Native app will open for the user.
    """
    flow = Flow.from_client_secrets_file(
        CLIENT_SECRETS_FILE, scopes=SCOPES, redirect_uri=redirect_uri
    )
    auth_url, _ = flow.authorization_url(
        access_type="offline",  # <-- Triggers Google to issue a refresh_token
        prompt="consent",       # <-- Forces refresh_token on every login, not just the first time
        state=user_id,          # Pass the unique user identity securely through the flow
    )
    return auth_url


def exchange_code_for_tokens(code: str, redirect_uri: str, user_id: str) -> Credentials:
    """
    Sub-Step B: Exchange the temporary one-time auth code for long-lived tokens.
    Triggered right after the user successfully logs into Google in the browser.
    """
    flow = Flow.from_client_secrets_file(
        CLIENT_SECRETS_FILE, scopes=SCOPES, redirect_uri=redirect_uri
    )
    flow.fetch_token(code=code)
    creds = flow.credentials
    _persist_credentials(user_id, creds)
    return creds


def get_valid_credentials(user_id: str) -> Credentials:
    """
    Sub-Step C: Retrieve working credentials for background processing.
    Called before any Gmail API request. Automatically and transparently 
    renews an expired access token using the stored refresh token.
    """
    path = TOKEN_STORE_PATH.format(user_id=user_id)
    if not os.path.exists(path):
        raise ValueError(f"No stored credentials for user {user_id}; run OAuth flow first.")

    with open(path, "r") as f:
        data = json.load(f)

    creds = Credentials.from_authorized_user_info(data, SCOPES)

    # If the short-lived access token has expired, refresh it silently using the refresh token
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        _persist_credentials(user_id, creds)

    return creds


def _persist_credentials(user_id: str, creds: Credentials) -> None:
    """
    Helper Function: Saves the tokens to a folder named 'tokens' on disk.
    (Note: For production, replace this file store with an encrypted database column).
    """
    path = TOKEN_STORE_PATH.format(user_id=user_id)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(creds.to_json())