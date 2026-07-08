import os
from dotenv import load_dotenv
load_dotenv()  
from pinecone import Pinecone

# Initialize the Pinecone client
pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
index = pc.Index(os.getenv("PINECONE_INDEX_NAME"))

def upsert_chunks(doc_id: str, chunks: list[str], embeddings: list[list[float]]):
    """Stores each chunk's vector along with text and structural tracking metadata."""
    vectors = []
    for i, (chunk, emb) in enumerate(zip(chunks, embeddings)):
        vectors.append({
            "id": f"{doc_id}_chunk_{i}",
            "values": emb,
            "metadata": {
                "text": chunk,       # Returns raw text string during retrieval
                "doc_id": doc_id,    # Traces chunk back to original document
                "chunk_index": i     # Preserves sequence context
            }
        })
    index.upsert(vectors=vectors)

def query_similar(query_embedding: list[float], top_k: int = 5):
    """Queries Pinecone using the vector to find the closest matching text chunks."""
    results = index.query(
        vector=query_embedding,
        top_k=top_k,
        include_metadata=True
    )
    return results