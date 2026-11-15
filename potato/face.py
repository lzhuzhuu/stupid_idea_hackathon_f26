"""Takes a close look at each face and turns just that face into a potato.

app.py's pose model says roughly where faces are. For each guess, this turns a square crop
around it upright and lets MediaPipe's face landmarks say where the face really is, which way
up it is, and where its outline, eyes, nose and mouth are.

Like Everyone Is You's paste-back, only the face changes: a potato is stretched over the face's
outline, and the person's own eyes, nose and mouth go back on it where they were (eyes and mouth
a bit bigger, for laughs), cut along their own outlines so no skin comes with them.
"""
import math
import urllib.request
from pathlib import Path
from typing import NamedTuple

import cv2
import mediapipe as mp
import numpy as np
from mediapipe.tasks.python import BaseOptions, vision
from PIL import Image, ImageChops, ImageOps

HERE = Path(__file__).parent
MODEL = HERE / "models" / "face_landmarker.task"
MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/"
    "face_landmarker/face_landmarker/float16/1/face_landmarker.task"
)

# MediaPipe face-mesh landmark ids.
FACE_OVAL = [10, 338, 297, 332, 284, 251, 389, 356, 454, 323, 361, 288, 397, 365, 379, 378, 400, 377,
             152, 148, 176, 149, 150, 136, 172, 58, 132, 93, 234, 127, 162, 21, 54, 103, 67, 109]
EYE_CORNERS = ((33, 133), (362, 263))
NOSE_TIP = 1
FACE_SIDES = (234, 454)  # the face's outline at ear height


class Part(NamedTuple):
    outline: list[int]  # landmark ids, in order around the part (the nose's are just points on it)
    zoom: float  # how much bigger it goes on the potato
    grow: float  # how far the outline grows to take in lashes and lip edges, in part widths


# Stuck on in this order, so the eyes and mouth go over the nose's edges.
PARTS = {
    "nose": Part([195, 5, 4, 1, 19, 94, 2, 98, 97, 326, 327, 129, 358, 64, 294], 1.1, 0.05),
    "eye_left": Part([33, 246, 161, 160, 159, 158, 157, 173, 133, 155, 154, 153, 145, 144, 163, 7], 1.4, 0.12),
    "eye_right": Part([362, 398, 384, 385, 386, 387, 388, 466, 263, 249, 390, 373, 374, 380, 381, 382], 1.4, 0.12),
    "mouth": Part([61, 185, 40, 39, 37, 0, 267, 269, 270, 409, 291, 375, 321, 405, 314, 17, 84, 181, 91, 146],
                  1.35, 0.06),
}
POTATO_FIT = 1.05  # potato size relative to the face's outline: a touch over, so no face edge shows
# The potato's edge: its colour runs into the person's skin colour over EDGE_BAND (share of the
# potato's width, in from its outline), reaching SKIN_AT_EDGE skin at the outline itself: under
# half, so even there it's mostly potato. EDGE_SOFT is a thin soft rim so the outline isn't jagged.
EDGE_BAND = 0.12
SKIN_AT_EDGE = 0.4
EDGE_SOFT = 0.015
SKIN_SPOTS = (50, 280, 151)  # landmarks on the cheeks and forehead, where the skin colour is sampled
FOREHEAD = 0.1  # the outline stops below the hairline; the potato reaches this much higher (in face heights)
NOSE_SHADE = (0.75, 1.2)  # how much darker/lighter than the potato the nose's shading may get
# A photo's colourfulness (average max-minus-min of R, G, B) at which the potato goes fully grey
# and fully coloured: black-and-white and sepia photos sit around 5-7, colour photos 14 and up.
GREY_AT, COLOUR_AT = 6.0, 12.0
CROP_SIZE = 384  # px; every face reaches MediaPipe at this size, however small it is in the photo
CROP_SCALE = 2.2  # crop side, in face widths: the whole head and a bit more
MAX_RENDER = 1600  # px; the biggest a potato is drawn before it's scaled onto the photo
CENTER_SLACK = 0.3  # a face whose nose is further than this (in crop sides) from the middle is someone else's

if not MODEL.exists():
    MODEL.parent.mkdir(exist_ok=True)
    urllib.request.urlretrieve(MODEL_URL, MODEL)
landmarker = vision.FaceLandmarker.create_from_options(
    # More than one: a crop around one face can catch the next person's too.
    vision.FaceLandmarkerOptions(base_options=BaseOptions(model_asset_path=str(MODEL)), num_faces=3)
)
finder = vision.FaceLandmarker.create_from_options(  # for whole tiles of the photo
    vision.FaceLandmarkerOptions(base_options=BaseOptions(model_asset_path=str(MODEL)), num_faces=10)
)


class Face(NamedTuple):
    x: float  # middle of the eyes and nose tip, in photo pixels
    y: float
    width: float  # across the face at ear height
    tilt: float  # degrees clockwise; 180 is upside down
    crop: tuple[float, float, float, float]  # the (x, y, width, tilt) the upright crop was made with
    marks: list  # MediaPipe's landmarks in that crop, 0..1


def look_closer(img: Image.Image, x: float, y: float, width: float, tilt: float) -> Face | None:
    """The face the pose model guessed at (x, y): where it really is, and its landmarks.

    None if there's no face there: the pose model also guesses faces on arms and between heads.
    """
    for turn in (0, 180):  # the pose model sometimes has a face upside down
        marks = landmarks(upright_crop(img, x, y, width, tilt + turn))
        if marks:
            break
    else:
        return None
    crop = (x, y, width, tilt + turn)
    x, y, width, tilt = measure(marks, *crop)
    # Crop again around the face as measured, so it sits straight and centred.
    if marks_again := landmarks(upright_crop(img, x, y, width, tilt)):
        crop, marks = (x, y, width, tilt), marks_again
    return Face(x, y, width, (tilt + 180) % 360 - 180, crop, marks)


def more_guesses(img: Image.Image) -> list[tuple[float, float, float, float]]:
    """(x, y, width, tilt) of the faces MediaPipe finds by itself, for faces the pose model
    misses. It searches overlapping tiles: on the whole photo at once it misses all but the biggest."""
    w, h = img.size
    tile_w, tile_h = w // 2, h * 2 // 3
    guesses = []
    for left in (0, w // 4, w // 2):
        for top in (0, h // 3):
            tile = img.crop((left, top, left + tile_w, top + tile_h))
            for marks in finder.detect(mp.Image(image_format=mp.ImageFormat.SRGB, data=np.asarray(tile))).face_landmarks:
                def at(i: int) -> tuple[float, float]:
                    return left + marks[i].x * tile_w, top + marks[i].y * tile_h
                (lx, ly), (rx, ry) = ([np.mean([at(i) for i in corners], axis=0) for corners in EYE_CORNERS])
                x, y = np.mean([(lx, ly), (rx, ry), at(NOSE_TIP)], axis=0)
                guesses.append((x, y, math.dist(*(at(i) for i in FACE_SIDES)),
                                math.degrees(math.atan2(ry - ly, rx - lx))))
    return guesses


def landmarks(crop: Image.Image) -> list | None:
    """MediaPipe's landmarks of the face in the middle of the crop, if there is one."""
    result = landmarker.detect(mp.Image(image_format=mp.ImageFormat.SRGB, data=np.asarray(crop)))
    near = [m for m in result.face_landmarks
            if math.dist((m[NOSE_TIP].x, m[NOSE_TIP].y), (0.5, 0.5)) < CENTER_SLACK]
    return min(near, key=lambda m: math.dist((m[NOSE_TIP].x, m[NOSE_TIP].y), (0.5, 0.5)), default=None)


def measure(marks: list, x: float, y: float, width: float, tilt: float) -> tuple[float, float, float, float]:
    """(x, y, width, tilt) of the face in the photo, from its landmarks in the crop made with
    (x, y, width, tilt)."""
    def point(i: int) -> tuple[float, float]:
        return marks[i].x * CROP_SIZE, marks[i].y * CROP_SIZE

    eye_l, eye_r = [np.mean([point(i) for i in corners], axis=0) for corners in EYE_CORNERS]
    u, v = np.mean([eye_l, eye_r, point(NOSE_TIP)], axis=0)
    crooked = math.degrees(math.atan2(eye_r[1] - eye_l[1], eye_r[0] - eye_l[0]))
    scale = width * CROP_SCALE / CROP_SIZE
    cos, sin = math.cos(math.radians(tilt)), math.sin(math.radians(tilt))
    du, dv = (u - CROP_SIZE / 2) * scale, (v - CROP_SIZE / 2) * scale
    face_width = math.dist(*(point(i) for i in FACE_SIDES)) * scale
    return x + du * cos - dv * sin, y + du * sin + dv * cos, face_width, tilt + crooked


def upright_crop(img: Image.Image, x: float, y: float, width: float, tilt: float,
                 size: int = CROP_SIZE) -> Image.Image:
    """A size×size square around the face at (x, y), turned so the face is upright."""
    scale = width * CROP_SCALE / size  # photo pixels per crop pixel
    cos = math.cos(math.radians(tilt)) * scale
    sin = math.sin(math.radians(tilt)) * scale
    half = size / 2
    # Crop pixel (u, v) comes from photo pixel (x, y) + turned-by-tilt (u - half, v - half).
    return img.transform(
        (size, size),
        Image.Transform.AFFINE,
        (cos, -sin, x - (cos - sin) * half, sin, cos, y - (sin + cos) * half),
        resample=Image.Resampling.BICUBIC,
    )


def potato_face(img: Image.Image, face: Face, potato: Image.Image) -> tuple[Image.Image, tuple[int, int]]:
    """The potato for this face, wearing its eyes, nose and mouth and turned to match the photo,
    and where its top-left corner goes. It's cut from img: make every face's before pasting any."""
    x, y, width, tilt = face.crop
    side = width * CROP_SCALE  # photo pixels the crop spans
    size = min(MAX_RENDER, max(CROP_SIZE, round(side)))  # drawn at about the photo's own resolution
    crop = upright_crop(img, x, y, width, tilt, size)

    def outline(ids: list[int]) -> np.ndarray:
        return np.array([(face.marks[i].x * size, face.marks[i].y * size) for i in ids], np.float32)

    # The potato, stretched over the face's outline.
    oval = outline(FACE_OVAL)
    (left, top), (right, bottom) = oval.min(axis=0), oval.max(axis=0)
    top -= (bottom - top) * FOREHEAD
    w, h = (right - left) * POTATO_FIT, (bottom - top) * POTATO_FIT
    spud = potato.resize((max(1, round(w)), max(1, round(h))), Image.Resampling.LANCZOS)
    spud = edge_into_skin(spud, skin_colour(crop, face, size))
    layer = Image.new("RGBA", (size, size))
    put(layer, spud, ((left + right) / 2, (top + bottom) / 2))

    # The parts, cut along their own outlines and stuck back where they were, bigger.
    parts = Image.new("RGBA", (size, size))
    for name, part in PARTS.items():
        points = outline(part.outline)
        if name == "nose":
            points = cv2.convexHull(points)[:, 0]
        grow = max(1, round((points[:, 0].max() - points[:, 0].min()) * part.grow))
        mask = np.zeros((size, size), np.uint8)
        cv2.fillPoly(mask, [np.round(points).astype(np.int32)], 255)
        mask = cv2.dilate(mask, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * grow + 1, 2 * grow + 1)))
        mask = cv2.GaussianBlur(mask, (0, 0), max(1, grow / 2))
        ys, xs = np.nonzero(mask)
        if not len(xs):
            continue
        box = (xs.min(), ys.min(), xs.max() + 1, ys.max() + 1)
        patch = crop.crop(box).convert("RGBA")
        patch.putalpha(Image.fromarray(mask).crop(box))
        if name == "nose":  # all skin: keep its light and shade, in the potato's colour
            patch = in_potato_colour(patch, layer.crop(box))
        zoomed = patch.resize((max(1, round(patch.width * part.zoom)), max(1, round(patch.height * part.zoom))),
                              Image.Resampling.LANCZOS)
        put(parts, zoomed, ((box[0] + box[2]) / 2, (box[1] + box[3]) / 2))
    # Nothing sticks out past the potato's outline.
    parts.putalpha(ImageChops.multiply(parts.getchannel("A"), layer.getchannel("A")))
    layer.alpha_composite(parts)

    # Back to the photo: its scale, and turned the way the head is.
    if size != round(side):
        layer = layer.resize((max(1, round(side)), max(1, round(side))), Image.Resampling.LANCZOS)
    layer = layer.rotate(-tilt, resample=Image.Resampling.BICUBIC, expand=True)
    return layer, (round(x - layer.width / 2), round(y - layer.height / 2))


def skin_colour(crop: Image.Image, face: Face, size: int) -> np.ndarray:
    """The person's skin colour: the median of small spots on the cheeks and forehead."""
    rgb = np.asarray(crop.convert("RGB")).astype(np.float32)
    r = max(2, round(size * 0.015))
    spots = []
    for i in SKIN_SPOTS:
        x, y = round(face.marks[i].x * size), round(face.marks[i].y * size)
        spots.append(rgb[max(0, y - r):y + r, max(0, x - r):x + r].reshape(-1, 3))
    return np.median(np.concatenate(spots), axis=0)


def edge_into_skin(spud: Image.Image, skin: np.ndarray) -> Image.Image:
    """The potato with its colour running into the skin colour toward its outline (still mostly
    potato there), and a thin soft rim instead of a hard cut."""
    rgba = np.asarray(spud).astype(np.float32)
    inside = (rgba[..., 3] > 127).astype(np.uint8)
    depth = cv2.distanceTransform(inside, cv2.DIST_L2, 5)  # pixels in from the outline
    near_edge = np.clip(1 - depth / max(1.0, EDGE_BAND * min(spud.size)), 0, 1)
    near_edge = near_edge * near_edge * (3 - 2 * near_edge)  # smoothstep: no line where the blend starts
    skin_share = (SKIN_AT_EDGE * near_edge)[..., None]
    rgba[..., :3] = rgba[..., :3] * (1 - skin_share) + skin * skin_share
    rim = round(EDGE_SOFT * min(spud.size))
    if rim >= 1:
        alpha = rgba[..., 3].astype(np.uint8)
        alpha = cv2.erode(alpha, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * rim + 1, 2 * rim + 1)))
        rgba[..., 3] = cv2.GaussianBlur(alpha, (0, 0), rim / 2)
    return Image.fromarray(np.clip(rgba, 0, 255).astype(np.uint8), "RGBA")


def tone_like(potato: Image.Image, photo: Image.Image) -> Image.Image:
    """The potato with no more colour than the photo has: grey in a black-and-white photo."""
    small = np.asarray(photo.convert("RGB").reduce(max(1, max(photo.size) // 256))).astype(np.float32)
    colourful = float((small.max(axis=2) - small.min(axis=2)).mean())
    keep = min(1.0, max(0.0, (colourful - GREY_AT) / (COLOUR_AT - GREY_AT)))
    if keep == 1.0:
        return potato
    rgb = potato.convert("RGB")
    toned = Image.blend(ImageOps.grayscale(rgb).convert("RGB"), rgb, keep)
    toned.putalpha(potato.getchannel("A"))
    return toned


def put(layer: Image.Image, im: Image.Image, center: tuple[float, float]) -> None:
    """Alpha-composite im onto layer, centred at center; whatever hangs off the edge is dropped."""
    piece = Image.new("RGBA", layer.size)
    piece.paste(im, (round(center[0] - im.width / 2), round(center[1] - im.height / 2)))
    layer.alpha_composite(piece)


def in_potato_colour(patch: Image.Image, under: Image.Image) -> Image.Image:
    """The patch's light and shade on the potato skin under it: a nose carved out of potato."""
    rgba = np.asarray(patch).astype(np.float32)
    potato = np.asarray(under).astype(np.float32)
    if potato[..., 3].sum() == 0:
        return patch
    light = rgba[..., :3] @ np.array([0.299, 0.587, 0.114], np.float32)
    mean = np.average(light.ravel(), weights=rgba[..., 3].ravel() + 1e-6)
    shade = np.clip(light / max(mean, 1.0), *NOSE_SHADE)[..., None]
    rgba[..., :3] = np.clip(potato[..., :3] * shade, 0, 255)
    return Image.fromarray(rgba.astype(np.uint8), "RGBA")
