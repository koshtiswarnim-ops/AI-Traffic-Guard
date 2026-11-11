"""
Video Processing Pipeline & Real-Time Surveillance Engine
Decouples high-FPS video playback/streaming from asynchronous AI inference so
demo clips, uploaded MP4s, webcams, and RTSP feeds play smoothly without lag.
"""
import os
import json
import time
import ctypes
import base64
import asyncio
import threading
from collections import deque
from pathlib import Path
import cv2
import numpy as np

from app.config import DEFAULT_VIDEO, VIDEOS_DIR, SNAPSHOTS_DIR, DEFAULT_ZONE_POLYGON
from app.core.detector import DualYoloDetector
from app.core.tracker import ByteTracker
from app.core.helmet_evaluator import HelmetEvaluator
from app.core.seatbelt_evaluator import SeatbeltEvaluator
from app.core.zone_manager import ZoneManager
from app.db.database import SessionLocal
from app.db.models import ViolationEvent

REF_WIDTH = 1350
REF_HEIGHT = 756
STREAM_WIDTH = 960
STREAM_HEIGHT = 540
DEMO_TIMELINES_PATH = Path(__file__).resolve().parent.parent / "core" / "demo_timelines.json"


class VideoPipeline:
    def __init__(self):
        self.source_type = "video"  # "video", "webcam", "rtsp"
        self.source_url = str(DEFAULT_VIDEO)
        self.camera_id = "CAM 01"
        self.camera_name = "AR2 Highway Surveillance Cam 01"
        self.location = "Ayesha Buni Sh Faisal AR2"

        self.cap = None
        self.cap_lock = threading.Lock()
        self.jpeg_lock = threading.Lock()
        self.ai_lock = threading.Lock()
        self.loop = None
        self.is_running = False
        self.is_paused = False
        self.fps = 30.0
        self.native_fps = 30.0
        self.frame_idx = 0
        self.total_frames = 705
        self.frame_seq = 0
        self.active_connections = set()

        # AI Models
        self.detector = DualYoloDetector()
        self.tracker = ByteTracker()
        self.helmet_eval = HelmetEvaluator()
        self.seatbelt_eval = SeatbeltEvaluator()
        self.zone_manager = ZoneManager(
            polygon_pts=DEFAULT_ZONE_POLYGON,
            on_event_callback=self._handle_committed_event
        )

        self.demo_timelines = self._load_demo_timelines()
        self.active_demo_spec = self._match_demo_spec(self.source_url)

        # Shared streaming state
        self.latest_frame = None
        self.latest_jpeg = None
        self.latest_telemetry = {}
        self._frame_event = None
        self._ws_telemetry_future = None

        # Async AI worker coordination
        self._ai_pending_frame = None
        self._ai_has_new_dets = False
        self._ai_latest_detections = []
        self._ai_wakeup = threading.Event()

        self.start_epoch = time.time()
        self.status = "ONLINE"
        self._update_operating_mode()

    def _load_demo_timelines(self):
        try:
            if DEMO_TIMELINES_PATH.exists():
                return json.loads(DEMO_TIMELINES_PATH.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"[VideoPipeline] Note loading demo timelines: {e}")
        return {}

    def _match_demo_spec(self, src: str):
        if self.source_type != "video" or not src:
            return None
        return self.demo_timelines.get(os.path.basename(str(src)))

    def _update_operating_mode(self):
        has_custom_viol_model = (
            self.helmet_eval.custom_model is not None
            and self.seatbelt_eval.custom_model is not None
        )
        if self.detector.is_real_model and has_custom_viol_model:
            self.operating_mode = "LIVE AI (YOLOv8 + BoT-SORT)"
        elif self.active_demo_spec is not None:
            self.operating_mode = "DEMO / SIMULATION MODE (YOLOv8 + CV)"
        elif self.detector.is_real_model:
            if self.source_type in ("rtsp", "webcam"):
                self.operating_mode = "LIVE CCTV (YOLOv8 + BoT-SORT + CV)"
            else:
                self.operating_mode = "DEMO / SIMULATION MODE (YOLOv8 + CV)"
        else:
            self.operating_mode = "DEMO / SIMULATION MODE"

    def set_source(self, source_type: str, source_url: str, camera_id="CAM 01", camera_name="Overhead Highway"):
        self.source_type = source_type
        self.source_url = source_url
        self.camera_id = camera_id
        self.camera_name = camera_name
        self.start_epoch = time.time()
        self.zone_manager.reset_session()
        self.detector.reset()
        self.tracker.reset()
        with self.ai_lock:
            self._ai_pending_frame = None
            self._ai_latest_detections = []
            self._ai_has_new_dets = False
        self.active_demo_spec = self._match_demo_spec(source_url)
        self._update_operating_mode()
        self.reconnect()

    def reconnect(self):
        with self.cap_lock:
            if self.cap is not None:
                self.cap.release()
                self.cap = None
            self.frame_idx = 0
            self.detector.reset()
            self.tracker.reset()
            self.zone_manager.reset_loop_tracks()
            with self.ai_lock:
                self._ai_pending_frame = None
                self._ai_latest_detections = []
                self._ai_has_new_dets = False
            self._open_capture_unlocked()

    def _resolve_video_path(self, src: str) -> str:
        if os.path.exists(src):
            return src
        candidate = VIDEOS_DIR / src
        if candidate.exists():
            return str(candidate)
        return str(DEFAULT_VIDEO)

    def _open_capture_unlocked(self):
        try:
            if self.source_type == "webcam":
                cam_idx = int(self.source_url) if str(self.source_url).isdigit() else 0
                self.cap = cv2.VideoCapture(cam_idx, cv2.CAP_DSHOW)
                self.total_frames = 0
                self.native_fps = 30.0
            elif self.source_type == "rtsp":
                os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;tcp"
                self.cap = cv2.VideoCapture(self.source_url, cv2.CAP_FFMPEG)
                self.total_frames = 0
                self.native_fps = 25.0
            else:
                video_path = self._resolve_video_path(str(self.source_url))
                self.source_url = video_path
                self.active_demo_spec = self._match_demo_spec(video_path)
                self._update_operating_mode()
                self.cap = cv2.VideoCapture(video_path)
                self.total_frames = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 705
                cap_fps = float(self.cap.get(cv2.CAP_PROP_FPS) or 30.0)
                self.native_fps = min(30.0, max(12.0, cap_fps))

            if not self.cap or not self.cap.isOpened():
                if self.source_type in ("rtsp", "webcam"):
                    self.status = f"OFFLINE (CONNECTION FAILED: {self.source_url})"
                    self.cap = None
                    return
                print(f"[VideoPipeline] Failed to open source {self.source_url}. Falling back to default video.")
                self.cap = cv2.VideoCapture(str(DEFAULT_VIDEO))
                self.source_type = "video"
                self.source_url = str(DEFAULT_VIDEO)
                self.active_demo_spec = self._match_demo_spec(self.source_url)
                self._update_operating_mode()
                self.total_frames = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 705
                self.native_fps = 30.0

            self.status = "ONLINE"
        except Exception as e:
            print(f"[VideoPipeline] Capture open error: {e}")
            self.status = f"ERROR: {str(e)}"

    def _handle_committed_event(self, event_data):
        vid = event_data['vehicle_id']
        vtype = event_data['vehicle_type']
        status = event_data['status']
        cam_slug = event_data.get('camera_id', self.camera_id).replace(' ', '_')
        crop = event_data['crop']

        filename = f"{cam_slug}_{vtype}_{vid}_{status.replace(' ', '_')}.jpg"
        filepath = SNAPSHOTS_DIR / filename

        if crop is not None and crop.size > 0:
            cv2.imwrite(str(filepath), crop)

        event_data['thumbnail_url'] = f"/snapshots/{filename}?t={int(time.time() * 1000)}"
        event_data['snapshot_path'] = str(filepath)

        if self.loop and self.loop.is_running():
            asyncio.run_coroutine_threadsafe(
                self._persist_event_to_db(event_data),
                self.loop
            )

    async def _persist_event_to_db(self, event_data):
        is_demo = self.active_demo_spec is not None

        def _sync_save():
            with SessionLocal() as session:
                cam_id = event_data.get('camera_id', self.camera_id)
                vid = event_data['vehicle_id']
                prev_verified = None
                if is_demo:
                    existing = (
                        session.query(ViolationEvent)
                        .filter(ViolationEvent.camera_id == cam_id, ViolationEvent.vehicle_id == vid)
                        .first()
                    )
                    if existing is not None:
                        if existing.is_verified:
                            prev_verified = (
                                existing.is_verified,
                                existing.verified_by,
                                existing.verified_status,
                                existing.notes,
                            )
                        session.delete(existing)
                        session.flush()

                ev = ViolationEvent(
                    camera_id=cam_id,
                    vehicle_id=vid,
                    vehicle_type=event_data['vehicle_type'],
                    status=event_data['status'],
                    is_violation=event_data['is_violation'],
                    confidence=event_data['confidence'],
                    timestamp_str=event_data['timestamp_str'],
                    thumbnail_url=event_data['thumbnail_url'],
                    snapshot_path=event_data.get('snapshot_path'),
                    is_verified=prev_verified[0] if prev_verified else False,
                    verified_by=prev_verified[1] if prev_verified else None,
                    verified_status=prev_verified[2] if prev_verified else None,
                    notes=prev_verified[3] if prev_verified else None,
                )
                session.add(ev)
                session.commit()
                session.refresh(ev)

                # Keep SQLite compact (retain latest 150 events)
                total_rows = session.query(ViolationEvent).count()
                if total_rows > 150:
                    old_rows = (
                        session.query(ViolationEvent.id)
                        .order_by(ViolationEvent.id.desc())
                        .offset(150)
                        .all()
                    )
                    if old_rows:
                        old_ids = [r[0] for r in old_rows]
                        session.query(ViolationEvent).filter(
                            ViolationEvent.id.in_(old_ids)
                        ).delete(synchronize_session=False)
                        session.commit()

                return ev.to_dict()

        try:
            ev_dict = await asyncio.to_thread(_sync_save)
            await self.broadcast_ws({
                "type": "NEW_EVENT",
                "event": ev_dict
            })
        except Exception as e:
            print(f"[VideoPipeline] DB persist error: {e}")

    async def broadcast_ws(self, message: dict):
        conns = list(self.active_connections)
        if not conns:
            return
        text = json.dumps(message)
        results = await asyncio.gather(
            *(asyncio.wait_for(ws.send_text(text), timeout=0.06) for ws in conns),
            return_exceptions=True,
        )
        dead_conns = {ws for ws, res in zip(conns, results) if isinstance(res, BaseException)}
        if dead_conns:
            self.active_connections.difference_update(dead_conns)

    def _pulse_frame_event(self):
        if self._frame_event is not None:
            old = self._frame_event
            self._frame_event = asyncio.Event()
            old.set()

    async def start(self):
        self.loop = asyncio.get_running_loop()
        self._frame_event = asyncio.Event()
        self.is_running = True
        with self.cap_lock:
            self._open_capture_unlocked()
        threading.Thread(target=self._ai_worker_loop, daemon=True).start()
        threading.Thread(target=self._capture_loop, daemon=True).start()

    def _ai_worker_loop(self):
        """Asynchronous YOLO + BoT-SORT worker for unannotated/live/uploaded streams."""
        while self.is_running:
            self._ai_wakeup.wait(timeout=0.5)
            self._ai_wakeup.clear()

            if self.is_paused or self.active_demo_spec is not None:
                continue

            with self.ai_lock:
                frame_to_infer = self._ai_pending_frame
                self._ai_pending_frame = None

            if frame_to_infer is None:
                continue

            try:
                dets = self.detector.detect(frame_to_infer)
                with self.ai_lock:
                    self._ai_latest_detections = dets
                    self._ai_has_new_dets = True
            except Exception as e:
                print(f"[AIWorker] Inference note: {e}")

    def _capture_loop(self):
        """Wall-clock paced 30 FPS playback + frame-synchronized telemetry publisher."""
        frame_times = deque(maxlen=60)
        last_ws_push = 0.0
        next_frame_t = time.perf_counter()

        winmm = None
        try:
            winmm = ctypes.windll.winmm
            winmm.timeBeginPeriod(1)
        except Exception:
            winmm = None

        try:
            while self.is_running:
                if self.is_paused:
                    time.sleep(0.05)
                    next_frame_t = time.perf_counter()
                    frame_times.clear()
                    continue

                step_interval = 1.0 / max(12.0, float(self.native_fps or 30.0))

                with self.cap_lock:
                    if self.cap is None or not self.cap.isOpened():
                        frame = None
                        need_reconnect = self.source_type in ("rtsp", "webcam")
                    else:
                        ret, frame = self.cap.read()
                        need_reconnect = False
                        if not ret:
                            if self.source_type == "video":
                                self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                                self.frame_idx = 0
                                self.detector.reset()
                                self.tracker.reset()
                                self.zone_manager.reset_loop_tracks()
                                with self.ai_lock:
                                    self._ai_pending_frame = None
                                    self._ai_latest_detections = []
                                    self._ai_has_new_dets = False
                                ret, frame = self.cap.read()
                            else:
                                self.status = "RECONNECTING"
                                need_reconnect = True

                if need_reconnect:
                    time.sleep(1.5)
                    self.reconnect()
                    next_frame_t = time.perf_counter()
                    continue

                if frame is None:
                    time.sleep(0.05)
                    continue

                cur_zero_idx = self.frame_idx
                self.frame_idx += 1

                # Normalize to canonical 1350x756 coordinate space
                if frame.shape[1] != REF_WIDTH or frame.shape[0] != REF_HEIGHT:
                    frame = cv2.resize(frame, (REF_WIDTH, REF_HEIGHT))
                self.latest_frame = frame

                # Encode single shared MJPEG frame cleanly
                stream_img = cv2.resize(frame, (STREAM_WIDTH, STREAM_HEIGHT), interpolation=cv2.INTER_LINEAR)
                ok, jpeg_buf = cv2.imencode('.jpg', stream_img, [cv2.IMWRITE_JPEG_QUALITY, 72])
                if ok:
                    with self.jpeg_lock:
                        self.latest_jpeg = jpeg_buf.tobytes()
                        self.frame_seq += 1
                    if self.loop and self.loop.is_running():
                        self.loop.call_soon_threadsafe(self._pulse_frame_event)

                # Evaluate frame state (synchronized demo vs async YOLO live pipeline)
                now_mono = time.perf_counter()
                urgent_push = False

                if self.active_demo_spec is not None:
                    demo_fps = float(self.active_demo_spec.get("fps", 30.0))
                    offset_sec = int(self.active_demo_spec.get("clock_offset_sec", 0))
                    total_sec = offset_sec + int(cur_zero_idx / max(1.0, demo_fps))
                    timecode = f"{total_sec // 60:02d}:{total_sec % 60:02d}"
                    processed_vehicles, state_changed = self.zone_manager.sync_demo_frame(
                        frame=frame,
                        frame_idx=cur_zero_idx,
                        demo_spec=self.active_demo_spec,
                        camera_id=self.camera_id
                    )
                    urgent_push = state_changed
                else:
                    elapsed_sec = int(time.time() - self.start_epoch)
                    timecode = f"{elapsed_sec // 60:02d}:{elapsed_sec % 60:02d}"

                    # Dispatch latest frame to async AI worker if free
                    with self.ai_lock:
                        if self._ai_pending_frame is None:
                            self._ai_pending_frame = frame
                            self._ai_wakeup.set()
                        has_new = self._ai_has_new_dets
                        new_dets = self._ai_latest_detections
                        if has_new:
                            self._ai_has_new_dets = False

                    if has_new:
                        tracked = self.tracker.update(new_dets)
                    else:
                        tracked = self.tracker.predict_step()

                    prev_checking = (
                        self.zone_manager.stats['car']['checking'],
                        self.zone_manager.stats['bike']['checking'],
                        self.zone_manager.stats['car']['total'],
                        self.zone_manager.stats['bike']['total'],
                    )
                    processed_vehicles = self.zone_manager.process_tracked_vehicles(
                        tracked_vehicles=tracked,
                        frame=frame,
                        helmet_eval=self.helmet_eval,
                        seatbelt_eval=self.seatbelt_eval,
                        timecode=timecode,
                        camera_id=self.camera_id
                    )
                    cur_checking = (
                        self.zone_manager.stats['car']['checking'],
                        self.zone_manager.stats['bike']['checking'],
                        self.zone_manager.stats['car']['total'],
                        self.zone_manager.stats['bike']['total'],
                    )
                    urgent_push = (prev_checking != cur_checking)

                # Rolling 1-second measured playback FPS
                frame_times.append(now_mono)
                cutoff = now_mono - 1.0
                while len(frame_times) > 2 and frame_times[0] < cutoff:
                    frame_times.popleft()
                if len(frame_times) >= 2:
                    span = frame_times[-1] - frame_times[0]
                    if span > 0:
                        self.fps = round(min(float(self.native_fps or 30.0) + 1.0, (len(frame_times) - 1) / span), 1)

                # Publish telemetry on state changes or at ~15 Hz without queueing WS backlog
                should_push = urgent_push or (now_mono - last_ws_push >= 0.066)
                if should_push:
                    last_ws_push = now_mono
                    payload = self._build_telemetry_payload(frame, timecode, processed_vehicles)
                    self.latest_telemetry = payload
                    if self.loop and self.loop.is_running() and self.active_connections:
                        ws_ready = self._ws_telemetry_future is None or self._ws_telemetry_future.done()
                        if urgent_push or ws_ready:
                            self._ws_telemetry_future = asyncio.run_coroutine_threadsafe(
                                self.broadcast_ws(payload), self.loop
                            )

                # Precision wall-clock pacing for true 1x smooth video speed
                next_frame_t += step_interval
                sleep_for = next_frame_t - time.perf_counter()
                if sleep_for > 0.0025:
                    time.sleep(sleep_for - 0.0015)
                    while time.perf_counter() < next_frame_t:
                        pass
                elif sleep_for > 0:
                    while time.perf_counter() < next_frame_t:
                        pass
                elif sleep_for < -0.15:
                    next_frame_t = time.perf_counter()
        finally:
            if winmm is not None:
                try:
                    winmm.timeEndPeriod(1)
                except Exception:
                    pass

    def _build_telemetry_payload(self, frame, timecode, processed_vehicles):
        zoom_veh = self.zone_manager.current_zoom_vehicle
        zoom_b64 = None
        if zoom_veh and zoom_veh.get('crop') is not None:
            try:
                c = zoom_veh['crop']
                if c.size > 0:
                    c_resized = cv2.resize(c, (220, 145))
                    _, buf = cv2.imencode('.jpg', c_resized, [cv2.IMWRITE_JPEG_QUALITY, 74])
                    zoom_b64 = f"data:image/jpeg;base64,{base64.b64encode(buf).decode('utf-8')}"
            except Exception:
                zoom_b64 = None

        return {
            "type": "TELEMETRY",
            "timestamp": timecode,
            "fps": self.fps,
            "frame_idx": self.frame_idx,
            "total_frames": self.total_frames,
            "camera_id": self.camera_id,
            "camera_name": self.camera_name,
            "location": self.location,
            "status": self.status,
            "operating_mode": self.operating_mode,
            "source_type": self.source_type,
            "is_pre_annotated": self.active_demo_spec is not None,
            "car": dict(self.zone_manager.stats['car']),
            "bike": dict(self.zone_manager.stats['bike']),
            "timeline_ticks": list(self.zone_manager.timeline_ticks),
            "toasts": list(self.zone_manager.toasts),
            "zoom": {
                "has_target": zoom_veh is not None and zoom_b64 is not None,
                "id": zoom_veh['id'] if zoom_veh else None,
                "type": zoom_veh['type'] if zoom_veh else None,
                "status": zoom_veh['status'] if zoom_veh else None,
                "conf": zoom_veh['conf'] if zoom_veh else 0.0,
                "timestamp": zoom_veh.get('timecode', timecode) if zoom_veh else timecode,
                "is_violation": zoom_veh.get('is_violation', False) if zoom_veh else False,
                "crop_b64": zoom_b64
            },
            "vehicles": processed_vehicles,
            "zone_polygon": self.zone_manager.polygon_pts.tolist()
        }

    def _placeholder_jpeg(self, text="CONNECTING TO CAMERA STREAM..."):
        canvas = np.zeros((STREAM_HEIGHT, STREAM_WIDTH, 3), dtype=np.uint8)
        canvas[:] = (15, 11, 8)
        cv2.putText(
            canvas, text, (STREAM_WIDTH // 2 - 220, STREAM_HEIGHT // 2),
            cv2.FONT_HERSHEY_SIMPLEX, 0.75, (0, 229, 255), 2, cv2.LINE_AA
        )
        _, jpeg = cv2.imencode('.jpg', canvas, [cv2.IMWRITE_JPEG_QUALITY, 75])
        return jpeg.tobytes()

    async def generate_mjpeg_stream(self):
        """Event-driven async MJPEG generator serving pre-encoded frames at full stream FPS."""
        last_seq = -1
        while self.is_running:
            evt = self._frame_event
            seq = self.frame_seq
            if seq != last_seq:
                with self.jpeg_lock:
                    frame_bytes = self.latest_jpeg
                    last_seq = self.frame_seq
                if frame_bytes is not None:
                    yield (
                        b'--frame\r\n'
                        b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n'
                    )
                    continue

            if evt is not None:
                try:
                    await asyncio.wait_for(evt.wait(), timeout=0.25)
                except asyncio.TimeoutError:
                    if self.latest_jpeg is None:
                        ph = self._placeholder_jpeg(
                            self.status if "ERROR" in self.status or "OFFLINE" in self.status else "INITIALIZING STREAM..."
                        )
                        yield (
                            b'--frame\r\n'
                            b'Content-Type: image/jpeg\r\n\r\n' + ph + b'\r\n'
                        )
            else:
                await asyncio.sleep(0.03)
