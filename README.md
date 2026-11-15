# stupid_idea_hackathon_f26
Create something stupid lmao

## Everyone Is You

A Chrome extension that hijacks every photo you upload. The moment you pick a photo in an
Instagram DM or on Discord, your webcam quietly snaps you, and every face in the photo is
swapped with *yours* before the site ever sees it. Your friends get a group photo where
everyone is you. Cups become bubble tea, bottles juice boxes, wine glasses baby bottles.

## Demo flow

### Before going on stage

1. Start the server and wait for `Running on http://127.0.0.1:8765`:
   ```bash
   .venv/bin/python -u server/app.py
   ```
2. In `chrome://extensions`, hit the reload icon on **Potato Upload** if the code changed,
   then **refresh the Instagram and Discord tabs** (a tab left open across an extension
   reload has a dead script).
3. Pin the extension (puzzle icon → pin), click it and turn the switch **on**: the icon shows a blue **ON**.
4. Open the Instagram DM and the Discord DM with your friend. Keep a group photo handy,
   e.g. `photo/10_park_selfie.jpg`.
5. Warm up once on http://127.0.0.1:8765/test (pick a photo, Submit) so the models are loaded
   and the camera permission is granted.
6. Sit facing the MacBook camera with decent light.

### On stage (about 2 minutes)

1. **Pitch:** "Ever sent a group photo and wished it was just you? Now it is."
2. **Instagram:** in the DM, click the photo button and pick the group photo in Finder.
   - The page says *swapping faces…* and the extension popup opens with the original on the left.
   - About 3 seconds later: *replaced: face, face, … (with your face)*. The popup shows the
     swapped thumbnail on the right, and the attachment in the message box is the swapped photo.
     The original never reaches Instagram.
3. Click **Send**. Your friend's phone shows a group photo where everyone is you.
4. **Discord:** drag a photo into the chat, or copy one and paste it (⌘V). Same thing.
5. **Proof:** open `server/output/` to show the webcam snapshot and the result it made.
6. *(Optional)* Turn the switch off and upload again: the photo goes through untouched.

### If something goes wrong

| What you see | Fix |
|---|---|
| Nothing happens, no message at the top | Refresh the page. |
| *Potato Upload was reloaded: refresh this page* | Refresh the page. |
| *Potato Upload is off* | Turn the switch on in the toolbar popup. |
| *server offline, original photo sent* | Start the server (step 1). |
| *replaced: …* without *(with your face)* | The camera didn't see a face: face the MacBook camera, more light. |

## How it works

- `extension/content.js` catches image uploads (file picker, drag and drop, paste) before the
  page sees them, sends each image to the local server through the service worker, then hands
  the page the swapped files. The originals go to the popup instead.
- `extension/main_world.js` makes file inputs that Instagram never adds to the page visible to
  `content.js`.
- `extension/popup.html` / `popup.js`: the on/off switch and the last upload (original vs. what was attached).
- `server/app.py`: Flask on `127.0.0.1:8765`; object stickers (YOLO11, the `REPLACEMENTS` dict);
  saves every result to `server/output/`.
- `server/face.py`: webcam snapshot from the computer's own camera (a nearby iPhone's
  Continuity Camera is skipped), then the face swap, using the same recipe as
  [Deep-Live-Cam](https://github.com/hacksider/Deep-Live-Cam): insightface finds the faces and
  `inswapper_128_fp16.onnx` swaps them. Set `SOURCE_PHOTO` to swap in a photo's face instead of the webcam's.

The extension runs on instagram.com, discord.com and the local test page; add sites in
`extension/manifest.json`. The first potato-filter version is commit `5b75f6e`.

## Setup

```bash
# Python 3.11–3.13 (torch has no wheels for 3.15 yet); insightface builds with Xcode CLT
python3.11 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -u server/app.py     # serves on http://127.0.0.1:8765
```

First run downloads the swap model (~280 MB, to `server/models/`) and insightface's
`buffalo_l` (~280 MB, to `~/.insightface/`). macOS asks once to let your terminal app use
the camera: allow it.

Load the extension: Chrome → `chrome://extensions` → Developer mode on → **Load unpacked** → pick `extension/`.

The insightface models are for non-commercial research use only. Stickers are
[Noto Emoji](https://github.com/googlefonts/noto-emoji) (Apache 2.0).
