// Relays images to the local Python server. Done here rather than in the
// content script so Instagram's CORS/CSP rules don't apply.
// Each feature is its own server; the popup picks which one gets the photos.
const SERVERS = {
  everyone: "http://127.0.0.1:8765/potatoify", // everyone_is_you/
  potato: "http://127.0.0.1:8766/potatoify", // potato/
};
const BADGE_COLORS = { everyone: "#1a73e8", potato: "#8b5a2b" };

chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
  if (msg.type === "showPopup") {
    // Unless the popup's "Hide this popup on upload" switch is on.
    chrome.storage.local.get({ hidePopup: false })
      .then(({ hidePopup }) => hidePopup || chrome.action.openPopup())
      .catch(() => {}); // fails if the window isn't focused; no big deal
    return;
  }
  if (msg.type !== "potatoify") return;
  chrome.storage.local.get({ feature: "everyone" })
    .then(({ feature }) => fetch(SERVERS[feature] ?? SERVERS.everyone, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ image: msg.image }),
    }))
    .then((res) => (res.ok ? res.json() : Promise.reject(new Error(`server said ${res.status}`))))
    .then(sendResponse)
    .catch((err) => sendResponse({ error: String(err) }));
  return true; // keep the channel open for the async reply
});

// "ON" on the toolbar icon while the popup's switch is on: blue for Everyone Is You, brown for Potato.
function showBadge({ enabled = false, feature = "everyone" }) {
  chrome.action.setBadgeText({ text: enabled ? "ON" : "" });
  chrome.action.setBadgeBackgroundColor({ color: BADGE_COLORS[feature] ?? BADGE_COLORS.everyone });
}
chrome.storage.local.get(["enabled", "feature"]).then(showBadge);
chrome.storage.onChanged.addListener((changes) => {
  if ("enabled" in changes || "feature" in changes) chrome.storage.local.get(["enabled", "feature"]).then(showBadge);
});
