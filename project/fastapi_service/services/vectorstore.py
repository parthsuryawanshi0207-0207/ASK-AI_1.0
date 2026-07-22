import os

from dotenv import load_dotenv
from pinecone import Pinecone, ServerlessSpec

from services.embeddings import EMBEDDING_DIMENSION

load_dotenv()

# Read from env so the same code works locally and on Render
_PINECONE_API_KEY = os.getenv("PINECONE_API_KEY", "fake-key-for-ci")
INDEX_NAME = os.getenv("PINECONE_INDEX_NAME", "ask-ai")

pc = Pinecone(api_key=_PINECONE_API_KEY)

_index = None


def get_index():
    """Lazily initialize and return the Pinecone index (creates it if missing)."""
    global _index
    if _index is None:
        if not pc.has_index(INDEX_NAME):
            pc.create_index(
                name=INDEX_NAME,
                dimension=EMBEDDING_DIMENSION,
                metric="cosine",
                spec=ServerlessSpec(cloud="aws", region="us-east-1"),
            )
        _index = pc.Index(INDEX_NAME)
    return _index


def upsert_chunks(chunks: list, embeddings: list, doc_id: str = None) -> None:
    """
    Upsert chunks into Pinecone.

    Accepts two calling conventions:
      1. upload router: upsert_chunks(chunks_of_dicts, embeddings)
         where each chunk is a dict with keys: text, doc_id, access_level, source
      2. email processing: upsert_chunks(doc_id=..., chunks=list[str], embeddings=...)
    """
    vectors = []
    for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
        if isinstance(chunk, dict):
            # Called from upload.py — chunk is already a rich dict
            chunk_doc_id = chunk.get("doc_id", doc_id or f"doc_{i}")
            vector_id = f"{chunk_doc_id}_chunk_{i}"
            metadata = {
                "doc_id": chunk_doc_id,
                "chunk_index": i,
                "text": chunk.get("text", ""),
                "access_level": chunk.get("access_level", "general"),
                "source": chunk.get("source", "upload"),
            }
        else:
            # Called from email_processing.py — chunk is a plain string
            chunk_doc_id = doc_id or f"doc_{i}"
            vector_id = f"{chunk_doc_id}_chunk_{i}"
            metadata = {
                "doc_id": chunk_doc_id,
                "chunk_index": i,
                "text": chunk,
                "access_level": "general",
                "source": "email",
            }

        vectors.append({"id": vector_id, "values": embedding, "metadata": metadata})

    if vectors:
        get_index().upsert(vectors=vectors)


def query_similar(query_embedding: list, user_tag: str = None, top_k: int = 5) -> dict:
    """
    Search Pinecone for the most similar chunks.
    Optionally filter by access_level (user_tag) so users only see their org's data.
    Returns a dict with a 'matches' key to match Pinecone's native response shape.
    """
    filter_dict = None
    if user_tag:
        filter_dict = {"access_level": {"$in": [user_tag, "general"]}}

    results = get_index().query(
        vector=query_embedding,
        top_k=top_k,
        include_metadata=True,
        filter=filter_dict,
    )
    
    # Convert Pinecone ScoredVector objects to standard dicts so query.py can use match["metadata"]
    normalized_matches = []
    for m in results.matches:
        normalized_matches.append({
            "id": m.id,
            "score": m.score,
            "metadata": m.metadata
        })
        
    return {"matches": normalized_matches}


def semantic_search(query_embedding: list, doc_id: str = None, top_k: int = 3) -> list:
    """Legacy helper used by the document CRUD endpoints."""
    filter_dict = {"doc_id": {"$eq": doc_id}} if doc_id else None
    results = get_index().query(
        vector=query_embedding,
        top_k=top_k,
        include_metadata=True,
        filter=filter_dict,
    )
    return [
        {
            "score": m.score,
            "doc_id": m.metadata.get("doc_id"),
            "chunk_index": m.metadata.get("chunk_index"),
            "text": m.metadata.get("text"),
        }
        for m in results.matches
    ]


def delete_document_vectors(doc_id: str) -> None:
    get_index().delete(filter={"doc_id": {"$eq": doc_id}})
