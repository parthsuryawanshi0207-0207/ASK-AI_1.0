import os

from dotenv import load_dotenv
from groq import Groq

load_dotenv()

client = Groq(
    api_key=os.getenv("GROQ_API_KEY")
)

MODEL = os.getenv(
    "LLM_MODEL",
    "llama-3.3-70b-versatile"
)

SYSTEM_PROMPT = """
You are an AI assistant for document question answering.

Answer ONLY using the provided context.

If the answer cannot be found in the context,
reply exactly:

'I could not find the answer in the provided documents.'

Do not make up information.
"""


def build_prompt(
    question: str,
    context_chunks: list[dict]
) -> str:

    context = ""

    for i, chunk in enumerate(context_chunks, start=1):
        context += (
            f"Source {i}\n"
            f"{chunk['text']}\n\n"
        )

    prompt = (
        f"Context:\n\n"
        f"{context}\n"
        f"Question:\n"
        f"{question}\n\n"
        f"Answer:"
    )

    return prompt


def generate_answer(
    question: str,
    context_chunks: list[dict]
) -> str:

    if not context_chunks:
        return (
            "I could not find the answer "
            "in the provided documents."
        )

    prompt = build_prompt(
        question,
        context_chunks
    )

    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {
                "role": "system",
                "content": SYSTEM_PROMPT
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        temperature=0
    )

    return response.choices[0].message.content