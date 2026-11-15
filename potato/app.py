"""Local potato server: the Chrome extension sends uploaded images here when the popup is set to Potato.

Every face in the photo (just the face) becomes a potato wearing that person's own eyes, nose
and mouth. Runs on port 8766, so it can run next to everyone_is_you/ (port 8765).
"""
import base64
import io
import math
import threading
from datetime import datetime
from pathlib import Path

from flask import Flask, jsonify, request, send_file
from markupsafe import escape
from PIL import Image, ImageOps
from ultralytics import YOLO

import face

HERE = Path(__file__).parent
ASSETS = HERE / "assets"
OUTPUT = HERE / "output"

FACE_STICKER = "potato.png"  # or "potato_sprouts.png"
POSE_CONFIDENCE = 0.25  # low: half-hidden people in group selfies still count
POSE_SIZE = 960  # bigger than YOLO's default 640, so small faces in group photos are found
KEYPOINT_CONFIDENCE = 0.4

app = Flask(__name__)
pose_model = YOLO(HERE / "yolo11n-pose.pt")  # downloaded (~6 MB) on first run
potato = Image.open(ASSETS / FACE_STICKER).convert("RGBA")
lock = threading.Lock()  # one photo at a time: the models don't share well
OUTPUT.mkdir(exist_ok=True)


def potatoify(img: Image.Image) -> tuple[Image.Image, int]:
    """The photo with a potato on every face, and how many faces that was."""
    img = ImageOps.exif_transpose(img).convert("RGB")
    faces = find_faces(img)
    # Make every potato before pasting any: a potato can cover the edge of the next face.
    spud = face.tone_like(potato, img)
    potatoes = [face.potato_face(img, f, spud) for f in faces]
    # Smallest first: bigger faces are usually nearer the camera, so their potatoes go on top.
    for _, (layer, corner) in sorted(zip(faces, potatoes), key=lambda pair: pair[0].width):
        img.paste(layer, corner, layer)
    return img, len(faces)


def find_faces(img: Image.Image) -> list[face.Face]:
    """Every face in the photo, checked by MediaPipe."""
    # The pose model is unreliable on upside-down people (lying down, handstands), so it
    # looks twice: upright faces in the photo as-is, upside-down ones in the photo flipped.
    w, h = img.size
    upright = [f for f in face_points(img) if abs(f[3]) <= 90]
    flipped = [(w - x, h - y, width, tilt + 180)
               for x, y, width, tilt in face_points(img.rotate(180)) if abs(tilt) <= 90]
    # It also misses some faces outright (heads half behind someone): MediaPipe looks too.
    guesses = upright + flipped + face.more_guesses(img)
    # Guesses can be upside down, merge two heads, or land on an arm: MediaPipe checks each
    # one, fixes where it is and which way up, or drops it.
    checked = [found for guess in guesses if (found := face.look_closer(img, *guess))]
    # The same head is found several times. Keep one: the right way up if any version of it is
    # (MediaPipe now and then reads a face upside down), else the biggest.
    faces = []
    for f in sorted(checked, key=lambda f: (abs(f.tilt) > 90, -f.width)):
        if all(math.dist((f.x, f.y), (kept.x, kept.y)) > kept.width / 2 for kept in faces):
            faces.append(f)
    return faces


def face_points(img: Image.Image) -> list[tuple[float, float, float, float]]:
    """(x, y, width, tilt in degrees) of each face, from the pose model's nose/eye/ear points."""
    result = pose_model(img, conf=POSE_CONFIDENCE, imgsz=POSE_SIZE, verbose=False)[0]
    if result.keypoints is None:
        return []
    faces = []
    for points in result.keypoints.data.tolist():
        nose, eye_l, eye_r, ear_l, ear_r = (
            (x, y) if c > KEYPOINT_CONFIDENCE else None for x, y, c in points[:5]
        )
        seen = [p for p in (nose, eye_l, eye_r, ear_l, ear_r) if p]
        if len(seen) < 2:
            continue  # facing away or too blurry
        if ear_l and ear_r:
            width = math.dist(ear_l, ear_r)
        elif eye_l and eye_r:
            width = math.dist(eye_l, eye_r) * 2.2
        else:
            width = max(math.dist(a, b) for a in seen for b in seen) * 1.8
        # COCO's "left eye" is the person's left, so it's on the right of a front-facing photo.
        level = (eye_r, eye_l) if eye_l and eye_r else (ear_r, ear_l) if ear_l and ear_r else None
        tilt = math.degrees(math.atan2(level[1][1] - level[0][1], level[1][0] - level[0][0])) if level else 0
        middle = [p for p in (nose, eye_l, eye_r) if p] or seen
        x, y = sum(p[0] for p in middle) / len(middle), sum(p[1] for p in middle) / len(middle)
        faces.append((x, y, width, tilt))
    return faces


@app.post("/potatoify")
def potatoify_endpoint():
    _, b64 = request.get_json()["image"].split(",", 1)
    with lock:
        img, faces = potatoify(Image.open(io.BytesIO(base64.b64decode(b64))))
    img.save(OUTPUT / f"{datetime.now():%Y%m%d-%H%M%S-%f}_result.jpg", quality=92)
    out = io.BytesIO()
    img.save(out, "JPEG", quality=92)
    print(f"potatoes: {faces}")
    return jsonify(
        image="data:image/jpeg;base64," + base64.b64encode(out.getvalue()).decode(),
        replaced=["face"] * faces,
        face=False,  # the extension says "(with your face)" when true; no webcam here
    )


@app.get("/test")
def test_page():
    return send_file(HERE / "test_page.html")


@app.post("/upload")
def upload():
    """Stand-in for a real site: shows exactly what the browser uploaded."""
    imgs = "".join(
        f'<p>{escape(f.filename)}</p>'
        f'<img src="data:{f.mimetype};base64,{base64.b64encode(f.read()).decode()}" style="max-width:100%">'
        for f in request.files.getlist("photo")
        if f.filename
    )
    return f'<!doctype html><meta charset="utf-8"><title>Uploaded</title>{imgs}<p><a href="/test">back</a></p>'


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8766)
