from fastapi import APIRouter
from pydantic import BaseModel
from services.embeddings import embed_query
from services.vectorstore import query_similar
from services.access_control import resolve_user_tag

from schemas.query import (
    QueryRequest,
    QueryResponse,
    SourceChunk
)

from services.rag import generate_answer

router = APIRouter(prefix="/query", tags=["query"])



@router.post(
    "/ask", 
    response_model=QueryResponse
)
async def ask_question(request: QueryRequest):
    domain = request.user_email.split("@")[-1]
    user_tag = resolve_user_tag(domain)

    query_embedding = embed_query(request.question)
    results = query_similar(query_embedding, user_tag=user_tag, top_k=5)
    
    matches = results["matches"]
    context_chunks = [
        {
            "text": match["metadata"]["text"],
            "score": match["score"],
            "doc_id": match["metadata"]["doc_id"],
            "access_level": match["metadata"]["access_level"] 
        }
        for match in matches
    ]

    answer = generate_answer(request.question, context_chunks)

    sources = [
        SourceChunk(
            text=match["metadata"]["text"],
            score=match["score"],
            doc_id=match["metadata"]["doc_id"],
            access_level=match["metadata"]["access_level"],
        )
        for match in matches
    ]

    return QueryResponse(
        question=request.question,
        answer=answer,
        sources=sources
    )
