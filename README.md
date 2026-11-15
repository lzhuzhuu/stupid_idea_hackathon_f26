# stupid_idea_hackathon_f26
Create something stupid lmao

One Chrome extension, two stupid face filters. The extension catches every photo you upload
(Instagram DMs, Discord), sends it to a local server, and hands the page the doctored copy
instead. The popup picks which filter you get.

| Folder | What it is | Runs on |
|---|---|---|
| [`ui/`](ui/) | The Chrome extension: catches uploads; popup with the on/off switch and the feature picker | Chrome |
| [`everyone_is_you/`](everyone_is_you/) | **Everyone Is You**: every face in the photo is swapped with yours (insightface) | `127.0.0.1:8765` |
| [`potato/`](potato/) | **Potato**: every face (just the face) turns into a real potato wearing that person's own eyes, nose and mouth (MediaPipe) | `127.0.0.1:8766` |
| `photo/` | Sample group photos for testing | |

Both servers answer the same request, so the extension doesn't care which one it talks to:
`POST /potatoify` with `{"image": "<data URL>"}` returns `{"image": "<data URL>", "replaced": [...], "face": true|false}`.
Each also serves a test page at `/test`.

## Setup

1. Start the servers, both at once from the repo root:
   ```bash
   python3 run.py              # Everyone Is You on 8765 and Potato on 8766
   python3 run.py everyone     # or just one: everyone / potato
   ```
   Ctrl+C stops them. Each server uses its own Python environment (`.venv` for Everyone Is You,
   `potato/.venv` for Potato); `run.py` prints the setup command if one is missing. Details, and
   the stage demo script, in [`everyone_is_you/README.md`](everyone_is_you/README.md) and
   [`potato/README.md`](potato/README.md).
2. Chrome → `chrome://extensions` → Developer mode on → **Load unpacked** → pick `ui/`.
   If you loaded the old `extension/` folder before, remove that one first: Chrome remembers the folder.
3. Click the extension icon, pick **Everyone Is You** or **Potato**, and turn the switch on.

Add sites in `ui/manifest.json`. Image credits are in each folder's README.
