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
    chrome.action.openPopup().catch(() => {}); // fails if the window isn't focused; no big deal
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

// After the extension is installed or reloaded, tabs that were already open still run the old
// content.js, which can't reach the extension any more. Give them a fresh one, so uploads there
// work without refreshing the page. (main_world.js lives in the page itself and keeps working.)
chrome.runtime.onInstalled.addListener(async () => {
  const [{ matches }] = chrome.runtime.getManifest().content_scripts;
  for (const tab of await chrome.tabs.query({ url: matches })) {
    chrome.scripting.executeScript({ target: { tabId: tab.id, allFrames: true }, files: ["content.js"] })
      .catch(() => {}); // e.g. a tab still loading, or a Chrome error page
  }
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
