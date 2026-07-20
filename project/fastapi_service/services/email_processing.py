"""
Single shared entry point for extracting structured, protected, tagged
content from a raw Gmail message -- used by BOTH the historical backfill
job (jobs/backfill_worker.py) and the real-time webhook handler
(routers/gmail_webhook.py), so extraction logic is never duplicated
between the two ingestion paths.

Pipeline per email:
  dedup check -> body + each attachment dispatched to the right extractor
  -> OCR-cache check/write for attachments that actually needed OCR
  -> PII hashing (roll numbers, grades) -> access-level classification
  -> return one record per body/attachment, ready for chunking

This intentionally stops BEFORE chunking/embeddings -- those stages are
unchanged from Stage 6/7 and are called by whichever router invokes this
function.
"""

import base64
import hashlib
import os
import tempfile

from services.attachment_processor import process_attachment, attachment_required_ocr
from services.pii import apply_pii_protection
from services.access_control import classify_access_level
from services.ocr_cache import get_cached_ocr_result, store_ocr_result
from services.dedup import is_already_processed, mark_processed


def extract_from_email(message: dict) -> list[dict]:
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

    for attachment in _get_attachments(message):
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
    raw_bytes = base64.urlsafe_b64decode(attachment["data"])
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
    except ValueError:
        return None  # unsupported attachment type -- skip, don't fail the email
    finally:
        os.remove(temp_path)

    if attachment_required_ocr(temp_path, ext):
        store_ocr_result(content_hash, text)

    return _build_record(text, source=filename, doc_id=f"{message_id}:{filename}")


def _extract_body(message: dict) -> str:
    """Pulls plain-text body from Gmail's nested MIME payload structure."""
    payload = message.get("payload", {})
    parts = payload.get("parts", [payload])
    for part in parts:
        if part.get("mimeType") == "text/plain":
            data = part.get("body", {}).get("data", "")
            return base64.urlsafe_b64decode(data).decode("utf-8", errors="ignore")
    return ""


def _get_attachments(message: dict) -> list[dict]:
    """Returns [{filename, data}] for every attachment part in the message."""
    attachments = []
    payload = message.get("payload", {})
    for part in payload.get("parts", []):
        filename = part.get("filename")
        body = part.get("body", {})
        if filename and body.get("attachmentId"):
            # In production, fetch the full attachment bytes via
            # messages.attachments.get(messageId, attachmentId) here.
            attachments.append({"filename": filename, "data": body.get("data", "")})
    return attachments
