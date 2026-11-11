"""
AI TrafficGuard - Production Surveillance Backend Entrypoint
"""
import os
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select

from app.config import SNAPSHOTS_DIR, VIDEOS_DIR, HOST, PORT, BASE_DIR
from app.db.database import init_db, SessionLocal
from app.db.models import ViolationEvent, CameraConfig
from app.api.routes import router, get_pipeline

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1. Initialize Database (events populated strictly from real AI detection pipeline)
    init_db()

    # 2. Start Video Pipeline
    pipe = get_pipeline()
    await pipe.start()
    print("[Startup] AI Video Pipeline active.")

    yield

    # Teardown
    pipe.is_running = False
    if pipe.cap:
        pipe.cap.release()
    print("[Shutdown] Pipeline stopped.")


app = FastAPI(
    title="AI TrafficGuard Surveillance API",
    description="Real-Time Traffic Violation Monitoring System (YOLO + BoT-SORT)",
    version="2.0.0",
    lifespan=lifespan
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static file routes for evidence snapshots & videos
app.mount("/snapshots", StaticFiles(directory=str(SNAPSHOTS_DIR)), name="snapshots")
app.mount("/videos", StaticFiles(directory=str(VIDEOS_DIR)), name="videos")

# API routes
app.include_router(router, prefix="/api")

# Serve frontend build if dist folder exists
frontend_dist = BASE_DIR.parent / "frontend" / "dist"
if frontend_dist.exists():
    app.mount("/", StaticFiles(directory=str(frontend_dist), html=True), name="frontend")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host=HOST, port=PORT, reload=False)
