import base64
import hashlib
import os
import tempfile

from services.attachment_processor import process_attachment, attachment_required_ocr
from services.pii import apply_pii_protection
from services.access_control import classify_access_level
from services.ocr_cache import get_cached_ocr_result, store_ocr_result
from services.dedup import is_already_processed, mark_processed


def extract_from_email(message: dict, gmail_service=None) -> list[dict]:
    """
    `message` is the parsed Gmail API message resource (already fetched
    via messages.get). Returns a list of records, each shaped:
        {"text": str, "source": str, "access_level": str, "doc_id": str}
    ready to be handed to chunk_text() per-record by the caller.
    """
    message_id = message["id"]
    if is_already_processed(message_id):
        return []

    records = []

    body_text = _extract_body(message)
    if body_text.strip():
        records.append(_build_record(body_text, source="body", doc_id=message_id))

    for attachment in _get_attachments(message, gmail_service=gmail_service):
        record = _process_single_attachment(attachment, message_id)
        if record is not None:
            records.append(record)

    mark_processed(message_id)
    return records


def _build_record(raw_text: str, source: str, doc_id: str) -> dict:
    protected_text = apply_pii_protection(raw_text)
    access_level = classify_access_level(protected_text)
    return {
        "text": protected_text,
        "source": source,
        "access_level": access_level,
        "doc_id": doc_id,
    }


def _process_single_attachment(attachment: dict, message_id: str) -> dict | None:
    filename = attachment["filename"]
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    raw_data = attachment.get("data", "")
    if not raw_data:
        return None

    try:
        raw_bytes = base64.urlsafe_b64decode(raw_data)
    except Exception:
        return None

    if not raw_bytes:
        return None

    content_hash = hashlib.sha256(raw_bytes).hexdigest()

    # Hash-based OCR cache (Section 4.1): identical attachments (e.g. the
    # same mess-bill image sent to hundreds of students) are extracted once.
    cached_text = get_cached_ocr_result(content_hash)
    if cached_text is not None:
        return _build_record(cached_text, source=filename, doc_id=f"{message_id}:{filename}")

    with tempfile.NamedTemporaryFile(suffix=f".{ext}", delete=False) as tmp:
        tmp.write(raw_bytes)
        temp_path = tmp.name

    try:
        text = process_attachment(temp_path, ext)
        if not text or not text.strip():
            return None

        if attachment_required_ocr(temp_path, ext):
            store_ocr_result(content_hash, text)

        return _build_record(text, source=filename, doc_id=f"{message_id}:{filename}")
    except ValueError:
        return None  # unsupported attachment type -- skip, don't fail the email
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


def _extract_body(message: dict) -> str:
    """Pulls plain-text body from Gmail's nested MIME payload structure."""
    payload = message.get("payload", {})
    parts = payload.get("parts", [payload])
    for part in parts:
        if part.get("mimeType") == "text/plain":
            data = part.get("body", {}).get("data", "")
            if data:
                return base64.urlsafe_b64decode(data).decode("utf-8", errors="ignore")
    return ""


def _get_attachments(message: dict, gmail_service=None) -> list[dict]:
    """Returns [{filename, data}] for every attachment part in the message."""
    attachments = []
    payload = message.get("payload", {})
    message_id = message.get("id")

    parts = payload.get("parts", [])
    for part in parts:
        filename = part.get("filename")
        body = part.get("body", {})
        attachment_id = body.get("attachmentId")

        if filename and (attachment_id or body.get("data")):
            data = body.get("data", "")

            # If payload didn't include inline data, fetch attachment bytes via Gmail API
            if not data and attachment_id and gmail_service and message_id:
                try:
                    att_res = gmail_service.users().messages().attachments().get(
                        userId="me", messageId=message_id, id=attachment_id
                    ).execute()
                    data = att_res.get("data", "")
                except Exception as exc:
                    print(f"Failed to fetch attachment {filename} (id={attachment_id}): {exc}")

            if data:
                attachments.append({"filename": filename, "data": data})

    return attachments
