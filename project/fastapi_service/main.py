import os
import uuid
from datetime import datetime
from fastapi import FastAPI, UploadFile, File, HTTPException

from services.document_loader import load_document
from services.chunking import chunk_text
from services.embeddings import embed_chunks, embed_query
from services.vectorstore import upsert_chunks, semantic_search, delete_document_vectors
from routers.gmail_webhook import router as gmail_webhook_router


# 1. Initialize the FastAPI application
app = FastAPI(
    title="ASK-AI Document CRUD",
    description="A complete CRUD API for uploading, retrieving, updating and deleting documents.",
    version="1.0"
)

app.include_router(gmail_webhook_router)

# 2. Storage settings
UPLOAD_DIR = "storage/uploads"
ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt", ".jpg", ".jpeg", ".png", ".tiff", ".bmp"}
os.makedirs(UPLOAD_DIR, exist_ok=True)

# 3. Mock "database" — maps document_id -> metadata
fake_db = {}


# ============================================================
# CRUD OPERATIONS
# ============================================================

# --- CREATE (Upload) ---
@app.post("/documents/upload", status_code=201, tags=["Documents"])
async def upload_document(file: UploadFile = File(...)):
    """CREATE: Upload a new document and store it on disk."""
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {ext}")

    contents = await file.read()

    doc_id = str(uuid.uuid4())
    unique_name = f"{doc_id[:8]}_{file.filename}"
    save_path = os.path.join(UPLOAD_DIR, unique_name)

    with open(save_path, "wb") as f:
        f.write(contents)

    parsed_text = load_document(save_path)

    if not parsed_text.strip():
        os.remove(save_path)
        raise HTTPException(
            status_code=422,
            detail="No text could be extracted or OCR'd from this file."
        )

    chunks = chunk_text(parsed_text, chunk_size=500, overlap=50)
    embeddings = embed_chunks(chunks)
    upsert_chunks(doc_id=doc_id, chunks=chunks, embeddings=embeddings)

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


# --- SEMANTIC SEARCH (the real RAG pipeline — embeddings + Pinecone) ---
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

    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {ext}")

    old_path = fake_db[doc_id]["path"]
    if os.path.exists(old_path):
        os.remove(old_path)

    contents = await file.read()
    unique_name = f"{doc_id[:8]}_{file.filename}"
    save_path = os.path.join(UPLOAD_DIR, unique_name)
    with open(save_path, "wb") as f:
        f.write(contents)

    parsed_text = load_document(save_path)

    if not parsed_text.strip():
        os.remove(save_path)
        raise HTTPException(
            status_code=422,
            detail="No text could be extracted or OCR'd from this file."
        )

    chunks = chunk_text(parsed_text, chunk_size=500, overlap=50)

    delete_document_vectors(doc_id)
    embeddings = embed_chunks(chunks)
    upsert_chunks(doc_id=doc_id, chunks=chunks, embeddings=embeddings)

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

    path = fake_db[doc_id]["path"]
    if os.path.exists(path):
        os.remove(path)

    deleted_item = fake_db.pop(doc_id)
    delete_document_vectors(doc_id)
    return {"detail": "Document deleted", "document": deleted_item}


# --- TEMPORARY: Test endpoint to confirm Pinecone upserts from email pipeline ---
@app.get("/test/check_pinecone", tags=["Testing"])
def check_pinecone(question: str, doc_id: str = "test_message_001"):
    query_embedding = embed_query(question)
    results = semantic_search(query_embedding, doc_id=doc_id, top_k=3)
    return results

