// Catches image uploads before the page sees them (file pickers, drag and drop, paste),
// swaps every image for its face-swapped version, then replays the events to the page.
let replaying = false;
let busy = 0;
let heldForm = null;
let enabled = false; // the popup's switch; off until the user turns it on

chrome.storage.local.get("enabled").then((saved) => {
  enabled = saved.enabled ?? false;
  console.log(`[potato] loaded on ${location.host}, switch is ${enabled ? "on" : "off"}`);
});
chrome.storage.onChanged.addListener((changes) => {
  if ("enabled" in changes) enabled = changes.enabled.newValue;
});

const hasImages = (files) => files.some((f) => f.type.startsWith("image/"));

const isImageInput = (target) =>
  target instanceof HTMLInputElement && target.type === "file" && hasImages([...(target.files ?? [])]);
const shouldIntercept = (target) => enabled && !replaying && isImageInput(target);

// The page gets "input" right before "change"; hold both back and replay them later.
window.addEventListener("input", (e) => {
  if (shouldIntercept(e.target)) e.stopImmediatePropagation();
}, true);

window.addEventListener("change", async (e) => {
  const input = e.target;
  if (!enabled && !replaying && isImageInput(input)) {
    console.log("[potato] saw an image upload, but the switch is off");
    toast("Potato Upload is off: turn it on from the toolbar icon");
    return;
  }
  if (!shouldIntercept(input)) return;
  e.stopImmediatePropagation();
  input.files = (await swapped([...input.files], "file picker")).files;
  replay(() => {
    input.dispatchEvent(new Event("input", { bubbles: true }));
    input.dispatchEvent(new Event("change", { bubbles: true }));
  });
}, true);

// Dropped and pasted files can only be read during the event, so copy them out first.
window.addEventListener("drop", async (e) => {
  const files = [...(e.dataTransfer?.files ?? [])];
  if (!enabled || replaying || !hasImages(files)) return;
  e.preventDefault();
  e.stopImmediatePropagation();
  const { target, clientX, clientY } = e;
  // Let the page close its "drop here" overlay; the files arrive once they're swapped.
  target.dispatchEvent(new DragEvent("dragleave", { bubbles: true, composed: true, clientX, clientY }));
  const dataTransfer = await swapped(files, "drop");
  // Drop zones close while we swap (Discord's does), so prefer the page's own file input.
  if (attachViaFileInput(dataTransfer.files)) return;
  replay(() => target.dispatchEvent(new DragEvent("drop", {
    bubbles: true, cancelable: true, composed: true, clientX, clientY, dataTransfer,
  })));
}, true);

window.addEventListener("paste", async (e) => {
  const files = [...(e.clipboardData?.files ?? [])];
  if (!enabled || replaying || !hasImages(files)) return;
  e.preventDefault();
  e.stopImmediatePropagation();
  const { target } = e;
  const clipboardData = await swapped(files, "paste");
  let handled = false;
  replay(() => {
    handled = !target.dispatchEvent(new ClipboardEvent("paste", {
      bubbles: true, cancelable: true, composed: true, clipboardData,
    }));
  });
  if (!handled) attachViaFileInput(clipboardData.files);
}, true);

// Hand files to the page's file input, as if they were picked by hand. False if there's none.
function attachViaFileInput(files) {
  const input = document.querySelector("input[type=file]");
  if (!input) return false;
  console.log("[potato] attaching through the page's file input");
  input.files = files;
  replay(() => {
    input.dispatchEvent(new Event("input", { bubbles: true }));
    input.dispatchEvent(new Event("change", { bubbles: true }));
  });
  return true;
}

async function swapped(files, how) {
  console.log(`[potato] intercepted ${how}:`, files.map((f) => f.name));
  toast("swapping faces…");
  busy++;
  try {
    // The originals go to the popup (opened for the user), never to the page.
    const items = await Promise.all(files.map(async (f) => ({ original: await thumbnail(f), swapped: null })));
    await saveUpload(items, "swapping");
    chrome.runtime.sendMessage({ type: "showPopup" }).catch(() => {});

    const results = await Promise.all(files.map(potatoify));
    for (const [i, result] of results.entries()) {
      if (result !== files[i]) items[i].swapped = await thumbnail(result);
    }
    await saveUpload(items, "done");

    const dt = new DataTransfer();
    results.forEach((f) => dt.items.add(f));
    return dt;
  } catch (err) {
    // Most often the extension was reloaded under this page ("Extension context invalidated").
    // Never swallow the upload: hand the page its originals.
    console.warn("[potato] could not swap, sending the originals:", err);
    toast(String(err).includes("context invalidated")
      ? "Potato Upload was reloaded: refresh this page"
      : "could not swap faces, original photo sent");
    const dt = new DataTransfer();
    files.forEach((f) => dt.items.add(f));
    return dt;
  } finally {
    busy--;
  }
}

function saveUpload(items, status) {
  return chrome.storage.local.set({ lastUpload: { site: location.host, at: Date.now(), status, items } });
}

async function thumbnail(file) {
  try {
    const bitmap = await createImageBitmap(file, { resizeWidth: 320, resizeQuality: "medium" });
    const canvas = new OffscreenCanvas(bitmap.width, bitmap.height);
    canvas.getContext("2d").drawImage(bitmap, 0, 0);
    return await readAsDataURL(await canvas.convertToBlob({ type: "image/jpeg", quality: 0.8 }));
  } catch {
    return null; // e.g. HEIC, which Chrome can't decode
  }
}

function replay(dispatch) {
  replaying = true;
  try {
    dispatch();
  } finally {
    replaying = false;
  }
  if (!busy && heldForm) {
    const form = heldForm;
    heldForm = null;
    form.requestSubmit();
  }
}

// Submitting before the potatoes are ready would send the originals; wait, then submit.
window.addEventListener("submit", (e) => {
  if (!busy) return;
  e.preventDefault();
  e.stopImmediatePropagation();
  heldForm = e.target;
}, true);

async function potatoify(file) {
  if (!file.type.startsWith("image/")) return file;
  try {
    const res = await chrome.runtime.sendMessage({ type: "potatoify", image: await readAsDataURL(file) });
    if (res.error) throw new Error(res.error);
    const withFace = res.face ? " (with your face)" : "";
    toast(res.replaced.length ? `replaced: ${res.replaced.join(", ")}${withFace}` : "nothing to replace");
    const bytes = Uint8Array.from(atob(res.image.split(",")[1]), (c) => c.charCodeAt(0));
    return new File([bytes], file.name.replace(/\.\w+$/, "") + ".jpg", { type: "image/jpeg" });
  } catch (err) {
    console.warn("[potato] upload passed through untouched:", err);
    toast("server offline, original photo sent");
    return file;
  }
}

function readAsDataURL(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result);
    reader.onerror = () => reject(reader.error);
    reader.readAsDataURL(file);
  });
}

function toast(text) {
  const el = Object.assign(document.createElement("div"), { textContent: text });
  el.dataset.potatoToast = "";
  el.style.cssText =
    "position:fixed;top:16px;left:50%;transform:translateX(-50%);z-index:2147483647;" +
    "background:#8b5a2b;color:#fff;padding:10px 18px;border-radius:999px;" +
    "font:600 14px system-ui;box-shadow:0 4px 12px rgba(0,0,0,.3)";
  document.body.append(el);
  setTimeout(() => el.remove(), 3000);
}
