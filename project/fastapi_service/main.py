from dotenv import load_dotenv
from fastapi import FastAPI
from routers import auth, gmail_webhook, query, upload

load_dotenv()

app = FastAPI()


@app.get("/")
def read_root():
    return {"Hello": "World"}


app.include_router(auth.router)
app.include_router(upload.router)
app.include_router(query.router)
app.include_router(gmail_webhook.router)
