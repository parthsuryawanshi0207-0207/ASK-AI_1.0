def chunk_text(
    text: str,
    chunk_size: int = 500,
    overlap: int = 50
) -> list[str]:

    chunks = []

    start = 0

    while start < len(text):

        end = start + chunk_size

        chunks.append(text[start:end])

        start += chunk_size - overlap

    return chunks



def chunk_record(record: dict) -> list[dict]:

    text_chunks = chunk_text(record["text"])
    return [
        {
            "text": chunk,
            "access_level": record["access_level"],
            "doc_id": record["doc_id"],
            "source": record["source"],
        }
        for chunk in text_chunks
    ]
