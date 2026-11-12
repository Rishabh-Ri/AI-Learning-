"""Start the FastAPI backend: python -m backend.run"""
import uvicorn

from common.config import settings

if __name__ == "__main__":
    uvicorn.run("backend.main:app", host=settings.BACKEND_HOST, port=settings.BACKEND_PORT, reload=True)
