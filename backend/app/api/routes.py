"""
FastAPI REST Endpoints and WebSocket Handlers for AI TrafficGuard
"""
import os
import time
import shutil
from typing import List, Optional
from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect, UploadFile, File, Form, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse
from sqlalchemy import select, desc
from sqlalchemy.orm import Session

from app.config import VIDEOS_DIR
from app.db.database import get_db
from app.db.models import ViolationEvent, CameraConfig
from app.services.video_pipeline import VideoPipeline

router = APIRouter()

# Global pipeline instance shared across application
pipeline: Optional[VideoPipeline] = None

def get_pipeline():
    global pipeline
    if pipeline is None:
        pipeline = VideoPipeline()
    return pipeline


@router.get("/status")
async def get_system_status():
    pipe = get_pipeline()
    return {
        "status": pipe.status,
        "operating_mode": pipe.operating_mode,
        "active_camera": pipe.camera_id,
        "camera_name": pipe.camera_name,
        "location": pipe.location,
        "fps": pipe.fps,
        "source_type": pipe.source_type,
        "source_url": pipe.source_url,
        "is_paused": pipe.is_paused,
        "total_frames": pipe.total_frames,
        "frame_idx": pipe.frame_idx
    }


@router.get("/telemetry")
async def get_telemetry():
    pipe = get_pipeline()
    return pipe.latest_telemetry or {
        "status": pipe.status,
        "car": pipe.zone_manager.stats['car'],
        "bike": pipe.zone_manager.stats['bike'],
        "fps": pipe.fps
    }


@router.get("/cameras")
def get_cameras(db: Session = Depends(get_db)):
    pipe = get_pipeline()
    db_cams = db.query(CameraConfig).all()
    
    if not db_cams:
        return [
            {
                "id": "CAM 01",
                "name": "AR2 Highway Surveillance Cam 01",
                "source_type": pipe.source_type,
                "source_url": pipe.source_url,
                "location": "Ayesha Buni Sh Faisal AR2",
                "is_active": True
            },
            {
                "id": "CAM 02",
                "name": "Downtown North Intersection",
                "source_type": "video",
                "source_url": "traffic_real_life_1.mp4",
                "location": "North Boulevard 04",
                "is_active": False
            },
            {
                "id": "CAM 03",
                "name": "Toll Plaza Inbound Lane 3",
                "source_type": "video",
                "source_url": "sample_feed_raw.mp4",
                "location": "Plaza Checkpoint E",
                "is_active": False
            }
        ]
    return [c.to_dict() for c in db_cams]


@router.post("/cameras")
def add_or_update_camera(
    id: str = Form(...),
    name: str = Form(...),
    source_type: str = Form(...),
    source_url: str = Form(...),
    location: str = Form("Highway"),
    db: Session = Depends(get_db)
):
    pipe = get_pipeline()
    pipe.set_source(source_type, source_url, camera_id=id, camera_name=name)
    pipe.location = location
    
    cam = db.query(CameraConfig).filter(CameraConfig.id == id).first()
    if not cam:
        cam = CameraConfig(id=id, name=name, source_type=source_type, source_url=source_url, location=location, is_active=True)
        db.add(cam)
    else:
        cam.name = name
        cam.source_type = source_type
        cam.source_url = source_url
        cam.location = location
        cam.is_active = True
    db.commit()

    return {
        "message": f"Camera {id} configured",
        "stream_status": pipe.status,
        "camera": cam.to_dict()
    }


@router.post("/upload")
def upload_video(file: UploadFile = File(...)):
    pipe = get_pipeline()
    filename = f"uploaded_{int(time.time())}_{file.filename}"
    target_path = VIDEOS_DIR / filename
    
    with open(target_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    pipe.set_source("video", str(target_path), camera_id="CAM 01", camera_name=f"Custom: {file.filename}")
    return {"message": "Video uploaded and loaded successfully", "path": str(target_path)}


@router.get("/events")
def get_events(
    limit: int = 50,
    violation_only: bool = False,
    db: Session = Depends(get_db)
):
    query = db.query(ViolationEvent).order_by(desc(ViolationEvent.id))
    if violation_only:
        query = query.filter(ViolationEvent.is_violation == True)
    events = query.limit(limit).all()
    return [ev.to_dict() for ev in events]


@router.post("/events/{event_id}/verify")
async def verify_event(
    event_id: int,
    verified_status: str = Form("CONFIRMED"),
    verified_by: str = Form("Officer Admin"),
    notes: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    event = db.query(ViolationEvent).filter(ViolationEvent.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
        
    event.is_verified = True
    event.verified_by = verified_by
    event.verified_status = verified_status
    if notes:
        event.notes = notes
    db.commit()
    db.refresh(event)
    
    pipe = get_pipeline()
    await pipe.broadcast_ws({
        "type": "EVENT_VERIFIED",
        "event": event.to_dict()
    })
    
    return {"message": "Event verified successfully", "event": event.to_dict()}


@router.get("/zone")
async def get_zone():
    pipe = get_pipeline()
    return {"zone_polygon": pipe.zone_manager.polygon_pts.tolist()}


@router.put("/zone")
async def update_zone(polygon: List[List[int]]):
    pipe = get_pipeline()
    pipe.zone_manager.update_polygon(polygon)
    return {"message": "Zone updated successfully", "zone_polygon": polygon}


@router.post("/control/pause")
async def toggle_pause():
    pipe = get_pipeline()
    pipe.is_paused = not pipe.is_paused
    return {"is_paused": pipe.is_paused}


@router.post("/control/reconnect")
async def reconnect_stream():
    pipe = get_pipeline()
    pipe.reconnect()
    return {"message": "Stream reconnected", "status": pipe.status}


@router.get("/stream/video_feed")
async def video_feed():
    """Stream live camera video as standard MJPEG stream"""
    pipe = get_pipeline()
    return StreamingResponse(
        pipe.generate_mjpeg_stream(),
        media_type="multipart/x-mixed-replace; boundary=frame"
    )


@router.websocket("/ws/live")
async def websocket_live_telemetry(websocket: WebSocket):
    """Real-time bi-directional WebSocket connection for telemetry, bounding boxes, and toasts"""
    await websocket.accept()
    pipe = get_pipeline()
    pipe.active_connections.add(websocket)
    
    # Send initial snapshot immediately
    if pipe.latest_telemetry:
        await websocket.send_json(pipe.latest_telemetry)
        
    try:
        while True:
            data = await websocket.receive_json()
            # Handle incoming client commands (e.g. pause, zone change, camera change)
            action = data.get("action")
            if action == "PAUSE":
                pipe.is_paused = not pipe.is_paused
            elif action == "RECONNECT":
                pipe.reconnect()
            elif action == "UPDATE_ZONE":
                new_zone = data.get("polygon")
                if new_zone:
                    pipe.zone_manager.update_polygon(new_zone)
    except WebSocketDisconnect:
        pipe.active_connections.discard(websocket)
    except Exception:
        pipe.active_connections.discard(websocket)
