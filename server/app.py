"""Local face-swap server: the Chrome extension sends every uploaded image here."""
import base64
import io
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

# COCO class name -> sticker that covers the whole object. Edit this to change what becomes what.
REPLACEMENTS = {
    "cup": "bubble_tea.png",
    "bottle": "juice_box.png",
    "wine glass": "baby_bottle.png",
}
CONFIDENCE = 0.35
PADDING = 0.15  # grow each object box so the sticker fully covers it

app = Flask(__name__)
model = YOLO(HERE / "yolo11n.pt")  # downloaded (~6 MB) on first run
stickers = {name: Image.open(ASSETS / file).convert("RGBA") for name, file in REPLACEMENTS.items()}
lock = threading.Lock()  # one photo at a time: the webcam and the models don't share well
OUTPUT.mkdir(exist_ok=True)


def transform(img: Image.Image, source: face.Face | None) -> tuple[Image.Image, list[str]]:
    img = ImageOps.exif_transpose(img).convert("RGB")
    objects = find_objects(img)
    swapped = 0
    if source is not None:
        img, swapped = face.swap_faces(img, source)
    for (x1, y1, x2, y2), name in objects:
        sticker = stickers[name].resize((max(1, round(x2 - x1)), max(1, round(y2 - y1))))
        img.paste(sticker, (round(x1), round(y1)), sticker)
    return img, [name for _, name in objects] + ["face"] * swapped


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


@app.post("/potatoify")
def potatoify_endpoint():
    _, b64 = request.get_json()["image"].split(",", 1)
    with lock:
        source = face.current_face(OUTPUT)
        img, replaced = transform(Image.open(io.BytesIO(base64.b64decode(b64))), source)
    img.save(OUTPUT / f"{datetime.now():%Y%m%d-%H%M%S-%f}_result.jpg", quality=92)
    out = io.BytesIO()
    img.save(out, "JPEG", quality=92)
    print(f"replaced: {replaced}")
    return jsonify(
        image="data:image/jpeg;base64," + base64.b64encode(out.getvalue()).decode(),
        replaced=replaced,
        face=source is not None,
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
