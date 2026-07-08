from fastapi import FastAPI
from dotenv import load_dotenv
app = FastAPI()

@app.get("/")
def read_root():
    return {"Hello": "World"}
from routers import upload, query

app.include_router(upload.router)
app.include_router(query.router)