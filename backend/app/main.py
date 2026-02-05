"""
FastAPI application entry point
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api import messages, webhooks, auto_response, rules, documents, reservations, dashboard
from app.db.database import init_db
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

app = FastAPI(
    title="SMS Reservation System API",
    description="Demo/MVP version with mock providers",
    version="1.0.0",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict this
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize database on startup
@app.on_event("startup")
async def startup_event():
    init_db()
    logging.info("Database initialized")


# Include routers
app.include_router(messages.router)
app.include_router(webhooks.router)
app.include_router(auto_response.router)
app.include_router(rules.router)
app.include_router(documents.router)
app.include_router(reservations.router)
app.include_router(dashboard.router)


@app.get("/")
async def root():
    return {
        "message": "SMS Reservation System API",
        "version": "1.0.0",
        "docs": "/docs",
    }


@app.get("/health")
async def health_check():
    return {"status": "healthy"}
