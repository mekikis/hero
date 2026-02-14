from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Optional, Tuple

import cv2
import numpy as np


def gstreamer_pipeline(
    sensor_id: int = 0,
    capture_width: int = 1920,
    capture_height: int = 1080,
    display_width: int = 960,
    display_height: int = 540,
    framerate: int = 30,
    flip_method: int = 2,
) -> str:
    # Matches JetsonHacks CSI-Camera pipeline (known-good)
    return (
        "nvarguscamerasrc sensor-id=%d ! "
        "video/x-raw(memory:NVMM), width=(int)%d, height=(int)%d, framerate=(fraction)%d/1 ! "
        "nvvidconv flip-method=%d ! "
        "video/x-raw, width=(int)%d, height=(int)%d, format=(string)BGRx ! "
        "videoconvert ! "
        "video/x-raw, format=(string)BGR ! appsink drop=1"
        % (
            sensor_id,
            capture_width,
            capture_height,
            framerate,
            flip_method,
            display_width,
            display_height,
        )
    )


@dataclass
class Frame:
    frame_id: int
    t_ns: int
    bgr: np.ndarray
    fps_est: float


class VideoSourceCSI:
    def __init__(
        self,
        sensor_id: int = 0,
        capture_width: int = 1920,
        capture_height: int = 1080,
        display_width: int = 960,
        display_height: int = 540,
        framerate: int = 30,
        flip_method: int = 2,
    ) -> None:
        self.pipeline = gstreamer_pipeline(
            sensor_id=sensor_id,
            capture_width=capture_width,
            capture_height=capture_height,
            display_width=display_width,
            display_height=display_height,
            framerate=framerate,
            flip_method=flip_method,
        )
        self.cap = cv2.VideoCapture(self.pipeline, cv2.CAP_GSTREAMER)
        if not self.cap.isOpened():
            raise RuntimeError(
                "Unable to open CSI camera via GStreamer.\n"
                f"Pipeline:\n{self.pipeline}\n"
                "Tip: test by running CSI-Camera/simple_camera.py"
            )

        self._frame_id = 0
        self._t0 = time.time()
        self._n = 0
        self._fps_est = 0.0

    def read(self) -> Optional[Frame]:
        ok, frame = self.cap.read()
        if not ok or frame is None:
            return None

        self._frame_id += 1
        self._n += 1
        now = time.time()
        dt = now - self._t0
        if dt >= 0.5:  # update twice a second
            self._fps_est = self._n / dt
            self._t0 = now
            self._n = 0

        return Frame(
            frame_id=self._frame_id,
            t_ns=time.time_ns(),
            bgr=frame,
            fps_est=self._fps_est,
        )

    def close(self) -> None:
        try:
            self.cap.release()
        finally:
            cv2.destroyAllWindows()
