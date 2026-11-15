// Catches <input type="file"> uploads before the page sees them, swaps every
// image for its potatoified version, then replays the events to the page.
let replaying = false;
let busy = 0;
let heldForm = null;

function shouldIntercept(target) {
  return (
    !replaying &&
    target instanceof HTMLInputElement &&
    target.type === "file" &&
    [...(target.files ?? [])].some((f) => f.type.startsWith("image/"))
  );
}

// The page gets "input" right before "change"; hold both back and replay them later.
window.addEventListener("input", (e) => {
  if (shouldIntercept(e.target)) e.stopImmediatePropagation();
}, true);

window.addEventListener("change", async (e) => {
  const input = e.target;
  if (!shouldIntercept(input)) return;
  e.stopImmediatePropagation();

  toast("potatoifying…");
  busy++;
  try {
    const files = await Promise.all([...input.files].map(potatoify));
    const dt = new DataTransfer();
    files.forEach((f) => dt.items.add(f));
    input.files = dt.files;

    replaying = true;
    try {
      input.dispatchEvent(new Event("input", { bubbles: true }));
      input.dispatchEvent(new Event("change", { bubbles: true }));
    } finally {
      replaying = false;
    }
  } finally {
    busy--;
  }
  if (!busy && heldForm) {
    const form = heldForm;
    heldForm = null;
    form.requestSubmit();
  }
}, true);

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
