import os
from pypdf import PdfReader
from docx import Document


def load_pdf(file_path: str) -> str:
    reader = PdfReader(file_path)

    text = ""

    for page in reader.pages:
        text += page.extract_text() or ""

    return text


def load_docx(file_path: str) -> str:
    doc = Document(file_path)

    return "\n".join(
        para.text
        for para in doc.paragraphs
    )


def load_txt(file_path: str) -> str:
    with open(file_path, "r", encoding="utf-8") as f:
        return f.read()


def load_document(file_path: str) -> str:
    ext = os.path.splitext(file_path)[1].lower()

    if ext == ".pdf":
        return load_pdf(file_path)

    elif ext == ".docx":
        return load_docx(file_path)

    elif ext == ".txt":
        return load_txt(file_path)

    else:
        raise ValueError(f"Unsupported file type: {ext}")