from pydantic import BaseModel


class QueryRequest(BaseModel):
    question: str
    user_email: str


class SourceChunk(BaseModel):
    text: str
    score: float
    doc_id: str
    access_level: str


class QueryResponse(BaseModel):
    question: str
    answer: str
    sources: list[SourceChunk]
