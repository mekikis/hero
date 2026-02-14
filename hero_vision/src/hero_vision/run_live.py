from __future__ import annotations

import cv2

from hero_vision.video_source import VideoSourceCSI


def main() -> None:
    window = "Hero Vision - Live"
    src = VideoSourceCSI(
        sensor_id=0,
        capture_width=1920,
        capture_height=1080,
        display_width=960,
        display_height=540,
        framerate=30,
        flip_method=2,
    )

    try:
        cv2.namedWindow(window, cv2.WINDOW_AUTOSIZE)

        while True:
            fr = src.read()
            if fr is None:
                print("Frame read failed.")
                break

            # HUD
            cv2.putText(
                fr.bgr,
                f"frame={fr.frame_id}  fps~{fr.fps_est:.1f}",
                (15, 35),
                cv2.FONT_HERSHEY_SIMPLEX,
                1.0,
                (255, 255, 255),
                2,
            )

            cv2.imshow(window, fr.bgr)
            key = cv2.waitKey(1) & 0xFF
            if key in (27, ord("q")):
                break

    finally:
        src.close()


if __name__ == "__main__":
    main()
