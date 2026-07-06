from datetime import datetime

from fastapi import APIRouter, UploadFile, HTTPException

from schemas.document import DocumentResponse

from services.storage import (
    save_file,
    is_allowed_file,
)
from services.document_loader import load_document
from services.chunking import chunk_text

router = APIRouter(
    prefix="/documents",
    tags=["Documents"]
)


@router.post(
    "/upload",
    response_model=DocumentResponse
)
async def upload_file(file: UploadFile):

    # Validate file type
    if not is_allowed_file(file.filename):
        raise HTTPException(
            status_code=400,
            detail="Unsupported file type."
        )

    # Read uploaded file
    contents = await file.read()

    if not contents:
        raise HTTPException(
            status_code=400,
            detail="Uploaded file is empty."
        )

    # Save file to local storage
    file_path = save_file(
        contents,
        file.filename
    )

    # Parse document
    text = load_document(file_path)

    if not text.strip():
        raise HTTPException(
            status_code=400,
            detail="No text could be extracted from the document."
        )

    # Chunk document
    chunks = chunk_text(
        text=text,
        chunk_size=500,
        overlap=50
    )

    return DocumentResponse(
        filename=file.filename,
        path=file_path,
        uploaded_at=datetime.utcnow()
    )