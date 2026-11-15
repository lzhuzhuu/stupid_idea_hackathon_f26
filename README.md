# stupid_idea_hackathon_f26
Create something stupid lmao

## Everyone Is You (branch `deep-live-cam`)

A Chrome extension that quietly face-swaps every photo you upload: the moment you pick a
photo, your webcam snaps you, and every face in the photo becomes *your* face.
Cups become bubble tea, bottles juice boxes, wine glasses baby bottles.

The potato-filter version lives on `main`.

- `extension/` – thin JS layer: catches `<input type="file">` uploads and swaps the images.
- `server/app.py` – local Flask server: object stickers (YOLO11) + calls the face swap.
  Objects-to-stickers is the `REPLACEMENTS` dict.
- `server/face.py` – webcam snapshot + face swap, using the same recipe as
  [Deep-Live-Cam](https://github.com/hacksider/Deep-Live-Cam): insightface finds faces and
  `inswapper_128_fp16.onnx` swaps them. Set `SOURCE_PHOTO` to use a photo instead of the webcam.
- `server/output/` – every result and webcam shot is saved here (git-ignored).

### Run it

```bash
# Python 3.11–3.13 (torch has no wheels for 3.15 yet); insightface builds with Xcode CLT
python3.11 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -u server/app.py     # serves on http://127.0.0.1:8765
```

First run downloads the swap model (~280 MB, to `server/models/`) and insightface's
`buffalo_l` (~280 MB, to `~/.insightface/`).

1. Chrome → `chrome://extensions` → turn on Developer mode → **Load unpacked** → pick `extension/`.
   After changing extension code, hit the reload icon on its card.
2. Open http://127.0.0.1:8765/test, pick a photo with people in it, hit Submit.
3. The first time, macOS asks to let your terminal app use the camera – allow it.

If the server isn't running, uploads go through untouched. If no face is found on any
camera, faces are left alone.

The insightface models are for non-commercial research use only. Stickers are
[Noto Emoji](https://github.com/googlefonts/noto-emoji) (Apache 2.0).
