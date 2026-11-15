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
