import torch
from sentence_transformers import SentenceTransformer


DEVICE = "cuda" if torch.cuda.is_available() else "cpu"


model = SentenceTransformer("intfloat/e5-large-v2", device=DEVICE)

def embed_chunks(chunks: list[str], batch_size: int = 16) -> list[list[float]]:
   
    prefixed = [f"passage: {chunk}" for chunk in chunks]
    embeddings = model.encode(
        prefixed,
        batch_size=batch_size,
        normalize_embeddings=True,  # Required for cosine similarity
        convert_to_numpy=True,
        show_progress_bar=False
    )
    return embeddings.tolist()

def embed_query(query: str) -> list[float]:
   
    embedding = model.encode(
        f"query: {query}",
        normalize_embeddings=True,
        convert_to_numpy=True
    )
    return embedding.tolist()