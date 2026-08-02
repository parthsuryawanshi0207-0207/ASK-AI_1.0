import uuid
from datetime import datetime

from fastapi import APIRouter, HTTPException, UploadFile
from schemas.document import DocumentResponse
from services.access_control import classify_access_level
from services.chunking import chunk_record
from services.document_loader import load_document
from services.embeddings import embed_chunks
from services.storage import is_allowed_file, save_file
from services.vectorstore import upsert_chunks

router = APIRouter(prefix="/documents", tags=["Documents"])


@router.post("/upload", response_model=DocumentResponse)
async def upload_file(file: UploadFile):

    if not is_allowed_file(file.filename):
        raise HTTPException(status_code=400, detail="Unsupported file type.")

    contents = await file.read()

    if not contents:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    # 3. Save file to local storage
    file_path = save_file(contents, file.filename)

    # 4. Parse document
    text = load_document(file_path)

    if not text.strip():
        raise HTTPException(status_code=400, detail="No text could be extracted from the document.")

    # 5. Preprocess extracted text

    # text = preprocess_text(text)

    # 6. Chunk document

    # Create a unique tracking ID for this document
    doc_id = str(uuid.uuid4())

    record = {
        "text": text,
        "doc_id": doc_id,
        "access_level": classify_access_level(text),
        "source_type": "document_upload",
        "source": file.filename,
        "filename": file.filename,
        "uploaded_at": datetime.utcnow().isoformat(),
    }
    chunks = chunk_record(record)

    # 7. Embed and upsert
    texts = [c["text"] for c in chunks]
    embeddings = embed_chunks(texts)

    # Stream vectors along with structural metadata straight to Pinecone
    upsert_chunks(chunks, embeddings)

    # 8. Return successful response [cite: 272]
    return DocumentResponse(filename=file.filename, path=file_path, uploaded_at=datetime.utcnow())
