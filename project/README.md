# ASK-AI

## Project Status

This repository contains the current implementation of the ASK-AI project. The main completed work is in two Python services:

- `django_backend`: a Django backend scaffold with a chat history model and database configuration.
- `fastapi_service`: a FastAPI service supporting document upload, parsing, storage, and chunking.

The frontend is currently a placeholder with no implemented UI.

---

## Repository Structure

- `project/django_backend/`
  - Django project core files
  - `chat_history/` app with a `ChatSession` model and PostgreSQL `vector` extension migration
  - `requirements.txt`
- `project/fastapi_service/`
  - FastAPI app and router files
  - document parsing and file storage services
  - tests for the root endpoint
  - `requirements.txt`
- `project/frontend/`
  - placeholder directory
- `project/storage/uploads/`
  - local upload storage directory used by the FastAPI service
- `docker-compose.yml`
  - local container volume mapping for file uploads
- `project/render.yaml`
  - Render deployment configuration for backend services and database

---

## Django Backend (`project/django_backend`)

### What is implemented

- Django 4.2+ project setup
- `chat_history` app registered in `INSTALLED_APPS`
- `ChatSession` model with `created_at` timestamp
- Migration to enable PostgreSQL `vector` extension via `CreateExtension("vector")`
- Django admin available at `/admin/`
- Database configured through `dj_database_url` with SQLite fallback
- Static file collection configured via `STATIC_ROOT`

### Key files

- `core/settings.py`
  - Django configuration and database setup
- `core/urls.py`
  - Admin URL route registration
- `chat_history/models.py`
  - `ChatSession` model definition
- `chat_history/migrations/0002_enable_pgvector.py`
  - Enables the `vector` extension for PostgreSQL
- `requirements.txt`
  - Django dependencies including `psycopg2-binary`, `dj-database-url`, and `gunicorn`

### Current limitations

- No API endpoints beyond the default Django admin route
- No authentication, user management, or chat history retrieval APIs yet

---

## FastAPI Service (`project/fastapi_service`)

### What is implemented

- FastAPI application scaffold in `main.py`
- Root health endpoint: `GET /` returns `{"Hello": "World"}`
- Document upload endpoint: `POST /documents/upload`
- File saving to `storage/uploads`
- Support for `.pdf`, `.docx`, and `.txt` document formats
- Document parsing for PDF, DOCX, and TXT files
- Text chunking logic with chunk size `500` and overlap `50`
- Validation for file type and empty files
- Response model containing filename, saved path, and upload timestamp
- Basic test for root endpoint

### Key files

- `main.py`
  - FastAPI app setup
- `routers/upload.py`
  - Upload route implementation and validation
- `services/storage.py`
  - Allowed file extension checks and file persistence
- `services/document_loader.py`
  - PDF, DOCX, and TXT parsing
- `services/chunking.py`
  - Text chunking utility
- `schemas/document.py`
  - Response model for uploaded documents
- `tests/test_main.py`
  - Root endpoint test
- `requirements.txt`
  - FastAPI and document-processing dependencies

### Current limitations

- Document chunks are created but not persisted anywhere yet
- No vector database or search/query integration implemented
- No user-facing UI; API-only
- No OpenAI or embeddings integration present yet

---

## Deployment and Environment

### `docker-compose.yml`

- Configures a local volume mapping:
  - `./project/storage/uploads` → `/app/storage/uploads` in the `fastapi_service` container

### `project/render.yaml`

- Defines two web services on Render:
  - `django-backend`
  - `fastapi-service`
- Defines a PostgreSQL database service `ask-ai-postgres`
- Sets environment variables for `DATABASE_URL`, `OPENAI_API_KEY`, `DJANGO_INTERNAL_URL`, and `VECTOR_DB_URL`
- Uses Python 3.11.0 for both services

---

## How to Run Locally

### Django backend

```bash
cd project/django_backend
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

### FastAPI service

```bash
cd project/fastapi_service
pip install -r requirements.txt
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### API endpoints

- Health check: `GET http://127.0.0.1:8000/`
- Upload document: `POST http://127.0.0.1:8000/documents/upload`

---

## Completed Work Summary

- Django backend scaffold created with database config and chat history model
- FastAPI service implemented for document upload, storage, parsing, and chunking
- Render deployment configuration added for both services and database
- Basic local upload storage directory and Docker volume mapping configured
- Root health endpoint test included

