from fastapi import APIRouter
from schemas.query import QueryRequest, QueryResponse, SourceChunk
from services.access_control import resolve_user_tag
from services.embeddings import embed_query
from services.rag import condense_query, generate_answer
from services.vectorstore import query_similar

router = APIRouter(prefix="/query", tags=["query"])


@router.post("/ask", response_model=QueryResponse)
async def ask_question(request: QueryRequest):
    domain = request.user_email.split("@")[-1]
    user_tag = resolve_user_tag(domain, email=request.user_email)

    # Rewrite ambiguous follow-up questions using active chat history
    search_query = condense_query(request.question, request.chat_history)
    query_embedding = embed_query(search_query)
    results = query_similar(query_embedding, user_tag=user_tag, top_k=10)

    matches = results["matches"]
    context_chunks = [
        {
            "text": match["metadata"]["text"],
            "score": match["score"],
            "doc_id": match["metadata"]["doc_id"],
            "access_level": match["metadata"]["access_level"],
            "sender": match["metadata"].get("sender", ""),
            "subject": match["metadata"].get("subject", ""),
            "date": match["metadata"].get("date", ""),
            "source_type": match["metadata"].get("source_type", "unknown"),
        }
        for match in matches
    ]

    answer = generate_answer(request.question, context_chunks, chat_history=request.chat_history)

    sources = [
        SourceChunk(
            text=match["metadata"]["text"],
            score=match["score"],
            doc_id=match["metadata"]["doc_id"],
            access_level=match["metadata"]["access_level"],
            sender=match["metadata"].get("sender"),
            subject=match["metadata"].get("subject"),
            date=match["metadata"].get("date"),
            source=match["metadata"].get("source"),
            source_type=match["metadata"].get("source_type"),
        )
        for match in matches
    ]

    return QueryResponse(question=request.question, answer=answer, sources=sources)
