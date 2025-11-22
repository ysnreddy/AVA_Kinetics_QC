import cv2
import numpy as np
import torch
from rfdetr import RFDETRMedium
from typing import List, Dict, Tuple, Optional
import logging

logger = logging.getLogger(__name__)


class KeyframeSelector:
    def __init__(self, detection_model: RFDETRMedium, device: str, person_class_id: int = 1):
        self.model = detection_model
        self.person_class_id = person_class_id
        self.device = device

    def _z_normalize(self, scores: List[float]) -> np.ndarray:
        scores_arr = np.array(scores)
        std = np.std(scores_arr)
        if std < 1e-6: return np.zeros_like(scores_arr)
        return (scores_arr - np.mean(scores_arr)) / std

    def select_best_keyframe(
            self, video_path: str, center_window_secs: float = 4.0, candidate_stride: int = 3
    ) -> Optional[Tuple[np.ndarray, int, List[Dict]]]:

        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened(): return None

        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = cap.get(cv2.CAP_PROP_FPS) or 30
        mid = total // 2
        win = int(center_window_secs / 2 * fps)

        indices = np.arange(max(0, mid - win), min(total, mid + win), candidate_stride)
        if indices.size == 0: return None

        frames_rgb = []
        detections = []
        for idx in indices:
            cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
            ret, f = cap.read()
            if ret:
                f_rgb = cv2.cvtColor(f, cv2.COLOR_BGR2RGB)
                frames_rgb.append(f_rgb)
                detections.append(self.model.predict(f_rgb, threshold=0.5))
        cap.release()
        if not frames_rgb: return None

        scores_conf = []
        scores_motion = []
        prev = None

        for f_rgb, dets in zip(frames_rgb, detections):
            # Confidence Score
            mask = np.zeros(0, dtype=bool)
            if hasattr(dets, 'class_id') and dets.class_id is not None:
                mask = (dets.class_id == self.person_class_id)
                conf = dets.confidence[mask].sum().item() if hasattr(dets, 'confidence') and mask.any() else 0
            else:
                conf = 0
            scores_conf.append(conf)

            # Motion Score
            gray = cv2.cvtColor(f_rgb, cv2.COLOR_RGB2GRAY)
            mot = 0
            if prev is not None:
                flow = cv2.calcOpticalFlowFarneback(prev, gray, None, 0.5, 3, 15, 3, 5, 1.2, 0)
                mag = np.sqrt(flow[..., 0] ** 2 + flow[..., 1] ** 2)
                if hasattr(dets, 'xyxy') and dets.xyxy is not None and mask.any():
                    boxes = dets.xyxy[mask].astype(int)
                    for x1, y1, x2, y2 in boxes:
                        # Clamp coordinates
                        h, w = mag.shape
                        x1, y1 = max(0, x1), max(0, y1)
                        x2, y2 = min(w, x2), min(h, y2)
                        if x2 > x1 and y2 > y1:
                            mot += mag[y1:y2, x1:x2].mean()
            scores_motion.append(mot)
            prev = gray

        # Final Score
        final = (0.7 * self._z_normalize(scores_motion)) + (0.3 * self._z_normalize(scores_conf))

        # Tie Breaker (Closer to middle is better)
        dist = np.abs(indices - mid)
        tie_break = 1.0 - (dist / (total / 2))
        final += (tie_break * 1e-6)

        best_i = np.argmax(final)

        # Formatting
        final_dets = []
        best_d = detections[best_i]
        if hasattr(best_d, 'xyxy') and best_d.xyxy is not None:
            mask = (best_d.class_id == self.person_class_id)
            if mask.any():
                for i, (box, c) in enumerate(zip(best_d.xyxy[mask], best_d.confidence[mask])):
                    final_dets.append({"track_id": i + 1, "bbox": [float(x) for x in box]})

        best_img_bgr = cv2.cvtColor(frames_rgb[best_i], cv2.COLOR_RGB2BGR)
        return best_img_bgr, indices[best_i], final_dets