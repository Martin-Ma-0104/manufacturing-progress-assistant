(() => {
  const storageKey = "production-assistant-layout-v1";
  const previous = window.__productionAssistantLayout;
  if (previous) previous.dispose();
  let root = null;
  let handle = null;
  let dragging = null;
  let position = null;
  let animation = null;
  let disposed = false;
  try {
    const saved = JSON.parse(sessionStorage.getItem(storageKey));
    if (saved && Number.isFinite(saved.x) && Number.isFinite(saved.y))
      position = {x: saved.x, y: saved.y};
  } catch (_) { /* Layout persistence is optional. */ }

  function save() {
    if (!position) return;
    try { sessionStorage.setItem(storageKey, JSON.stringify(position)); } catch (_) {}
  }
  function clamp(x, y) {
    const rect = root.getBoundingClientRect();
    return {
      x: Math.max(12, Math.min(x, window.innerWidth - rect.width - 12)),
      y: Math.max(60, Math.min(y, window.innerHeight - rect.height - 12))
    };
  }
  function place(x, y, persist = true) {
    if (!root || !root.querySelector(".st-key-ai_panel_body")) return;
    position = clamp(x, y);
    root.style.left = position.x + "px";
    root.style.top = position.y + "px";
    root.style.right = "auto";
    root.style.bottom = "auto";
    if (persist) save();
  }
  function pointerDown(event) {
    if (event.button !== 0 || !root) return;
    const rect = root.getBoundingClientRect();
    dragging = {x: event.clientX - rect.x, y: event.clientY - rect.y};
    handle.setPointerCapture(event.pointerId);
    event.preventDefault();
  }
  function pointerMove(event) {
    if (dragging) place(event.clientX - dragging.x, event.clientY - dragging.y, false);
  }
  function pointerEnd() { if (dragging) save(); dragging = null; }
  function keyDown(event) {
    if (!root) return;
    const directions = {ArrowLeft: [-16, 0], ArrowRight: [16, 0], ArrowUp: [0, -16], ArrowDown: [0, 16]};
    if (directions[event.key]) {
      const rect = root.getBoundingClientRect();
      const [x, y] = directions[event.key];
      place(rect.x + x, rect.y + y);
      event.preventDefault();
    } else if (event.key === "Escape") {
      root.querySelector(".st-key-ai_close button")?.click();
    }
  }
  function detach() {
    if (!handle) return;
    handle.removeEventListener("pointerdown", pointerDown);
    handle.removeEventListener("pointermove", pointerMove);
    handle.removeEventListener("pointerup", pointerEnd);
    handle.removeEventListener("pointercancel", pointerEnd);
    handle.removeEventListener("keydown", keyDown);
    handle = null;
  }
  function bind() {
    if (disposed) return;
    animation = null;
    const nextRoot = document.querySelector(".st-key-ai_floating_root");
    const nextHandle = nextRoot?.querySelector("[data-ai-drag-handle]") || null;
    if (nextRoot !== root || nextHandle !== handle) {
      detach(); root = nextRoot; handle = nextHandle;
      if (handle) {
        handle.addEventListener("pointerdown", pointerDown);
        handle.addEventListener("pointermove", pointerMove);
        handle.addEventListener("pointerup", pointerEnd);
        handle.addEventListener("pointercancel", pointerEnd);
        handle.addEventListener("keydown", keyDown);
      }
    }
    if (!root) return;
    if (!handle) {
      // Collapsing always returns the launcher to its unobtrusive corner.
      root.style.removeProperty("left"); root.style.removeProperty("top");
      root.style.removeProperty("right"); root.style.removeProperty("bottom");
    } else if (position) place(position.x, position.y, false);
    else {
      const rect = root.getBoundingClientRect();
      place(rect.x, rect.y, false);
    }
  }
  function schedule() {
    if (!disposed && animation === null) animation = requestAnimationFrame(bind);
  }
  const observer = new MutationObserver(schedule);
  // Observe element mounting only. No page text, fields, attributes or data
  // are read; callbacks select only the assistant's own container/handle.
  observer.observe(document.body, {childList: true, subtree: true});
  window.addEventListener("resize", schedule);
  window.__productionAssistantLayout = {dispose() {
    disposed = true;
    if (animation !== null) cancelAnimationFrame(animation);
    observer.disconnect(); window.removeEventListener("resize", schedule); detach();
  }};
  bind();
})();
