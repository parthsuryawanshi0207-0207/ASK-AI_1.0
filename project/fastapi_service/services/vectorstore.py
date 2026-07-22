import os

from dotenv import load_dotenv
from pinecone import Pinecone, ServerlessSpec
from services.embeddings import EMBEDDING_DIMENSION

load_dotenv()

pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY", "fake-key-for-ci"))

INDEX_NAME = "ask-ai"

_index = None


def get_index():
    """Lazily initialize and return the Pinecone index."""
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


def upsert_chunks(doc_id: str, chunks: list[str], embeddings: list[list[float]]) -> None:
    vectors = []
    for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
        vector_id = f"{doc_id}_chunk_{i}"
        vectors.append(
            {
                "id": vector_id,
                "values": embedding,
                "metadata": {"doc_id": doc_id, "chunk_index": i, "text": chunk},
            }
        )

    if vectors:
        get_index().upsert(vectors=vectors)


def semantic_search(query_embedding: list[float], doc_id: str = None, top_k: int = 3) -> list[dict]:
    filter_dict = {"doc_id": {"$eq": doc_id}} if doc_id else None

    results = get_index().query(vector=query_embedding, top_k=top_k, include_metadata=True, filter=filter_dict)

    matches = []
    for match in results.matches:
        matches.append(
            {
                "score": match.score,
                "doc_id": match.metadata.get("doc_id"),
                "chunk_index": match.metadata.get("chunk_index"),
                "text": match.metadata.get("text"),
            }
        )

    return matches


def delete_document_vectors(doc_id: str) -> None:
    get_index().delete(filter={"doc_id": {"$eq": doc_id}})
