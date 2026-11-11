"""
BoT-SORT / ByteTrack Multi-Object Tracker Implementation
Preserves persistent BoT-SORT tracking IDs from Ultralytics when available,
and performs Kalman-filtered IoU tracking when running fallback detectors.
"""
import numpy as np


class KalmanBoxTracker:
    count = 2500  # Starting vehicle ID counter

    def __init__(self, bbox, cls_type="CAR", external_id=None):
        if external_id is not None:
            self.id = int(external_id)
        else:
            self.id = KalmanBoxTracker.count
            KalmanBoxTracker.count += 1
        self.cls_type = cls_type
        self.external_id = external_id

        self.bbox = np.array(bbox, dtype=np.float32)
        self.time_since_update = 0
        self.hits = 1
        self.age = 0

        cx = (bbox[0] + bbox[2]) / 2.0
        cy = (bbox[1] + bbox[3]) / 2.0
        w = bbox[2] - bbox[0]
        h = bbox[3] - bbox[1]
        self.state = np.array([cx, cy, w * h, w / (h + 1e-6), 0, 0, 0, 0], dtype=np.float32)

    def predict(self):
        self.state[0] += self.state[4]
        self.state[1] += self.state[5]
        self.age += 1
        self.time_since_update += 1
        return self.get_bbox()

    def update(self, bbox):
        self.time_since_update = 0
        self.hits += 1

        prev_cx, prev_cy = self.state[0], self.state[1]
        cx = (bbox[0] + bbox[2]) / 2.0
        cy = (bbox[1] + bbox[3]) / 2.0
        w = bbox[2] - bbox[0]
        h = bbox[3] - bbox[1]

        self.state[4] = 0.7 * self.state[4] + 0.3 * (cx - prev_cx)
        self.state[5] = 0.7 * self.state[5] + 0.3 * (cy - prev_cy)
        self.state[0] = cx
        self.state[1] = cy
        self.state[2] = w * h
        self.state[3] = w / (h + 1e-6)
        self.bbox = np.array(bbox, dtype=np.float32)

    def get_bbox(self):
        cx, cy, s, r = self.state[0], self.state[1], self.state[2], self.state[3]
        w = np.sqrt(max(1.0, s * r))
        h = max(1.0, s / (w + 1e-6))
        return np.array([cx - w / 2.0, cy - h / 2.0, cx + w / 2.0, cy + h / 2.0], dtype=np.float32)


def compute_iou(box1, box2):
    x1 = max(box1[0], box2[0])
    y1 = max(box1[1], box2[1])
    x2 = min(box1[2], box2[2])
    y2 = min(box1[3], box2[3])

    inter = max(0.0, x2 - x1) * max(0.0, y2 - y1)
    area1 = (box1[2] - box1[0]) * (box1[3] - box1[1])
    area2 = (box2[2] - box2[0]) * (box2[3] - box2[1])
    union = area1 + area2 - inter
    return inter / (union + 1e-6)


class ByteTracker:
    def __init__(self, max_lost_frames=20, iou_thresh=0.25):
        self.trackers = []
        self.ext_trackers = {}  # ext_id -> KalmanBoxTracker
        self.max_lost_frames = max_lost_frames
        self.iou_thresh = iou_thresh

    def reset(self):
        self.trackers = []
        self.ext_trackers = {}

    def predict_step(self):
        """Advance active Kalman trackers by one display frame without resetting hits (smooth 30 FPS interpolation)."""
        results = []
        active_ext = self.ext_trackers if self.ext_trackers else None
        if active_ext is not None:
            dead_ids = []
            for eid, trk in active_ext.items():
                trk_box = trk.predict()
                if trk.time_since_update > self.max_lost_frames:
                    dead_ids.append(eid)
                    continue
                results.append({
                    'id': trk.id,
                    'type': trk.cls_type,
                    'bbox': trk_box,
                    'sub_detections': getattr(trk, 'last_sub_dets', None)
                })
            for eid in dead_ids:
                del active_ext[eid]
            return results

        for trk in self.trackers:
            trk_box = trk.predict()
            if trk.time_since_update <= self.max_lost_frames:
                results.append({
                    'id': trk.id,
                    'type': trk.cls_type,
                    'bbox': trk_box,
                    'sub_detections': getattr(trk, 'last_sub_dets', None)
                })
        return results

    def update(self, detections):
        # Unified external BoT-SORT path (maintains Kalman velocity for 30 FPS interpolation)
        ext_dets = [d for d in detections if d.get('track_id') is not None]
        if ext_dets:
            seen_ids = set()
            results = []
            for d in ext_dets:
                ext_id = 2500 + int(d['track_id'])
                seen_ids.add(ext_id)
                if ext_id not in self.ext_trackers:
                    trk = KalmanBoxTracker(d['bbox'], d['type'], external_id=ext_id)
                    self.ext_trackers[ext_id] = trk
                else:
                    trk = self.ext_trackers[ext_id]
                    trk.update(d['bbox'])
                    trk.cls_type = d['type']
                trk.last_sub_dets = d.get('sub_detections')
                results.append({
                    'id': ext_id,
                    'type': d['type'],
                    'bbox': np.array(d['bbox'], dtype=np.float32),
                    'sub_detections': d.get('sub_detections')
                })
            # Age stale tracks slightly without erasing brief 1-2 frame occlusions
            for eid in list(self.ext_trackers.keys()):
                if eid not in seen_ids:
                    self.ext_trackers[eid].predict()
                    if self.ext_trackers[eid].time_since_update > self.max_lost_frames:
                        del self.ext_trackers[eid]
            return results

        for trk in self.trackers:
            trk.predict()

        if len(detections) == 0:
            self.trackers = [t for t in self.trackers if t.time_since_update <= self.max_lost_frames]
            return []

        matched_det_idx = set()
        if len(self.trackers) > 0:
            iou_matrix = np.zeros((len(self.trackers), len(detections)), dtype=np.float32)
            for t_idx, trk in enumerate(self.trackers):
                trk_box = trk.get_bbox()
                for d_idx, det in enumerate(detections):
                    bonus = 0.15 if trk.cls_type == det['type'] else -0.30
                    iou_matrix[t_idx, d_idx] = compute_iou(trk_box, det['bbox']) + bonus

            while True:
                max_iou = np.max(iou_matrix)
                if max_iou < self.iou_thresh:
                    break
                t_idx, d_idx = np.unravel_index(np.argmax(iou_matrix), iou_matrix.shape)
                matched_det_idx.add(d_idx)
                self.trackers[t_idx].update(detections[d_idx]['bbox'])
                self.trackers[t_idx].cls_type = detections[d_idx]['type']
                iou_matrix[t_idx, :] = -1
                iou_matrix[:, d_idx] = -1

        for d_idx, det in enumerate(detections):
            if d_idx not in matched_det_idx:
                if det['bbox'][1] < 450:
                    self.trackers.append(KalmanBoxTracker(det['bbox'], det['type']))

        self.trackers = [t for t in self.trackers if t.time_since_update <= self.max_lost_frames]

        results = []
        for trk in self.trackers:
            sub_dets = None
            trk_box = trk.get_bbox()
            best_iou = 0
            for det in detections:
                iou = compute_iou(trk_box, det['bbox'])
                if iou > best_iou:
                    best_iou = iou
                    sub_dets = det.get('sub_detections')

            results.append({
                'id': trk.id,
                'type': trk.cls_type,
                'bbox': trk_box,
                'sub_detections': sub_dets
            })
        return results
