"""Snaps the webcam and cuts out the user's eyes and mouth to stick on the stickers."""
import time
import urllib.request
from datetime import datetime
from pathlib import Path

import cv2
import mediapipe as mp
import numpy as np
from mediapipe.tasks.python import BaseOptions, vision
from PIL import Image, ImageDraw, ImageFilter

HERE = Path(__file__).parent
MODEL = HERE / "models" / "face_landmarker.task"
MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/"
    "face_landmarker/face_landmarker/float16/1/face_landmarker.task"
)

# MediaPipe face-mesh landmark ids, named by the side of the photo they land on.
# Eyes include the eyebrows, which carry most of the expression.
PARTS = {
    "eye_left": [33, 7, 163, 144, 145, 153, 154, 155, 133, 173, 157, 158, 159, 160, 161, 246,
                 70, 63, 105, 66, 107],
    "eye_right": [362, 382, 381, 380, 374, 373, 390, 249, 263, 466, 388, 387, 386, 385, 384, 398,
                  300, 293, 334, 296, 336],
    "mouth": [61, 146, 91, 181, 84, 17, 314, 405, 321, 375, 291, 409, 270, 269, 267, 0, 37, 39, 40, 185],
}
PART_PADDING = 0.35
# Where each part goes on a sticker: (x offset, y offset, width) in units of the
# radius of the biggest circle that fits inside the sticker.
LAYOUT = {"eye_left": (-0.42, -0.3, 0.7), "eye_right": (0.42, -0.3, 0.7), "mouth": (0, 0.45, 0.9)}
WARMUP_FRAMES = 20  # the first webcam frames are dark while auto-exposure settles
FACE_TTL = 10  # seconds; one webcam shot covers a whole multi-photo upload
# OpenCV camera indexes to try. A nearby iPhone (Continuity Camera) can take index 0,
# so we try each and move the first one that sees a face to the front.
camera_order = [0, 1, 2]

if not MODEL.exists():
    MODEL.parent.mkdir(exist_ok=True)
    urllib.request.urlretrieve(MODEL_URL, MODEL)
landmarker = vision.FaceLandmarker.create_from_options(
    vision.FaceLandmarkerOptions(base_options=BaseOptions(model_asset_path=str(MODEL)), num_faces=1)
)
_cache: tuple[float, dict[str, Image.Image] | None] = (0.0, None)


def current_face(save_dir: Path) -> dict[str, Image.Image] | None:
    """Eye and mouth patches from a fresh webcam shot, or None if there's no camera or face."""
    global _cache
    taken_at, parts = _cache
    if time.time() - taken_at > FACE_TTL:
        parts = None
        for index in list(camera_order):
            shot = snap_webcam(index)
            if shot is None:
                continue
            shot.save(save_dir / f"{datetime.now():%Y%m%d-%H%M%S-%f}_webcam{index}.jpg")
            parts = cut_parts(shot)
            if parts:
                camera_order.remove(index)
                camera_order.insert(0, index)
                break
        print("webcam:", f"face found on camera {camera_order[0]}" if parts else "no face on any camera")
        _cache = (time.time(), parts)
    return parts


def snap_webcam(index: int) -> Image.Image | None:
    cam = cv2.VideoCapture(index)
    try:
        ok, frame = False, None
        for _ in range(WARMUP_FRAMES):
            ok, frame = cam.read()
        return Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)) if ok else None
    finally:
        cam.release()


def cut_parts(photo: Image.Image) -> dict[str, Image.Image] | None:
    result = landmarker.detect(mp.Image(image_format=mp.ImageFormat.SRGB, data=np.asarray(photo)))
    if not result.face_landmarks:
        return None
    marks = result.face_landmarks[0]
    parts = {}
    for name, ids in PARTS.items():
        xs = [marks[i].x * photo.width for i in ids]
        ys = [marks[i].y * photo.height for i in ids]
        pad_w, pad_h = (max(xs) - min(xs)) * PART_PADDING, (max(ys) - min(ys)) * PART_PADDING
        box = (min(xs) - pad_w, min(ys) - pad_h, max(xs) + pad_w, max(ys) + pad_h)
        patch = photo.crop(tuple(round(v) for v in box)).convert("RGBA")
        patch.putalpha(oval_mask(patch.size))
        parts[name] = patch
    return parts


def oval_mask(size: tuple[int, int]) -> Image.Image:
    w, h = size
    blur = max(1, min(w, h) // 10)
    inset = 2 * blur  # keep the blurred edge inside the patch so no rectangle shows
    mask = Image.new("L", size, 0)
    ImageDraw.Draw(mask).ellipse((inset, inset, w - 1 - inset, h - 1 - inset), fill=255)
    return mask.filter(ImageFilter.GaussianBlur(blur))


def face_spot(sticker: Image.Image) -> tuple[float, float, float]:
    """Center and radius of the biggest circle that fits inside the sticker."""
    inside = (np.asarray(sticker.getchannel("A")) > 128).astype(np.uint8)
    _, radius, _, (cx, cy) = cv2.minMaxLoc(cv2.distanceTransform(inside, cv2.DIST_L2, 5))
    return cx, cy, radius


def stick_on(sticker: Image.Image, parts: dict[str, Image.Image]) -> None:
    """Paste the eyes and mouth onto the thickest part of the sticker, in place."""
    cx, cy, radius = face_spot(sticker)
    for name, (dx, dy, width) in LAYOUT.items():
        w = max(1, round(width * radius))
        part = parts[name].resize((w, max(1, round(w * parts[name].height / parts[name].width))))
        x = round(cx + dx * radius - part.width / 2)
        y = round(cy + dy * radius - part.height / 2)
        sticker.alpha_composite(part, (max(0, x), max(0, y)))
