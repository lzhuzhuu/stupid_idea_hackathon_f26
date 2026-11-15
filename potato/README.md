## Potato

Every face in a photo you upload turns into a real potato, just the face: hair, ears and neck stay
as they were. The potato wears that person's own eyes, nose and mouth, where they were on the face,
eyes and mouth a bit bigger for laughs, so each potato keeps its person's expression. No webcam.

Runs on port **8766**, so it can run next to `everyone_is_you/` (port 8765).

- `app.py`: collects guesses of where faces are (YOLO11 pose on the photo and on the photo upside
  down, plus MediaPipe on overlapping tiles), has MediaPipe check each one, drops duplicates, and
  pastes the potatoes, smallest first so nearer faces end up on top. The potato photo is
  `FACE_STICKER` (`potato.png`, or `potato_sprouts.png` for one with sprouts).
- `face.py`: for each guess, turns a crop around it upright and finds the face's landmarks
  (MediaPipe). That fixes where the face is and which way up (the pose model sometimes has faces
  upside down) and drops guesses with no face (arms). Then, like Everyone Is You's paste-back,
  only the face changes: the potato is stretched over the face's outline, and the eyes, nose
  and mouth are cut along their own outlines (no skin around them) and put back on it.
  Settings at the top:
  - `PARTS`: which parts go on, and how much bigger (`zoom`: eyes 1.4×, mouth 1.35×, nose 1.1×).
  - `POTATO_FIT` / `FOREHEAD`: how far past the face's outline the potato reaches.
  - `EDGE_BAND` / `SKIN_AT_EDGE`: toward its outline the potato's colour runs into the person's skin
    colour (sampled from their cheeks and forehead) over `EDGE_BAND` of its width, reaching
    `SKIN_AT_EDGE` (0.4) at the edge, so it's still mostly potato there. `EDGE_SOFT` is a thin soft
    rim so the outline isn't jagged.
  - `NOSE_SHADE`: the nose is all skin, so it keeps only its light and shade, on the potato's skin.
  - `GREY_AT` / `COLOUR_AT`: in black-and-white or sepia photos the potato goes grey too.
- `output/`: every result is saved here (git-ignored).

Tested on the 10 photos in `photo/`: every visible face gets its potato (37 faces, about 1–1.5 s
a photo on a MacBook CPU), people lying upside down included.

### Run it

```bash
# Python 3.11–3.13 (torch has no wheels for 3.15 yet). Its own venv, separate from everyone_is_you's.
python3.12 -m venv potato/.venv
potato/.venv/bin/pip install -r potato/requirements.txt
potato/.venv/bin/python -u potato/app.py     # serves on http://127.0.0.1:8766
```

1. Load `ui/` in Chrome (see the main README), click the extension icon, pick **Potato**, and
   turn the switch on. The icon shows a brown **ON**.
2. Open http://127.0.0.1:8766/test, pick a photo with people in it (e.g. from `photo/`), hit Submit.

If the server isn't running, uploads go through untouched. iPhone HEIC photos also go through
untouched: there's no `pillow-heif` here yet (`everyone_is_you/` has it).

### Potato photos

Both stickers are cut out of photos from Wikimedia Commons and turned upright:

- `assets/potato.png`: [OnePotato.jpg](https://commons.wikimedia.org/wiki/File:OnePotato.jpg) by Fk,
  [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0). The cut-out is shared under the same license.
- `assets/potato_sprouts.png`: [Potato with sprouts.jpg](https://commons.wikimedia.org/wiki/File:Potato_with_sprouts.jpg)
  by ZooFari, public domain.
