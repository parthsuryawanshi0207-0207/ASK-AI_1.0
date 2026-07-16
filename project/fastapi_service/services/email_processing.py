import base64
import hashlib
import os
import tempfile

from services.attachment import process_attachment, attachment_required_ocr
from services.ocr_cache import get_cached_ocr_result, store_ocr_result
from services.dedup import is_already_processed, mark_processed
from services.chunking import chunk_text
from services.embeddings import embed_chunks
from services.vectorstore import upsert_chunks


def process_email_message(message: dict) -> dict:
    """
    Single entry point: raw Gmail message (dict, from messages.get(format='full'))
    -> dedup -> extract body + attachments -> chunk -> embed -> upsert.
    Reuses your EXACT existing document CRUD pipeline functions --
    nothing in chunking.py, embeddings.py, or vectorstore.py changes.
    """
    message_id = message["id"]

    if is_already_processed(message_id):
        return {"status": "skipped_duplicate", "message_id": message_id}

    indexed_sources = []

    # --- Body ---
    body_text = _extract_body(message)
    if body_text.strip():
        _index_one(text=body_text, doc_id=message_id)
        indexed_sources.append("body")

    # --- Attachments ---
    for attachment in _get_attachments(message):
        source = _process_single_attachment(attachment, message_id)
        if source is not None:
            indexed_sources.append(source)

    mark_processed(message_id)
    return {"status": "indexed", "message_id": message_id, "sources": indexed_sources}


def _index_one(text: str, doc_id: str) -> None:
    """Mirrors exactly what your upload_document() endpoint does after parsing."""
    chunks = chunk_text(text, chunk_size=500, overlap=50)
    embeddings = embed_chunks(chunks)
    upsert_chunks(doc_id=doc_id, chunks=chunks, embeddings=embeddings)


def _process_single_attachment(attachment: dict, message_id: str) -> str | None:
    filename = attachment["filename"]
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    raw_bytes = base64.urlsafe_b64decode(attachment["data"])
    content_hash = hashlib.sha256(raw_bytes).hexdigest()

    # doc_id per attachment -- keeps it separately addressable/deletable
    # in Pinecone, same pattern your delete_document_vectors() already uses
    doc_id = f"{message_id}__{filename}"

    cached_text = get_cached_ocr_result(content_hash)
    if cached_text is not None:
        _index_one(text=cached_text, doc_id=doc_id)
        return f"{filename} (cached)"

    with tempfile.NamedTemporaryFile(suffix=f".{ext}", delete=False) as tmp:
        tmp.write(raw_bytes)
        temp_path = tmp.name

    try:
        text = process_attachment(temp_path, ext)
    except ValueError:
        return None  # unsupported type -- skip this attachment only
    finally:
        os.remove(temp_path)

    if not text.strip():
        return None  # OCR/extraction returned nothing usable

    if attachment_required_ocr(temp_path, ext):
        store_ocr_result(content_hash, text)

    _index_one(text=text, doc_id=doc_id)
    return filename


def _extract_body(message: dict) -> str:
    payload = message.get("payload", {})
    parts = payload.get("parts", [payload])
    for part in parts:
        if part.get("mimeType") == "text/plain":
            data = part.get("body", {}).get("data", "")
            return base64.urlsafe_b64decode(data).decode("utf-8", errors="ignore")
    return ""


def _get_attachments(message: dict) -> list[dict]:
    attachments = []
    payload = message.get("payload", {})
    for part in payload.get("parts", []):
        filename = part.get("filename")
        body = part.get("body", {})
        if filename and body.get("attachmentId"):
            attachments.append({
                "filename": filename,
                "data": body.get("data", ""),
                "attachmentId": body.get("attachmentId"),
            })
    return attachments