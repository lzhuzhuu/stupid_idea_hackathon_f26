// Relays images to the local Python server. Done here rather than in the
// content script so Instagram's CORS/CSP rules don't apply.
const SERVER = "http://127.0.0.1:8765/potatoify";

chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
  if (msg.type !== "potatoify") return;
  fetch(SERVER, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ image: msg.image }),
  })
    .then((res) => (res.ok ? res.json() : Promise.reject(new Error(`server said ${res.status}`))))
    .then(sendResponse)
    .catch((err) => sendResponse({ error: String(err) }));
  return true; // keep the channel open for the async reply
});

// "ON" on the toolbar icon while the popup's switch is on.
function showBadge(enabled) {
  chrome.action.setBadgeText({ text: enabled ? "ON" : "" });
}
chrome.action.setBadgeBackgroundColor({ color: "#1a73e8" });
chrome.storage.local.get("enabled").then(({ enabled = false }) => showBadge(enabled));
chrome.storage.onChanged.addListener((changes) => {
  if ("enabled" in changes) showBadge(changes.enabled.newValue);
});
