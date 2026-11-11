"""
SQLAlchemy Database Models for AI TrafficGuard
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, Float, DateTime, Text, JSON
from app.db.database import Base

class ViolationEvent(Base):
    __tablename__ = "violation_events"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    camera_id = Column(String(50), index=True, default="CAM 01")
    vehicle_id = Column(Integer, index=True)
    vehicle_type = Column(String(20), index=True)  # CAR, BIKE
    status = Column(String(50))                    # HELMET, NO HELMET, SEATBELT, NO SEATBELT
    is_violation = Column(Boolean, index=True)
    confidence = Column(Float, default=0.92)
    timestamp_str = Column(String(50))             # Formatted timecode e.g. 01:11
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Evidence snapshots
    thumbnail_url = Column(String(255))
    snapshot_path = Column(String(255))
    
    # Manual verification
    is_verified = Column(Boolean, default=False)
    verified_by = Column(String(100), nullable=True)
    verified_status = Column(String(50), nullable=True) # CONFIRMED, REJECTED, OVERRIDDEN
    notes = Column(Text, nullable=True)

    def to_dict(self):
        return {
            "id": self.id,
            "camera_id": self.camera_id,
            "vehicle_id": self.vehicle_id,
            "vehicle_type": self.vehicle_type,
            "status": self.status,
            "is_violation": self.is_violation,
            "confidence": self.confidence,
            "timestamp": self.timestamp_str,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "thumbnail_url": self.thumbnail_url,
            "is_verified": self.is_verified,
            "verified_by": self.verified_by,
            "verified_status": self.verified_status,
            "notes": self.notes
        }

class CameraConfig(Base):
    __tablename__ = "camera_configs"

    id = Column(String(50), primary_key=True)       # CAM 01
    name = Column(String(100))                       # Main Highway Overhead AR2
    source_type = Column(String(20), default="video") # video, webcam, rtsp
    source_url = Column(String(500))
    location = Column(String(100), default="Ayesha Buni Sh Faisal AR2")
    is_active = Column(Boolean, default=True)
    zone_polygon = Column(JSON, nullable=True)       # [[x1,y1], [x2,y2], ...]
    created_at = Column(DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "source_type": self.source_type,
            "source_url": self.source_url,
            "location": self.location,
            "is_active": self.is_active,
            "zone_polygon": self.zone_polygon
        }
