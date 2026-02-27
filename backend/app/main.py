"""Factory Action Console - FastAPI Application."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api import cameras, events, websocket
from app.config import settings
from app.database import init_db
from app.services.camera_manager import camera_manager
from app.services.event_service import event_service


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    # Startup
    print(f"Starting {settings.app_name}...")

    # Initialize database
    await init_db()
    print("Database initialized")

    # Set up event callback
    async def on_event_completed(event_data: dict):
        """Handle completed detection events."""
        try:
            await event_service.create_event(event_data)
            print(f"Event saved: {event_data.get('id')}")
        except Exception as e:
            print(f"Failed to save event: {e}")

    camera_manager.set_event_callback(lambda e: on_event_completed(e))

    yield

    # Shutdown
    print("Shutting down...")
    await camera_manager.stop_all()
    print("All cameras stopped")


# Create FastAPI app
app = FastAPI(
    title=settings.app_name,
    description="Real-time worker hydration action detection for industrial automation",
    version="1.0.0",
    lifespan=lifespan,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(cameras.router)
app.include_router(events.router)
app.include_router(websocket.router)

# Mount static files for snapshots and clips
app.mount("/static/snapshots",
          StaticFiles(directory=str(settings.snapshots_dir)), name="snapshots")
app.mount("/static/clips",
          StaticFiles(directory=str(settings.clips_dir)), name="clips")


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "name": settings.app_name,
        "version": "1.0.0",
        "status": "running",
    }


@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "cameras_running": len(camera_manager.get_running_cameras()),
    }


@app.get("/api/status")
async def system_status():
    """Get system status."""
    running_cameras = camera_manager.get_running_cameras()
    camera_statuses = []

    for cam_id in running_cameras:
        processor = camera_manager.get_processor(cam_id)
        if processor:
            camera_statuses.append({
                "camera_id": cam_id,
                "status": processor.status,
                "fps": processor.fps,
                "frames": processor.frame_count,
            })

    return {
        "app_name": settings.app_name,
        "running_cameras": len(running_cameras),
        "cameras": camera_statuses,
    }


# For running with uvicorn directly
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
    )
