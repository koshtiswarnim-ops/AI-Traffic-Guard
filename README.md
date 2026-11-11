# 🚦 AI TrafficGuard: Production AI Traffic Violation Monitoring System

[![FastAPI](https://img.shields.io/badge/Backend-FastAPI-009688.svg)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/Frontend-React_19_+_Vite-61DAFB.svg)](https://react.dev/)
[![Tailwind CSS](https://img.shields.io/badge/UI-Tailwind_CSS-38B2AC.svg)](https://tailwindcss.com/)
[![OpenCV](https://img.shields.io/badge/Vision-OpenCV_4.x-brightgreen.svg)](https://opencv.org/)
[![YOLO](https://img.shields.io/badge/AI-YOLOv8_%7C_YOLOv11-orange.svg)](https://github.com/ultralytics/ultralytics)
[![Tracker](https://img.shields.io/badge/Tracker-BoT--SORT_%2F_ByteTrack-blueviolet.svg)](https://github.com/ifzhang/ByteTrack)
[![Database](https://img.shields.io/badge/Storage-PostgreSQL_%2F_SQLite-336791.svg)](https://www.postgresql.org/)

**AI TrafficGuard** is an end-to-end city surveillance traffic violation detection and monitoring system designed strictly for traffic control rooms. It pairs high-speed computer vision models with real-time surveillance analytics to detect two primary safety violations:
1. 🪖 **Helmet vs. No-Helmet Violation Detection** (Motorcycles) with **Driver Priority Disambiguation**
2. 🚗 **Seatbelt vs. No-Seatbelt Violation Detection** (Passenger Vehicles) with **Windshield Cabin Analysis**

---

## 🖥️ Surveillance UI Layout (Surveillance Control Room Aesthetic)

Recreated pixel-faithfully from real city surveillance monitoring terminals:

- **Main CCTV Stream (72% Width)**:
  - Top OSD Bar: `CAM 01 | DETECTION | LIVE | FPS | TIMESTAMP | G: region`
  - Translucent Yellow Polygon **Check Zone** (`CHECK ZONE`) across the road corridor
  - Vehicle Bounding Boxes: Persistent tracking IDs (`BIKE #2797`, `CAR #2562`)
  - State Indicators: Grey for Approaching, Amber Yellow for Checking in Zone, Bright Green for Compliant, Red for Violations
  - Stacked Floating Toast Banners: `BIKE ID2745 PASSED: HELMET`
  - Technical Surveillance Metadata: IP address, MAC address, Admin session, Location tag
  - In-Player Controls: Calibration mode, Play/Pause, Reconnect, Camera Source Switcher, Fullscreen
- **Right Monitoring Panel (28% Width)**:
  - Header: `TRAFFIC VIOLATION MONITOR`, `🔴 LIVE` blinking indicator, `YOLO + BoT-SORT | SEATBELT + HELMET`
  - **Cars | Seatbelt Card**: Total Cars, Checking, Seatbelt, No Seatbelt, Compliance %
  - **Bikes | Helmet Card**: Total Bikes, Checking, Helmet, No Helmet, Compliance %, Segmented History Ticks
  - **Live Zoom Section**: Real-time cropped bounding box HUD when vehicle enters check zone, or `WAITING FOR VEHICLE`
  - **Recent Results Feed**: Vertically scrollable list of recent detection events with evidence thumbnails, vehicle tracking IDs, compliance badges, timestamps, and manual verification triggers
- **Bottom Status Bar**:
  - `VIEW: DETECTION | FPS: 30.1 | PROCESSED FRAMES: 2165 / 3636 | ACTIVE CAMERA: CAM 01 (MAIN HIGHWAY AR2)`

---

## 🧠 Accurate Computer Vision Rules

### 1. Driver vs. Passenger Disambiguation (Motorcycles)
- In real-world traffic, motorcycles frequently carry pillion passengers.
- The pipeline isolates the **driver** (seated in front controlling the handlebars) from passengers sitting behind.
- **Strict Compliance Rule**: Violation status (`HELMET` vs `NO HELMET`) is determined strictly by the **driver's helmet status**, ensuring passengers never skew driver violation statistics.

### 2. Windshield Cabin Analysis (Cars)
- Automatically isolates the driver windshield cabin region from oncoming vehicles.
- Analyzes 3-point seatbelt diagonal strap vectors and torso geometry between 25° and 65°.

### 3. Predefined Polygon Check Zone & Multi-Frame Consensus Voting
- 4-point yellow polygon road zone.
- Rather than a brittle single-frame decision, evaluations are gathered over **3 to 5 consecutive frames** within the zone and resolved via majority voting to prevent false positives from glare, headlights, or motion blur.

### 4. Duplicate Violation Prevention
- Each tracked vehicle maintains persistent identity via BoT-SORT / ByteTrack Kalman filtering.
- State machine enforces single commit per passage: `APPROACHING` ➔ `CHECKING` ➔ `PASSED`.
- No duplicate records or artificial counter bumps are permitted.

### 5. Manual Verification & Audit Trail
- Surveillance operators can click on any recorded event to open the **Evidence Verification & Audit Review** modal.
- Operators can inspect full-resolution crops, adjust status (`CONFIRMED VIOLATION`, `FALSE POSITIVE`, `MARK COMPLIANT`), and record officer audit notes.

---

## 🚀 Quick Start Guide

### 1. One-Click Launch (Full-Stack)
Double-click `run_system.bat` or run:
```bash
cd backend
python -m uvicorn main:app --host 0.0.0.0 --port 8000
```
Then navigate to: **`http://localhost:8000`**

### 2. Development Mode (Frontend Hot Reload + Backend)
Double-click `run_dev.bat` or run concurrently:
```bash
# Terminal 1 (Backend API & WebSocket)
cd backend
python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload

# Terminal 2 (Vite React Client)
cd frontend
npm run dev
```
Navigate to: **`http://localhost:5173`**

---

## 📹 Operating Modes

1. **DEMO MODE**:
   - Ingests real-world highway surveillance footage (`cctv_camera_feed.mp4`, `traffic_real_life_1.mp4`, `sample_feed_raw.mp4`).
   - Supports uploading any custom MP4 file directly through the UI.
2. **LIVE CCTV MODE (RTSP)**:
   - Configure IP Camera using RTSP URL (`rtsp://username:password@ip:port/stream`).
   - All RTSP decoding is handled securely inside the Python FastAPI backend via OpenCV and FFmpeg (never directly from browser JavaScript).
   - Includes automatic reconnect and error recovery handling.
