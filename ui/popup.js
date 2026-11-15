const box = document.getElementById("enabled");
const status = document.getElementById("status");
const featureRadios = [...document.querySelectorAll("input[name=feature]")];
const ON_TEXT = {
  everyone: "On: photos you upload get your face. Needs everyone_is_you/app.py running.",
  potato: "On: faces in photos you upload become potatoes. Needs potato/app.py running.",
};
let feature = "everyone";

function show(enabled) {
  box.checked = enabled;
  featureRadios.forEach((radio) => (radio.checked = radio.value === feature));
  status.textContent = enabled ? ON_TEXT[feature] : "Off: uploads go through untouched.";
}

// The last intercepted upload: what was picked, and what the page got instead.
function showUpload(upload) {
  if (!upload) return;
  document.getElementById("last").hidden = false;
  const time = new Date(upload.at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  document.getElementById("last-title").textContent = `Last upload · ${upload.site} · ${time}`;
  document.getElementById("pairs").replaceChildren(...upload.items.map((item) => {
    const pair = document.createElement("div");
    pair.className = "pair";
    const pending = upload.status === "swapping" ? "swapping…" : "unchanged";
    pair.append(figure(item.original, "Original", "no preview"), figure(item.swapped, "Attached instead", pending));
    return pair;
  }));
}

function figure(src, caption, placeholder) {
  const fig = document.createElement("figure");
  const pic = src ? Object.assign(document.createElement("img"), { src }) : document.createElement("div");
  if (!src) pic.textContent = placeholder;
  fig.append(pic, Object.assign(document.createElement("figcaption"), { textContent: caption }));
  return fig;
}

chrome.storage.local.get(["enabled", "feature", "lastUpload"]).then(({ enabled = false, feature: saved, lastUpload }) => {
  feature = saved ?? "everyone";
  show(enabled);
  showUpload(lastUpload);
});
chrome.storage.onChanged.addListener((changes) => {
  if ("lastUpload" in changes) showUpload(changes.lastUpload.newValue);
});
box.addEventListener("change", () => {
  chrome.storage.local.set({ enabled: box.checked });
  show(box.checked);
});
featureRadios.forEach((radio) => radio.addEventListener("change", () => {
  feature = radio.value;
  chrome.storage.local.set({ feature });
  show(box.checked);
}));
