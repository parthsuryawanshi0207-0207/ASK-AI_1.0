import os
import uuid
from datetime import datetime
from fastapi import FastAPI, UploadFile, File, HTTPException

from services.document_loader import load_document
from services.chunking import chunk_text
from services.qa import answer_question
from services.embeddings import embed_chunks, embed_query
from services.vectorstore import upsert_chunks, semantic_search, delete_document_vectors

# 1. Initialize the FastAPI application
app = FastAPI(
    title="ASK-AI Document CRUD",
    description="A complete CRUD API for uploading, retrieving, updating and deleting documents.",
    version="1.0"
)

# 2. Storage settings
UPLOAD_DIR = "storage/uploads"
ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt", ".jpg", ".jpeg", ".png", ".tiff", ".bmp"}
os.makedirs(UPLOAD_DIR, exist_ok=True)

# 3. Mock "database" — maps document_id -> metadata
# In a real project this would be a proper DB table
fake_db = {}


# ============================================================
# CRUD OPERATIONS
# ============================================================

# --- CREATE (Upload) ---
@app.post("/documents/upload", status_code=201, tags=["Documents"])
async def upload_document(file: UploadFile = File(...)):
    """CREATE: Upload a new document and store it on disk."""

    # Validate extension
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {ext}")

    # Read file contents
    contents = await file.read()

    # Generate unique id + filename
    doc_id = str(uuid.uuid4())
    unique_name = f"{doc_id[:8]}_{file.filename}"
    save_path = os.path.join(UPLOAD_DIR, unique_name)

    # Save to disk
    with open(save_path, "wb") as f:
        f.write(contents)

    # --- Stage 2: Parsing (now OCR-aware for images/scanned PDFs) ---
    parsed_text = load_document(save_path)

    # Fail loudly if OCR/extraction returned nothing usable, rather than
    # silently indexing zero chunks
    if not parsed_text.strip():
        os.remove(save_path)
        raise HTTPException(
            status_code=422,
            detail="No text could be extracted or OCR'd from this file."
        )

    # --- Stage 3: Chunking ---
    chunks = chunk_text(parsed_text, chunk_size=500, overlap=50)

    # --- Stage 4: Embeddings + Vector Storage ---
    embeddings = embed_chunks(chunks)
    upsert_chunks(doc_id=doc_id, chunks=chunks, embeddings=embeddings)

    # Save metadata + parsed text + chunks in fake_db
    fake_db[doc_id] = {
        "id": doc_id,
        "filename": file.filename,
        "path": save_path,
        "uploaded_at": datetime.now().isoformat(),
        "text": parsed_text,
        "chunks": chunks,
        "chunk_count": len(chunks)
    }

    return fake_db[doc_id]


# --- READ (All) ---
@app.get("/documents/", tags=["Documents"])
def get_all_documents():
    """READ: Retrieve metadata for all uploaded documents."""
    return list(fake_db.values())


# --- READ (Single) ---
@app.get("/documents/{doc_id}", tags=["Documents"])
def get_document(doc_id: str):
    """READ: Retrieve metadata for a single document by its ID."""
    if doc_id not in fake_db:
        raise HTTPException(status_code=404, detail="Document not found")
    return fake_db[doc_id]


# --- READ (Parsed text only) ---
@app.get("/documents/{doc_id}/text", tags=["Documents"])
def get_document_text(doc_id: str):
    """READ: Retrieve just the parsed plain text of a document."""
    if doc_id not in fake_db:
        raise HTTPException(status_code=404, detail="Document not found")
    return {"id": doc_id, "text": fake_db[doc_id]["text"]}


# --- READ (Chunks only) ---
@app.get("/documents/{doc_id}/chunks", tags=["Documents"])
def get_document_chunks(doc_id: str):
    """READ: Retrieve the list of chunks generated for a document."""
    if doc_id not in fake_db:
        raise HTTPException(status_code=404, detail="Document not found")
    return {
        "id": doc_id,
        "chunk_count": fake_db[doc_id]["chunk_count"],
        "chunks": fake_db[doc_id]["chunks"]
    }


# --- ASK (Simple keyword-based Q&A over the document's chunks) ---
@app.get("/documents/{doc_id}/ask", tags=["Documents"])
def ask_document(doc_id: str, question: str):
    """
    Ask a question about a document (e.g. 'what is the late fine?').
    Searches the document's chunks for matching keywords and tries to
    pull out any charge/amount mentioned nearby.

    NOTE: This is a simple keyword search, not true semantic search.
    Full semantic Q&A will come once the embeddings stage is added.
    """
    if doc_id not in fake_db:
        raise HTTPException(status_code=404, detail="Document not found")

    chunks = fake_db[doc_id]["chunks"]
    result = answer_question(chunks, question)
    return result


# --- SEMANTIC SEARCH (embeddings-based, understands meaning not just keywords) ---
@app.get("/documents/{doc_id}/semantic_ask", tags=["Documents"])
def semantic_ask_document(doc_id: str, question: str, top_k: int = 3):
    """
    Ask a question using true semantic search: the question is embedded
    into a vector, and Pinecone returns the chunks whose meaning is
    closest to it — even if they don't share exact keywords.
    """
    if doc_id not in fake_db:
        raise HTTPException(status_code=404, detail="Document not found")

    query_embedding = embed_query(question)
    results = semantic_search(query_embedding, doc_id=doc_id, top_k=top_k)

    return {
        "question": question,
        "results": results
    }


# --- UPDATE (Replace file) ---
@app.put("/documents/{doc_id}", tags=["Documents"])
async def update_document(doc_id: str, file: UploadFile = File(...)):
    """UPDATE: Replace an existing document's file with a new upload."""
    if doc_id not in fake_db:
        raise HTTPException(status_code=404, detail="Document not found to update")

    # Validate extension
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {ext}")

    # Remove the old file from disk
    old_path = fake_db[doc_id]["path"]
    if os.path.exists(old_path):
        os.remove(old_path)

    # Save the new file
    contents = await file.read()
    unique_name = f"{doc_id[:8]}_{file.filename}"
    save_path = os.path.join(UPLOAD_DIR, unique_name)
    with open(save_path, "wb") as f:
        f.write(contents)

    # Re-run parsing + chunking on the new file (OCR-aware)
    parsed_text = load_document(save_path)

    if not parsed_text.strip():
        os.remove(save_path)
        raise HTTPException(
            status_code=422,
            detail="No text could be extracted or OCR'd from this file."
        )

    chunks = chunk_text(parsed_text, chunk_size=500, overlap=50)

    # Replace old vectors for this doc with fresh ones from the new file
    delete_document_vectors(doc_id)
    embeddings = embed_chunks(chunks)
    upsert_chunks(doc_id=doc_id, chunks=chunks, embeddings=embeddings)

    # Overwrite metadata with new data
    fake_db[doc_id] = {
        "id": doc_id,
        "filename": file.filename,
        "path": save_path,
        "uploaded_at": datetime.now().isoformat(),
        "text": parsed_text,
        "chunks": chunks,
        "chunk_count": len(chunks)
    }
    return fake_db[doc_id]


# --- DELETE ---
@app.delete("/documents/{doc_id}", tags=["Documents"])
def delete_document(doc_id: str):
    """DELETE: Permanently remove a document from disk and the database."""
    if doc_id not in fake_db:
        raise HTTPException(status_code=404, detail="Document not found to delete")

    # Remove file from disk
    path = fake_db[doc_id]["path"]
    if os.path.exists(path):
        os.remove(path)

    deleted_item = fake_db.pop(doc_id)
    delete_document_vectors(doc_id)
    return {"detail": "Document deleted", "document": deleted_item}
