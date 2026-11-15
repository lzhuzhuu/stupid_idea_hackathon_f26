"""Local potato server: the Chrome extension sends every uploaded image here."""
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

# Every face gets this sticker, like a face filter.
FACE_STICKER = "potato.png"
FACE_SIZE = 0.6  # radius of the potato's round middle, relative to the face width
# COCO class name -> sticker that covers the whole object. Edit this to change what becomes what.
REPLACEMENTS = {
    "cup": "bubble_tea.png",
    "bottle": "juice_box.png",
    "wine glass": "baby_bottle.png",
}
CONFIDENCE = 0.35
POSE_CONFIDENCE = 0.25  # lower than objects: half-hidden people in group selfies still count
POSE_SIZE = 960  # bigger than YOLO's default 640, so small faces in group photos are found
KEYPOINT_CONFIDENCE = 0.4
PADDING = 0.15  # grow each object box so the sticker fully covers it

app = Flask(__name__)
model = YOLO(HERE / "yolo11n.pt")  # both models are downloaded (~6 MB each) on first run
pose_model = YOLO(HERE / "yolo11n-pose.pt")
stickers = {name: Image.open(ASSETS / file).convert("RGBA") for name, file in REPLACEMENTS.items()}
potato = Image.open(ASSETS / FACE_STICKER).convert("RGBA")
potato_spot = face.face_spot(potato)
lock = threading.Lock()  # one photo at a time: the webcam and the models don't share well
OUTPUT.mkdir(exist_ok=True)


def potatoify(img: Image.Image, parts: dict[str, Image.Image] | None) -> tuple[Image.Image, list[str]]:
    img = ImageOps.exif_transpose(img).convert("RGB")
    objects, faces = find_objects(img), find_faces(img)
    for (x1, y1, x2, y2), name in objects:
        sticker = stickers[name].resize((max(1, round(x2 - x1)), max(1, round(y2 - y1))))
        if parts:
            face.stick_on(sticker, parts)
        img.paste(sticker, (round(x1), round(y1)), sticker)
    for x, y, width, tilt in faces:
        put_potato(img, x, y, width, tilt, parts)
    return img, [name for _, name in objects] + ["face"] * len(faces)


def find_objects(img: Image.Image) -> list[tuple[tuple[float, ...], str]]:
    result = model(img, conf=CONFIDENCE, verbose=False)[0]
    hits = []
    for (x1, y1, x2, y2), cls in zip(result.boxes.xyxy.tolist(), result.boxes.cls.tolist()):
        if result.names[int(cls)] in REPLACEMENTS:
            pad_w, pad_h = (x2 - x1) * PADDING, (y2 - y1) * PADDING
            hits.append(((x1 - pad_w, y1 - pad_h, x2 + pad_w, y2 + pad_h), result.names[int(cls)]))
    # Biggest first, so smaller things on top stay visible.
    hits.sort(key=lambda hit: (hit[0][2] - hit[0][0]) * (hit[0][3] - hit[0][1]), reverse=True)
    return hits


def find_faces(img: Image.Image) -> list[tuple[float, float, float, float]]:
    # The pose model is unreliable on upside-down people (lying down, handstands), so it
    # looks twice: upright faces in the photo as-is, upside-down ones in the photo flipped.
    w, h = img.size
    upright = [f for f in face_points(img) if abs(f[3]) <= 90]
    flipped = [(w - x, h - y, width, tilt + 180)
               for x, y, width, tilt in face_points(img.rotate(180)) if abs(tilt) <= 90]
    # Biggest first; skip a face whose middle is inside one already kept (same head found twice).
    faces = []
    for f in sorted(upright + flipped, key=lambda f: f[2], reverse=True):
        if all(math.dist(f[:2], kept[:2]) > kept[2] / 2 for kept in faces):
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


def put_potato(img: Image.Image, x: float, y: float, width: float, tilt: float,
               parts: dict[str, Image.Image] | None) -> None:
    """Paste a potato so its round middle sits on the face at (x, y), turned with the head."""
    spot_x, spot_y, spot_r = potato_spot
    scale = FACE_SIZE * width / spot_r
    sticker = potato.resize((max(1, round(potato.width * scale)), max(1, round(potato.height * scale))))
    if parts:
        face.stick_on(sticker, parts)
    # Where the potato's middle ends up after rotating around the sticker's center.
    dx, dy = spot_x * scale - sticker.width / 2, spot_y * scale - sticker.height / 2
    sticker = sticker.rotate(-tilt, resample=Image.Resampling.BICUBIC, expand=True)
    t = math.radians(tilt)
    ax = sticker.width / 2 + dx * math.cos(t) - dy * math.sin(t)
    ay = sticker.height / 2 + dx * math.sin(t) + dy * math.cos(t)
    img.paste(sticker, (round(x - ax), round(y - ay)), sticker)


@app.post("/potatoify")
def potatoify_endpoint():
    _, b64 = request.get_json()["image"].split(",", 1)
    with lock:
        parts = face.current_face(OUTPUT)
        img, replaced = potatoify(Image.open(io.BytesIO(base64.b64decode(b64))), parts)
    img.save(OUTPUT / f"{datetime.now():%Y%m%d-%H%M%S-%f}_result.jpg", quality=92)
    out = io.BytesIO()
    img.save(out, "JPEG", quality=92)
    print(f"replaced: {replaced}")
    return jsonify(
        image="data:image/jpeg;base64," + base64.b64encode(out.getvalue()).decode(),
        replaced=replaced,
        face=parts is not None,
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
    app.run(host="127.0.0.1", port=8765)
