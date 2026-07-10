from fastapi import APIRouter
from pydantic import BaseModel
from services.embeddings import embed_query
from services.vectorstore import query_similar

from schemas.query import (
    QueryRequest,
    QueryResponse
)

from services.rag import generate_answer

router = APIRouter(prefix="/query", tags=["query"])

class QueryRequest(BaseModel):
    question: str

@router.post(
    "/ask", 
    response_model=QueryResponse
)
async def ask_question(request: QueryRequest):
    query_embedding = embed_query(request.question)
    results = query_similar(query_embedding, top_k=5)
    
    matches = [
        {
            "text": match["metadata"]["text"],
            "score": match["score"],
            "doc_id": match["metadata"]["doc_id"]
        }
        for match in results["matches"]
    ]

    answer = generate_answer(
        question=request.question,
        context_chunks=matches
    )

    return QueryResponse(
        question=request.question,
        answer=answer
    )
