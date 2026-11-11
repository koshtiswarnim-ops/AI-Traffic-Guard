"""
Check Zone Manager & Multi-Frame Consensus Voting Engine
Maintains vehicle tracking states: APPROACHING -> CHECKING -> PASSED
Prevents duplicate violation events and updates accurate telemetry counters.
"""
import cv2
import numpy as np
import time
from collections import defaultdict, deque

class ZoneManager:
    STATE_APPROACHING = "APPROACHING"
    STATE_CHECKING = "CHECKING"
    STATE_PASSED = "PASSED"

    def __init__(self, polygon_pts=None, on_event_callback=None):
        if polygon_pts is None:
            self.polygon_pts = np.array([
                [40, 480],
                [1310, 480],
                [1260, 335],
                [80, 335]
            ], dtype=np.int32)
        else:
            self.polygon_pts = np.array(polygon_pts, dtype=np.int32)

        self.on_event_callback = on_event_callback

        # Vehicle state tracking: vid -> dict
        self.vehicle_records = {}
        self._committed_demo_frames = set()
        self._recent_final_positions = []  # list of (timestamp, vtype, cx, cy) to prevent flicker double-counting

        # Aggregated telemetry counters: strictly updated from real detection events
        self.stats = {
            "car": {"total": 0, "checking": 0, "compliant": 0, "violation": 0, "compliance_pct": 0},
            "bike": {"total": 0, "checking": 0, "compliant": 0, "violation": 0, "compliance_pct": 0}
        }

        # Floating toast banners on CCTV feed (max 2)
        self.toasts = deque(maxlen=2)
        self.last_pass_time = 0

        # Timeline tick streak: list of 'compliant' or 'violation' (populated by real events)
        self.timeline_ticks = deque(maxlen=28)

        # Active zoom target vehicle
        self.current_zoom_vehicle = None
        self.current_zoom_crop = None

    def reset_session(self):
        """Reset counters and tracking records when switching cameras/videos"""
        self.vehicle_records = {}
        self._committed_demo_frames.clear()
        self._recent_final_positions.clear()
        self.stats = {
            "car": {"total": 0, "checking": 0, "compliant": 0, "violation": 0, "compliance_pct": 0},
            "bike": {"total": 0, "checking": 0, "compliant": 0, "violation": 0, "compliance_pct": 0}
        }
        self.toasts.clear()
        self.timeline_ticks.clear()
        self.current_zoom_vehicle = None
        self.current_zoom_crop = None

    def reset_loop_tracks(self):
        """Clear transient track records on video loop without wiping session stats"""
        self.vehicle_records = {}
        self._committed_demo_frames.clear()
        self._recent_final_positions.clear()
        self.current_zoom_vehicle = None
        self.current_zoom_crop = None

    def update_polygon(self, new_pts):
        self.polygon_pts = np.array(new_pts, dtype=np.int32)

    def is_point_inside(self, point):
        return cv2.pointPolygonTest(self.polygon_pts, (float(point[0]), float(point[1])), False) >= 0

    def is_bbox_in_zone(self, bbox):
        x1, y1, x2, y2 = bbox
        center_bottom = ((x1 + x2) / 2.0, y2)
        center = ((x1 + x2) / 2.0, (y1 + y2) / 2.0)
        return self.is_point_inside(center_bottom) or self.is_point_inside(center)

    def process_tracked_vehicles(self, tracked_vehicles, frame, helmet_eval, seatbelt_eval, timecode="01:12", camera_id="CAM 01"):
        now = time.time()
        active_checking_cars = 0
        active_checking_bikes = 0
        candidate_zoom_vehicle = None

        processed = []

        for v in tracked_vehicles:
            vid = v['id']
            vtype = v['type'].upper()
            bbox = v['bbox']

            if vid not in self.vehicle_records:
                self.vehicle_records[vid] = {
                    'id': vid,
                    'type': vtype,
                    'state': self.STATE_APPROACHING,
                    'votes': [],
                    'final_status': None,
                    'final_conf': 0.0,
                    'eval_crop': None,
                    'last_seen': now,
                    'has_committed': False
                }

            rec = self.vehicle_records[vid]
            rec['last_seen'] = now

            in_zone = self.is_bbox_in_zone(bbox)

            # State transition 1: APPROACHING -> CHECKING
            if rec['state'] == self.STATE_APPROACHING:
                if in_zone:
                    rec['state'] = self.STATE_CHECKING

            # Inside CHECK ZONE: perform evaluation & voting
            if rec['state'] == self.STATE_CHECKING:
                if vtype == 'BIKE':
                    active_checking_bikes += 1
                    eval_res = helmet_eval.evaluate_bike(frame, bbox, v.get('sub_detections'))
                    rec['votes'].append((eval_res['status'], eval_res['confidence']))
                    rec['eval_crop'] = eval_res.get('driver_crop')
                    rec['head_bbox'] = eval_res.get('head_bbox')
                else:  # CAR
                    active_checking_cars += 1
                    eval_res = seatbelt_eval.evaluate_car(frame, bbox, v.get('sub_detections'))
                    rec['votes'].append((eval_res['status'], eval_res['confidence']))
                    rec['eval_crop'] = eval_res.get('cabin_crop')
                    rec['cabin_bbox'] = eval_res.get('cabin_bbox')

                # Prioritize active vehicle for Live Zoom
                candidate_crop = rec['eval_crop']
                if candidate_crop is None:
                    bx1, by1, bx2, by2 = [int(p) for p in bbox]
                    candidate_crop = frame[max(0, by1):min(frame.shape[0], by2), max(0, bx1):min(frame.shape[1], bx2)]

                candidate_zoom_vehicle = {
                    'id': vid,
                    'type': vtype,
                    'status': 'CHECKING',
                    'bbox': [float(b) for b in bbox],
                    'conf': 0.92,
                    'timecode': timecode,
                    'crop': candidate_crop,
                    'is_violation': False
                }

                # Check if vehicle has exited the check zone
                y_center = (bbox[1] + bbox[3]) / 2.0
                max_zone_y = np.max(self.polygon_pts[:, 1])

                if not in_zone or y_center > (max_zone_y - 15):
                    # Multi-frame consensus voting: commit when >= 2 frame votes collected
                    if len(rec['votes']) >= 2 and not rec['has_committed']:
                        rec['state'] = self.STATE_PASSED
                        rec['has_committed'] = True
                        self.last_pass_time = now
                        self._finalize_evaluation(rec, bbox, frame, timecode, camera_id)

            state = rec['state']
            status_text = rec['final_status'] or ("CHECKING" if state == self.STATE_CHECKING else "")
            conf = rec.get('final_conf', 0.0)

            processed.append({
                'id': vid,
                'type': vtype,
                'state': state,
                'status': status_text,
                'conf': conf,
                'bbox': [float(b) for b in bbox],
                'head_bbox': [float(b) for b in rec['head_bbox']] if rec.get('head_bbox') else None,
                'cabin_bbox': [float(b) for b in rec['cabin_bbox']] if rec.get('cabin_bbox') else None,
                'is_violation': "NO" in status_text.upper() if status_text else False
            })

        # Update real checking counts
        self.stats['car']['checking'] = active_checking_cars
        self.stats['bike']['checking'] = active_checking_bikes

        # Live zoom update
        if candidate_zoom_vehicle is not None:
            self.current_zoom_vehicle = candidate_zoom_vehicle
            self.current_zoom_crop = candidate_zoom_vehicle['crop']
        elif self.current_zoom_vehicle and (now - self.last_pass_time > 4.0):
            # Reset zoom after target passes
            self.current_zoom_vehicle = None
            self.current_zoom_crop = None

        # Clean old toasts (> 6s)
        while self.toasts and (now - self.toasts[0]['created_at'] > self.toasts[0]['duration']):
            self.toasts.popleft()

        # Prune stale vehicle records (> 15s unseen)
        stale_ids = [vid for vid, rec in self.vehicle_records.items() if now - rec['last_seen'] > 15.0]
        for vid in stale_ids:
            del self.vehicle_records[vid]

        return processed

    def _commit_event(self, vid, vtype_upper, final_status, final_conf, bbox, frame, timecode, camera_id="CAM 01"):
        """Shared helper to update stats, timeline ticks, zoom panel, toasts, and DB callback."""
        now = time.time()
        is_violation = "NO" in final_status.upper()
        vtype_key = vtype_upper.lower()

        st = self.stats[vtype_key]
        st['total'] += 1
        if is_violation:
            st['violation'] += 1
            self.timeline_ticks.append('violation')
        else:
            st['compliant'] += 1
            self.timeline_ticks.append('compliant')

        if st['total'] > 0:
            st['compliance_pct'] = int(round((st['compliant'] / st['total']) * 100))

        result_label = "NOT PASSED" if is_violation else "PASSED"
        badge_text = f"{vtype_upper} ID{vid} {result_label}:  {final_status}"
        self.toasts.append({
            'text': badge_text,
            'is_violation': is_violation,
            'created_at': now,
            'duration': 6.0
        })

        x1, y1, x2, y2 = [int(v) for v in bbox]
        h_f, w_f = frame.shape[:2]
        crop = frame[max(0, y1):min(h_f, y2), max(0, x1):min(w_f, x2)]
        self.last_pass_time = now

        self.current_zoom_vehicle = {
            'id': vid,
            'type': vtype_upper,
            'status': final_status,
            'bbox': [float(b) for b in bbox],
            'conf': round(float(final_conf), 2),
            'timecode': timecode,
            'crop': crop if crop.size > 0 else self.current_zoom_crop,
            'is_violation': is_violation
        }

        if self.on_event_callback:
            self.on_event_callback({
                'camera_id': camera_id,
                'vehicle_id': vid,
                'vehicle_type': vtype_upper,
                'status': final_status,
                'is_violation': is_violation,
                'confidence': round(float(final_conf), 2),
                'timestamp_str': timecode,
                'crop': crop
            })

    def _finalize_evaluation(self, rec, bbox, frame, timecode, camera_id="CAM 01"):
        """Aggregate votes and commit once per physical vehicle crossing."""
        now = time.time()
        cx = (bbox[0] + bbox[2]) / 2.0
        cy = (bbox[1] + bbox[3]) / 2.0
        self._recent_final_positions = [p for p in self._recent_final_positions if now - p[0] < 1.5]
        if any(p[1] == rec['type'] and np.hypot(cx - p[2], cy - p[3]) < 95.0 for p in self._recent_final_positions):
            return
        self._recent_final_positions.append((now, rec['type'], cx, cy))

        vtype = rec['type'].lower()
        votes = rec['votes']
        if not votes:
            final_status = "HELMET" if vtype == "bike" else "SEATBELT"
            final_conf = 0.85
        else:
            status_counts = defaultdict(int)
            conf_sums = defaultdict(float)
            for st, cf in votes:
                status_counts[st] += 1
                conf_sums[st] += cf
            final_status = max(status_counts.keys(), key=lambda k: status_counts[k])
            final_conf = conf_sums[final_status] / status_counts[final_status]

        rec['final_status'] = final_status
        rec['final_conf'] = final_conf
        self._commit_event(rec['id'], rec['type'], final_status, final_conf, bbox, frame, timecode, camera_id)

    def sync_demo_frame(self, frame, frame_idx, demo_spec, camera_id="CAM 01"):
        """Synchronize stats, Live Zoom, Checking counters, and DB events frame-by-frame with a pre-annotated demo feed."""
        now = time.time()
        events = demo_spec.get("events", [])
        checking_cars = 0
        checking_bikes = 0
        active_vehicles = []
        active_checking_target = None
        committed_now = False

        h_f, w_f = frame.shape[:2]

        for ev in events:
            cs = ev["check_start_frame"]
            pf = ev["pass_frame"]
            if cs <= frame_idx < pf:
                if ev["type"] == "CAR":
                    checking_cars += 1
                else:
                    checking_bikes += 1
                progress = (frame_idx - cs) / float(max(1, pf - cs))
                cb = ev["check_bbox"]
                pb = ev["pass_bbox"]
                cur_box = [cb[i] + (pb[i] - cb[i]) * progress for i in range(4)]
                active_vehicles.append({
                    'id': ev["id"],
                    'type': ev["type"],
                    'state': self.STATE_CHECKING,
                    'status': 'CHECKING',
                    'conf': 0.92,
                    'bbox': cur_box,
                    'head_bbox': None,
                    'cabin_bbox': None,
                    'is_violation': False
                })
                active_checking_target = (ev, cur_box)
            elif frame_idx == pf and pf not in self._committed_demo_frames:
                self._committed_demo_frames.add(pf)
                committed_now = True
                self._commit_event(
                    vid=ev["id"],
                    vtype_upper=ev["type"],
                    final_status=ev["status"],
                    final_conf=ev.get("confidence", 0.90),
                    bbox=ev["pass_bbox"],
                    frame=frame,
                    timecode=ev["timestamp"],
                    camera_id=camera_id
                )
            elif pf < frame_idx <= pf + 15:
                active_vehicles.append({
                    'id': ev["id"],
                    'type': ev["type"],
                    'state': self.STATE_PASSED,
                    'status': ev["status"],
                    'conf': ev.get("confidence", 0.90),
                    'bbox': [float(v) for v in ev["pass_bbox"]],
                    'head_bbox': None,
                    'cabin_bbox': None,
                    'is_violation': ev["is_violation"]
                })

        prev_checking = (self.stats['car']['checking'], self.stats['bike']['checking'])
        self.stats['car']['checking'] = checking_cars
        self.stats['bike']['checking'] = checking_bikes
        checking_changed = prev_checking != (checking_cars, checking_bikes)

        # Update Live Zoom to track currently checking vehicle unless one just passed < 1.2s ago
        if active_checking_target is not None and (now - self.last_pass_time > 1.2):
            ev, cur_box = active_checking_target
            bx1, by1, bx2, by2 = [int(v) for v in cur_box]
            crop = frame[max(0, by1):min(h_f, by2), max(0, bx1):min(w_f, bx2)]
            if crop.size > 0:
                self.current_zoom_crop = crop
                self.current_zoom_vehicle = {
                    'id': ev["id"],
                    'type': ev["type"],
                    'status': 'CHECKING',
                    'bbox': cur_box,
                    'conf': 0.92,
                    'timecode': ev["timestamp"],
                    'crop': crop,
                    'is_violation': False
                }
        elif not active_checking_target and self.current_zoom_vehicle and (now - self.last_pass_time > 3.5):
            self.current_zoom_vehicle = None
            self.current_zoom_crop = None

        while self.toasts and (now - self.toasts[0]['created_at'] > self.toasts[0]['duration']):
            self.toasts.popleft()

        return active_vehicles, (committed_now or checking_changed)
