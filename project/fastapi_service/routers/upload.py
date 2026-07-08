import uuid
from datetime import datetime
from fastapi import APIRouter, UploadFile, HTTPException
from schemas.document import DocumentResponse


from services.storage import save_file, is_allowed_file
from services.document_loader import load_document
from services.chunking import chunk_text


from services.embeddings import embed_chunks
from services.vectorstore import upsert_chunks

router = APIRouter(
    prefix="/documents",
    tags=["Documents"]
)

@router.post(
    "/upload",
    response_model=DocumentResponse
)
async def upload_file(file: UploadFile):

    
    if not is_allowed_file(file.filename):
        raise HTTPException(
            status_code=400,
            detail="Unsupported file type."
        )

    
    contents = await file.read()

    if not contents:
        raise HTTPException(
            status_code=400,
            detail="Uploaded file is empty."
        )

    # 3. Save file to local storage
    file_path = save_file(
        contents,
        file.filename
    )

    # 4. Parse document
    text = load_document(file_path)

    if not text.strip():
        raise HTTPException(
            status_code=400,
            detail="No text could be extracted from the document."
        )

    # 5. Preprocess extracted text 

    # text = preprocess_text(text)

    # 6. Chunk document
    chunks = chunk_text(
        text=text,
        chunk_size=500,
        overlap=50
    )

   
    embeddings = embed_chunks(chunks)

    # Create a unique tracking ID for this document [cite: 272]
    doc_id = str(uuid.uuid4())

    # Stream vectors along with structural metadata straight to Pinecone [cite: 262, 272]
    upsert_chunks(doc_id, chunks, embeddings)

    # 8. Return successful response [cite: 272]
    return DocumentResponse(
        filename=file.filename,
        path=file_path,
        uploaded_at=datetime.utcnow()
    )