## Potato

Works like a face filter on every photo you upload: the moment you pick a photo, your webcam
quietly snaps you, and every face in the photo gets a potato with *your* eyes and mouth on it.
Cups become bubble tea, bottles juice boxes, wine glasses baby bottles.

This is the first working version (commit `5b75f6e`), moved here unchanged except that it now
runs on port **8766**, so it can run next to `everyone_is_you/` (port 8765).

- `app.py`: finds faces (YOLO11 pose) and objects (YOLO11), pastes stickers.
  Objects-to-stickers is the `REPLACEMENTS` dict; the face sticker is `FACE_STICKER`.
- `face.py`: webcam snapshot plus MediaPipe face landmarks to cut out your eyes and mouth.
- `output/`: every result and webcam shot is saved here (git-ignored).

### Run it

```bash
# Python 3.11–3.13 (torch has no wheels for 3.15 yet). Its own venv, separate from everyone_is_you's.
python3.11 -m venv potato/.venv
potato/.venv/bin/pip install -r potato/requirements.txt
potato/.venv/bin/python -u potato/app.py     # serves on http://127.0.0.1:8766
```

1. Load `ui/` in Chrome (see the main README), click the extension icon, pick **Potato**, and
   turn the switch on. The icon shows a brown **ON**.
2. Open http://127.0.0.1:8766/test, pick a photo with people in it (e.g. from `photo/`), hit Submit.
3. The first time, macOS asks to let your terminal app use the camera: allow it.

If the server isn't running, uploads go through untouched. If no face is found on any
camera, the potatoes go on without your features.

### Not carried over from everyone_is_you yet

- **HEIC photos** (iPhone) fail here and go through untouched: there's no `pillow-heif`.
- **Camera choice:** `face.py` tries OpenCV camera indexes 0–2, so a nearby iPhone's Continuity
  Camera can get picked. `everyone_is_you/face.py` skips phone cameras with `cv2_enumerate_cameras`.

Stickers are [Noto Emoji](https://github.com/googlefonts/noto-emoji) (Apache 2.0).
