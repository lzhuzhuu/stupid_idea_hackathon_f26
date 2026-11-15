# stupid_idea_hackathon_f26
Create something stupid lmao

## Potato Upload

A Chrome extension that works like a face filter on every photo you upload: the moment you
pick a photo, your webcam quietly snaps you, and every face in the photo gets a potato with
*your* eyes and mouth on it. Cups become bubble tea, bottles juice boxes, wine glasses baby bottles.

- `extension/` – thin JS layer: catches `<input type="file">` uploads and swaps the images.
- `server/app.py` – local Python server: finds faces (YOLO11 pose) and objects (YOLO11), pastes stickers.
  Objects-to-stickers is the `REPLACEMENTS` dict; the face sticker is `FACE_STICKER`.
- `server/face.py` – webcam snapshot + MediaPipe face landmarks to cut out your eyes and mouth.
- `server/output/` – every result and webcam shot is saved here (git-ignored).

### Run it

```bash
# Python 3.11–3.13 (torch has no wheels for 3.15 yet)
python3.11 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -u server/app.py     # serves on http://127.0.0.1:8765
```

1. Chrome → `chrome://extensions` → turn on Developer mode → **Load unpacked** → pick `extension/`.
   After changing extension code, hit the reload icon on its card.
2. Open http://127.0.0.1:8765/test, pick a photo with people in it, hit Submit.
3. The first time, macOS asks to let your terminal app use the camera – allow it.

If the server isn't running, uploads go through untouched. If no face is found on any
camera, the potatoes go on without your features.

Stickers are [Noto Emoji](https://github.com/googlefonts/noto-emoji) (Apache 2.0).
