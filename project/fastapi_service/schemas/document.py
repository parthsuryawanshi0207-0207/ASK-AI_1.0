from pydantic import BaseModel
from datetime import datetime


class DocumentResponse(BaseModel):
    filename: str
    path: str
    uploaded_at: datetime