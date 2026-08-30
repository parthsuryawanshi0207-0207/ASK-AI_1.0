# PowerShell script to launch Celery worker locally on Windows
Write-Host "========================================" -ForegroundColor Cyan
Write-Host " Starting Ask AI Celery Background Worker" -ForegroundColor Cyan
Write-Host " Pool: solo (Required for Windows)      " -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

$VENV_PYTHON = "C:\Users\parth\OneDrive\Desktop\Projects\AskAI\final_email2\ASK-AI\project\fastapi_service\.venv\Scripts\python.exe"

& $VENV_PYTHON -m celery -A jobs.celery_app worker --loglevel=info -P solo
