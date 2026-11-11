"""
Dual YOLO Detection Engine + BoT-SORT Tracking Integration
Detects Vehicles (Cars, Motorcycles, Buses, Trucks) and Persons.
Associates persons (drivers/riders) with their vehicles.
Supports Ultralytics YOLOv8/v11 + BoT-SORT with an OpenCV motion contour fallback.
"""
import os
from pathlib import Path
import cv2
import numpy as np

BACKEND_DIR = Path(__file__).resolve().parent.parent.parent


class DualYoloDetector:
    def __init__(self, vehicle_model_path=None, conf_thresh=0.22):
        self.vehicle_model_path = vehicle_model_path
        self.conf_thresh = conf_thresh
        self.vehicle_model = None
        self.is_real_model = False

        self._init_models()
        self.bg_subtractor = cv2.createBackgroundSubtractorMOG2(
            history=300, varThreshold=30, detectShadows=True
        )

    def _init_models(self):
        try:
            import torch
            torch.set_num_threads(min(4, os.cpu_count() or 4))
            from ultralytics import YOLO
            default_weights = BACKEND_DIR / "yolov8n.pt"
            path_to_try = self.vehicle_model_path or (
                str(default_weights) if default_weights.exists() else "yolov8n.pt"
            )
            if os.path.exists(path_to_try):
                self.vehicle_model = YOLO(path_to_try)
                self.is_real_model = True
                print(f"[Detector] Ultralytics YOLO + BoT-SORT initialized ({path_to_try})")
            else:
                print(f"[Detector] YOLO weights '{path_to_try}' not locally cached. Using Vision Optical Flow Engine.")
                self.vehicle_model = None
                self.is_real_model = False
        except Exception as e:
            print(f"[Detector] Ultralytics YOLO initialization note: {e}. Utilizing Vision Optical Engine.")
            self.vehicle_model = None
            self.is_real_model = False

    def reset(self):
        """Reset tracker & background subtractor state when switching/looping sources"""
        if self.vehicle_model is not None:
            try:
                self.vehicle_model.predictor = None
            except Exception:
                pass
        self.bg_subtractor = cv2.createBackgroundSubtractorMOG2(
            history=300, varThreshold=30, detectShadows=True
        )

    def detect(self, frame):
        """
        Detect vehicles and associate rider/driver person detections.
        Returns:
            detections: list of dicts:
                [{'bbox': [x1, y1, x2, y2], 'type': 'CAR' or 'BIKE', 'conf': float, 'track_id': int|None, 'sub_detections': list}, ...]
        """
        if self.vehicle_model is not None and self.is_real_model:
            try:
                return self._detect_yolo(frame)
            except Exception as e:
                print(f"[Detector] YOLO inference error, falling back to contours: {e}")
                return self._detect_cv_contours(frame)

        return self._detect_cv_contours(frame)

    @staticmethod
    def _box_iou(a, b):
        ix1 = max(a[0], b[0])
        iy1 = max(a[1], b[1])
        ix2 = min(a[2], b[2])
        iy2 = min(a[3], b[3])
        inter = max(0, ix2 - ix1) * max(0, iy2 - iy1)
        if inter <= 0:
            return 0.0
        area_a = max(1, (a[2] - a[0]) * (a[3] - a[1]))
        area_b = max(1, (b[2] - b[0]) * (b[3] - b[1]))
        return inter / float(area_a + area_b - inter)

    def _detect_yolo(self, frame):
        h_f, w_f = frame.shape[:2]
        frame_area = float(h_f * w_f)
        results = self.vehicle_model.track(
            frame,
            imgsz=480,
            conf=self.conf_thresh,
            classes=[0, 1, 2, 3, 5, 7],
            persist=True,
            tracker="botsort.yaml",
            verbose=False
        )
        raw_vehicles = []
        persons = []

        for r in results:
            for box in r.boxes:
                cls_id = int(box.cls[0])
                cls_name = r.names[cls_id].lower()
                conf = float(box.conf[0])
                x1, y1, x2, y2 = [int(v) for v in box.xyxy[0]]
                bw, bh = x2 - x1, y2 - y1
                area_ratio = (bw * bh) / frame_area
                # Reject full-frame false positives and sub-pixel noise
                if area_ratio > 0.40 or area_ratio < 0.0018 or bw > w_f * 0.65:
                    continue

                track_id = int(box.id[0]) if box.id is not None else None

                if cls_name == "person":
                    persons.append({
                        'bbox': [x1, y1, x2, y2],
                        'conf': conf,
                        'cy': (y1 + y2) / 2.0
                    })
                    continue

                vtype = None
                if any(k in cls_name for k in ['motorcycle', 'bike', 'bicycle']):
                    vtype = 'BIKE'
                elif any(k in cls_name for k in ['car', 'truck', 'bus', 'vehicle', 'van']):
                    vtype = 'CAR'

                if vtype:
                    raw_vehicles.append({
                        'bbox': [x1, y1, x2, y2],
                        'type': vtype,
                        'conf': conf,
                        'track_id': track_id,
                        'sub_detections': []
                    })

        # Cross-class NMS to avoid counting one car multiple times as car+bus+truck
        raw_vehicles.sort(key=lambda d: d['conf'], reverse=True)
        vehicles = []
        for cand in raw_vehicles:
            if any(self._box_iou(cand['bbox'], kept['bbox']) > 0.45 for kept in vehicles):
                continue
            vehicles.append(cand)

        # Associate detected persons (drivers/riders) with overlapping vehicles
        for v in vehicles:
            vx1, vy1, vx2, vy2 = v['bbox']
            pad_y = int((vy2 - vy1) * 0.25) if v['type'] == 'BIKE' else 0
            for p in persons:
                px1, py1, px2, py2 = p['bbox']
                pcx = (px1 + px2) / 2.0
                pcy = (py1 + py2) / 2.0
                if (vx1 - 15) <= pcx <= (vx2 + 15) and (vy1 - pad_y) <= pcy <= (vy2 + 10):
                    ph = py2 - py1
                    head_y2 = py1 + max(12, int(ph * 0.35))
                    v['sub_detections'].append({
                        'bbox': (px1, py1, px2, head_y2),
                        'class': 'head',
                        'conf': p['conf'],
                        'cy': (py1 + head_y2) / 2.0
                    })

        return vehicles

    def _detect_cv_contours(self, frame):
        """
        OpenCV background subtraction and morphological filtering fallback.
        """
        h, w = frame.shape[:2]
        mask = np.zeros((h, w), dtype=np.uint8)
        road_poly = np.array([
            [int(w * 0.05), h],
            [int(w * 0.95), h],
            [int(w * 0.90), int(h * 0.20)],
            [int(w * 0.10), int(h * 0.20)]
        ])
        cv2.fillPoly(mask, [road_poly], 255)

        masked_frame = cv2.bitwise_and(frame, frame, mask=mask)
        fg_mask = self.bg_subtractor.apply(masked_frame)
        _, thresh = cv2.threshold(fg_mask, 200, 255, cv2.THRESH_BINARY)

        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
        cleaned = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel, iterations=2)
        cleaned = cv2.morphologyEx(cleaned, cv2.MORPH_OPEN, kernel, iterations=1)

        contours, _ = cv2.findContours(cleaned, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        detections = []

        for cnt in contours:
            area = cv2.contourArea(cnt)
            if area < 1600:
                continue

            x, y, cw, ch = cv2.boundingRect(cnt)
            aspect = cw / float(ch + 1e-5)
            if area > 14000 or (cw > 110 and ch > 100):
                vtype = 'CAR'
                conf = 0.85
            elif ch > cw and area < 14000:
                vtype = 'BIKE'
                conf = 0.82
            else:
                vtype = 'CAR' if aspect > 1.0 else 'BIKE'
                conf = 0.80

            detections.append({
                'bbox': [x, y, x + cw, y + ch],
                'type': vtype,
                'conf': conf,
                'track_id': None,
                'sub_detections': []
            })

        return detections
