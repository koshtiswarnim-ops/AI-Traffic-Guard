"""
Seatbelt vs. No-Seatbelt Evaluator for Passenger Cars
Extracts front windshield/cabin ROI and detects diagonal seatbelt strap presence.
"""
import cv2
import numpy as np

class SeatbeltEvaluator:
    def __init__(self, model_path=None, conf_threshold=0.50):
        self.model_path = model_path
        self.conf_threshold = conf_threshold
        self.custom_model = None

        if model_path:
            self._load_model()

    def _load_model(self):
        try:
            from ultralytics import YOLO
            self.custom_model = YOLO(self.model_path)
            print(f"[SeatbeltEvaluator] Loaded YOLO model from {self.model_path}")
        except Exception as e:
            print(f"[SeatbeltEvaluator] Model load info: {e}")
            self.custom_model = None

    def evaluate_car(self, frame, car_bbox, sub_detections=None):
        cx1, cy1, cx2, cy2 = [int(v) for v in car_bbox]
        h_frame, w_frame = frame.shape[:2]
        cx1, cy1 = max(0, cx1), max(0, cy1)
        cx2, cy2 = min(w_frame, cx2), min(h_frame, cy2)

        car_crop = frame[cy1:cy2, cx1:cx2]
        if car_crop.size == 0:
            return {
                'status': 'SEATBELT',
                'confidence': 0.70,
                'cabin_bbox': None,
                'cabin_crop': None
            }

        # Windshield / Cabin ROI extraction (top 20% to 65% of vehicle)
        ch, cw = car_crop.shape[:2]
        windshield_y1 = int(ch * 0.20)
        windshield_y2 = int(ch * 0.65)
        windshield_x1 = int(cw * 0.15)
        windshield_x2 = int(cw * 0.85)

        cabin_crop = car_crop[windshield_y1:windshield_y2, windshield_x1:windshield_x2]
        cabin_global_bbox = (
            cx1 + windshield_x1,
            cy1 + windshield_y1,
            cx1 + windshield_x2,
            cy1 + windshield_y2
        )

        # Case 1: Custom YOLO model
        if self.custom_model is not None and cabin_crop.size > 0:
            results = self.custom_model(cabin_crop, conf=self.conf_threshold, verbose=False)
            has_seatbelt = False
            max_conf = 0.50
            for r in results:
                for box in r.boxes:
                    cls_id = int(box.cls[0])
                    cls_name = r.names[cls_id].lower()
                    conf = float(box.conf[0])
                    if 'seatbelt' in cls_name and 'no' not in cls_name:
                        has_seatbelt = True
                        max_conf = max(max_conf, conf)
                    elif 'no' in cls_name and 'seatbelt' in cls_name:
                        has_seatbelt = False
                        max_conf = max(max_conf, conf)
            status = 'SEATBELT' if has_seatbelt else 'NO SEATBELT'
            return {
                'status': status,
                'confidence': max_conf,
                'cabin_bbox': cabin_global_bbox,
                'cabin_crop': cabin_crop
            }

        # Case 2: Sub-detections supplied
        if sub_detections:
            for d in sub_detections:
                if d.get('class') in ['seatbelt', 'no_seatbelt']:
                    status = 'SEATBELT' if d['class'] == 'seatbelt' else 'NO SEATBELT'
                    return {
                        'status': status,
                        'confidence': d.get('conf', 0.85),
                        'cabin_bbox': cabin_global_bbox,
                        'cabin_crop': cabin_crop
                    }

        # Case 3: Computer Vision Diagonal Edge Strap Analysis
        return self._heuristic_seatbelt_detection(cabin_crop, cabin_global_bbox)

    def _heuristic_seatbelt_detection(self, cabin_crop, cabin_global_bbox):
        if cabin_crop is None or cabin_crop.size == 0:
            return {
                'status': 'SEATBELT',
                'confidence': 0.75,
                'cabin_bbox': cabin_global_bbox,
                'cabin_crop': None
            }

        ch, cw = cabin_crop.shape[:2]
        # Focus on interior driver/passenger chest area (avoid side A-pillar frames & roof edge)
        inner = cabin_crop[int(ch * 0.28):max(int(ch * 0.30) + 4, int(ch * 0.88)),
                           int(cw * 0.22):max(int(cw * 0.24) + 4, int(cw * 0.78))]
        if inner.size == 0:
            inner = cabin_crop

        gray = cv2.cvtColor(inner, cv2.COLOR_BGR2GRAY)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(6, 6))
        enhanced = clahe.apply(gray)

        edges = cv2.Canny(enhanced, 70, 180)
        min_len = max(14, int(inner.shape[0] * 0.32))
        lines = cv2.HoughLinesP(edges, 1, np.pi / 180, threshold=28, minLineLength=min_len, maxLineGap=8)

        diagonal_lines_count = 0
        if lines is not None:
            for line in lines:
                x1, y1, x2, y2 = line[0]
                dx = x2 - x1
                dy = y2 - y1
                angle = abs(np.degrees(np.arctan2(dy, dx)))
                if 32 <= angle <= 62:
                    diagonal_lines_count += 1

        has_seatbelt = diagonal_lines_count >= 2
        conf = 0.86 if has_seatbelt else 0.82
        status = 'SEATBELT' if has_seatbelt else 'NO SEATBELT'

        return {
            'status': status,
            'confidence': conf,
            'cabin_bbox': cabin_global_bbox,
            'cabin_crop': cabin_crop
        }
