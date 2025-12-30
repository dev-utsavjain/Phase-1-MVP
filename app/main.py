from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.database import engine
from app.models import Base
from app.api.v1 import auth, tasks, calendar, reminders, integrations

# Create tables
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Unified Inbox API",
    version="1.0.0",
    docs_url="/api/docs"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # React frontend
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(tasks.router, prefix="/api/v1/tasks", tags=["tasks"])
app.include_router(calendar.router, prefix="/api/v1/calendar", tags=["calendar"])
app.include_router(reminders.router, prefix="/api/v1/reminders", tags=["reminders"])
app.include_router(integrations.router, prefix="/api/v1/integrations", tags=["integrations"])

@app.get("/")
def root():
    return {"message": "Unified Inbox API", "status": "running"}