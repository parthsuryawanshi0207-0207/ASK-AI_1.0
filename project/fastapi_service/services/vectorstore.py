import os
from dotenv import load_dotenv
load_dotenv()  
from pinecone import Pinecone

# Initialize the Pinecone client
pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
index = pc.Index(os.getenv("PINECONE_INDEX_NAME"))

def upsert_chunks(chunks: list[dict], embeddings: list[list[float]]) -> None:
    
    vectors = []
    for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
        vectors.append({
            "id": f"{chunk['doc_id']}-{i}",
            "values": embedding,
            "metadata": {
                "text": chunk["text"],  # Returns raw text string during retrival
                "access_level": chunk["access_level"],  # Tells the access level of individual chunk
                "doc_id": chunk["doc_id"],  #Traces chunk back to original document
                "source": chunk["source"],  # Tells where the chunk came from
            },
        })
    index.upsert(vectors=vectors)

def query_similar(query_embedding: list[float], user_tag: str, top_k: int = 5) -> dict:
    """Queries Pinecone using the vector to find the closest matching text chunks."""

    from services.access_control import allowed_access_levels
    allowed_levels = allowed_access_levels(user_tag)

    return index.query(
        vector=query_embedding,
        top_k=top_k,
        include_metadata=True,
        filter={"access_level": {"$in": allowed_levels}},
    )
