"""
Helmet vs. No-Helmet Evaluator for Motorcycles
Handles Driver vs. Passenger disambiguation so passenger detection
does not affect the driver's compliance result.
"""
import cv2
import numpy as np

class HelmetEvaluator:
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
            print(f"[HelmetEvaluator] Loaded YOLO model from {self.model_path}")
        except Exception as e:
            print(f"[HelmetEvaluator] Model load info: {e}")
            self.custom_model = None

    def evaluate_bike(self, frame, bike_bbox, sub_detections=None):
        """
        Evaluate a motorcycle bounding box for helmet compliance.
        bike_bbox: (x1, y1, x2, y2)
        """
        bx1, by1, bx2, by2 = [int(v) for v in bike_bbox]
        h_frame, w_frame = frame.shape[:2]
        bx1, by1 = max(0, bx1), max(0, by1)
        bx2, by2 = min(w_frame, bx2), min(h_frame, by2)

        bike_crop = frame[by1:by2, bx1:bx2]
        if bike_crop.size == 0:
            return {
                'status': 'HELMET',
                'confidence': 0.75,
                'head_bbox': None,
                'driver_crop': None,
                'passenger_results': []
            }

        # Case 1: Custom YOLO model loaded
        if self.custom_model is not None:
            results = self.custom_model(bike_crop, conf=self.conf_threshold, verbose=False)
            candidates = []
            for r in results:
                for box in r.boxes:
                    cls_id = int(box.cls[0])
                    cls_name = r.names[cls_id].lower()
                    conf = float(box.conf[0])
                    lx1, ly1, lx2, ly2 = [int(v) for v in box.xyxy[0]]
                    gx1, gy1, gx2, gy2 = bx1 + lx1, by1 + ly1, bx1 + lx2, by1 + ly2
                    candidates.append({
                        'bbox': (gx1, gy1, gx2, gy2),
                        'class': 'helmet' if 'helmet' in cls_name and 'no' not in cls_name else 'no_helmet',
                        'conf': conf,
                        'cy': (gy1 + gy2) / 2.0
                    })
            if candidates:
                return self._disambiguate_driver(candidates, bike_bbox, frame)

        # Case 2: Sub-detections supplied
        if sub_detections:
            return self._disambiguate_driver(sub_detections, bike_bbox, frame)

        # Case 3: Computer Vision Feature Extractor (Edge/Color/Contour on rider head region)
        return self._heuristic_head_evaluation(bike_crop, bx1, by1, bx2, by2, frame)

    def _disambiguate_driver(self, candidates, bike_bbox, frame):
        """
        Disambiguate Driver vs Passenger:
        In oncoming traffic heading down, the driver is positioned in FRONT (lower/central relative to handlebars).
        We sort candidates by positioning and evaluate the DRIVER.
        """
        if not candidates:
            return {
                'status': 'HELMET',
                'confidence': 0.75,
                'head_bbox': None,
                'driver_crop': None,
                'passenger_results': []
            }

        candidates_sorted = sorted(candidates, key=lambda c: c.get('cy', c['bbox'][3]), reverse=True)
        driver = candidates_sorted[0]
        passengers = candidates_sorted[1:] if len(candidates_sorted) > 1 else []

        hx1, hy1, hx2, hy2 = [int(v) for v in driver['bbox']]
        hx1, hy1 = max(0, hx1), max(0, hy1)
        hx2, hy2 = min(frame.shape[1], hx2), min(frame.shape[0], hy2)
        driver_crop = frame[hy1:hy2, hx1:hx2]

        if driver.get('class') in ('helmet', 'no_helmet'):
            status = 'HELMET' if driver['class'] == 'helmet' else 'NO HELMET'
            conf = driver.get('conf', 0.85)
        elif driver_crop.size > 0:
            # Evaluate isolated driver head crop
            status, conf = self._classify_head_crop(driver_crop)
        else:
            status, conf = 'HELMET', 0.75

        return {
            'status': status,
            'confidence': conf,
            'head_bbox': (hx1, hy1, hx2, hy2),
            'driver_crop': driver_crop if driver_crop.size > 0 else None,
            'passenger_results': passengers
        }

    def _classify_head_crop(self, head_crop):
        gray = cv2.cvtColor(head_crop, cv2.COLOR_BGR2GRAY)
        blur = cv2.GaussianBlur(gray, (5, 5), 0)
        edges = cv2.Canny(blur, 50, 150)
        edge_density = np.sum(edges > 0) / (edges.size + 1e-5)

        hsv = cv2.cvtColor(head_crop, cv2.COLOR_BGR2HSV)
        sat = hsv[:, :, 1]
        val = hsv[:, :, 2]
        has_color_or_shine = (np.mean(val) > 90 and np.std(val) > 40) or np.mean(sat) > 50

        is_helmet = has_color_or_shine and edge_density < 0.22
        conf = 0.88 if is_helmet else 0.84
        return ('HELMET' if is_helmet else 'NO HELMET'), conf

    def _heuristic_head_evaluation(self, bike_crop, bx1, by1, bx2, by2, frame):
        bh, bw = bike_crop.shape[:2]
        head_roi_h = int(bh * 0.38)
        head_roi_w = int(bw * 0.60)
        start_x = int(bw * 0.20)

        head_crop = bike_crop[0:head_roi_h, start_x:start_x + head_roi_w]
        if head_crop.size == 0:
            return {'status': 'HELMET', 'confidence': 0.75, 'head_bbox': None, 'driver_crop': None, 'passenger_results': []}

        status, conf = self._classify_head_crop(head_crop)

        head_box = (
            bx1 + start_x,
            by1,
            bx1 + start_x + head_roi_w,
            by1 + head_roi_h
        )

        return {
            'status': status,
            'confidence': conf,
            'head_bbox': head_box,
            'driver_crop': head_crop,
            'passenger_results': []
        }
