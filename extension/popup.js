const box = document.getElementById("enabled");
const status = document.getElementById("status");

function show(enabled) {
  box.checked = enabled;
  status.textContent = enabled
    ? "On: photos you upload get your face."
    : "Off: uploads go through untouched.";
}

chrome.storage.local.get("enabled").then(({ enabled = false }) => show(enabled));
box.addEventListener("change", () => {
  chrome.storage.local.set({ enabled: box.checked });
  show(box.checked);
});
