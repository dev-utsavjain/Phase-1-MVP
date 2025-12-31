# FastAPI 

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.database import engine, Base
from app.api import auth, tasks, google_sync

# Create tables
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Unified Inbox API",
    version="1.0.0",
    description="Minimal MVP - Google Calendar & Gmail Integration"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routes
app.include_router(auth.router, prefix="/api/auth", tags=["Authentication"])
app.include_router(tasks.router, prefix="/api/tasks", tags=["Tasks"])
app.include_router(google_sync.router, prefix="/api/google", tags=["Google Sync"])

@app.get("/")
def root():
    return {
        "message": "Unified Inbox API - Minimal MVP",
        "status": "running",
        "docs": "/docs"
    }

@app.get("/health")
def health():
    return {"status": "healthy"}