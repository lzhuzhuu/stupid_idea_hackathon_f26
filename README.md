# stupid_idea_hackathon_f26
Create something stupid lmao

One Chrome extension, two stupid face filters. The extension catches every photo you upload
(Instagram DMs, Discord), sends it to a local server, and hands the page the doctored copy
instead. The popup picks which filter you get.

| Folder | What it is | Runs on |
|---|---|---|
| [`ui/`](ui/) | The Chrome extension: catches uploads; popup with the on/off switch and the feature picker | Chrome |
| [`everyone_is_you/`](everyone_is_you/) | **Everyone Is You**: every face in the photo is swapped with yours (insightface) | `127.0.0.1:8765` |
| [`potato/`](potato/) | **Potato**: every face becomes a potato with your eyes and mouth (MediaPipe) | `127.0.0.1:8766` |
| `photo/` | Sample group photos for testing | |

Both servers answer the same request, so the extension doesn't care which one it talks to:
`POST /potatoify` with `{"image": "<data URL>"}` returns `{"image": "<data URL>", "replaced": [...], "face": true|false}`.
Each also serves a test page at `/test`.

## Setup

1. Start the server for the feature you want. See [`everyone_is_you/README.md`](everyone_is_you/README.md)
   (also has the stage demo script) or [`potato/README.md`](potato/README.md).
2. Chrome → `chrome://extensions` → Developer mode on → **Load unpacked** → pick `ui/`.
   If you loaded the old `extension/` folder before, remove that one first: Chrome remembers the folder.
3. Click the extension icon, pick **Everyone Is You** or **Potato**, and turn the switch on.

Add sites in `ui/manifest.json`. Stickers are [Noto Emoji](https://github.com/googlefonts/noto-emoji) (Apache 2.0).
