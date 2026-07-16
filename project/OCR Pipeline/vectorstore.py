import os
from dotenv import load_dotenv
from pinecone import Pinecone, ServerlessSpec

from services.embeddings import EMBEDDING_DIMENSION

load_dotenv()

pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))

INDEX_NAME = "ask-ai"

# Create the index once, if it doesn't already exist.
# This only runs the actual creation the first time the app starts;
# on every later startup it just confirms the index is already there.
if not pc.has_index(INDEX_NAME):
    pc.create_index(
        name=INDEX_NAME,
        dimension=EMBEDDING_DIMENSION,
        metric="cosine",
        spec=ServerlessSpec(cloud="aws", region="us-east-1")
    )

index = pc.Index(INDEX_NAME)


def upsert_chunks(doc_id: str, chunks: list[str], embeddings: list[list[float]]) -> None:
    """
    Store each chunk's embedding vector in Pinecone, tagged with which
    document and which chunk position it came from (as metadata), plus
    the original chunk text itself so it can be returned directly on
    a search hit without needing a separate lookup.

    'upsert' means: insert if the ID is new, overwrite if it already exists.
    """
    vectors = []
    for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
        vector_id = f"{doc_id}_chunk_{i}"
        vectors.append({
            "id": vector_id,
            "values": embedding,
            "metadata": {
                "doc_id": doc_id,
                "chunk_index": i,
                "text": chunk
            }
        })

    if vectors:
        index.upsert(vectors=vectors)


def semantic_search(query_embedding: list[float], doc_id: str = None, top_k: int = 3) -> list[dict]:
    """
    Find the chunks whose embeddings are most similar (in meaning) to
    the query embedding. Optionally restrict the search to a single
    document via metadata filtering.
    """
    filter_dict = {"doc_id": {"$eq": doc_id}} if doc_id else None

    results = index.query(
        vector=query_embedding,
        top_k=top_k,
        include_metadata=True,
        filter=filter_dict
    )

    matches = []
    for match in results.matches:
        matches.append({
            "score": match.score,
            "doc_id": match.metadata.get("doc_id"),
            "chunk_index": match.metadata.get("chunk_index"),
            "text": match.metadata.get("text")
        })

    return matches


def delete_document_vectors(doc_id: str) -> None:
    """
    Remove all vectors belonging to a document, e.g. when the document
    itself is deleted or re-uploaded via PUT.
    """
    index.delete(filter={"doc_id": {"$eq": doc_id}})
