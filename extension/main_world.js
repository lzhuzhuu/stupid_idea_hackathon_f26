// Runs in the page's own JS world. Some sites (Instagram among them) can open the file picker
// from an <input type="file"> that was never added to the page, so its events never reach
// content.js's listeners on window.

// Attach such inputs, hidden, right before the picker opens...
for (const method of ["click", "showPicker"]) {
  const original = HTMLInputElement.prototype[method];
  if (!original) continue;
  HTMLInputElement.prototype[method] = function (...args) {
    if (this.type === "file" && !this.isConnected) {
      this.hidden = true;
      document.documentElement.append(this);
    }
    return original.apply(this, args);
  };
}

// ...and for pickers opened some other way, listen on every new <input> before the page does:
// hold back events from a still-detached one, attach it, and fire them again from there.
const createElement = Document.prototype.createElement;
Document.prototype.createElement = function (tag, ...rest) {
  const el = createElement.call(this, tag, ...rest);
  if (String(tag).toLowerCase() === "input") {
    el.addEventListener("input", holdIfDetached, true);
    el.addEventListener("change", holdIfDetached, true);
  }
  return el;
};

function holdIfDetached(e) {
  const input = e.currentTarget;
  if (input.type !== "file" || input.isConnected) return;
  e.stopImmediatePropagation();
  if (e.type !== "change") return;
  input.hidden = true;
  document.documentElement.append(input);
  input.dispatchEvent(new Event("input", { bubbles: true }));
  input.dispatchEvent(new Event("change", { bubbles: true }));
}
