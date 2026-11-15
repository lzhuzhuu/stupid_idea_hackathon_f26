// Runs in the page's own JS world. Some sites (Instagram among them) open the file picker
// from an <input type="file"> that was never added to the page, so its events never reach
// content.js's listeners on window. Attach such inputs, hidden, right before the picker opens.
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
