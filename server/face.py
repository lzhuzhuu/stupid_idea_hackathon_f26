"""Snaps the webcam and swaps the user's face onto every face in a photo.

Same recipe as Deep-Live-Cam (https://github.com/hacksider/Deep-Live-Cam): insightface finds
the faces and its inswapper model does the swap.
"""
import time
import urllib.request
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np
from cv2_enumerate_cameras import enumerate_cameras
from cv2_enumerate_cameras.camera_info import CameraInfo
from insightface.app import FaceAnalysis
from insightface.app.common import Face
from insightface.model_zoo import get_model
from PIL import Image

HERE = Path(__file__).parent
SWAPPER = HERE / "models" / "inswapper_128_fp16.onnx"
SWAPPER_URL = "https://huggingface.co/hacksider/deep-live-cam/resolve/main/inswapper_128_fp16.onnx"
# Point this at a photo to swap in that face instead of the webcam's (handy for testing).
SOURCE_PHOTO: Path | None = None
WARMUP_FRAMES = 20  # the first webcam frames are dark while auto-exposure settles
FACE_TTL = 10  # seconds; one webcam shot covers a whole multi-photo upload
# Camera names to skip: a nearby iPhone shows up as a camera too (Continuity Camera).
PHONE_CAMERA_WORDS = ("iphone", "ipad", "desk view")
PROVIDERS = ["CPUExecutionProvider"]

if not SWAPPER.exists():
    SWAPPER.parent.mkdir(exist_ok=True)
    urllib.request.urlretrieve(SWAPPER_URL, SWAPPER)
# buffalo_l (~280 MB) is downloaded to ~/.insightface on first run.
analyser = FaceAnalysis(name="buffalo_l", allowed_modules=["detection", "recognition"], providers=PROVIDERS)
analyser.prepare(ctx_id=0, det_size=(640, 640))
swapper = get_model(str(SWAPPER), providers=PROVIDERS)
_cache: tuple[float, Face | None] = (0.0, None)


def current_face(save_dir: Path) -> Face | None:
    """The face to swap in: from SOURCE_PHOTO, or a fresh webcam shot. None if there's no face."""
    global _cache
    if SOURCE_PHOTO:
        return biggest_face(Image.open(SOURCE_PHOTO))
    taken_at, source = _cache
    if time.time() - taken_at > FACE_TTL:
        source = None
        camera = computer_camera()
        shot = snap_webcam(camera) if camera is not None else None
        if shot:
            shot.save(save_dir / f"{datetime.now():%Y%m%d-%H%M%S-%f}_webcam.jpg")
            source = biggest_face(shot)
        print("webcam:", "no computer camera" if shot is None else "face found" if source else "no face")
        _cache = (time.time(), source)
    return source


def computer_camera() -> CameraInfo | None:
    """The computer's own camera, never a phone's."""
    return next(
        (cam for cam in enumerate_cameras(cv2.CAP_AVFOUNDATION)
         if not any(word in cam.name.lower() for word in PHONE_CAMERA_WORDS)),
        None,
    )


def snap_webcam(camera: CameraInfo) -> Image.Image | None:
    cam = cv2.VideoCapture(camera.index, camera.backend)
    try:
        ok, frame = False, None
        for _ in range(WARMUP_FRAMES):
            ok, frame = cam.read()
        return Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)) if ok else None
    finally:
        cam.release()


def biggest_face(photo: Image.Image) -> Face | None:
    faces = analyser.get(to_bgr(photo))
    return max(faces, key=lambda f: (f.bbox[2] - f.bbox[0]) * (f.bbox[3] - f.bbox[1]), default=None)


def swap_faces(img: Image.Image, source: Face) -> tuple[Image.Image, int]:
    """Put the source face on every face in the photo. Returns the result and how many were swapped."""
    frame = to_bgr(img)
    targets = analyser.get(frame)
    for target in targets:
        frame = swapper.get(frame, target, source, paste_back=True)
    return Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)), len(targets)


def to_bgr(photo: Image.Image) -> np.ndarray:
    return cv2.cvtColor(np.asarray(photo.convert("RGB")), cv2.COLOR_RGB2BGR)
